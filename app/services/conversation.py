"""Conversation Manager for the Voice RAG Assistant.

This module orchestrates the conversation flow and manages LLM interactions,
coordinating between input analysis, RAG processing, and response generation.

A2UI Integration:
- When RAG is called, A2UI templates can be filled from knowledge base
- A2UI updates are emitted to frontend for visual rendering

Feedback Integration:
- When user ends conversation, feedback UI is shown
- Feedback is collected before session closes
"""

import asyncio
import re
import time
from typing import Any, Callable, Dict, Optional

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame, EndFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.llm_service import FunctionCallParams, LLMService

# Universal context system (pipecat 0.0.98)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)

from app.services.input_analyzer import InputAnalyzer
from app.services.rag import RAGService, LightRAGService, A2UIResponse
from app.services.groq_llm_service import GroqLLMService

# Import A2UI system
try:
    from app.services.a2ui import A2UIRAGService, get_a2ui_rag_service
    A2UI_AVAILABLE = True
except ImportError as e:
    A2UI_AVAILABLE = False
    logger.warning(f"A2UI system not available: {e}")

# Import feedback generator
from app.services.a2ui.feedback_generator import generate_feedback_message

# Import feedback store access (for reading submitted responses)
from app.services.feedback_store import get_feedback_by_session

# Question ID to readable label mapping for TTS
FEEDBACK_QUESTION_LABELS = {
    "overall_experience": "overall experience",
    "information_helpful": "information helpfulness",
    "voice_quality": "voice quality",
    "would_use_again": "likelihood to use again",
}

# Response value to readable text mapping for TTS
FEEDBACK_RESPONSE_LABELS = {
    "excellent": "Excellent",
    "good": "Good",
    "okay": "Okay",
    "poor": "Poor",
    "very_helpful": "Very Helpful",
    "somewhat": "Somewhat Helpful",
    "not_really": "Not Really Helpful",
    "not_at_all": "Not Helpful At All",
    "clear": "Clear and Natural",
    "mostly_clear": "Mostly Clear",
    "hard_to_understand": "Hard to Understand",
    "definitely": "Definitely",
    "probably": "Probably",
    "maybe": "Maybe",
    "no": "No",
}

# SmartTurn v3 - ML-based end-of-turn detection (optional)
# Use LoggingSmartTurnAnalyzer wrapper for detailed turn detection logs
try:
    from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
    from app.processors.logging_turn_analyzer import LoggingSmartTurnAnalyzer
    SMART_TURN_AVAILABLE = True
