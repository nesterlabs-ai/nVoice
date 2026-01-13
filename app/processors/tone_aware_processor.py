"""Tone-Aware Processor for dynamic voice selection.

This processor sits in the pipeline and detects emotional tone from user speech.
It uses MSP-PODCAST trained wav2vec2 for dimensional emotion detection from voice prosody.

Features:
- MSP-PODCAST model trained on real podcast conversations (not acted speech)
- Dimensional emotions: arousal, dominance, valence (more nuanced)
- Maps dimensions to 4 voice tones (neutral, excited, frustrated, sad)
- Stability system prevents rapid voice switching
- Falls back to text-based detection if unavailable
- Zero cost (fully local inference)
"""

from typing import Optional
import time
import json
import numpy as np

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    InterimTranscriptionFrame,
    TranscriptionUpdateFrame,
    AudioRawFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    OutputTransportMessageFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.services.tone_detector import ToneDetector, TONE_TO_VOICE, DEFAULT_VOICE
from app.services.msp_emotion_detector import (
    get_msp_detector,
    MSPEmotionDetector,
)
from app.services.chatterbox_tts import ChatterboxTTSService


class ToneAwareProcessor(FrameProcessor):
    """Processor that detects emotional tone and switches TTS voice.

    Uses MSP-PODCAST trained wav2vec2 for dimensional emotion detection:
    1. Audio frames are processed by wav2vec2 model (trained on MSP-PODCAST)
    2. Model returns arousal, dominance, valence (0-1 scale)
    3. Dimensions are mapped to our 4 voice tones
    4. Voice is switched based on stability system

    Dimensional emotion mapping:
    - High arousal + negative valence = frustrated
    - High arousal + positive valence = excited
    - Low arousal + negative valence = sad
    - Low/medium arousal + positive valence = neutral

    Flow:
    1. User speaks (frustrated/excited/sad/neutral)
    2. Audio sent to MSP-PODCAST model for dimensional emotion detection
    3. Model returns arousal/dominance/valence
    4. Dimensions mapped to tone (neutral/excited/frustrated/sad)
    5. Stability system checks (cooldown, confidence)
    6. TTS voice switched if stable
    7. Bot responds with appropriate voice

    Attributes:
        emotion_detector: MSPEmotionDetector for audio analysis
        tone_detector: ToneDetector for text-based fallback
        tts_service: Reference to TTS service for voice switching
        enabled: Whether tone-aware voice switching is enabled
        current_voice_model: Currently active voice model
    """

    def __init__(
        self,
        tts_service=None,
        cooldown_seconds: float = 2.0,  # Slightly longer for stability
        enabled: bool = True,
        **kwargs
    ):
        """Initialize the ToneAwareProcessor.

        Args:
            tts_service: Reference to Deepgram TTS service for voice switching
            cooldown_seconds: Minimum time between voice switches
            enabled: Whether to enable tone-aware voice switching
            **kwargs: Additional arguments passed to FrameProcessor
        """
        super().__init__(**kwargs)

        # MSP-PODCAST detector (trained on real podcast conversations)
        self.emotion_detector: MSPEmotionDetector = get_msp_detector()

        # Text-based fallback detector
        self.tone_detector = ToneDetector(cooldown_seconds=cooldown_seconds)

        self.tts_service = tts_service
        self.enabled = enabled

        # Voice switching state
        self.current_voice_model: str = DEFAULT_VOICE
        self._current_tone: str = "neutral"

        # Detection state
        self._latest_arousal: float = 0.5
        self._latest_dominance: float = 0.5
        self._latest_valence: float = 0.5
        self._latest_emotion: str = "neutral"
        self._latest_tone: str = "neutral"
        self._latest_confidence: float = 0.0

        # ===== STABILITY SYSTEM =====
        # Tuned for MSP-PODCAST dimensional emotions:
        # 1. Cooldown: 2.0s (prevent rapid switching)
        # 2. Confidence gate: 25% (dimensional clarity threshold)
        # 3. 2-frame agreement: Require consistent detection

        self._stability_counter: int = 0
        self._stability_last_tone: str = "neutral"
        self._last_switch_time: float = 0.0
        self._switch_cooldown: float = cooldown_seconds
        self._confidence_threshold: float = 0.05  # Dimensional clarity threshold (lowered for more responsive tone adaptation)
        self._stability_frames_required: int = 2   # Require 2 consistent detections

        # Audio buffer for MSP-PODCAST processing
        # 1000ms for better dimensional emotion detection
        self._audio_buffer: bytes = b""
        self._audio_buffer_duration_ms: int = 0
        self._min_buffer_ms: int = 1000  # 1 second for stable dimension detection

        # Voice switch deferral - don't interrupt bot speech
        self._bot_is_speaking: bool = False
        self._pending_voice_switch: Optional[tuple] = None  # (voice, tone) to switch to

        # VAD threshold for silence detection
        self._vad_threshold: int = 500  # Skip audio below this amplitude

        logger.info(
            f"ToneAwareProcessor MSP-PODCAST: conf=0.25, buffer=1000ms, "
            f"stability=2, cooldown={cooldown_seconds}s"
        )

    async def initialize(self) -> None:
        """Initialize MSP-PODCAST wav2vec2 model (lazy loading)."""
        if self.enabled:
            connected = await self.emotion_detector.connect()
            if connected:
                logger.info("MSP-PODCAST wav2vec2 emotion detection ready (natural conversation, $0)")
            else:
                logger.warning("MSP-PODCAST initialization failed, using text fallback")

    def set_tts_service(self, tts_service) -> None:
        """Set the TTS service reference for voice switching.

        Args:
            tts_service: The Deepgram TTS service instance
        """
        self.tts_service = tts_service
        logger.info("TTS service connected to ToneAwareProcessor")

    def _can_switch_cooldown(self) -> bool:
        """Check if cooldown period has passed since last switch."""
        if self._last_switch_time == 0.0:
            return True
        return (time.time() - self._last_switch_time) >= self._switch_cooldown

    def _is_tone_stable(self, tone: str, confidence: float) -> bool:
        """Check if tone is stable enough for voice switching.

        Args:
            tone: Detected tone
            confidence: Confidence score (dimensional clarity)

        Returns:
            True if stable enough to switch
        """
        # Check confidence gate (dimensional clarity)
        if confidence < self._confidence_threshold:
            self._stability_counter = 0
            return False

        # Check cooldown
        if not self._can_switch_cooldown():
            return False

        # Track consecutive same-tone detections
        if tone == self._stability_last_tone:
            self._stability_counter += 1
        else:
            self._stability_last_tone = tone
            self._stability_counter = 1

        is_stable = self._stability_counter >= self._stability_frames_required

        if is_stable:
            logger.info(
                f"STABLE (MSP): {tone} ({confidence:.0%}) "
                f"[{self._stability_counter}/{self._stability_frames_required}]"
            )

        return is_stable

    def _record_switch(self, tone: str) -> None:
        """Record that a voice switch happened."""
        self._last_switch_time = time.time()
        self._stability_counter = 0
        self._current_tone = tone

    def _get_current_tone(self) -> str:
        """Get the current tone."""
        return self._current_tone

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames for emotion detection and voice switching.

        Args:
            frame: The frame to process
            direction: Direction of frame flow
        """
        await super().process_frame(frame, direction)

        if not self.enabled:
            await self.push_frame(frame, direction)
            return

        # Track bot speaking state to avoid interrupting speech
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_is_speaking = True
            logger.debug("Bot started speaking - voice switches deferred")

        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_is_speaking = False
            logger.debug("Bot stopped speaking")
            # Apply any pending voice switch now that bot finished speaking
            if self._pending_voice_switch:
                voice, tone = self._pending_voice_switch
                self._pending_voice_switch = None
                await self._apply_voice_switch(voice, tone)

        # Process audio frames for MSP-PODCAST (only user input, not bot output)
        if (
            isinstance(frame, AudioRawFrame)
            and direction == FrameDirection.DOWNSTREAM
            and self.emotion_detector.is_connected
        ):
            await self._process_audio_frame(frame)

        # Process transcription frames for fallback/logging
        transcription_types = (
            TranscriptionFrame,
            InterimTranscriptionFrame,
            TranscriptionUpdateFrame,
        )
        if isinstance(frame, transcription_types):
            text = getattr(frame, "text", "")
            frame_name = type(frame).__name__
            logger.debug(f"{frame_name}: '{text}'")

            # If MSP-PODCAST not connected, use text-based detection
            if not self.emotion_detector.is_connected and text and text.strip():
                await self._process_text_fallback(text)

        # Always pass frame downstream
        await self.push_frame(frame, direction)

    async def _process_audio_frame(self, frame: AudioRawFrame) -> None:
        """Process audio frame with MSP-PODCAST model.

        Buffers audio and sends to model every 1000ms for emotion detection.
        Includes VAD filter to skip silence.

        Args:
            frame: Audio frame with raw PCM data
        """
        # VAD filter: Skip silence to improve accuracy
        audio_array = np.frombuffer(frame.audio, dtype=np.int16)
        mean_amplitude = np.mean(np.abs(audio_array))
        if mean_amplitude < self._vad_threshold:
            return  # Skip silent frames

        # Add to buffer
        self._audio_buffer += frame.audio

        # Get actual sample rate from frame (default 16kHz)
        sample_rate = getattr(frame, 'sample_rate', 16000)

        # Calculate buffer duration (16kHz * 2 bytes = 32 bytes/ms)
        self._audio_buffer_duration_ms = len(self._audio_buffer) / 32

        # Process at 1000ms (MSP-PODCAST optimal for stable dimensions)
        if self._audio_buffer_duration_ms >= self._min_buffer_ms:
            try:
                # Send to MSP-PODCAST for dimensional emotion detection
                result = await self.emotion_detector.process_audio(
                    self._audio_buffer,
                    sample_rate=sample_rate
                )

                if result:
                    self._latest_arousal = result.arousal
                    self._latest_dominance = result.dominance
                    self._latest_valence = result.valence
                    self._latest_emotion = result.emotion
                    self._latest_tone = result.tone
                    self._latest_confidence = result.confidence

                    # Emit emotion data to frontend via WebSocket
                    await self._emit_emotion_event(result)

                    # Check if we should switch voice (only if above threshold)
                    if result.confidence >= self._confidence_threshold:
                        await self._check_voice_switch(result.tone, result.confidence)

            except Exception as e:
                logger.error(f"MSP-PODCAST audio processing error: {e}")

            # Clear buffer
            self._audio_buffer = b""
            self._audio_buffer_duration_ms = 0

    async def _process_text_fallback(self, text: str) -> None:
        """Process text with LLM-based tone detection (fallback).

        Used when MSP-PODCAST is not available.

        Args:
            text: Transcribed text
        """
        try:
            tone = await self.tone_detector.detect_tone_llm(text)
            confidence = 0.7  # Text-based detection has moderate confidence

            logger.info(f"TEXT FALLBACK: {tone} ({confidence:.0%})")

            await self._check_voice_switch(tone, confidence)

        except Exception as e:
            logger.error(f"Text tone detection error: {e}")

    async def _check_voice_switch(self, tone: str, confidence: float) -> None:
        """Check if voice should be switched based on detected tone.

        Args:
            tone: Detected tone
            confidence: Confidence score
        """
        current_tone = self._get_current_tone()

        logger.debug(
            f"_check_voice_switch: tone={tone}, current={current_tone}, "
            f"tts_service={self.tts_service is not None}"
        )

        # Only switch if tone is different
        if tone != current_tone:
            is_stable = self._is_tone_stable(tone, confidence)
            has_tts = self.tts_service is not None

            logger.info(
                f"VOICE SWITCH CHECK: tone={tone}, stable={is_stable}, "
                f"tts_connected={has_tts}, current={current_tone}"
            )

            if is_stable and has_tts:
                voice = TONE_TO_VOICE.get(tone, DEFAULT_VOICE)
                self._record_switch(tone)
                logger.info(f"INITIATING VOICE SWITCH: {current_tone} -> {tone} (voice: {voice})")
                await self._switch_voice_now(voice, tone)
            else:
                logger.debug(
                    f"Tone: {tone} ({confidence:.0%}) - "
                    f"waiting [{self._stability_counter}/{self._stability_frames_required}]"
                )

    async def _switch_voice_now(self, new_voice: str, tone: str) -> None:
        """Request voice switch - defers if bot is speaking.

        Args:
            new_voice: The new voice model to use
            tone: The detected emotional tone
        """
        logger.info(
            f"_switch_voice_now called: new_voice={new_voice}, tone={tone}, "
            f"tts_service={self.tts_service is not None}, bot_speaking={self._bot_is_speaking}"
        )

        if not self.tts_service:
            logger.warning("Cannot switch voice: TTS service not connected")
            return

        # If bot is currently speaking, defer the switch until it finishes
        if self._bot_is_speaking:
            self._pending_voice_switch = (new_voice, tone)
            logger.info(
                f"VOICE SWITCH DEFERRED: {self.current_voice_model} -> {new_voice} "
                f"(tone: {tone}) - waiting for bot to finish speaking"
            )
            return

        # Bot not speaking, apply immediately
        logger.info(f"Bot not speaking, applying voice switch immediately")
        await self._apply_voice_switch(new_voice, tone)

    async def _apply_voice_switch(self, new_voice: str, tone: str) -> None:
        """Actually apply the voice switch (only call when bot is not speaking).

        For Chatterbox TTS: Uses set_emotion() to control exaggeration and cfg_weight
        For other TTS: Uses set_voice() to switch voice model

        Args:
            new_voice: The new voice model to use (for non-Chatterbox TTS)
            tone: The detected emotional tone
        """
        logger.info(
            f"_apply_voice_switch called: new_voice={new_voice}, tone={tone}, "
            f"tts_service type={type(self.tts_service).__name__}"
        )

        if not self.tts_service:
            logger.warning("_apply_voice_switch: No TTS service!")
            return

        try:
            old_tone = self._current_tone

            # Check if using Chatterbox TTS (emotion-based control)
            if isinstance(self.tts_service, ChatterboxTTSService):
                # Chatterbox uses set_emotion() for audible tone changes
                # This controls exaggeration and cfg_weight parameters
                logger.info(f"Chatterbox TTS: Setting emotion to '{tone}'")
                self.tts_service.set_emotion(tone)
                self.current_voice_model = tone  # Track as tone for Chatterbox
                logger.info(
                    f"✅ EMOTION SWITCHED (Chatterbox): {old_tone} -> {tone}"
                )

                # Emit tone switch event to frontend
                await self._emit_tone_switch_event(old_tone, tone)
            else:
                # Other TTS providers: Use voice switching
                old_voice = self.current_voice_model
                logger.info(f"Calling tts_service.set_voice('{new_voice}')")
                self.tts_service.set_voice(new_voice)
                self.current_voice_model = new_voice

                # Verify the voice was set
                actual_voice = getattr(self.tts_service, '_voice_id', 'unknown')
                logger.info(f"TTS service _voice_id is now: {actual_voice}")
                logger.info(
                    f"✅ VOICE SWITCHED: {old_voice} -> {new_voice} (tone: {tone})"
                )

                # Emit tone switch event to frontend
                await self._emit_tone_switch_event(old_voice, new_voice)

        except Exception as e:
            logger.error(f"Error switching voice/emotion: {e}")
            import traceback
            traceback.print_exc()

    async def _emit_emotion_event(self, result) -> None:
        """Emit emotion detection event to frontend via WebSocket.

        Args:
            result: MSPEmotionResult with arousal, dominance, valence, emotion, tone, confidence
        """
        try:
            # Create emotion data payload for frontend
            # Use RTVI-compliant "server-message" type for proper callback routing
            emotion_message = {
                "label": "rtvi-ai",
                "type": "server-message",
                "data": {
                    "message_type": "emotion_detected",
                    "arousal": round(result.arousal, 2),
                    "dominance": round(result.dominance, 2),
                    "valence": round(result.valence, 2),
                    "emotion": result.emotion,
                    "tone": result.tone,
                    "confidence": round(result.confidence, 2),
                    "timestamp": result.timestamp,
                }
            }

            # Push data frame to transport (will be sent via WebSocket)
            data_frame = OutputTransportMessageFrame(message=emotion_message)
            await self.push_frame(data_frame)

            logger.info(f"✓ Emitted emotion event via WebSocket: {result.emotion} ({result.confidence:.0%}) - A:{result.arousal:.2f} D:{result.dominance:.2f} V:{result.valence:.2f}")

        except Exception as e:
            logger.error(f"Error emitting emotion event: {e}")

    async def _emit_tone_switch_event(self, old_tone: str, new_tone: str) -> None:
        """Emit tone switch event to frontend via WebSocket.

        Args:
            old_tone: Previous tone/voice
            new_tone: New tone/voice
        """
        try:
            # Create tone switch payload for frontend
            # Use RTVI-compliant "server-message" type for proper callback routing
            switch_message = {
                "label": "rtvi-ai",
                "type": "server-message",
                "data": {
                    "message_type": "tone_switched",
                    "old_tone": old_tone,
                    "new_tone": new_tone,
                    "timestamp": time.time(),
                }
            }

            # Push data frame to transport (will be sent via WebSocket)
            data_frame = OutputTransportMessageFrame(message=switch_message)
            await self.push_frame(data_frame)

            logger.debug(f"Emitted tone switch event: {old_tone} -> {new_tone}")

        except Exception as e:
            logger.error(f"Error emitting tone switch event: {e}")

    def get_current_voice(self) -> str:
        """Get the current TTS voice."""
        return self.current_voice_model

    def get_stats(self) -> dict:
        """Get processor statistics."""
        return {
            "enabled": self.enabled,
            "msp_connected": self.emotion_detector.is_connected,
            "tts_connected": self.tts_service is not None,
            "current_voice_model": self.current_voice_model,
            "current_tone": self._current_tone,
            "latest_arousal": self._latest_arousal,
            "latest_dominance": self._latest_dominance,
            "latest_valence": self._latest_valence,
            "latest_emotion": self._latest_emotion,
            "latest_tone": self._latest_tone,
            "latest_confidence": self._latest_confidence,
            "stability_counter": self._stability_counter,
            "stability_last_tone": self._stability_last_tone,
            "stability_frames_required": self._stability_frames_required,
            "switch_cooldown": self._switch_cooldown,
            "confidence_threshold": self._confidence_threshold,
            "time_since_last_switch": (
                time.time() - self._last_switch_time
                if self._last_switch_time > 0
                else None
            ),
        }

    def reset(self) -> None:
        """Reset detector and voice state to default."""
        self.tone_detector.reset()
        self.emotion_detector.reset()
        self.current_voice_model = DEFAULT_VOICE
        self._current_tone = "neutral"
        self._latest_arousal = 0.5
        self._latest_dominance = 0.5
        self._latest_valence = 0.5
        self._latest_emotion = "neutral"
        self._latest_tone = "neutral"
        self._latest_confidence = 0.0
        self._stability_counter = 0
        self._stability_last_tone = "neutral"
        self._last_switch_time = 0.0
        self._audio_buffer = b""
        self._audio_buffer_duration_ms = 0
        self._bot_is_speaking = False
        self._pending_voice_switch = None

        if self.tts_service:
            if isinstance(self.tts_service, ChatterboxTTSService):
                self.tts_service.set_emotion("neutral")
                logger.info("Emotion reset to neutral (Chatterbox)")
            else:
                self.tts_service.set_voice(DEFAULT_VOICE)
                logger.info(f"Voice reset to default: {DEFAULT_VOICE}")

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.emotion_detector.disconnect()
        logger.info("ToneAwareProcessor cleaned up")
