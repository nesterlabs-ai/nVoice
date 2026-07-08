"""Noise Handler Processor for managing background noise and VAD false positives.

This processor monitors voice activity patterns and implements noise rejection
and recovery mechanisms when the system gets stuck in background noise loops.

Pattern-based noise detection for robust VAD false positive handling.
"""

import asyncio
import time
from typing import Optional

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TranscriptionFrame,
    CancelFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class NoiseHandlerProcessor(FrameProcessor):
    """Processor to handle background noise and prevent VAD false positive loops.

    This processor detects patterns that indicate background noise rather than
    real speech, such as:
    - Rapid start/stop speech events (< 0.5s apart)
    - Very short speech segments (< 0.5s duration)
    - Empty or short transcriptions

    When noise is detected, it enters recovery mode which temporarily blocks
    speech detection to prevent noise loops.
    """

    def __init__(
        self,
        max_false_starts: int = 3,
        silence_timeout: float = 5.0,
        min_speech_duration: float = 0.5,
        recovery_delay: float = 2.0,
    ):
        """Initialize the noise handler.

        Args:
            max_false_starts: Maximum false starts before triggering recovery
            silence_timeout: Seconds of silence needed to reset false start counter
            min_speech_duration: Minimum duration for valid speech detection
            recovery_delay: Delay before re-enabling after noise detection
        """
        super().__init__()

        self.max_false_starts = max_false_starts
        self.silence_timeout = silence_timeout
        self.min_speech_duration = min_speech_duration
        self.recovery_delay = recovery_delay

        # State tracking
        self.false_start_count = 0
        self.last_speech_start: Optional[float] = None
        self.last_silence_time: Optional[float] = None
        self.in_recovery_mode = False
        self.recovery_task: Optional[asyncio.Task] = None
        self.consecutive_short_utterances = 0
        self.is_user_speaking = False

        logger.info(
            f"🔇 NoiseHandler initialized - max_false_starts: {max_false_starts}, "
            f"min_speech_duration: {min_speech_duration}s, recovery_delay: {recovery_delay}s"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames and handle noise detection patterns.

        Args:
            frame: The frame to process
            direction: Direction of frame flow
        """
        await super().process_frame(frame, direction)

        current_time = time.time()

        # Handle user started speaking
        if isinstance(frame, UserStartedSpeakingFrame):
            await self._handle_speech_start(frame, current_time, direction)
            return

        # Handle user stopped speaking
        elif isinstance(frame, UserStoppedSpeakingFrame):
            await self._handle_speech_stop(frame, current_time, direction)
            return

        # Handle transcription frames
        elif isinstance(frame, TranscriptionFrame):
            await self._handle_transcription(frame, current_time)

        # Reset silence tracking on any non-speech frames
        elif not isinstance(frame, (UserStartedSpeakingFrame, UserStoppedSpeakingFrame)):
            self.last_silence_time = current_time

        # Pass frame downstream
        await self.push_frame(frame, direction)

    async def _handle_speech_start(
        self, frame: UserStartedSpeakingFrame, current_time: float, direction: FrameDirection
    ) -> None:
        """Handle user started speaking events."""

        # If in recovery mode, block speech starts temporarily
        if self.in_recovery_mode:
            logger.debug("🔇 Blocking speech start during noise recovery mode")
            return  # Drop the frame - don't pass it downstream

        # Check if this might be a false start (too soon after last stop)
        if self.last_speech_start and current_time - self.last_speech_start < 0.5:
            self.consecutive_short_utterances += 1
            logger.warning(
                f"⚠️ Potential false start detected - consecutive short: {self.consecutive_short_utterances}"
            )

            # If too many false starts, enter recovery mode
            if self.consecutive_short_utterances >= self.max_false_starts:
                await self._enter_recovery_mode()
                return  # Drop the frame

        # Track speech start
        self.last_speech_start = current_time
        self.is_user_speaking = True

        # Pass the frame downstream
        await self.push_frame(frame, direction)

    async def _handle_speech_stop(
        self, frame: UserStoppedSpeakingFrame, current_time: float, direction: FrameDirection
    ) -> None:
        """Handle user stopped speaking events."""

        if not self.is_user_speaking:
            # Got stop without start - possible noise artifact
            logger.warning("⚠️ Received speech stop without corresponding start")
            return  # Drop the frame

        # Check speech duration
        if self.last_speech_start:
            speech_duration = current_time - self.last_speech_start

            # Very short speech segments are likely noise
            if speech_duration < self.min_speech_duration:
                self.false_start_count += 1
                logger.warning(
                    f"⚠️ Short speech segment ({speech_duration:.2f}s) - "
                    f"false starts: {self.false_start_count}/{self.max_false_starts}"
                )

                # If too many false starts, enter recovery mode
                if self.false_start_count >= self.max_false_starts:
                    await self._enter_recovery_mode()
                    return  # Drop the frame
            else:
                # Valid speech detected - reset counters
                self.false_start_count = 0
                self.consecutive_short_utterances = 0

        self.is_user_speaking = False
        self.last_silence_time = current_time

        # Pass the frame downstream
        await self.push_frame(frame, direction)

    async def _handle_transcription(self, frame: TranscriptionFrame, current_time: float) -> None:
        """Handle transcription frames to validate speech activity."""

        # If we get actual transcription content, it's likely real speech
        if frame.text and frame.text.strip():
            logger.debug(f"✅ Valid transcription received: '{frame.text.strip()[:50]}...'")
            # Reset all noise counters
            self.false_start_count = 0
            self.consecutive_short_utterances = 0
        else:
            # Empty transcription might indicate noise
            logger.debug("⚠️ Empty transcription - possible noise artifact")

    async def _enter_recovery_mode(self) -> None:
        """Enter recovery mode to prevent noise loops."""

        if self.in_recovery_mode:
            return  # Already in recovery mode

        self.in_recovery_mode = True
        logger.warning(
            f"🚨 Entering noise recovery mode for {self.recovery_delay}s - "
            f"blocking speech detection temporarily"
        )

        # Send interruption to cancel any ongoing processing
        await self.push_frame(CancelFrame())

        # Cancel any existing recovery task
        if self.recovery_task and not self.recovery_task.done():
            self.recovery_task.cancel()

        # Schedule recovery
        self.recovery_task = asyncio.create_task(self._recovery_timer())

    async def _recovery_timer(self) -> None:
        """Recovery timer to exit recovery mode."""
        try:
            await asyncio.sleep(self.recovery_delay)
            await self._exit_recovery_mode()
        except asyncio.CancelledError:
            logger.debug("Recovery timer cancelled")

    async def _exit_recovery_mode(self) -> None:
        """Exit recovery mode and reset counters."""

        self.in_recovery_mode = False
        self.false_start_count = 0
        self.consecutive_short_utterances = 0
        self.is_user_speaking = False

        logger.info("✅ Exited noise recovery mode - speech detection re-enabled")

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.recovery_task and not self.recovery_task.done():
            self.recovery_task.cancel()
            try:
                await self.recovery_task
            except asyncio.CancelledError:
                pass

        logger.info("NoiseHandler processor cleaned up")
