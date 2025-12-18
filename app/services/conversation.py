"""Conversation Manager for the Voice RAG Assistant.

This module orchestrates the conversation flow and manages LLM interactions,
coordinating between input analysis, RAG processing, and response generation.
"""

from typing import Dict, Any

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.llm_service import FunctionCallParams, LLMService

from app.services.input_analyzer import InputAnalyzer
from app.services.rag import RAGService


class ConversationManager:
    """Service responsible for managing conversation flow and LLM interactions.
    
    This class coordinates between input analysis, RAG processing, and response generation
    to provide a seamless conversational experience.
    """
    
    # 20 different thinking phrases that cycle linearly
    THINKING_PHRASES = [
        "Let me look that up.",
        "Searching my knowledge base.",
        "One moment please.",
        "Let me find that for you.",
        "Checking my sources.",
        "Looking into that now.",
        "Give me a second.",
        "Searching for information.",
        "Let me see what I can find.",
        "One sec.",
        "Checking the database.",
        "Looking that up.",
        "Let me research that.",
        "Searching now.",
        "Finding the answer.",
        "Just a moment.",
        "Let me check.",
        "Looking for details.",
        "Searching the knowledge base.",
        "Finding information for you.",
    ]

    def __init__(self,
                 input_analyzer: InputAnalyzer,
                 rag_service: RAGService,
                 llm_config: Dict[str, Any] = None,
                 language_config: Dict[str, Any] = None):
        """Initialize the Conversation Manager.
        
        Args:
            input_analyzer: Input analyzer service instance
            rag_service: RAG service instance
            llm_config: Configuration for the LLM service
            language_config: Language configuration settings
        """
        self.input_analyzer = input_analyzer
        self.rag_service = rag_service
        self.llm_config = llm_config or {}
        self.language_config = language_config or {}
        self.llm_service = None
        self.tts_service = None
        self.context_aggregator = None
        self._thinking_phrase_index = 0  # Counter for cycling through phrases

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

        return self.llm_service

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
                if self.tts_service:
                    phrase = self._get_next_thinking_phrase()
                    await self.tts_service.queue_frame(TTSSpeakFrame(phrase))

            @self.llm_service.event_handler("on_function_calls_finished")
            async def on_function_calls_finished(service, function_calls):
                logger.info(f"Function calls finished: {function_calls}")

    async def _handle_rag_call(self, params: FunctionCallParams) -> None:
        """Handle RAG system function calls.
        
        Args:
            params: Function call parameters
        """
        question = params.arguments.get("question", "")

        try:
            logger.info(f"Processing RAG call for: {question}")
            response = await self.rag_service.get_response(question)
            await params.result_callback(response)
        except Exception as e:
            logger.error(f"Error in RAG call: {e}")
            error_response = f"I apologize, but I encountered an error while processing your question: {str(e)}"
            await params.result_callback(error_response)

    def create_function_schemas(self) -> ToolsSchema:
        """Create function schemas for LLM tool usage.
        
        Returns:
            ToolsSchema containing all function definitions
        """
        rag_function = FunctionSchema(
            name="call_rag_system",
            description="MANDATORY: Use this function for ANY question about Nesterlabs, the company, what you are, who you are, services, projects, team, clients, location, or contact information. ALWAYS use this for questions like 'what are you', 'who are you', 'tell me about you', 'what does Nesterlabs do', etc.",
            properties={
                "question": {
                    "type": "string",
                    "description": "The user's question about Nesterlabs, the company, services, or any factual information",
                },
            },
            required=["question"],
        )

        # Removed analyze_user_input function - unused and adds complexity
        return ToolsSchema(standard_tools=[rag_function])

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
            # Use custom system prompt from config
            system_message = custom_system_prompt + """

TOOL USAGE:
- RESPOND DIRECTLY for: greetings, how are you, thank you, goodbye, simple questions
- USE call_rag_system for: questions about Nesterlabs, company info, projects, services, or specific facts

CRITICAL RAG RULES:
- When you receive function results, summarize the key points BRIEFLY
- Extract only the most relevant information from RAG results
- Never give long explanations - keep it conversational
- If RAG returns detailed info, pick the 2-3 most important points only
"""
        else:
            # Default system prompt
            system_message = """
You are a helpful AI voice assistant. Keep responses SHORT and CONCISE - ideal for voice conversation.

RESPONSE RULES:
- Keep answers to 1-3 sentences maximum
- Be direct and to the point
- Speak naturally in conversational English
- RESPOND DIRECTLY for: greetings, how are you, thank you, goodbye
- USE call_rag_system for: questions about specific topics, facts, or information

CRITICAL RAG RULES:
- When you receive function results, summarize the key points BRIEFLY
- Extract only the most relevant information from RAG results
- Never give long explanations - keep it conversational
- If RAG returns detailed info, pick the 2-3 most important points only
"""
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

        context = self.create_context()
        self.context_aggregator = self.llm_service.create_context_aggregator(context)
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
