"""Tone-Aware Processor for dynamic voice selection.

This processor sits in the pipeline after STT and before LLM.
It intercepts TranscriptionFrame, uses Gemini Flash LLM for accurate
emotional tone detection, and immediately switches TTS voice so the
bot responds with the appropriate voice for the user's emotional state.
"""

from typing import Optional

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.services.tone_detector import ToneDetector, TONE_TO_VOICE, DEFAULT_VOICE


class ToneAwareProcessor(FrameProcessor):
    """Processor that detects emotional tone and switches TTS voice.

    Intercepts TranscriptionFrame, analyzes the text for emotional tone,
    and immediately switches the TTS voice so the bot's response matches
    the user's emotional state.

    Flow:
    1. User speaks (frustrated/excited/sad/neutral)
    2. TranscriptionFrame received with user text
    3. Tone detected using Gemini Flash LLM (~100-150ms)
    4. TTS WebSocket disconnected and voice changed
    5. Bot responds with new voice (WebSocket auto-reconnects)

    Attributes:
        tone_detector: ToneDetector instance for emotion analysis
        tts_service: Reference to TTS service for voice switching
        enabled: Whether tone-aware voice switching is enabled
        current_voice_model: Currently active voice model
    """

    def __init__(
        self,
        tts_service=None,
        cooldown_seconds: float = 3.0,
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
        self.tone_detector = ToneDetector(cooldown_seconds=cooldown_seconds)
        self.tts_service = tts_service
        self.enabled = enabled

        # Voice switching state
        self.current_voice_model: str = DEFAULT_VOICE

        logger.info(
            f"ToneAwareProcessor initialized (enabled={enabled}, cooldown={cooldown_seconds}s)"
        )

    def set_tts_service(self, tts_service) -> None:
        """Set the TTS service reference for voice switching.

        Args:
            tts_service: The Deepgram TTS service instance
        """
        self.tts_service = tts_service
        logger.info("TTS service connected to ToneAwareProcessor")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames and detect tone on TranscriptionFrame.

        Args:
            frame: The frame to process
            direction: Direction of frame flow
        """
        await super().process_frame(frame, direction)

        # Only process TranscriptionFrame (final STT results)
        if isinstance(frame, TranscriptionFrame) and self.enabled:
            text = frame.text
            if text and text.strip():
                await self._process_transcription(text)

        # Always pass frame downstream
        await self.push_frame(frame, direction)

    async def _process_transcription(self, text: str) -> None:
        """Process transcription text for tone detection.

        Uses Gemini Flash LLM for accurate tone detection, then immediately
        switches voice so the bot responds with the appropriate voice.

        Args:
            text: Transcribed user speech
        """
        try:
            # Detect tone using LLM (async) for better accuracy
            detected_tone, voice, should_switch = await self.tone_detector.process_input_async(text)

            if should_switch and self.tts_service:
                # Apply voice change IMMEDIATELY so bot responds with new voice
                await self._switch_voice_now(voice, detected_tone)
            else:
                logger.debug(f"Tone detected: {detected_tone} (no switch needed)")

        except Exception as e:
            logger.error(f"Error in tone detection: {e}")
            # Don't fail the pipeline on tone detection errors

    async def _switch_voice_now(self, new_voice: str, tone: str) -> None:
        """Immediately switch voice before bot responds.

        This ensures the bot's response uses the voice matching the user's emotional state.

        Args:
            new_voice: The new voice model to use
            tone: The detected emotional tone
        """
        if not self.tts_service:
            logger.warning("Cannot apply voice change: TTS service not connected")
            return

        try:
            old_voice = self.current_voice_model

            # Set the new voice on the TTS service
            self.tts_service.set_voice(new_voice)

            # Disconnect the WebSocket - it will reconnect with new voice on next run_tts
            if hasattr(self.tts_service, '_disconnect'):
                await self.tts_service._disconnect()
                logger.info(
                    f"🎭 VOICE SWITCHED NOW: {old_voice} → {new_voice} "
                    f"(tone: {tone}) - bot will respond with new voice"
                )
            else:
                logger.info(
                    f"🎭 VOICE SET: {new_voice} (no _disconnect method, applies on reconnect)"
                )

            # Update current voice
            self.current_voice_model = new_voice

        except Exception as e:
            logger.error(f"Error switching voice: {e}")

    def get_current_voice(self) -> str:
        """Get the current TTS voice.

        Returns:
            Current voice model name
        """
        return self.tone_detector.get_current_voice()

    def get_stats(self) -> dict:
        """Get processor statistics.

        Returns:
            Dictionary with tone detector stats
        """
        return {
            "enabled": self.enabled,
            "tts_connected": self.tts_service is not None,
            "current_voice_model": self.current_voice_model,
            **self.tone_detector.get_stats()
        }

    def reset(self) -> None:
        """Reset tone detector and voice state to default."""
        self.tone_detector.reset()
        self.current_voice_model = DEFAULT_VOICE
        if self.tts_service:
            self.tts_service.set_voice(DEFAULT_VOICE)
            logger.info(f"Voice reset to default: {DEFAULT_VOICE}")
