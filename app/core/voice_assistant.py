"""
Main Voice Assistant orchestrator.

This module contains the VoiceAssistant class that coordinates all services
and manages the overall voice assistant functionality including:
- Speech-to-Text processing
- Text-to-Speech synthesis
- RAG (Retrieval Augmented Generation)
- Conversation management
- Pipeline orchestration
"""

import asyncio
import time
from typing import Any, Dict, List

from loguru import logger
from pipecat.frames.frames import TTSSpeakFrame, TranscriptionFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
# NOTE: STTMuteFilter removed - was blocking greeting trigger, creating deadlock
# from pipecat.processors.filters.stt_mute_filter import STTMuteFilter, STTMuteConfig, STTMuteStrategy
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.transports.base_transport import BaseTransport

# Import interruption strategy for barge-in support
try:
    from pipecat.audio.interruptions.min_words_interruption_strategy import MinWordsInterruptionStrategy
    INTERRUPTION_STRATEGY_AVAILABLE = True
except ImportError:
    INTERRUPTION_STRATEGY_AVAILABLE = False
    logger.warning("MinWordsInterruptionStrategy not available - interruptions may not work correctly")

from app.services.conversation import ConversationManager
from app.services.input_analyzer import InputAnalyzer
from app.services.latency import LatencyAnalyzer
from app.services.rag import RAGService, create_rag_service
from app.services.stt import SpeechToTextService
from app.services.tts import TextToSpeechService
from app.processors.tone_aware_processor import ToneAwareProcessor
from app.processors.text_filter_processor import TextFilterProcessor
from app.processors.visual_hint_processor import VisualHintProcessor
from app.processors.noise_handler import NoiseHandlerProcessor
from app.processors.minimal_prefilter import MinimalPreFilter
from app.processors.interruption_filter import InterruptionFilterProcessor


