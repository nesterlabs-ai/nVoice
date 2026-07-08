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
from pipecat.frames.frames import TTSSpeakFrame, EndFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.llm_service import FunctionCallParams, LLMService

# Universal context system (pipecat 1.x)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)
# pipecat 1.x: VAD, end-of-turn, and STT-mute all moved off the transport and
# onto the user aggregator via strategy objects.
from pipecat.turns.user_turn_strategies import (
    UserTurnStrategies,
    FilterIncompleteUserTurnStrategies,
)
from pipecat.turns.user_turn_completion_mixin import UserTurnCompletionConfig
from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import (
    TurnAnalyzerUserTurnStopStrategy,
)
# Barge-in gating: min_words applies ONLY while the bot is speaking (blocks
# "yeah"/"okay" backchannels from interrupting), and drops to 1 word when the bot
# is idle (so a 1-word answer like "yes" still registers). Transcription-based, so
# it ignores background noise that never produces a clean transcript.
from pipecat.turns.user_start.min_words_user_turn_start_strategy import (
    MinWordsUserTurnStartStrategy,
)
from pipecat.turns.user_mute.mute_until_first_bot_complete_user_mute_strategy import (
    MuteUntilFirstBotCompleteUserMuteStrategy,
)

# Concise replacement for pipecat's default turn-completion instruction (~2000
# tokens). That default is verbose and sent on EVERY turn; this ~130-token
# version keeps the ✓/○/◐ contract and cuts per-turn prompt cost/latency.
TURN_COMPLETION_INSTRUCTIONS = (
    "Begin EVERY reply with a turn-completion marker as the very first character:\n"
    "  ✓  — the user finished a complete thought or question. Output ✓, then a space, then your full spoken answer.\n"
    "  ○  — the user was cut off mid-sentence and will resume in a moment. Output ONLY the single character ○, nothing else.\n"
    "  ◐  — the user is still thinking or asked for a moment (\"hmm\", \"let me think\", \"hold on\"). Output ONLY the single character ◐, nothing else.\n"
    "Grammatically complete is not always conversationally complete: \"That's a good question.\" alone → ◐; "
    "\"I'd go with the second one because\" (trailing off) → ○; a full question or statement → ✓ plus your answer.\n"
    "Never explain the marker; never output anything besides the single character for ○ or ◐."
)

from app.services.input_analyzer import InputAnalyzer
from app.services.rag import RAGService, LightRAGService, A2UIResponse
from app.services.groq_llm_service import GroqLLMService
from app.services.tally_submission import TallySubmissionService
from app.utils.validation import validate_email, spell_out_email

# Import A2UI system
try:
    from app.services.a2ui import A2UIRAGService, get_a2ui_rag_service
    A2UI_AVAILABLE = True
