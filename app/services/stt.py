"""
Speech-to-Text service for the Voice Assistant.

This module provides speech-to-text functionality using various STT engines
including Whisper and Deepgram, with support for text normalization and
noise filtering.
"""

import re
import unicodedata
from typing import Any, Dict, List, Tuple

# deepgram-sdk 7.x removed the top-level `LiveOptions`. Pipecat 1.4.0 ships a
# compatibility shim mirroring the old class; import it from there.
from pipecat.services.deepgram.stt import LiveOptions
from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.deepgram.stt import DeepgramSTTService
# Deepgram Flux: conversational STT with model-native turn detection
# (StartOfTurn / EndOfTurn / EagerEndOfTurn). Pairs with
# ExternalUserTurnStrategies on the aggregator — Flux drives the turn, not
# VAD/SmartTurn.
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
# WhisperSTTService (and its faster_whisper dependency) is imported lazily in
# _initialize_service() only when the whisper provider is selected. Deepgram is
# the production provider and faster_whisper is not installed in that path.
from pipecat.transcriptions.language import Language


class STTCorrectionsMixin:
    """Unicode normalization + config-driven corrections for STT services.

    Cooperative mixin: list it BEFORE the concrete STT service base so its
    push_frame/queue_frame overrides run first and `super()` resolves through
    the service's MRO. Corrections are loaded from config.yaml
    `stt.config.corrections` as {"pattern": regex, "replacement": text} entries,
    compiled once via _init_corrections().
    """

    def _init_corrections(self, corrections: List[Dict] = None) -> None:
        self._corrections: List[Tuple[re.Pattern, str]] = []
        if corrections:
            for entry in corrections:
                try:
                    compiled = re.compile(entry["pattern"], re.IGNORECASE)
                    self._corrections.append((compiled, entry["replacement"]))
                except (re.error, KeyError) as e:
                    logger.warning(f"Invalid STT correction entry {entry}: {e}")
            logger.info(f"STT post-processing: {len(self._corrections)} corrections loaded")

    def _normalize_text(self, text: str) -> str:
        """Normalize Unicode text to prevent encoding issues.

        Args:
            text: Input text to normalize

        Returns:
            Normalized text string
        """
        if not text:
            return text

        try:
            # Normalize to NFC form (canonical decomposition, then composition)
            normalized = unicodedata.normalize("NFC", text)
            return normalized.encode("utf-8").decode("utf-8")
        except (UnicodeError, TypeError) as e:
            logger.warning(f"Text normalization failed for '{text}': {e}")
            return text

    def _apply_corrections(self, text: str) -> str:
        """Apply config-driven STT corrections to transcribed text.

        Args:
            text: Transcribed text that may contain misrecognitions

        Returns:
            Text with corrections applied
        """
        if not text or not self._corrections:
            return text
        for pattern, replacement in self._corrections:
            text = pattern.sub(replacement, text)
        return text

    async def push_frame(self, frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        """Override push_frame to normalize text and fix proper nouns.

        Args:
            frame: Frame to push
            direction: Frame direction
        """
        # Log and normalize TranscriptionFrames
        if isinstance(frame, TranscriptionFrame):
            logger.info(f"🎤 STT push_frame: TranscriptionFrame text='{frame.text}'")
            if frame.text:
                corrected = self._apply_corrections(self._normalize_text(frame.text))
                if corrected != frame.text:
                    logger.debug(f"STT corrected: '{frame.text}' -> '{corrected}'")
                    frame = TranscriptionFrame(
                        text=corrected,
                        user_id=frame.user_id,
                        timestamp=frame.timestamp,
                        language=getattr(frame, "language", None),
                    )

        await super().push_frame(frame, direction)

    async def queue_frame(self, frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        """Override queue_frame to log transcription frames.

        Args:
            frame: Frame to queue
            direction: Frame direction
        """
        # Log TranscriptionFrames
        if isinstance(frame, TranscriptionFrame):
            logger.info(f"🎤 STT queue_frame: TranscriptionFrame text='{frame.text}'")

        await super().queue_frame(frame, direction)


class TextNormalizedDeepgramSTTService(STTCorrectionsMixin, DeepgramSTTService):
    """Nova (listen v1) STT with normalization + corrections."""

    def __init__(self, api_key: str, live_options: LiveOptions = None,
                 corrections: List[Dict] = None, **kwargs):
        super().__init__(api_key=api_key, live_options=live_options, **kwargs)
        self._init_corrections(corrections)


class TextNormalizedFluxSTTService(STTCorrectionsMixin, DeepgramFluxSTTService):
    """Deepgram Flux STT with normalization + corrections.

    Same post-processing as the Nova service; turn detection is handled by
    Flux itself (EOT/EagerEOT events broadcast as user-speaking frames).
    """

    def __init__(self, *args, corrections: List[Dict] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_corrections(corrections)


class SpeechToTextService:
    """Service for converting speech to text.

    Provides a unified interface for speech-to-text functionality using
    different STT providers (Whisper, Deepgram).

    Attributes:
        stt_provider: Name of the STT provider
        stt_service: Underlying STT service instance
        config: Configuration dictionary
    """

    def __init__(self, stt_provider: str = "whisper", **kwargs):
        """Initialize the Speech-to-Text service.

        Args:
            stt_provider: STT provider ("whisper" or "deepgram")
            **kwargs: Additional configuration parameters
        """
        self.stt_provider = stt_provider
        self.stt_service = None
        self.config = kwargs

    def initialize(self) -> Any:
        """Initialize the STT service based on the provider.

        Returns:
            Initialized STT service instance

        Raises:
            ValueError: If provider is unsupported or API key is missing
        """
        if self.stt_provider == "whisper":
            from pipecat.services.whisper.stt import WhisperSTTService
            self.stt_service = WhisperSTTService(
                device=self.config.get("device", "cpu"),
                model=self.config.get("model", "small"),
                no_speech_prob=self.config.get("no_speech_prob", 0.3),
            )
        elif self.stt_provider == "deepgram_flux":
            api_key = self.config.get("api_key")
            if not api_key:
                raise ValueError("Deepgram API key is required")

            flux_cfg = self.config.get("flux", {})
            settings = TextNormalizedFluxSTTService.Settings(
                model=flux_cfg.get("model", "flux-general-en"),
                eot_threshold=flux_cfg.get("eot_threshold", 0.7),
                eot_timeout_ms=flux_cfg.get("eot_timeout_ms"),
                eager_eot_threshold=flux_cfg.get("eager_eot_threshold"),
                keyterm=list(self.config.get("keyterms") or []) or None,
            )
            # native_interruption=True: Flux's model-based StartOfTurn barges in
            # directly (it's trained to ignore noise/backchannels). Set false to
            # fall back to the MinWords word-count gate on the aggregator instead.
            should_interrupt = bool(flux_cfg.get("native_interruption", True))
            self.stt_service = TextNormalizedFluxSTTService(
                api_key=api_key,
                settings=settings,
                should_interrupt=should_interrupt,
                corrections=self.config.get("corrections", []),
            )
            logger.info(
                f"Initialized Deepgram FLUX STT: model={settings.model}, "
                f"eot_threshold={settings.eot_threshold}, "
                f"eager_eot={settings.eager_eot_threshold or 'off'}, "
                f"native_interruption={should_interrupt}, "
                f"keyterms={len(self.config.get('keyterms') or [])}"
            )
        elif self.stt_provider == "deepgram":
            api_key = self.config.get("api_key")
            if not api_key:
                raise ValueError("Deepgram API key is required")

            language = self.config.get("language", "en")
            detect_language = self.config.get("detect_language", False)

            live_options_config = {
                "model": self.config.get("model", "nova-2"),
                "smart_format": self.config.get("smart_format", True),
                "punctuate": self.config.get("punctuate", True),
                "endpointing": self.config.get("endpointing", 500),
                "utterance_end_ms": self.config.get("utterance_end_ms", 1200),
                "interim_results": self.config.get("interim_results", True),
            }
            # Nova-3 keyterm prompting: bias recognition toward brand/founder terms
            # at DECODE time, so "Nesterlabs" doesn't come out as "Nestle labs" in
            # the first place. Complements (and should shrink) the regex
            # corrections below, which only patch mistakes after the fact.
            keyterms = self.config.get("keyterms")
            if keyterms:
                live_options_config["keyterm"] = list(keyterms)
                logger.info(f"Deepgram keyterm boosting: {len(keyterms)} terms")

            # NOTE: `filler_words` and `vad_events` are intentionally NOT passed.
            # deepgram-sdk 7.x (pulled in by pipecat 1.4.0) removed them from
            # AsyncV1Client.connect(); pipecat's LiveOptions shim forwards unknown
            # options as raw kwargs, so passing either raises
            # "connect() got an unexpected keyword argument 'filler_words'" and the
            # STT socket retries forever. Both default to False in Deepgram anyway
            # (no filler words returned; local Silero VAD handles speech detection),
            # so omitting them preserves the previous behavior.

            # NOTE: Deepgram's `keywords` param breaks Nova-3 WebSocket connections.
            # Proper noun correction is handled via config-driven post-processing
            # in TextNormalizedDeepgramSTTService._apply_corrections() instead.
            corrections = self.config.get("corrections", [])

            if detect_language:
                live_options_config["detect_language"] = True
            elif language == "multi" or language == "hi" or self.config.get("support_hinglish", False):
                # Multi-language mode: Hindi + English (Hinglish) support via Deepgram Nova-3
                live_options_config["language"] = "multi"
            else:
                language_mapping = {"en": Language.EN, "hi": Language.HI}
                live_options_config["language"] = language_mapping.get(language, Language.EN)

            live_options = LiveOptions(**live_options_config)
            logger.info(
                f"Deepgram LiveOptions: smart_format={live_options_config['smart_format']}, "
                f"endpointing={live_options_config['endpointing']}ms"
            )

            self.stt_service = TextNormalizedDeepgramSTTService(
                api_key=api_key, live_options=live_options, corrections=corrections
            )
        else:
            raise ValueError(f"Unsupported STT provider: {self.stt_provider}")

        logger.info(f"Initialized STT service: {self.stt_provider}")
        return self.stt_service

    def get_service(self) -> Any:
        """Get the STT service instance, initializing if needed.

        Returns:
            STT service instance
        """
        if self.stt_service is None:
            self.initialize()
        return self.stt_service

    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration.

        Returns:
            Configuration dictionary
        """
        return {"provider": self.stt_provider, "config": self.config}

    def update_config(self, **kwargs) -> None:
        """Update configuration and reinitialize if needed.

        Args:
            **kwargs: New configuration parameters
        """
        self.config.update(kwargs)
        logger.info(f"Updated STT config: {kwargs}")

        if self.stt_service is not None:
            logger.info("Re-initializing STT service with new config")
            self.initialize()