except ImportError:
    SMART_TURN_AVAILABLE = False
    logger.info("SmartTurn v3 not available - using transcription-based turn detection")

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
                 a2ui_enabled: bool = True,
                 smart_turn_config: Dict[str, Any] = None):
        """Initialize the Conversation Manager.

        Args:
            input_analyzer: Input analyzer service instance
            rag_service: RAG service instance
            llm_config: Configuration for the LLM service
            language_config: Language configuration settings
            a2ui_enabled: Enable A2UI visual generation from RAG responses
            smart_turn_config: SmartTurn v3 configuration (enabled, cpu_count, timeout)
        """
        self.input_analyzer = input_analyzer
        self.rag_service = rag_service
        self.llm_config = llm_config or {}
        self.language_config = language_config or {}
        self.smart_turn_config = smart_turn_config or {}
        self.llm_service = None
        self.tts_service = None
        self.context_aggregator = None
        self.context = None  # Store LLMContext for greeting access
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

        # Feedback state tracking
        self._waiting_for_feedback = False
        self._feedback_start_time: Optional[float] = None
        self._feedback_timeout_task: Optional[asyncio.Task] = None
        self._feedback_callback: Optional[Callable] = None  # Callback to emit feedback UI
        self._session_id: str = ""
        self._feedback_received = False
        self._llm_ref = None  # Store LLM reference for closing session

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
            # Groq — uses GroqLLMService which merges consecutive user
            # messages to prevent intermittent "Failed to call a function" errors
            model = self.llm_config.get("model", "llama-3.3-70b-versatile")
            self.llm_service = GroqLLMService(
                api_key=api_key,
                model=model,
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
        # cancel_on_interruption=False: RAG call continues in background during barge-in.
        # Without this, interruption cancels the task, result_callback is never called,
        # context gets "CANCELLED" tool result, and the bot goes silent.
        self.llm_service.register_function(
            "call_rag_system", self._handle_rag_call, cancel_on_interruption=False
        )
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

    def set_feedback_callback(self, callback: Callable) -> None:
        """Set the callback function for emitting feedback UI to frontend.

        Args:
            callback: Async function that takes (message_data: Dict) and emits to frontend
        """
        self._feedback_callback = callback
        logger.info("📝 Feedback callback registered for frontend updates")

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID for feedback tracking.

        Args:
            session_id: The session identifier
        """
        self._session_id = session_id

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

            # Note: on_function_calls_finished not available in Pipecat 0.0.98
            # (only on_function_calls_started and on_completion_timeout are registered)

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
        """Handle end conversation function call with feedback collection.

        When the LLM detects the user wants to end the conversation, this:
        1. Speaks a feedback prompt
        2. Emits feedback UI to the frontend
        3. Waits for feedback submission or timeout
        4. Then closes the session

        Args:
            params: Function call parameters
        """
        logger.warning("🔴 End conversation function called by LLM")

        # Store LLM reference for later session closure
        self._llm_ref = params.llm

        # Check if feedback callback is available
        if self._feedback_callback:
            # Feedback flow: ask for feedback before closing
            feedback_prompt = (
                "Before you go, I'd love your feedback. "
                "Please take a moment to rate your experience on the screen. "
                "You can also skip if you're in a hurry."
            )
            logger.info(f"📢 Pushing feedback prompt to TTS: '{feedback_prompt}'")

            if self.tts_service:
                await self.tts_service.queue_frame(TTSSpeakFrame(feedback_prompt))

            # Emit feedback UI to frontend
            await self._emit_feedback_ui()

            # Return empty response to prevent LLM generating more text
            await params.result_callback("")

            # Set feedback waiting state
            self._waiting_for_feedback = True
            self._feedback_start_time = time.time()
            self._feedback_received = False

            # Start feedback timeout (45 seconds, polls every 2s for submitted feedback)
            self._feedback_timeout_task = asyncio.create_task(
                self._feedback_timeout_handler()
            )

            logger.info("📝 Waiting for feedback submission or timeout...")
            # Session closure will be handled by close_session() called from API or timeout

        else:
            # No feedback callback - use legacy immediate close
            logger.info("No feedback callback - using immediate close")
            farewell_message = "Goodbye! Thank you for visiting Nesterlabs."
            logger.info(f"📢 Pushing farewell message to TTS: '{farewell_message}'")

            if self.tts_service:
                await self.tts_service.queue_frame(TTSSpeakFrame(farewell_message))

            await params.result_callback("")

            # Wait for TTS playback
            logger.info("⏳ Waiting 3.5 seconds for farewell TTS to complete...")
            await asyncio.sleep(3.5)
            logger.info("✅ Wait complete, sending EndFrame")

            # Push EndFrame upstream to terminate the session
            await params.llm.push_frame(EndFrame(), FrameDirection.UPSTREAM)
            logger.info("🛑 EndFrame sent - session will terminate")

    async def _emit_feedback_ui(self) -> None:
        """Emit feedback UI component to frontend."""
        feedback_message = generate_feedback_message(self._session_id)

        if self._feedback_callback:
            try:
                await self._feedback_callback(feedback_message)
                logger.info(f"📤 Sent feedback UI for session {self._session_id}")
            except Exception as e:
                logger.error(f"❌ Failed to emit feedback UI: {e}")

    async def _feedback_timeout_handler(self) -> None:
        """Handle feedback timeout - polls every 2 seconds for 45 seconds total.

        If feedback is submitted before timeout, closes immediately with responses.
        If timeout expires without feedback, closes with default farewell.
        """
        total_timeout = 45  # Total seconds to wait
        poll_interval = 2   # Check every 2 seconds
        elapsed = 0

        while elapsed < total_timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            # Check if feedback was already received (session closed elsewhere)
            if not self._waiting_for_feedback:
                return

            # Check if feedback was submitted to the API
            feedback_data = get_feedback_by_session(self._session_id)
            if feedback_data and not feedback_data.get("skipped", False):
                logger.info(f"✅ Feedback detected for session {self._session_id}, closing with responses")
                await self.close_session(feedback_received=True)
                return
            elif feedback_data and feedback_data.get("skipped", False):
                logger.info(f"⏭️ Feedback skipped for session {self._session_id}")
                await self.close_session(feedback_received=False)
                return

        # Timeout reached without feedback
        if self._waiting_for_feedback:
            logger.info(f"⏰ Feedback timeout ({total_timeout}s) for session {self._session_id}")
            await self.close_session(feedback_received=False)

    def _build_feedback_response_message(self) -> str:
        """Build a TTS message that reads back the user's feedback selections."""
        feedback_data = get_feedback_by_session(self._session_id)

        if not feedback_data or not feedback_data.get("responses"):
            return "Thank you for your feedback! Goodbye, and have a great day!"

        responses = feedback_data["responses"]
        parts = ["You selected"]

        response_texts = []
        for question_id, value in responses.items():
            question_label = FEEDBACK_QUESTION_LABELS.get(question_id, question_id)
            response_label = FEEDBACK_RESPONSE_LABELS.get(value, value)
            response_texts.append(f"{response_label} for {question_label}")

        if response_texts:
            # Join with commas and "and" for the last item
            if len(response_texts) == 1:
                parts.append(response_texts[0])
            elif len(response_texts) == 2:
                parts.append(f"{response_texts[0]} and {response_texts[1]}")
            else:
                parts.append(", ".join(response_texts[:-1]) + f", and {response_texts[-1]}")

        parts.append(". Thank you for your feedback! Goodbye, and have a great day!")

        return " ".join(parts)

    async def close_session(self, feedback_received: bool = False) -> None:
        """Close the session after feedback or timeout.

        Called by:
        - Timeout handler when feedback is detected
        - Timeout handler after 45 seconds
        - Skip button click

        Args:
            feedback_received: Whether feedback was submitted
        """
        # Cancel timeout task if still running
        if self._feedback_timeout_task and not self._feedback_timeout_task.done():
            self._feedback_timeout_task.cancel()
            try:
                await self._feedback_timeout_task
            except asyncio.CancelledError:
                pass

        self._waiting_for_feedback = False
        self._feedback_received = feedback_received

        # Build and speak the farewell message
        if feedback_received:
            # Speak back the user's selections
            farewell = self._build_feedback_response_message()
            logger.info(f"📢 Speaking feedback summary (full): '{farewell}'")
            logger.info(f"📢 Session ID for feedback lookup: {self._session_id}")
        else:
            farewell = "Goodbye! Thank you for visiting Nesterlabs."
            logger.info("📢 No feedback received, using default farewell")

        logger.info(f"📢 Pushing farewell message: '{farewell}'")

        # Push TTS frame through the pipeline (not queue_frame which may not work during wait state)
        if self._llm_ref:
            await self._llm_ref.push_frame(TTSSpeakFrame(farewell), FrameDirection.DOWNSTREAM)
            logger.info("✅ TTS frame pushed downstream through LLM")
        elif self.tts_service:
            # Fallback to queue_frame if no LLM reference
            await self.tts_service.queue_frame(TTSSpeakFrame(farewell))
            logger.info("⚠️ Used queue_frame fallback (LLM ref not available)")

        # Wait for TTS to complete speaking all 4 feedback selections
        await asyncio.sleep(13.0)  # Allow TTS to speak full summary before closing

        # Close the session
        if self._llm_ref:
            await self._llm_ref.push_frame(EndFrame(), FrameDirection.UPSTREAM)
            logger.info(f"🛑 Session {self._session_id} closed (feedback_received={feedback_received})")
        else:
            logger.warning("No LLM reference available to close session")

    def is_waiting_for_feedback(self) -> bool:
        """Check if session is waiting for feedback."""
        return self._waiting_for_feedback

    def create_function_schemas(self) -> ToolsSchema:
        """Create function schemas for LLM tool usage.
        
        Returns:
            ToolsSchema containing all function definitions
        """
        rag_function = FunctionSchema(
            name="call_rag_system",
            description="Search the knowledge base for detailed information. Use this function when: (1) User asks about specific project details, case studies, results, or architecture (e.g., 'tell me more about Sarah', 'what were the results?', 'explain the healthcare project'). (2) User asks to go deeper: 'tell me more', 'explain in detail', 'go deeper'. (3) User asks questions where showing a visual UI template would enhance the experience — project listings, team profiles, service details, contact information. (4) User asks about blog posts, technical deep-dives, or specific metrics. Do NOT use for basic company info, founder names, contact details, service overview, greetings, or farewells — answer those directly from your knowledge.",
            properties={
                "question": {
                    "type": "string",
                    "description": "The user's question to search the knowledge base for detailed information or visual content",
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

    def create_context(self) -> LLMContext:
        """Create the LLM context with system messages and tools.

        Uses the new universal LLMContext (replaces deprecated OpenAILLMContext).

        Returns:
            LLMContext for the conversation
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

        # No initial user prompt - greeting is handled via direct TTS
        # This prevents the LLM from generating a multi-sentence greeting
        messages = [
            {"role": "system", "content": system_message},
        ]

        # Use new universal LLMContext (replaces deprecated OpenAILLMContext)
        context = LLMContext(messages=messages, tools=tools)
        return context

    def create_context_aggregator(self) -> Any:
        """Create the context aggregator for the conversation.

        Uses LLMContextAggregatorPair (pipecat 0.0.98).
        SmartTurn v3 is configured at the transport level via turn_analyzer param.

        Returns:
            The context aggregator pair instance
        """
        if not self.llm_service:
            self.initialize_llm()

        self.context = self.create_context()  # Store for greeting access

        # Create user params (pipecat 0.0.98 - no user_turn_strategies or user_mute_strategies)
        user_params = LLMUserAggregatorParams()

        # Create assistant params (default)
        assistant_params = LLMAssistantAggregatorParams(
            expect_stripped_words=True  # TTS typically sends stripped words
        )

        # Create the universal context aggregator pair
        self.context_aggregator = LLMContextAggregatorPair(
            context=self.context,
            user_params=user_params,
            assistant_params=assistant_params
        )

        logger.info("📋 Context aggregator created (LLMContextAggregatorPair)")
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