except ImportError as e:
    A2UI_AVAILABLE = False
    logger.warning(f"A2UI system not available: {e}")

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
    
    # Legacy thinking phrases kept for non-critical future use.
    # Do not speak these during RAG calls; they make the assistant sound hesitant.
    THINKING_PHRASES = [
        "That's a nuanced one... let me get this right.",
        "I'm thinking through how we've handled this before.",
        "Interesting — let me recall the specifics on that.",
        "Give me a second — I want to get this right.",
        "I'm pulling from our internal work on this...",
        "Let me think through our take on that.",
        "That touches on something specific — give me a moment.",
        "I'm recalling a pattern we've used for exactly this...",
        "Let me get the details right on this one.",
        "That's worth being precise about — one moment.",
        "I'm running through how we've framed this before.",
        "Let me consult our work on that specifically.",
        "Mmm, that's a good one — let me think it through.",
        "I want to give you the right answer on this, give me a second.",
        "I'm sharpening my focus on that — just a moment.",
        "Let me pull the right reference for this.",
        "That's a specific territory — let me get it right.",
        "I'm walking through our internal approach on this...",
        "One moment — I want to be precise here.",
        "Let me make sure I give you the right angle on this.",
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

        # Appointment booking state
        self._booking_in_progress = False
        self.tally_service = TallySubmissionService()

        # Pipeline task and RTVI processor references (set after pipeline creation)
        self._task = None
        self._rtvi_processor = None
        self._conversation_ending = False

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
            temperature = self.llm_config.get("temperature", 0.7)
            max_tokens = self.llm_config.get("max_tokens", 300)
            reasoning_effort = self.llm_config.get("reasoning_effort")

            if reasoning_effort:
                # GPT-5.x reasoning models REJECT reasoning_effort + function tools
                # on /v1/chat/completions ("Please use /v1/responses instead").
                # OpenAIResponsesLLMService speaks /v1/responses over a persistent
                # WebSocket with incremental context — validated live:
                # gpt-5.5 + tools + reasoning.effort=none → warm TTFB ~0.85s
                # (vs 1.9s for gpt-5.5-with-tools on chat completions).
                from pipecat.services.openai.responses.llm import (
                    OpenAIResponsesLLMService,
                    OpenAIResponsesLLMSettings,
                )

                class NesterResponsesLLMService(OpenAIResponsesLLMService):
                    """Cancels stale ○/◐ re-prompt timeouts once a ✓ answer lands.

                    Upstream mixin bug (observed live): a pending
                    incomplete-turn timeout started by an earlier ○ fragment is
                    NOT cancelled when a later turn completes with ✓ — it fires
                    after the real answer and speaks a leftover nudge like
                    "Tell me what the repo does today..." out of nowhere.
                    """

                    async def _push_turn_text(self, text):
                        had_pending = (
                            getattr(self, "_incomplete_timeout_task", None) is not None
                        )
                        await super()._push_turn_text(text)
                        # ✓ just resolved this turn — any timeout left over from a
                        # previous ○ fragment is now stale; kill it.
                        if had_pending and getattr(self, "_turn_complete_found", False):
                            try:
                                await self._cancel_incomplete_timeout()
                                logger.debug(
                                    "Cancelled stale incomplete-turn timeout after ✓ answer"
                                )
                            except Exception as e:
                                logger.debug(f"Stale timeout cancel skipped: {e}")

                settings = OpenAIResponsesLLMSettings(
                    model=model,
                    temperature=temperature,
                    max_completion_tokens=max_tokens,  # mapped to max_output_tokens
                    extra={"reasoning": {"effort": reasoning_effort}},
                )
                self.llm_service = NesterResponsesLLMService(
                    api_key=api_key, settings=settings
                )
                logger.info(
                    f"Initialized OpenAI Responses LLM service (WebSocket): model={model}, "
                    f"max_output_tokens={max_tokens}, reasoning_effort={reasoning_effort}"
                )
            else:
                # Plain chat-completions path (non-reasoning models like gpt-4.1).
                # NOTE: previously only api_key+model were passed, so config
                # temperature/max_tokens were silently ignored. Now wired via Settings.
                settings = OpenAILLMService.Settings(
                    model=model,
                    temperature=temperature,
                    max_completion_tokens=max_tokens,
                )
                self.llm_service = OpenAILLMService(api_key=api_key, settings=settings)
                logger.info(
                    f"Initialized OpenAI LLM service: model={model}, "
                    f"max_completion_tokens={max_tokens}"
                )
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
        self.llm_service.register_function("start_appointment_booking", self._handle_start_booking)
        self.llm_service.register_function("submit_appointment", self._handle_submit_appointment)

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

    def set_pipeline_task(self, task: Any) -> None:
        """Set the pipeline task reference for controlling pipeline params.

        Args:
            task: The PipelineTask instance
        """
        self._task = task

    def set_rtvi_processor(self, rtvi: Any) -> None:
        """Set the RTVI processor for sending server messages to the frontend.

        Args:
            rtvi: The RTVIProcessor instance
        """
        self._rtvi_processor = rtvi

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

                # Skip thinking phrase for certain functions that don't need "let me check"
                skip_functions = [
                    'call_rag_system',
                    'end_conversation',
                    'start_appointment_booking',
                    'submit_appointment',
                    'cancel_appointment_booking',
                ]
                if function_calls and any(func in str(call) for func in skip_functions for call in function_calls):
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

            elapsed_total_ms = (time.time() - start_time) * 1000
            logger.info(f"✅ RAG call completed for: {question[:50]}...")

            try:
                from app.services.cloudwatch_metrics import emit_rag_call
                emit_rag_call("", elapsed_total_ms, success=True)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error in RAG call: {e}")
            import traceback
            logger.error(traceback.format_exc())
            error_response = f"I apologize, but I encountered an error while processing your question: {str(e)}"
            await params.result_callback(error_response)

            try:
                from app.services.cloudwatch_metrics import emit_rag_call, emit_error
                elapsed_ms = (time.time() - start_time) * 1000
                emit_rag_call("", elapsed_ms, success=False)
                emit_error("RAGError")
            except Exception:
                pass

    async def _handle_end_conversation(self, params: FunctionCallParams) -> None:
        """Handle end conversation function call.

        When the LLM detects the user wants to end the conversation:
        1. Marks conversation as ending (blocks session timeout re-trigger)
        2. Disables interruptions so farewell TTS cannot be cut off
        3. Signals frontend to show "session ended" UI
        4. Plays a varied farewell message
        5. Waits for TTS playback, then terminates the session

        Args:
            params: Function call parameters
        """
        import asyncio
        import random

        logger.warning("🔴 End conversation function called by LLM")

        # Guard: prevent double-invocation (e.g. session timeout races with LLM)
        if self._conversation_ending:
            logger.warning("⚠️ end_conversation called while already ending — ignoring")
            await params.result_callback("")
            return
        self._conversation_ending = True

        # NOTE: pipecat 1.x PipelineParams is immutable (pydantic), so runtime
        # toggling of allow_interruptions is no longer possible. Farewell
        # protection now comes from MinWordsUserTurnStartStrategy (2 real words
        # needed to barge in during bot speech), which filters the background
        # noise this toggle used to guard against.

        # Signal frontend that session is ending so it can show the "session ended" UI
        if self._rtvi_processor:
            try:
                from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
                await self._rtvi_processor.push_frame(
                    RTVIServerMessageFrame(data={"message_type": "conversation_ending"})
                )
                logger.info("📤 conversation_ending signal sent to frontend")
            except Exception as e:
                logger.warning(f"Could not send conversation_ending signal: {e}")

        # Pick a varied farewell from a pool — sounds more natural than a single hardcoded line
        farewell_options = [
            "It was great chatting with you! Hope to connect again soon — take care!",
            "Thanks for stopping by. Best of luck with your project!",
            "Really enjoyed talking through this with you. Best of luck!",
            "Thanks for the conversation! Reach out anytime — goodbye for now.",
        ]
        farewell_message = random.choice(farewell_options)
        logger.info(f"📢 Pushing farewell message to TTS: '{farewell_message}'")

        if self.tts_service:
            await self.tts_service.queue_frame(TTSSpeakFrame(farewell_message))

        # Return empty response so LLM does not generate additional text
        await params.result_callback("")

        # Wait for TTS generation + playback (~1s gen + ~2.5s playback = 3.5s)
        logger.info("⏳ Waiting 3.5 seconds for farewell TTS to complete...")
        await asyncio.sleep(3.5)
        logger.info("✅ Wait complete, sending EndFrame")

        # Push EndFrame upstream to terminate the session
        await params.llm.push_frame(EndFrame(), FrameDirection.UPSTREAM)
        logger.info("🛑 EndFrame sent - session will terminate")

    async def _handle_start_booking(self, params: FunctionCallParams) -> None:
        """Handle start appointment booking function call.

        Initiates the appointment booking flow and sets internal state.

        Args:
            params: Function call parameters
        """
        logger.info("📅 Start appointment booking function called")

        # Set booking state flag
        self._booking_in_progress = True

        # Return a prompt to collect user information
        response = "Great! What's your first name?"
        await params.result_callback(response)

        logger.info("✅ Appointment booking flow initiated")

    async def _handle_submit_appointment(self, params: FunctionCallParams) -> None:
        """Handle appointment submission function call.

        Validates and submits the appointment data to Tally.so.

        Args:
            params: Function call parameters with first_name, last_name, email
        """
        logger.info("📋 Submit appointment function called")

        # Extract parameters
        first_name = params.arguments.get("first_name", "").strip()
        last_name = params.arguments.get("last_name", "").strip()
        email = params.arguments.get("email", "").strip()

        logger.info(f"Appointment details: {first_name} {last_name} ({email})")

        # Validate email
        is_valid, normalized_email = validate_email(email)

        if not is_valid:
            logger.warning(f"Invalid email format: {email}")
            error_msg = "That email doesn't look quite right. Could you please spell it out again slowly?"
            await params.result_callback(error_msg)
            return

        # Validate required fields
        if not first_name or not last_name:
            logger.warning("Missing required fields")
            error_msg = "I need both your first and last name. Could you provide those?"
            await params.result_callback(error_msg)
            return

        try:
            # Submit to Tally.so
            result = await self.tally_service.submit_appointment(
                first_name=first_name,
                last_name=last_name,
                email=normalized_email
            )

            if result["success"]:
                logger.info("✅ Appointment submitted successfully")

                # Reset booking state
                self._booking_in_progress = False

                # Return success message - LLM will then call end_conversation
                success_msg = result["message"]
                await params.result_callback(success_msg)

            else:
                logger.error(f"Appointment submission failed: {result.get('error')}")
                error_msg = result["error"]
                await params.result_callback(error_msg)
                # Keep booking in progress so user can retry
                logger.info("Booking state maintained for retry")

        except Exception as e:
            logger.error(f"Error submitting appointment: {e}")
            import traceback
            logger.error(traceback.format_exc())

            error_msg = "I encountered an error while submitting. Could you please contact us directly at contact@nesterlabs.com?"
            await params.result_callback(error_msg)

            # Reset booking state on error
            self._booking_in_progress = False

    def create_function_schemas(self) -> ToolsSchema:
        """Create function schemas for LLM tool usage.
        
        Returns:
            ToolsSchema containing all function definitions
        """
        rag_function = FunctionSchema(
            name="call_rag_system",
            description="Search the knowledge base for deeper or more specific information. Use this function when: (1) the user asks about specific project details, case studies, results, named architectures, or metrics; (2) the user asks to go deeper after a direct answer; (3) the question would benefit from a visual UI template; (4) the user asks about blog posts, technical deep-dives, or documented methodologies. Do NOT use for basic company info, greetings, farewells, or core Nesterlabs operating questions that should be answered directly from your knowledge first. Answer directly when the user asks high-level questions like how we build voice bots, whether we use accelerators or internal stack, how we ensure reliability, what our stack looks like at a high level, or how we work. Use RAG only if the user then asks for specifics, examples, metrics, or deeper detail.",
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
            description="Call this function when the user wants to end the conversation AND has declined the appointment offer, OR when the user confirms there is nothing more they need after a successful booking. IMPORTANT: Before calling this on a farewell, you must FIRST offer to schedule an appointment. Only call end_conversation if they decline the appointment offer or after booking when user says they are done.",
            properties={},
            required=[],
        )

        start_booking_function = FunctionSchema(
            name="start_appointment_booking",
            description="Start the appointment booking process. Call this when the user agrees to schedule an appointment (either after a farewell offer or mid-conversation contact request). This initiates the flow to collect their name and email.",
            properties={},
            required=[],
        )

        submit_appointment_function = FunctionSchema(
            name="submit_appointment",
            description="Submit appointment booking after collecting first name, last name, and email. CRITICAL: Only call this AFTER you have confirmed the email address character-by-character with the user and they have confirmed it is correct. Do not call this if the email has not been verbally confirmed.",
            properties={
                "first_name": {
                    "type": "string",
                    "description": "User's first name",
                },
                "last_name": {
                    "type": "string",
                    "description": "User's last name",
                },
                "email": {
                    "type": "string",
                    "description": "User's confirmed email address",
                },
            },
            required=["first_name", "last_name", "email"],
        )

        return ToolsSchema(standard_tools=[
            rag_function,
            end_conversation_function,
            start_booking_function,
            submit_appointment_function
        ])

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

    def create_context_aggregator(
        self,
        vad_analyzer: Any = None,
        turn_analyzer: Any = None,
        interruption_config: Optional[Dict[str, Any]] = None,
        user_idle_timeout: float = 0,
    ) -> Any:
        """Create the context aggregator for the conversation.

        Uses LLMContextAggregatorPair (pipecat 1.x). In 1.x the transport no
        longer owns VAD, end-of-turn detection, or STT muting — they are
        attached here on the user aggregator:
          - vad_analyzer: Silero VAD instance (moved off transport params).
          - turn_analyzer: SmartTurn v3 ML analyzer, wrapped in a
            TurnAnalyzerUserTurnStopStrategy (replaces transport turn_analyzer).
          - user_mute_strategies: MuteUntilFirstBotCompleteUserMuteStrategy
            replaces the removed STTMuteFilter (mute until first bot turn done).

        Args:
            vad_analyzer: VAD analyzer built by the transport layer.
            turn_analyzer: SmartTurn v3 end-of-turn analyzer (or None).

        Returns:
            The context aggregator pair instance
        """
        if not self.llm_service:
            self.initialize_llm()

        self.context = self.create_context()  # Store for greeting access

        # SmartTurn v3 end-of-turn now attaches as a user-turn stop strategy.
        # Optionally gate finalization on the LLM's turn-completion verdict
        # (pipecat 1.x FilterIncompleteUserTurnStrategies): the LLM prefixes each
        # response with ✓ (complete) / ○ (incomplete short) / ◐ (incomplete long).
        # Only ✓ finalizes the turn; ○/◐ keep it open so multi-clause speakers are
        # not cut off mid-thought. This is a semantic fix for the fragmented long
        # turns seen in CloudWatch, layered on top of the SmartTurn detector.
        stop_strategies = (
            [TurnAnalyzerUserTurnStopStrategy(turn_analyzer=turn_analyzer)]
            if turn_analyzer is not None
            else None
        )

        # Barge-in START strategy. MinWordsUserTurnStartStrategy is used ALONE (no
        # extra VAD/Transcription start strategy) because start strategies are OR'd
        # and the earliest wins — a plain transcription strategy would fire on word
        # one and bypass the min-words gate during bot speech. This single strategy
        # already needs `min_words` words to barge in while the bot speaks, but only
        # 1 word when the bot is idle (so short answers like "yes" still register).
        # Future upgrade: swap in KrispVivaIPUserTurnStartStrategy (model-based
        # backchannel/background-voice rejection) — requires the krisp_audio SDK.
        interruption_config = interruption_config or {}
        start_strategies = None
        if interruption_config.get("enabled", True):
            barge_in_min_words = int(interruption_config.get("min_words", 2))
            start_strategies = [
                MinWordsUserTurnStartStrategy(min_words=barge_in_min_words, use_interim=True)
            ]
            logger.info(
                f"🎤 Barge-in: MinWordsUserTurnStartStrategy "
                f"(min_words={barge_in_min_words} during bot speech, 1 word when idle)"
            )

        filter_incomplete = bool(self.smart_turn_config.get("filter_incomplete_turns", False))
        user_turn_strategies = None
        if filter_incomplete:
            completion_config = UserTurnCompletionConfig(
                instructions=TURN_COMPLETION_INSTRUCTIONS,
                incomplete_short_timeout=float(
                    self.smart_turn_config.get("incomplete_short_timeout", 4.0)
                ),
                incomplete_long_timeout=float(
                    self.smart_turn_config.get("incomplete_long_timeout", 8.0)
                ),
            )
            user_turn_strategies = FilterIncompleteUserTurnStrategies(
                start=start_strategies,
                stop=stop_strategies,
                config=completion_config,
            )
            logger.info(
                "🧠 Turn-completion markers ENABLED "
                f"(FilterIncompleteUserTurnStrategies, short={completion_config.incomplete_short_timeout}s, "
                f"long={completion_config.incomplete_long_timeout}s, "
                f"SmartTurn={'yes' if turn_analyzer is not None else 'defaults'})"
            )
        elif start_strategies is not None or stop_strategies is not None:
            user_turn_strategies = UserTurnStrategies(
                start=start_strategies, stop=stop_strategies
            )
            logger.info("🧠 SmartTurn v3 attached via TurnAnalyzerUserTurnStopStrategy")

        # Create user params — VAD, turn detection, and greeting-mute all live here now.
        # user_idle_timeout > 0 emits `on_user_turn_idle` (handled in
        # voice_assistant to speak a gentle re-engagement) when the caller goes quiet.
        user_params = LLMUserAggregatorParams(
            vad_analyzer=vad_analyzer,
            user_turn_strategies=user_turn_strategies,
            user_mute_strategies=[MuteUntilFirstBotCompleteUserMuteStrategy()],
            user_idle_timeout=float(user_idle_timeout or 0),
        )

        # Create assistant params. pipecat 1.x removed `expect_stripped_words`
        # (the aggregator now handles word concatenation/spacing internally).
        # Context summarization keeps long sessions' prompts bounded (defaults:
        # summarize past 8k tokens down toward 6k) so late-conversation TTFB
        # stays flat instead of growing with history.
        assistant_params = LLMAssistantAggregatorParams(
            enable_context_summarization=bool(
                self.llm_config.get("context_summarization_enabled", True)
            ),
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
