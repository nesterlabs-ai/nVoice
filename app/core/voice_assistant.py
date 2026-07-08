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
from pipecat.frames.frames import (
    TTSSpeakFrame,
    TextFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
# STTMuteFilter was removed in pipecat 1.x; muting is now a user-mute strategy
# on the context aggregator (see ConversationManager.create_context_aggregator).
# RTVI 2.0 (pipecat 1.4.0) removed RTVIConfig; RTVIProcessor no longer takes a
# config= (or transport=) argument.
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIProcessor
from pipecat.transports.base_transport import BaseTransport

# Barge-in / interruption is handled in pipecat 1.x by user-turn-START strategies
# on the context aggregator (see ConversationManager.create_context_aggregator),
# not by a PipelineParams interruption strategy. The old
# `pipecat.audio.interruptions.MinWordsInterruptionStrategy` was removed in 1.x.

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
from app.processors.subtitle_sync_processor import SubtitleSyncProcessor
from app.processors.question_card_context_processor import QuestionCardContextProcessor


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
        self.rtvi = RTVIProcessor()
        self.latency_analyzer = LatencyAnalyzer()

        # STT mute filter - mutes STT only during the first bot greeting
        # MUTE_UNTIL_FIRST_BOT_COMPLETE: blocks user audio only during initial greeting TTS,
        # then allows all user input through (including barge-in interruptions)
        # Self-interruption prevention relies on:
        #   1. Client-side echoCancellation: true (getUserMedia constraint)
        #   2. VAD params (confidence=0.7, min_volume=0.5, start_secs=0.2)
        # STT muting until the first bot turn completes is now handled by
        # MuteUntilFirstBotCompleteUserMuteStrategy inside the context aggregator
        # (pipecat 1.x removed the standalone STTMuteFilter processor).

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

        # Text filter processor to remove markdown before TTS.
        # inject_laughter=True only for Cartesia — it understands [laughter] tags natively.
        tts_provider_for_filter = self.config.get("tts", {}).get("provider", "elevenlabs")
        self.text_filter = TextFilterProcessor(
            enabled=True,
            inject_laughter=(tts_provider_for_filter == "cartesia"),
        )

        # Visual hint processor - now minimal, A2UI is handled via RAG calls only
        # A2UI (Agent-to-UI) is triggered ONLY when call_rag_system is invoked
        # This prevents visual cards from showing on every LLM response
        a2ui_config = self.config.get("a2ui", {})
        a2ui_enabled = a2ui_config.get("enabled", True)
        logger.info(f"🎨 A2UI system enabled (RAG-triggered only): {a2ui_enabled}")
        self.visual_hint_processor = VisualHintProcessor(
            enabled=True,
            stream_words=False,  # Disabled: SubtitleSyncProcessor handles subtitle timing via upstream TTSTextFrame
            detect_content=False,  # Legacy visual hints disabled
            use_a2ui=False,  # A2UI now handled via RAG calls in ConversationManager
        )

        # Subtitle sync processor - emits subtitles synced with TTS audio playback
        # Intercepts upstream TTSTextFrame (timed by transport) for perfect audio-text sync
        self.subtitle_sync = SubtitleSyncProcessor()

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

        # Injects compact per-turn house-answer guidance based on the latest user question.
        self.question_card_processor = None

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
        self.question_card_processor = QuestionCardContextProcessor(
            conversation_manager=self.conversation_manager,
            enabled=conversation_config.get("question_cards_enabled", True),
        )

        # Detected caller emotion steers the LLM's wording (system-note upsert),
        # not just the TTS voice.
        self.tone_processor.set_conversation_manager(self.conversation_manager)

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

        # Get context aggregator. In pipecat 1.x, VAD + SmartTurn v3 + greeting
        # mute are configured here (on the user aggregator) rather than on the
        # transport, so pass the analyzers built by the transport layer.
        idle_cfg = self.config.get("server", {}).get("idle_reengage", {})
        context_aggregator = self.conversation_manager.create_context_aggregator(
            vad_analyzer=getattr(self, "_vad_analyzer", None),
            turn_analyzer=getattr(self, "_turn_analyzer", None),
            interruption_config=self.config.get("server", {}).get("interruption", {}),
            user_idle_timeout=(
                float(idle_cfg.get("timeout_secs", 25))
                if idle_cfg.get("enabled", True)
                else 0
            ),
        )

        # Gentle re-engagement when the caller goes quiet (native 1.4.0
        # on_user_turn_idle event — replaces relying solely on the 10-min timeout).
        self._idle_nudges_sent = 0
        max_nudges = int(idle_cfg.get("max_nudges", 2))
        nudge_text = idle_cfg.get(
            "prompt", "Still with me? Happy to dig into anything else about what we build."
        )

        @context_aggregator.user().event_handler("on_user_turn_idle")
        async def on_user_turn_idle(aggregator):
            # Don't nudge over the bot's own speech, and cap nudges per session.
            if self.tone_processor and getattr(self.tone_processor, "_bot_is_speaking", False):
                return
            if self._idle_nudges_sent >= max_nudges:
                return
            self._idle_nudges_sent += 1
            logger.info(f"💤 User idle — re-engaging ({self._idle_nudges_sent}/{max_nudges})")
            await self.task.queue_frame(LLMFullResponseStartFrame())
            await self.task.queue_frame(TextFrame(nudge_text))
            await self.task.queue_frame(LLMFullResponseEndFrame())

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
        # Greeting-mute is now enforced inside context_aggregator.user() via
        # MuteUntilFirstBotCompleteUserMuteStrategy (pipecat 1.x).
        pipeline_processors.extend([
            self.tone_processor,          # AFTER STT to receive both audio AND transcriptions for hybrid mode
            self.question_card_processor,  # Inject latest-question house answer guidance before LLM context
            context_aggregator.user(),    # Context aggregator (receives only unmuted frames)
            self.rtvi,
            llm,
            self.visual_hint_processor,   # Stream text and detect content for visual cards
            self.text_filter,             # Remove markdown before TTS
            # SentenceAggregator intentionally omitted: Cartesia's CartesiaTTSService
            # is constructed with aggregate_sentences=False, so LLM tokens stream
            # token-by-token into Cartesia's persistent WebSocket (continue=true).
            # Sentence-level aggregation was creating audible gaps between sentences
            # because each sentence triggered a separate Cartesia request.
            tts,
            self.subtitle_sync,           # Sync subtitles with TTS audio via upstream TTSTextFrame
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

        # Barge-in gating (min-words) is configured on the user aggregator via
        # MinWordsUserTurnStartStrategy (see create_context_aggregator), not here.
        # allow_interruptions=True lets the aggregator emit interruption frames.

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

            # Start 10-minute session timeout
            asyncio.create_task(self._session_timeout(timeout_secs=600))

            # Brief settle before greeting. pipecat 1.x's PipelineTask already
            # blocks until StartFrame traverses the whole pipeline ("pipeline is
            # now ready" in logs), so the old 1.5s wait double-counted that.
            await asyncio.sleep(0.5)
            logger.info("🎤 Pipeline ready, sending greeting...")

            # Queue greeting through the TASK so it flows through the full pipeline.
            # This is critical: the MuteUntilFirstBotComplete user-mute strategy
            # needs to see TTS start/stop frames to know when the bot's first
            # speech begins/ends. Pushing directly to self.tts bypasses the
            # pipeline and the user is never unmuted.

            # Randomized greeting messages for variety
            import random
            greeting_options = [
                "Hi, I'm Nester AI from Nesterlabs. We work like an internal AI-native team for companies building serious AI products. What are you working on? ",
                "Hey there! I'm Nester AI from Nesterlabs. We help teams move voice and agentic systems into real production. What are you building? ",
                "Hi! I'm Nester AI, part of the Nesterlabs team. Are you shaping something new, or trying to make an existing product work better? ",
                "Hello! I'm Nester AI from Nesterlabs. We help define and ship AI products that need to work in the real world. What brings you here today? "
            ]
            # Add trailing space to ensure last word is emitted (not buffered for next chunk)
            greeting_text = random.choice(greeting_options)

            # Inject condensed DOC3 scenario tone patterns into context BEFORE the user speaks.
            # This pre-loads tone calibration so the LLM responds correctly from turn 1.
            # It is injected as a hidden system note — not spoken aloud.
            DESIGNER_TONE_WARMUP = """[Consultative voice reference — apply naturally, never mention these labels]

When user says "we need a redesign" → ask what is actually driving it: usability, conversion, trust, workflow friction, or positioning.
When user asks about your process → explain Imagine, Make, and Scale in simple language: understand the workflow first, build the system as one execution layer, then harden it under real usage.
When user says "we just need UI screens" → agree, then sanity-check whether the flow has been validated with real users or operators.
When user says "widget", "UI", "screens", or "product" in a fuzzy way → interpret it as product-definition territory first: flow, interface behavior, trust, error handling, and brand expression.
When user is building an AI product → explore trust, human handoff, error states, and where AI should or should not act.
When user asks whether Nesterlabs is an agency or staff augmentation → make the contrast explicit: we work more like an embedded AI-native product, UX, research, and engineering team.
When user asks deep technical questions → answer directly first with concrete system language: runtime, state, orchestration, memory, permissions, interruption handling, approvals, observability, and escalation. Only suggest a conversation with Kunal if the user wants a deeper working session.
When user asks product, UX, brand, roadmap, or design strategy questions → answer directly first as a team that does research, product framing, UX systems, brand expression, and product direction. Only suggest Shrey if they want a deeper strategy conversation.
When user wants something to "feel premium" → translate that into clarity, restraint, speed, predictability, trust, and product coherence.
When the user has already made the use case clear → stop reopening broad discovery and answer directly.
For technical answers in voice mode → keep it to one architectural point and one concrete detail unless the user asks for more.
Universal pattern: direct answer first, one useful insight, then one good question if needed. Never pitch. Never oversell internal tools."""

            # Send frames to properly signal utterance boundaries:
            # 1. LLMFullResponseStartFrame - initializes utterance_id
            # 2. TextFrame - the greeting text (flows through VisualHintProcessor → TTS)
            # 3. LLMFullResponseEndFrame - flushes word buffer and finalizes
            logger.info(f"🎤 Queueing greeting with utterance frames: '{greeting_text[:50]}...'")
            await self.task.queue_frame(LLMFullResponseStartFrame())
            await self.task.queue_frame(TextFrame(greeting_text))
            await self.task.queue_frame(LLMFullResponseEndFrame())
            logger.info(f"✅ Greeting frames queued successfully")

            # Add tone warmup + greeting to conversation context
            # Warmup is a hidden system note — gives the LLM scenario tone patterns before turn 1
            if self.conversation_manager and self.conversation_manager.context:
                self.conversation_manager.context.messages.append(
                    {"role": "system", "content": DESIGNER_TONE_WARMUP}
                )
                # The greeting is intentionally NOT appended here: it flows through
                # the pipeline as TTS and the assistant context aggregator captures
                # it automatically. Appending it manually duplicated the greeting as
                # two assistant turns in the LLM context (wasted tokens, confusing
                # history).
                logger.info("📝 Designer tone warmup added to conversation context")

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info(f"Client disconnected: {client}")
            # Don't reset greeting time here - let it expire naturally after 5 seconds
            # Don't cancel task immediately - the server loop will handle cleanup
            # and restart for new connections. Cancelling here causes issues when
            # a replacement connection arrives (Pipecat closes old connection first)
            logger.debug("Client disconnected, awaiting session end")

        logger.info("Transport handlers set up successfully")

    async def run(
        self,
        transport: BaseTransport,
        handle_sigint: bool = True,
        vad_analyzer: Any = None,
        turn_analyzer: Any = None,
    ) -> None:
        """Run the voice assistant.

        Args:
            transport: The transport layer for audio input/output
            handle_sigint: Whether to handle SIGINT for graceful shutdown
            vad_analyzer: Silero VAD instance. In pipecat 1.x this attaches to
                the user aggregator, not the transport.
            turn_analyzer: SmartTurn v3 end-of-turn analyzer (or None), also
                attached to the user aggregator in pipecat 1.x.
        """
        logger.info("Starting Voice Assistant...")

        # Stored so create_pipeline() can wire them into the context aggregator.
        self._vad_analyzer = vad_analyzer
        self._turn_analyzer = turn_analyzer

        # Initialize services if not already done
        if not self.conversation_manager:
            logger.debug("Initializing services...")
            self.initialize_services()

        # Create pipeline and task
        logger.debug("Creating pipeline...")
        await self.create_pipeline(transport)

        logger.debug("Creating task...")
        self.create_task()

        # Wire pipeline task and RTVI processor into ConversationManager
        # (must happen after create_task() so self.task is available)
        if self.conversation_manager:
            self.conversation_manager.set_pipeline_task(self.task)
            self.conversation_manager.set_rtvi_processor(self.rtvi)
            logger.info("🔗 Pipeline task and RTVI processor wired into ConversationManager")

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

    async def _session_timeout(self, timeout_secs: int = 600) -> None:
        """Proactively wrap up the session after a time limit.

        After `timeout_secs` seconds, if the conversation is not already ending,
        directly speaks a wrap-up prompt via TTS and injects it into the LLM context
        as an assistant turn. The user's natural response then flows through the LLM
        which (guided by an injected system message) proceeds with appointment booking
        or calls end_conversation().

        Args:
            timeout_secs: Seconds before the timeout fires (default 600 = 10 min)
        """
        await asyncio.sleep(timeout_secs)

        # Skip if conversation is already winding down
        if self.conversation_manager and self.conversation_manager._conversation_ending:
            logger.info(f"⏱️ Session timeout fired but conversation already ending — skipping")
            return

        logger.info(f"⏱️ {timeout_secs // 60}-minute session timeout reached — speaking wrap-up prompt")

        # System message tells LLM how to handle the user's next response
        timeout_system_msg = (
            "[SESSION TIME LIMIT REACHED] The voice session has been active for 10 minutes. "
            "You have just spoken the wrap-up prompt to the user. "
            "Now wait for their response. If they want to schedule a call: proceed with the appointment booking flow. "
            "If they decline or say no: thank them warmly and call end_conversation(). "
            "Do NOT mention 'session time limit' or 'timer' to the user."
        )

        # The pre-composed wrap-up speech that we'll say directly via TTS
        timeout_speech = (
            "We've been chatting for a while now — I want to make sure I'm not keeping you! "
            "Would you like to schedule some time with the Nester team for a deeper conversation?"
        )

        # 1. Inject system guidance so LLM knows the context when user replies
        if self.conversation_manager and self.conversation_manager.context:
            self.conversation_manager.context.messages.append(
                {"role": "system", "content": timeout_system_msg}
            )
            # Also record the wrap-up speech as an assistant turn so conversation history is consistent
            self.conversation_manager.context.messages.append(
                {"role": "assistant", "content": timeout_speech}
            )
            logger.info("📝 Timeout system message + assistant turn injected into context")

        # 2. Speak the wrap-up prompt directly via TTS (bypasses LLM entirely)
        #    The user hears the question; their reply naturally triggers the LLM via
        #    the normal STT → VAD → context aggregator pipeline path.
        if self.conversation_manager and self.conversation_manager.tts_service:
            try:
                from pipecat.frames.frames import TTSSpeakFrame
                await self.conversation_manager.tts_service.queue_frame(
                    TTSSpeakFrame(timeout_speech)
                )
                logger.info(f"🔊 Timeout wrap-up spoken via TTS: '{timeout_speech}'")
            except Exception as e:
                logger.warning(f"Could not speak timeout wrap-up: {e}")
        else:
            logger.warning("⚠️ TTS service not available for timeout wrap-up")

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
