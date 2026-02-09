"""Transcription-Validated Interruption Filter Processor.

This processor implements smart interruption handling that distinguishes
real user speech from phantom noise/echo by using Deepgram's transcription
output as validation.

The problem being solved:
- Pipecat's VAD triggers InterruptionFrames on ANY audio activity (noise, echo)
- These phantom interruptions cancel in-flight operations (RAG calls, LLM)
- allow_interruptions=False doesn't fully prevent this in Pipecat 0.0.100

The solution:
- When bot IS speaking: allow InterruptionFrame immediately (proper barge-in)
- When bot is NOT speaking: HOLD InterruptionFrame and wait for Deepgram
  - If a valid transcription arrives (real speech) → release the held frame
  - If timeout with no valid transcription (phantom noise) → discard the frame

Pipeline placement: AFTER STT and MinimalPreFilter, BEFORE context_aggregator.
This way the filter sees only transcriptions that passed quality checks.
"""

import time
from typing import Optional, Tuple

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TranscriptionFrame,
)

# Try to import StartInterruptionFrame if available
try:
    from pipecat.frames.frames import StartInterruptionFrame
except ImportError:
    StartInterruptionFrame = None

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class InterruptionFilterProcessor(FrameProcessor):
    """Filters InterruptionFrames using Deepgram transcription validation.

    This processor sits in the pipeline and:
    1. Tracks whether the bot is currently speaking
    2. When bot IS speaking: allows InterruptionFrames (user barge-in)
    3. When bot is NOT speaking: holds InterruptionFrames and waits for
       a valid transcription to confirm it's real speech, not phantom noise

    This prevents:
    - Phantom VAD events (noise, echo) from cancelling RAG calls
    - User queries from being dropped when bot is silent

    While allowing:
    - Real user barge-in when bot is speaking
    - Real user interruptions during silence (confirmed by transcription)
    """

    def __init__(
        self,
        grace_period_after_bot_speech: float = 0.5,
        min_speaking_time_before_interrupt: float = 1.5,
        transcription_wait_timeout: float = 2.0,
        debug: bool = False,
    ):
        """Initialize the interruption filter.

        Args:
            grace_period_after_bot_speech: Seconds after bot stops speaking to
                still allow interruptions immediately (handles frame latency)
            min_speaking_time_before_interrupt: Minimum seconds bot must be speaking
                before allowing interruptions (prevents echo from interrupting)
            transcription_wait_timeout: Seconds to wait for transcription validation
                before discarding a held InterruptionFrame (phantom noise timeout)
            debug: Enable debug logging
        """
        super().__init__()

        self._bot_speaking = False
        self._bot_started_speaking_time: Optional[float] = None
        self._bot_stopped_speaking_time: Optional[float] = None
        self._grace_period = grace_period_after_bot_speech
        self._min_speaking_time = min_speaking_time_before_interrupt
        self._transcription_wait_timeout = transcription_wait_timeout
        self._debug = debug

        # Held interruption frame (waiting for transcription validation)
        self._held_interruption: Optional[Tuple[Frame, FrameDirection]] = None
        self._held_at: Optional[float] = None

        # Stats
        self._blocked_count = 0
        self._allowed_count = 0
        self._held_released_count = 0
        self._held_discarded_count = 0

        logger.info(
            f"🛡️ InterruptionFilter initialized (transcription-validated) - "
            f"grace_period: {grace_period_after_bot_speech}s, "
            f"min_speaking_time: {min_speaking_time_before_interrupt}s, "
            f"transcription_wait_timeout: {transcription_wait_timeout}s"
        )

    def _is_in_grace_period(self) -> bool:
        """Check if we're still in the grace period after bot stopped speaking."""
        if self._bot_stopped_speaking_time is None:
            return False
        elapsed = time.time() - self._bot_stopped_speaking_time
        return elapsed < self._grace_period

    def _has_spoken_enough(self) -> bool:
        """Check if the bot has been speaking long enough to allow interruptions."""
        if self._bot_started_speaking_time is None:
            return False
        elapsed = time.time() - self._bot_started_speaking_time
        return elapsed >= self._min_speaking_time

    def _should_allow_immediately(self) -> bool:
        """Determine if an InterruptionFrame should be allowed through immediately.

        Returns:
            True if the interruption should be allowed (bot is speaking long enough
            or we're in the grace period after bot stopped)
        """
        if self._bot_speaking:
            if self._has_spoken_enough():
                return True
            else:
                if self._debug:
                    elapsed = time.time() - (self._bot_started_speaking_time or time.time())
                    logger.debug(
                        f"🛡️ Bot only speaking for {elapsed:.2f}s, "
                        f"need {self._min_speaking_time}s before allowing interruption"
                    )
                return False

        if self._is_in_grace_period():
            return True

        return False

    async def _release_held_interruption(self):
        """Release a held InterruptionFrame (transcription confirmed it's real speech)."""
        if self._held_interruption:
            frame, direction = self._held_interruption
            self._held_interruption = None
            self._held_at = None
            self._held_released_count += 1
            logger.info(
                f"🔓 Held InterruptionFrame RELEASED (real speech confirmed) - "
                f"released: {self._held_released_count}, discarded: {self._held_discarded_count}"
            )
            await self.push_frame(frame, direction)

    def _discard_held_interruption(self):
        """Discard a held InterruptionFrame (phantom noise, no valid transcription)."""
        if self._held_interruption:
            self._held_interruption = None
            self._held_at = None
            self._held_discarded_count += 1
            logger.info(
                f"🛡️ Held InterruptionFrame DISCARDED (phantom noise — no valid transcription) - "
                f"released: {self._held_released_count}, discarded: {self._held_discarded_count}"
            )

    def _check_held_timeout(self):
        """Check if a held InterruptionFrame has timed out."""
        if self._held_interruption and self._held_at:
            if time.time() - self._held_at > self._transcription_wait_timeout:
                self._discard_held_interruption()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames with transcription-validated interruption filtering.

        Args:
            frame: The frame to process
            direction: Direction of frame flow
        """
        await super().process_frame(frame, direction)

        # --- Track bot speaking state ---

        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            self._bot_started_speaking_time = time.time()
            self._bot_stopped_speaking_time = None
            if self._debug:
                logger.debug(
                    f"🔊 Bot started speaking - "
                    f"interruptions allowed after {self._min_speaking_time}s"
                )
            # If holding an interruption and bot starts speaking, release it
            # (the interruption was likely the trigger for the bot's response)
            await self._release_held_interruption()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            self._bot_started_speaking_time = None
            self._bot_stopped_speaking_time = time.time()
            if self._debug:
                logger.debug(
                    f"🔇 Bot stopped speaking - "
                    f"grace period for {self._grace_period}s"
                )
            await self.push_frame(frame, direction)
            return

        # --- Track user speaking state (for logging) ---

        if isinstance(frame, UserStartedSpeakingFrame):
            if self._debug:
                logger.debug(
                    f"👤 User started speaking - "
                    f"bot_speaking: {self._bot_speaking}, "
                    f"in_grace: {self._is_in_grace_period()}, "
                    f"held: {self._held_interruption is not None}"
                )
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStoppedSpeakingFrame):
            if self._debug:
                logger.debug("👤 User stopped speaking")
            await self.push_frame(frame, direction)
            return

        # --- Filter InterruptionFrames ---

        interruption_types = (InterruptionFrame,)
        if StartInterruptionFrame is not None:
            interruption_types = (InterruptionFrame, StartInterruptionFrame)

        if isinstance(frame, interruption_types):
            frame_type = type(frame).__name__

            if self._should_allow_immediately():
                # Bot is speaking (long enough) or in grace period → allow barge-in
                self._allowed_count += 1
                logger.info(
                    f"✅ {frame_type} ALLOWED (barge-in) - "
                    f"bot_speaking: {self._bot_speaking}, "
                    f"allowed: {self._allowed_count}, blocked: {self._blocked_count}"
                )
                await self.push_frame(frame, direction)
            else:
                # Bot is NOT speaking (or just started) → hold and wait for transcription
                self._blocked_count += 1
                self._held_interruption = (frame, direction)
                self._held_at = time.time()
                logger.info(
                    f"⏳ {frame_type} HELD (waiting for transcription validation) - "
                    f"timeout: {self._transcription_wait_timeout}s, "
                    f"allowed: {self._allowed_count}, blocked: {self._blocked_count}"
                )
            return

        # --- Transcription validation for held interruptions ---

        if isinstance(frame, TranscriptionFrame):
            if self._held_interruption:
                text = frame.text.strip() if frame.text else ""
                if text:
                    # A valid transcription arrived → real user speech
                    logger.info(
                        f"✅ Transcription '{text[:40]}' validates held InterruptionFrame → releasing"
                    )
                    await self._release_held_interruption()
            # Always pass transcriptions through
            await self.push_frame(frame, direction)
            return

        # --- Check for held frame timeout on every other frame ---
        self._check_held_timeout()

        # Pass all other frames through unchanged
        await self.push_frame(frame, direction)

    def get_stats(self) -> dict:
        """Get statistics about interruption filtering."""
        return {
            "allowed_immediately": self._allowed_count,
            "held_total": self._blocked_count,
            "held_released": self._held_released_count,
            "held_discarded": self._held_discarded_count,
            "bot_speaking": self._bot_speaking,
            "in_grace_period": self._is_in_grace_period(),
            "currently_holding": self._held_interruption is not None,
        }
