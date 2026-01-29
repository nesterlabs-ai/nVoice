"""Conversation Manager for the Voice RAG Assistant.

This module orchestrates the conversation flow and manages LLM interactions,
coordinating between input analysis, RAG processing, and response generation.

A2UI Integration:
- When RAG is called, A2UI templates can be filled from knowledge base
- A2UI updates are emitted to frontend for visual rendering
"""

import re
from typing import Any, Callable, Dict, Optional

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame, EndFrame, OutputTransportMessageFrame
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.llm_service import FunctionCallParams, LLMService

from app.services.input_analyzer import InputAnalyzer
from app.services.rag import RAGService, LightRAGService, A2UIResponse

# Import A2UI system
try:
    from app.services.a2ui import A2UIRAGService, get_a2ui_rag_service
    A2UI_AVAILABLE = True
except ImportError as e:
    A2UI_AVAILABLE = False
    logger.warning(f"A2UI system not available: {e}")

# Voice constant (default only - actual voice is controlled by ToneAwareProcessor)
DEFAULT_VOICE = "aura-2-athena-en"  # Natural, clear female voice - default


class ConversationManager:
    """Service responsible for managing conversation flow and LLM interactions.
    
    This class coordinates between input analysis, RAG processing, and response generation
    to provide a seamless conversational experience.
    """
    
    # 20 natural, conversational thinking phrases that sound more human
    THINKING_PHRASES = [
        "Umm, let me check that.",
        "Oh, let me look that up for you.",
        "Give me a sec.",
        "Hmm, let me find that.",
        "One moment.",
        "Let me see.",
        "Ah, let me search for that.",
        "Okay, checking now.",
        "Let me pull that up.",
        "Umm, searching.",
        "Yeah, let me find that.",
        "Hold on.",
        "Let me look into that.",
        "Hmm, one sec.",
        "Okay, let me check.",
        "Searching for that now.",
        "Let me grab that info.",
        "Just a moment.",
        "Alright, looking that up.",
        "Let me find that for you.",
    ]

    def __init__(self,
                 input_analyzer: InputAnalyzer,
                 rag_service: RAGService,
                 llm_config: Dict[str, Any] = None,
                 language_config: Dict[str, Any] = None,
                 a2ui_enabled: bool = True):
        """Initialize the Conversation Manager.

        Args:
            input_analyzer: Input analyzer service instance
            rag_service: RAG service instance
            llm_config: Configuration for the LLM service
            language_config: Language configuration settings
            a2ui_enabled: Enable A2UI visual generation from RAG responses
        """
        self.input_analyzer = input_analyzer
        self.rag_service = rag_service
        self.llm_config = llm_config or {}
        self.language_config = language_config or {}
        self.llm_service = None
        self.tts_service = None
        self.context_aggregator = None
        self.context = None  # Store OpenAILLMContext for greeting access
        self._thinking_phrase_index = 0  # Counter for cycling through phrases

        # A2UI integration
        self._a2ui_enabled = a2ui_enabled and A2UI_AVAILABLE
        self._a2ui_rag_service: Optional[A2UIRAGService] = None
        self._a2ui_callback: Optional[Callable] = None  # Callback to emit A2UI to frontend

        if self._a2ui_enabled:
            logger.info("🎨 A2UI enabled for RAG responses")
            if isinstance(rag_service, LightRAGService):
                self._a2ui_rag_service = get_a2ui_rag_service(
                    rag_service=rag_service,
                    enabled=True,
                    tier_mode="auto",
                )
                logger.info("✅ A2UI RAG Service initialized with full LightRAG support")
            else:
                logger.warning("⚠️ RAG service is not LightRAG - A2UI will use local generation only")
        else:
            logger.info("A2UI disabled or not available")

        logger.info("Initialized Conversation Manager")

    def initialize_llm(self) -> LLMService:
        """Initialize the LLM service.

        Returns:
            The initialized LLM service
        """
        api_key = self.llm_config.get("api_key")
        if not api_key:
            raise ValueError("LLM API key is required")

        provider = self.llm_config.get("provider", "google")

        if provider == "openai":
            model = self.llm_config.get("model", "gpt-4o")
            self.llm_service = OpenAILLMService(
                api_key=api_key,
                model=model
            )
            logger.info(f"Initialized OpenAI LLM service with model: {model}")
        elif provider == "groq":
            # Groq (using OpenAI-compatible API)
            model = self.llm_config.get("model", "llama-3.3-70b-versatile")
            self.llm_service = OpenAILLMService(
                api_key=api_key,
                model=model,
                base_url="https://api.groq.com/openai/v1"
            )
            logger.info(f"Initialized Groq LLM service with model: {model}")
        else:
            # Google Gemini
            model = self.llm_config.get("model", "gemini-1.5-flash-latest")
            self.llm_service = GoogleLLMService(
                api_key=api_key,
                model=model
            )
            logger.info(f"Initialized Google Gemini LLM service with model: {model}")

        # Register function handlers
        self.llm_service.register_function("call_rag_system", self._handle_rag_call)
        self.llm_service.register_function("end_conversation", self._handle_end_conversation)

        return self.llm_service

    def set_a2ui_callback(self, callback: Callable) -> None:
        """Set the callback function for emitting A2UI updates to frontend.

        The callback receives an A2UI document dict and should emit it to the transport.

        Args:
            callback: Async function that takes (a2ui_doc: Dict, query: str) and emits to frontend
        """
        self._a2ui_callback = callback
        logger.info("🎨 A2UI callback registered for frontend updates")

    def _get_next_thinking_phrase(self) -> str:
        """Get the next thinking phrase in the cycle.

        Returns:
            The next thinking phrase, cycling through the list linearly.
        """
        phrase = self.THINKING_PHRASES[self._thinking_phrase_index]
        self._thinking_phrase_index = (self._thinking_phrase_index + 1) % len(self.THINKING_PHRASES)
        return phrase

    def set_tts_service(self, tts_service: Any) -> None:
        """Set the TTS service for function call feedback.
        
        Args:
            tts_service: The TTS service instance
        """
        self.tts_service = tts_service

        if self.llm_service:
            # Add event handlers for function calls
            @self.llm_service.event_handler("on_function_calls_started")
            async def on_function_calls_started(service, function_calls):
                import time
                logger.info(f"🔧 FUNCTION CALL START: {function_calls} at {time.time()}")

                # Skip thinking phrase for end_conversation function (it has its own farewell)
                if function_calls and any('end_conversation' in str(call) for call in function_calls):
                    return

                # RAG calls now use the same voice as set by ToneAwareProcessor
                # (hybrid audio + text tone detection)
                if self.tts_service:
                    phrase = self._get_next_thinking_phrase()
                    await self.tts_service.queue_frame(TTSSpeakFrame(phrase))

            @self.llm_service.event_handler("on_function_calls_finished")
            async def on_function_calls_finished(service, function_calls):
                import time
                logger.info(f"✅ FUNCTION CALL END: {function_calls} at {time.time()}")

    def _strip_markdown(self, text: str) -> str:
        """Strip markdown formatting from text for voice output.
        
        Args:
            text: Text with markdown formatting
            
        Returns:
            Plain text without markdown
        """
        # Remove markdown bold/italic (**text**, *text*)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        
        # Remove markdown headers (# Header, ## Header, etc.)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Remove markdown links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove markdown code blocks ```code``` and `code`
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # Remove markdown lists (- item, * item, 1. item)
        text = re.sub(r'^[\s]*[-*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
        
        # Remove extra whitespace
        text = re.sub(r'\n\s*\n', '\n', text)
        text = text.strip()
        
        return text

    def _is_error_response(self, text: str) -> bool:
        """Heuristic to detect RAG error responses."""
        if not text:
            return True
        normalized = text.strip().lower()
        return (
            "i encountered an error while searching the knowledge base" in normalized
            or "i apologize, but i encountered an error" in normalized
            or "error while searching the knowledge base" in normalized
            or normalized.startswith("i encountered an error")
            or normalized.startswith("i apologize, but i encountered an error")
        )

    async def _handle_rag_call(self, params: FunctionCallParams) -> None:
        """Handle RAG system function calls with A2UI support.

        Uses a single sequential query that retrieves both text and A2UI template
        from the same LightRAG call. This avoids connection pooling issues that
        occur with parallel requests.

        Args:
            params: Function call parameters
        """
        import time
        question = params.arguments.get("question", "")

        try:
            logger.info(f"Processing RAG call for: {question}")
            start_time = time.time()

            # If A2UI is enabled, use the A2UI RAG service for combined query
            if self._a2ui_enabled and self._a2ui_rag_service:
                logger.info("🎨 Using SEQUENTIAL RAG + A2UI pipeline...")

                # Single query that returns both text and A2UI template
                a2ui_response: A2UIResponse = await self._a2ui_rag_service.query(
                    query=question,
                    force_text_only=False,
                )

                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"⏱️ RAG+A2UI query completed in {elapsed_ms:.1f}ms")

                # Check for error responses
                if self._is_error_response(a2ui_response.text):
                    logger.warning("⚠️ RAG returned error text")
                    await params.result_callback(a2ui_response.text)
                    return

                # Strip markdown for voice output
                cleaned_response = self._strip_markdown(a2ui_response.text)

                # Send text response to LLM -> TTS
                await params.result_callback(cleaned_response)

                # If we got an A2UI document, emit it to frontend
                if a2ui_response.a2ui and self._a2ui_callback:
                    logger.info(f"📤 Emitting A2UI update to frontend: {a2ui_response.template_type}")
                    try:
                        await self._a2ui_callback(a2ui_response.a2ui, question)
                        logger.info("✅ A2UI emitted successfully")
                    except Exception as e:
                        logger.error(f"❌ Failed to emit A2UI update: {e}")
                else:
                    logger.info("ℹ️ No A2UI template generated for this query")

            else:
                # Standard RAG query without A2UI
                response = await self.rag_service.get_response(question)
                # Strip markdown formatting for voice output
                cleaned_response = self._strip_markdown(response)
                await params.result_callback(cleaned_response)

            logger.info(f"✅ RAG call completed for: {question[:50]}...")

        except Exception as e:
            logger.error(f"Error in RAG call: {e}")
            import traceback
            logger.error(traceback.format_exc())
            error_response = f"I apologize, but I encountered an error while processing your question: {str(e)}"
            await params.result_callback(error_response)

    async def _handle_end_conversation(self, params: FunctionCallParams) -> None:
        """Handle end conversation function call.

        When the LLM detects the user wants to end the conversation, this sends
        an EndFrame upstream to gracefully terminate the session.

        Args:
            params: Function call parameters
        """
        import asyncio
        from pipecat.frames.frames import TTSSpeakFrame

        logger.warning("🔴 End conversation function called by LLM")

        # Push farewell message directly to TTS to avoid extra LLM round
        farewell_message = "Goodbye! Thank you for visiting Nesterlabs."
        logger.info(f"📢 Pushing farewell message to TTS: '{farewell_message}'")

        if self.tts_service:
            await self.tts_service.queue_frame(TTSSpeakFrame(farewell_message))

        # Return empty response to function to avoid LLM generating more text
        await params.result_callback("")

        # Wait for: TTS generation + TTS playback
        # ~1s TTS generation + ~2.5s TTS playback = 3.5s total
        logger.info("⏳ Waiting 3.5 seconds for farewell TTS to complete...")
        await asyncio.sleep(3.5)
        logger.info("✅ Wait complete, sending EndFrame")

        # Push EndFrame upstream to terminate the session
        await params.llm.push_frame(EndFrame(), FrameDirection.UPSTREAM)
        logger.info("🛑 EndFrame sent - session will terminate")

    def create_function_schemas(self) -> ToolsSchema:
        """Create function schemas for LLM tool usage.
        
        Returns:
            ToolsSchema containing all function definitions
        """
        rag_function = FunctionSchema(
            name="call_rag_system",
            description="MANDATORY: Use this function for ANY question about specific projects, case studies, detailed work examples, or when the user asks to 'know more' or 'learn more' about something. ALWAYS use this function when the user asks about: 'specific projects', 'project details', 'case studies', 'examples of work', 'what projects you work on', 'tell me more about your projects', or any variation asking for detailed project information. This function searches the knowledge base for comprehensive information. DO NOT skip this function for project-related questions.",
            properties={
                "question": {
                    "type": "string",
                    "description": "The user's specific or detailed question that requires searching the knowledge base for information beyond basic facts",
                },
            },
            required=["question"],
        )

        end_conversation_function = FunctionSchema(
            name="end_conversation",
            description="CRITICAL: Call this function IMMEDIATELY when the user says ANY farewell or wants to end. This includes single words like 'goodbye', 'bye', 'later' or phrases like 'see you', 'talk to you later', 'have a good day', 'end call', 'end conversation', 'hang up', 'disconnect', 'that's all', 'nothing else', 'I'm done', 'gotta go', 'need to go', 'catch you later', or ANY variation of farewell/goodbye. DO NOT just respond to farewells - you MUST call this function.",
            properties={},
            required=[],
        )

        return ToolsSchema(standard_tools=[rag_function, end_conversation_function])

    def create_context(self) -> OpenAILLMContext:
        """Create the LLM context with system messages and tools.

        Returns:
            OpenAILLMContext for the conversation
        """
        tools = self.create_function_schemas()

        support_hinglish = self.language_config.get("support_hinglish", False)
        primary_language = self.language_config.get("primary", "en")

        # Get custom system prompt from config, or use default
        custom_system_prompt = self.llm_config.get("system_prompt", "")

        if custom_system_prompt:
            # Use custom system prompt from config (it already includes identity rules)
            system_message = custom_system_prompt
            logger.info(f"Using custom system prompt (length: {len(system_message)} chars)")
        else:
            # Default system prompt (fallback only)
            logger.warning("No custom system prompt found in config, using default")
            system_message = """
You are a helpful AI voice assistant. Keep responses SHORT and CONCISE - ideal for voice conversation.

RESPONSE RULES:
- Keep answers to 1-3 sentences maximum
- Be direct and to the point
- Speak naturally in conversational English
- RESPOND DIRECTLY for: greetings, how are you, thank you, goodbye
- USE call_rag_system for: questions about specific topics, facts, or information

CRITICAL RAG RULES (SPEED IS IMPORTANT):
- When you receive RAG function results, READ THEM DIRECTLY to the user
- Do NOT rephrase, summarize, or reprocess RAG results - just speak them naturally
- The RAG system already provides well-formatted answers - trust them
- Only add a brief intro like "Here's what I found:" if needed
- NEVER delay speaking by over-processing the RAG response
"""
        
        # CRITICAL: Add explicit identity enforcement at the start
        # This ensures the bot NEVER identifies as a generic LLM
        identity_enforcement = """
CRITICAL IDENTITY RULES - YOU MUST FOLLOW THESE:
- You are the Nesterlabs voice assistant, NOT a generic AI or language model
- When asked "who are you" or "what are you", you MUST respond: "I'm the Nesterlabs voice assistant. I help visitors learn about Nesterlabs, our services, and connect with our team."
- NEVER say you are "a large language model" or "trained by Google" or "trained by OpenAI"
- NEVER identify as a generic AI - you are specifically the Nesterlabs voice assistant
- If asked about your identity, always say you are the Nesterlabs voice assistant

CONVERSATION ENDING PROTOCOL:
- When the user says goodbye, bye, end call, or wants to end the conversation:
  * YOU MUST call the end_conversation function - DO NOT just respond with text
  * The end_conversation function will handle the farewell and disconnect automatically
  * CRITICAL: Call end_conversation() for ANY farewell phrase (bye, goodbye, see you, end call, etc.)
- NEVER just respond to farewells without calling the end_conversation function

"""
        system_message = identity_enforcement + system_message
        # No initial user prompt - greeting is handled via direct TTS
        # This prevents the LLM from generating a multi-sentence greeting
        messages = [
            {"role": "system", "content": system_message},
        ]

        context = OpenAILLMContext(messages, tools)
        return context

    def create_context_aggregator(self) -> Any:
        """Create the context aggregator for the conversation.

        Returns:
            The context aggregator instance
        """
        if not self.llm_service:
            self.initialize_llm()

        self.context = self.create_context()  # Store for greeting access
        self.context_aggregator = self.llm_service.create_context_aggregator(self.context)
        return self.context_aggregator

    def get_llm_service(self) -> LLMService:
        """Get the LLM service instance.
        
        Returns:
            The LLM service instance
        """
        if not self.llm_service:
            self.initialize_llm()
        return self.llm_service

    def get_context_aggregator(self) -> Any:
        """Get the context aggregator instance.
        
        Returns:
            The context aggregator instance
        """
        if not self.context_aggregator:
            self.create_context_aggregator()
        return self.context_aggregator

    def update_system_message(self, new_message: str) -> None:
        """Update the system message for the conversation.
        
        Args:
            new_message: The new system message
        """
        logger.info("Updating system message")
        # This would require recreating the context - implement as needed
        logger.warning("System message update not fully implemented")

    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics.
        
        Returns:
            Dictionary containing conversation statistics
        """
        return {
            "llm_initialized": self.llm_service is not None,
            "context_aggregator_initialized": self.context_aggregator is not None,
            "tts_service_connected": self.tts_service is not None,
            "input_analyzer_ready": self.input_analyzer is not None,
            "rag_service_ready": self.rag_service is not None,
        }
