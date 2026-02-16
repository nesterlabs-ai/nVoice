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
from typing import Any, Dict, List

from loguru import logger
from pipecat.frames.frames import TTSSpeakFrame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.filters.stt_mute_filter import STTMuteFilter, STTMuteConfig, STTMuteStrategy
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
from app.processors.smart_interruption_processor import SmartInterruptionProcessor


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

        # STT mute filter - mutes STT only during the first bot greeting
        # MUTE_UNTIL_FIRST_BOT_COMPLETE: blocks user audio only during initial greeting TTS,
        # then allows all user input through (including barge-in interruptions)
        # Self-interruption prevention relies on:
        #   1. Client-side echoCancellation: true (getUserMedia constraint)
        #   2. VAD params (confidence=0.7, min_volume=0.5, start_secs=0.2)
        self.stt_mute_filter = STTMuteFilter(
            config=STTMuteConfig(strategies={STTMuteStrategy.MUTE_UNTIL_FIRST_BOT_COMPLETE})
        )

        # Tone-aware processor for dynamic voice selection using MSP-PODCAST + LLM text sentiment
        # Uses Google API key for Gemini-based text sentiment detection
        # Can be disabled via config for performance testing (wav2vec2 is CPU-intensive)
        google_api_key = self.config.get("conversation", {}).get("llm", {}).get("api_key")
        server_config = self.config.get("server", {})
        emotion_enabled = server_config.get("emotion_detection_enabled", True)
        logger.info(
            f"[EMOTION-DIAG] Emotion detection config: enabled={emotion_enabled}, "
            f"groq_api_key={'SET' if google_api_key and not google_api_key.startswith('$') else 'MISSING'}"
        )
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

        # Smart interruption processor - validates interruptions to prevent false barge-ins
        smart_int_config = server_config.get("smart_interruption", {})
        smart_int_enabled = smart_int_config.get("enabled", True)
        logger.info(f"🛡️ Smart interruption validation enabled: {smart_int_enabled}")
        self.smart_interruption = SmartInterruptionProcessor(
            enabled=smart_int_enabled,
            min_confidence_threshold=smart_int_config.get("min_confidence", 0.7),
        )

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

        # Initialize Conversation Manager with A2UI support and SmartTurn v3
        conversation_config = self.config.get("conversation", {})
        language_config = self.config.get("language", {})
        a2ui_config = self.config.get("a2ui", {})
        a2ui_enabled = a2ui_config.get("enabled", True)
        server_config = self.config.get("server", {})
        smart_turn_config = server_config.get("smart_turn", {})

        # Include system_prompt in llm_config so ConversationManager can access it
        llm_config = conversation_config.get("llm", {}).copy()
        llm_config["system_prompt"] = conversation_config.get("system_prompt", "")
        self.conversation_manager = ConversationManager(
            input_analyzer=self.input_analyzer,
            rag_service=self.rag_service,
            llm_config=llm_config,
            language_config=language_config,
            a2ui_enabled=a2ui_enabled,
            smart_turn_config=smart_turn_config,  # SmartTurn v3 config for ML-based turn detection
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

        # Get context aggregator (SmartTurn v3 is now configured here via UserTurnStrategies)
        context_aggregator = self.conversation_manager.get_context_aggregator()

        # Store LLM, TTS and context for greeting injection
        self.llm = llm
        self.tts = tts
        self.context_aggregator = context_aggregator

        # Set up TTS service in conversation manager for function call feedback
        self.conversation_manager.set_tts_service(tts)

        # Connect TTS to tone processor for dynamic voice switching
        self.tone_processor.set_tts_service(tts)

        # Connect VisualHintProcessor to ToneProcessor for A2UI query capture
        self.tone_processor.set_visual_hint_processor(self.visual_hint_processor)

        # Set up A2UI callback for emitting visual updates from RAG responses
        # This enables the full LightRAG + A2UI pipeline
        self.conversation_manager.set_a2ui_callback(self._emit_a2ui_update)

        # Initialize MSP-PODCAST wav2vec2 for emotion detection
        logger.info("[EMOTION-DIAG] About to call tone_processor.initialize()...")
        await self.tone_processor.initialize()
        logger.info(
            f"[EMOTION-DIAG] After initialize: "
            f"detector_connected={self.tone_processor.emotion_detector.is_connected}, "
            f"detector_model={self.tone_processor.emotion_detector.model is not None}, "
            f"hybrid_detector={self.tone_processor.hybrid_detector is not None}, "
            f"enabled={self.tone_processor.enabled}"
        )

        # Get smart interruption config for conditional pipeline inclusion
        server_config = self.config.get("server", {})
        smart_int_config = server_config.get("smart_interruption", {})
        smart_int_enabled = smart_int_config.get("enabled", True)

        # Create pipeline
        # ToneAwareProcessor receives audio frames for SpeechBrain emotion detection
        # VisualHintProcessor streams text word-by-word and emits visual hints
        # TextFilterProcessor removes markdown before TTS

        # Build pipeline processors list
        pipeline_processors = [
            transport.input(),
            stt,                          # STT first to generate transcriptions
        ]

        # Only add SmartInterruptionProcessor if enabled
        if smart_int_enabled:
            pipeline_processors.append(self.smart_interruption)  # Validate interruptions from transcriptions
            logger.info("🛡️ SmartInterruptionProcessor added to pipeline")
        else:
            logger.info("🛡️ SmartInterruptionProcessor DISABLED - not added to pipeline")

        # Continue with rest of pipeline
        # STTMuteFilter MUST be before context_aggregator.user() to block
        # VAD/transcription frames during bot speech (prevents self-interruption)
        pipeline_processors.extend([
            self.tone_processor,          # AFTER STT to receive both audio AND transcriptions for hybrid mode
            self.stt_mute_filter,         # Mute BEFORE context - blocks VAD/STT frames during bot speech
            context_aggregator.user(),    # Context aggregator (receives only unmuted frames)
            self.rtvi,
            llm,
            self.visual_hint_processor,   # Stream text and detect content for visual cards
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

        # Build pipeline params with interruption support
        pipeline_params = PipelineParams(
            enable_metrics=enable_metrics,
            enable_usage_metrics=enable_metrics,
            idle_timeout_secs=60,  # Increased from default ~5s to prevent premature cancellation
            report_only_initial_ttfb=True,  # Only report first TTFB for cleaner metrics
            allow_interruptions=True,  # Enable barge-in - user can interrupt bot speech
        )

        # Interruption strategy configuration
        # When interruption_strategies is set, pipecat DEFERS interruption to the
        # LLM aggregator (waits for word count check). When empty, pipecat sends
        # InterruptionFrame IMMEDIATELY on any UserStartedSpeakingFrame during bot speech.
        # Using immediate interruption for reliable barge-in behavior.
        server_config = self.config.get("server", {})
        interruption_config = server_config.get("interruption", {})
        min_words = interruption_config.get("min_words", 0)

        if INTERRUPTION_STRATEGY_AVAILABLE and min_words > 0:
            pipeline_params.interruption_strategies = [MinWordsInterruptionStrategy(min_words=min_words)]
            logger.info(f"🎤 Interruption: DEFERRED mode (MinWords={min_words})")
        else:
            # No strategies = immediate interruption on any speech during bot output
            logger.info(f"🎤 Interruption: IMMEDIATE mode (any speech stops TTS)")

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

            # Queue greeting through the TASK so it flows through the full pipeline
            # This is critical: STTMuteFilter needs to see TTS start/stop frames
            # to know when bot speech begins/ends. Pushing directly to self.tts
            # bypasses the pipeline and the mute filter never unmutes.

            # Randomized greeting messages for variety
            import random
            greeting_options = [
                "Hi, I'm Nester A I. We're reimagining intelligence through research, design, and technology. What brings you here today?",
                "Hey there! I'm Nester A I from Nesterlabs. We build AI products with a human touch. What are you working on?",
                "Welcome! I'm the Nesterlabs voice assistant. We specialize in voice AI and agentic systems. How can I help you today?",
                "Hi! Nester A I here. We help companies build amazing AI experiences. Tell me about your project.",
                "Hello! I'm Nester A I, your guide to Nesterlabs. We're an AI studio in the Bay Area. What would you like to explore?"
            ]
            greeting_text = random.choice(greeting_options)

            # Send TextFrame first for subtitles/transcript, then TTSSpeakFrame for audio
            await self.task.queue_frame(TextFrame(greeting_text))
            await self.task.queue_frame(TTSSpeakFrame(greeting_text))
            logger.info(f"🎤 Greeting sent with subtitle: '{greeting_text[:50]}...'")

            # Add greeting to conversation context so LLM knows it already greeted
            if self.conversation_manager and self.conversation_manager.context:
                self.conversation_manager.context.messages.append(
                    {"role": "assistant", "content": greeting_text}
                )
                logger.info("📝 Greeting added to conversation context")

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