class VoiceAssistant:
    """Main Voice Assistant class that coordinates all services.

    This class orchestrates the speech-to-text, text-to-speech, input analysis,
    RAG processing, and conversation management services to provide a complete
    voice assistant experience.

    Attributes:
        config: Configuration dictionary for all services
        stt_service: Speech-to-Text service instance
        tts_service: Text-to-Speech service instance
        input_analyzer: Input analysis service
        rag_service: RAG service for knowledge retrieval
        conversation_manager: Manages conversation context and LLM
        pipeline: Pipecat processing pipeline
        task: Pipeline task
        runner: Pipeline runner
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Voice Assistant.

        Args:
            config: Configuration dictionary containing settings for all services
        """
        self.config = config or {}

        # Initialize services
        self.stt_service = None
        self.tts_service = None
        self.input_analyzer = None
        self.rag_service = None
        self.conversation_manager = None

        # Pipeline components
        self.pipeline = None
        self.task = None
        self.runner = None
        self.rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
        self.latency_analyzer = LatencyAnalyzer()

        # NOTE: STTMuteFilter removed - it was blocking the greeting trigger, creating a deadlock
        # Goonj doesn't use STTMuteFilter and works fine without it

        # Tone-aware processor for dynamic voice selection using MSP-PODCAST + LLM text sentiment
        # Uses Google API key for Gemini-based text sentiment detection
        # Can be disabled via config for performance testing (wav2vec2 is CPU-intensive)
        google_api_key = self.config.get("conversation", {}).get("llm", {}).get("api_key")
        server_config = self.config.get("server", {})
        emotion_enabled = server_config.get("emotion_detection_enabled", True)
        logger.info(f"Emotion detection enabled: {emotion_enabled}")
        self.tone_processor = ToneAwareProcessor(
            cooldown_seconds=3.0,  # Cooldown between voice switches
            enabled=emotion_enabled,  # Read from config - can disable for performance
            groq_api_key=google_api_key,  # Pass Google API key for LLM text sentiment (Gemini)
        )

        # Text filter processor to remove markdown before TTS
        self.text_filter = TextFilterProcessor(enabled=True)

        # Visual hint processor - now minimal, A2UI is handled via RAG calls only
        # A2UI (Agent-to-UI) is triggered ONLY when call_rag_system is invoked
        # This prevents visual cards from showing on every LLM response
        a2ui_config = self.config.get("a2ui", {})
        a2ui_enabled = a2ui_config.get("enabled", True)
        logger.info(f"🎨 A2UI system enabled (RAG-triggered only): {a2ui_enabled}")
        self.visual_hint_processor = VisualHintProcessor(
            enabled=True,
            stream_words=True,  # Word-by-word streaming is the sole transcript renderer
            detect_content=False,  # Legacy visual hints disabled
            use_a2ui=False,  # A2UI now handled via RAG calls in ConversationManager
        )

        # Noise handler processor - pattern-based noise detection and recovery
        # Pattern-based noise detection for robust noise handling
        noise_handler_config = server_config.get("noise_handler", {})
        noise_handler_enabled = noise_handler_config.get("enabled", True)
        logger.info(f"🔇 Noise handler enabled: {noise_handler_enabled}")
        self.noise_handler = NoiseHandlerProcessor(
            max_false_starts=noise_handler_config.get("max_false_starts", 3),
            min_speech_duration=noise_handler_config.get("min_speech_duration", 0.5),
            recovery_delay=noise_handler_config.get("recovery_delay", 2.0),
        ) if noise_handler_enabled else None

        # Minimal pre-filter - transcription-level noise filtering
        # Drops low-confidence transcriptions and noise markers
        prefilter_config = server_config.get("prefilter", {})
        prefilter_enabled = prefilter_config.get("enabled", True)
        logger.info(f"🔇 Minimal pre-filter enabled: {prefilter_enabled}")
        self.prefilter = MinimalPreFilter(
            confidence_threshold=prefilter_config.get("confidence_threshold", 0.5),
            min_length=prefilter_config.get("min_length", 2),
            greeting_protection=prefilter_config.get("greeting_protection", True),
        ) if prefilter_enabled else None

        # Interruption filter - blocks InterruptionFrames when bot is not speaking
        # This prevents user queries from being cancelled by pipecat's interruption system
        # when there's no ongoing bot speech to interrupt
        interruption_config = server_config.get("interruption_filter", {})
        interruption_filter_enabled = interruption_config.get("enabled", True)
        logger.info(f"🛡️ Interruption filter enabled: {interruption_filter_enabled}")
        self.interruption_filter = InterruptionFilterProcessor(
            grace_period_after_bot_speech=interruption_config.get("grace_period", 0.5),
            min_speaking_time_before_interrupt=interruption_config.get("min_speaking_time", 1.5),
            transcription_wait_timeout=interruption_config.get("transcription_wait_timeout", 2.0),
            debug=interruption_config.get("debug", False),
        ) if interruption_filter_enabled else None

        # Store LLM and context references for greeting injection
        self.llm = None
        self.context_aggregator = None

        # Track conversation ending
        self.conversation_should_end = False

        # Track if greeting has been sent (with timestamp to prevent duplicates within 5 seconds)
        self._greeting_sent_at = 0

        logger.info("Initialized Voice Assistant")

    def initialize_services(self) -> None:
        """Initialize all service components."""
        logger.info("Initializing Voice Assistant services...")

        # Initialize Speech-to-Text service
        stt_config = self.config.get("stt", {})
        self.stt_service = SpeechToTextService(
            stt_provider=stt_config.get("provider", "whisper"),
            **stt_config.get("config", {}),
        )

        # Initialize Text-to-Speech service
        tts_config = self.config.get("tts", {})
        self.tts_service = TextToSpeechService(
            tts_provider=tts_config.get("provider", "elevenlabs"),
            **tts_config.get("config", {}),
        )

        # Initialize Input Analyzer
        input_config = self.config.get("input_analyzer", {})
        self.input_analyzer = InputAnalyzer(
            custom_patterns=input_config.get("custom_patterns")
        )

        # Initialize RAG Service
        rag_config = self.config.get("rag", {})
        self.rag_service = create_rag_service(rag_config)

        # Initialize Conversation Manager with A2UI support
        conversation_config = self.config.get("conversation", {})
        language_config = self.config.get("language", {})
        a2ui_config = self.config.get("a2ui", {})
        a2ui_enabled = a2ui_config.get("enabled", True)

        # Include system_prompt in llm_config so ConversationManager can access it
        llm_config = conversation_config.get("llm", {}).copy()
        llm_config["system_prompt"] = conversation_config.get("system_prompt", "")
        self.conversation_manager = ConversationManager(
            input_analyzer=self.input_analyzer,
            rag_service=self.rag_service,
            llm_config=llm_config,
            language_config=language_config,
            a2ui_enabled=a2ui_enabled,
        )

        logger.info("All services initialized successfully")

    async def create_pipeline(self, transport: BaseTransport) -> Pipeline:
        """Create the processing pipeline.

        Args:
            transport: The transport layer for audio input/output

        Returns:
            The configured pipeline

        Raises:
            ValueError: If services are not initialized
        """
        if not self.conversation_manager:
            raise ValueError("Services must be initialized before creating pipeline")

        # Get service instances
        stt = self.stt_service.get_service()
        tts = self.tts_service.get_service()
        llm = self.conversation_manager.get_llm_service()
        context_aggregator = self.conversation_manager.get_context_aggregator()

        # Store LLM, TTS and context for greeting injection
        self.llm = llm
        self.tts = tts
        self.context_aggregator = context_aggregator

        # Set up TTS service in conversation manager for function call feedback
        self.conversation_manager.set_tts_service(tts)

        # Set up A2UI callback for emitting visual updates from RAG responses
        self.conversation_manager.set_a2ui_callback(self._emit_a2ui_update)

        # NOTE: ToneProcessor and VisualHintProcessor initialization REMOVED
        # Simplifying to match Goonj's working approach

        # Create pipeline - SIMPLIFIED like Goonj
        # TextFilterProcessor removes markdown before TTS

        # Build pipeline processors list
        # SIMPLIFIED pipeline (matching Goonj's working approach):
        # Input -> STT -> PreFilter -> Context -> LLM -> TextFilter -> TTS -> Output
        # NOTE: Removed InterruptionFilter and NoiseHandler - Goonj doesn't use them
        pipeline_processors = [
            transport.input(),
        ]

        # STT to generate transcriptions
        pipeline_processors.append(stt)

        # Add MinimalPreFilter after STT to filter garbage transcriptions
        if self.prefilter:
            pipeline_processors.append(self.prefilter)
            logger.info("🔇 MinimalPreFilter added to pipeline (after STT)")

        # NOTE: InterruptionFilterProcessor NOT in pipeline — with allow_interruptions=False,
        # InterruptionTaskFrames are ignored by the task, and no InterruptionFrames
        # are generated through the pipeline. The filter has no frames to act on.

        pipeline_processors.extend([
            context_aggregator.user(),    # Context aggregator adds messages to LLM context
            self.rtvi,
            llm,
            self.text_filter,             # Remove markdown before TTS
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ])

        self.pipeline = Pipeline(pipeline_processors)

        logger.info("Pipeline created successfully")
        return self.pipeline

    def create_task(self, enable_metrics: bool = True) -> PipelineTask:
        """Create the pipeline task.

        Args:
            enable_metrics: Whether to enable metrics collection

        Returns:
            The configured pipeline task

        Raises:
            ValueError: If pipeline is not created
        """
        if not self.pipeline:
            raise ValueError("Pipeline must be created before creating task")

        # Build pipeline params
        # allow_interruptions=False prevents the PipelineTask from processing
        # InterruptionTaskFrames generated by Pipecat's deprecated VAD handler.
        # These task-level frames bypass the pipeline entirely and cannot be filtered,
        # so any noise triggering VAD would cut off the bot mid-speech.
        # RAG calls are additionally protected by asyncio.shield + generation counter.
        pipeline_params = PipelineParams(
            enable_metrics=enable_metrics,
            enable_usage_metrics=enable_metrics,
            idle_timeout_secs=60,
            report_only_initial_ttfb=True,
            allow_interruptions=False,
        )

        logger.info("🎤 Interruptions DISABLED — InterruptionTaskFrames ignored by task")

        self.task = PipelineTask(
            self.pipeline,
            params=pipeline_params,
            observers=[RTVIObserver(self.rtvi)],
        )

        logger.info("Pipeline task created successfully")
        return self.task

    def setup_transport_handlers(self, transport: BaseTransport) -> None:
        """Set up transport event handlers.

        Args:
            transport: The transport instance to set up handlers for

        Raises:
            ValueError: If task is not created
        """
        if not self.task:
            raise ValueError("Task must be created before setting up transport handlers")

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info(f"✅ Client connected: {client}")

            # Wait for pipeline to be fully ready (StartFrame must be processed)
            await asyncio.sleep(1.5)
            logger.info("🎤 Pipeline ready, sending greeting...")

            # Use TTSSpeakFrame to speak a pre-written greeting
            # This is the most reliable approach - bypasses LLM and goes straight to TTS
            from pipecat.frames.frames import TTSSpeakFrame
            greeting_text = (
                "Hey! I'm the Nesterlabs voice assistant. "
                "I can help you learn about our AI services and expertise. "
                "What would you like to know?"
            )

            # Queue TTSSpeakFrame through the task - this goes through the pipeline correctly
            greeting_frame = TTSSpeakFrame(text=greeting_text)
            await self.task.queue_frame(greeting_frame)
            logger.info("🎤 Greeting sent via TTSSpeakFrame")

            # Add greeting to conversation context so LLM knows it already greeted
            # Without this, the LLM generates a redundant greeting on the first user message
            if self.conversation_manager and self.conversation_manager.context:
                self.conversation_manager.context.messages.append(
                    {"role": "assistant", "content": greeting_text}
                )
                logger.info("📝 Greeting added to conversation context")

            # Disable greeting protection after 4 seconds (greeting takes ~3-4s to play)
            if self.prefilter:
                await asyncio.sleep(4.0)
                self.prefilter.disable_greeting_protection()
                logger.info("🛡️ Greeting protection disabled - user can now speak")

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info(f"Client disconnected: {client}")
            # Don't reset greeting time here - let it expire naturally after 5 seconds
            # Don't cancel task immediately - the server loop will handle cleanup
            # and restart for new connections. Cancelling here causes issues when
            # a replacement connection arrives (Pipecat closes old connection first)
            logger.debug("Client disconnected, awaiting session end")

        logger.info("Transport handlers set up successfully")

    async def run(self, transport: BaseTransport, handle_sigint: bool = True) -> None:
        """Run the voice assistant.

        Args:
            transport: The transport layer for audio input/output
            handle_sigint: Whether to handle SIGINT for graceful shutdown
        """
        logger.info("Starting Voice Assistant...")

        # Initialize services if not already done
        if not self.conversation_manager:
            logger.debug("Initializing services...")
            self.initialize_services()

        # Create pipeline and task
        logger.debug("Creating pipeline...")
        await self.create_pipeline(transport)

        logger.debug("Creating task...")
        self.create_task()

        # Set up transport handlers
        logger.debug("Setting up transport handlers...")
        self.setup_transport_handlers(transport)

        # Create and run the pipeline runner
        logger.info("Creating pipeline runner...")
        self.runner = PipelineRunner(handle_sigint=handle_sigint)
        logger.info("Starting pipeline runner...")
        await self.runner.run(self.task)

        logger.info("Voice Assistant stopped")

    async def _emit_a2ui_update(self, a2ui_doc: Dict[str, Any], query: str) -> None:
        """Emit A2UI update to frontend via the pipeline.

        This callback is called by ConversationManager when A2UI is generated from RAG.

        Args:
            a2ui_doc: A2UI document structure
            query: Original user query
        """
        import time

        logger.info("=" * 60)
        logger.info("📤 EMITTING A2UI UPDATE FROM RAG PIPELINE")
        logger.info(f"   Query: '{query[:50]}...'")
        logger.info(f"   Template: {a2ui_doc.get('root', {}).get('type', 'unknown')}")
        logger.info(f"   Tier: {a2ui_doc.get('_metadata', {}).get('tier_name', 'unknown')}")
        logger.info("=" * 60)

        message_data = {
            "message_type": "a2ui_update",
            "a2ui": a2ui_doc,
            "query": query,
            "timestamp": time.time(),
        }

        try:
            from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
            data_frame = RTVIServerMessageFrame(data=message_data)
            await self.rtvi.push_frame(data_frame)
            logger.info("✅ A2UI update emitted to frontend successfully")
        except Exception as e:
            logger.error(f"❌ Failed to emit A2UI update: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_service_status(self) -> Dict[str, Any]:
        """Get the status of all services.

        Returns:
            Dictionary containing the status of all services
        """
        return {
            "stt_service": {
                "initialized": self.stt_service is not None,
                "config": self.stt_service.get_config() if self.stt_service else None,
            },
            "tts_service": {
                "initialized": self.tts_service is not None,
                "config": self.tts_service.get_config() if self.tts_service else None,
            },
            "input_analyzer": {
                "initialized": self.input_analyzer is not None,
                "patterns": self.input_analyzer.get_patterns() if self.input_analyzer else None,
            },
            "rag_service": {
                "initialized": self.rag_service is not None,
                "status": self.rag_service.get_status() if self.rag_service else None,
            },
            "conversation_manager": {
                "initialized": self.conversation_manager is not None,
                "stats": (
                    self.conversation_manager.get_conversation_stats()
                    if self.conversation_manager
                    else None
                ),
            },
            "pipeline": {
                "created": self.pipeline is not None,
                "task_created": self.task is not None,
                "runner_created": self.runner is not None,
            },
            "latency_analyzer": {
                "initialized": self.latency_analyzer is not None,
                "statistics": (
                    self.latency_analyzer.get_statistics() if self.latency_analyzer else None
                ),
            },
        }

    def shutdown(self) -> None:
        """Gracefully shut down the voice assistant."""
        logger.info("Shutting down Voice Assistant...")

        if self.task:
            asyncio.create_task(self.task.cancel())

        logger.info("Voice Assistant shut down complete")

    @classmethod
    def create_from_config(cls, config_dict: Dict[str, Any]) -> "VoiceAssistant":
        """Create a VoiceAssistant instance from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary

        Returns:
            Configured VoiceAssistant instance
        """
        instance = cls(config_dict)
        instance.initialize_services()
        return instance
