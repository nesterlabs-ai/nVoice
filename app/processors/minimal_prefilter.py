"""
Minimal Pre-Filter for Transcription Noise Filtering.

A lightweight filter that drops ONLY absolute garbage before it reaches the LLM.
This is intentionally minimal - we let the LLM decide what's meaningful.

Design Philosophy:
- NO pattern matching for words like "hmm", "okay"
- NO rule-based classification of acknowledgments
- ONLY filter: low confidence, noise markers, too short, punctuation-only

Minimal pre-filter for transcription-level noise filtering.
"""

import re
from typing import Tuple

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class MinimalPreFilter(FrameProcessor):
    """
    Minimal pre-filter for transcriptions.

    Only drops frames that are clearly garbage:
    1. Confidence < threshold (STT is unsure)
    2. Length < 2 characters (single char is noise)
    3. Deepgram noise markers ([noise], [music], etc.)
    4. Punctuation-only text

    Everything else goes to LLM for intelligent handling.
    """

    # Deepgram noise markers - these are explicitly labeled as non-speech
    DEEPGRAM_NOISE_MARKERS = frozenset({
        "[noise]",
        "[music]",
        "[laughter]",
        "[inaudible]",
        "[silence]",
        "[blank_audio]",
        "[applause]",
        "[crosstalk]",
    })

    # System triggers that should ALWAYS pass through, even during greeting protection
    # These are internal triggers, not actual user speech
    SYSTEM_TRIGGER_PREFIXES = (
        "[SYSTEM_GREETING]",
        "[CONTINUE_NARRATION]",
        "[SYSTEM_",  # Catch-all for future system triggers
    )

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        min_length: int = 2,
        enabled: bool = True,
        greeting_protection: bool = True,
        **kwargs,
    ):
        """
        Initialize the minimal pre-filter.

        Args:
            confidence_threshold: Drop transcriptions below this confidence (0.0-1.0)
            min_length: Drop text shorter than this
            enabled: Whether filtering is active
            greeting_protection: Block transcriptions until first greeting completes
        """
        super().__init__(**kwargs)

        self.confidence_threshold = confidence_threshold
        self.min_length = min_length
        self.enabled = enabled

        # Greeting protection - drops ALL transcriptions until first greeting completes
        self._greeting_protection_active = greeting_protection

        # Stats for monitoring
        self._stats = {
            "total_frames": 0,
            "dropped_low_confidence": 0,
            "dropped_too_short": 0,
            "dropped_noise_marker": 0,
            "dropped_punctuation_only": 0,
            "dropped_greeting_protection": 0,
            "passed_through": 0,
        }

        logger.info(
            f"🔇 MinimalPreFilter initialized: "
            f"confidence_threshold={confidence_threshold}, "
            f"min_length={min_length}, "
            f"greeting_protection={greeting_protection}"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """
        Process frames and filter only absolute garbage.

        Args:
            frame: The frame to process
            direction: Direction of frame flow
        """
        await super().process_frame(frame, direction)

        # Only filter TranscriptionFrames going downstream
        if not isinstance(frame, TranscriptionFrame) or direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        # If filtering disabled, pass everything
        if not self.enabled:
            await self.push_frame(frame, direction)
            return

        self._stats["total_frames"] += 1

        # Get text and confidence
        text = frame.text.strip() if frame.text else ""
        confidence = self._get_confidence(frame)

        # ALWAYS allow system triggers through (greeting, narration, etc.)
        # These are internal triggers, not actual user speech
        if self._is_system_trigger(text):
            logger.info(f"🚀 [PREFILTER] System trigger ALLOWED through: '{text[:60]}...'")
            self._stats["passed_through"] += 1
            await self.push_frame(frame, direction)
            return

        # Greeting protection - drop transcriptions until disabled
        if self._greeting_protection_active:
            logger.debug(f"🛡️ [PREFILTER] Greeting protection active - dropping: '{text[:50]}...'")
            self._stats["dropped_greeting_protection"] += 1
            return  # Don't push frame

        # Check if should drop
        should_drop, reason = self._should_drop(text, confidence)

        if should_drop:
            logger.debug(
                f"🗑️ [PREFILTER] Dropped: '{text}' "
                f"(reason={reason}, confidence={confidence:.2f})"
            )
            self._stats[f"dropped_{reason}"] += 1
            # Don't push frame - it's dropped
            return

        # Pass through to LLM
        self._stats["passed_through"] += 1
        logger.debug(f"✅ [PREFILTER] Passed: '{text}' (confidence={confidence:.2f})")

        await self.push_frame(frame, direction)

    def _get_confidence(self, frame: TranscriptionFrame) -> float:
        """
        Extract confidence score from TranscriptionFrame.

        Args:
            frame: TranscriptionFrame with result attribute

        Returns:
            Confidence score 0.0-1.0, defaults to 1.0 if not available
        """
        try:
            # Try to get confidence from Deepgram result
            if hasattr(frame, "result") and frame.result:
                result = frame.result

                # Deepgram LiveResultResponse structure
                if hasattr(result, "channel"):
                    channel = result.channel
                    if hasattr(channel, "alternatives") and channel.alternatives:
                        return channel.alternatives[0].confidence

                # Alternative structure (dict-like)
                if isinstance(result, dict):
                    channel = result.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if alternatives:
                        return alternatives[0].get("confidence", 1.0)

            # No result attribute - assume high confidence
            return 1.0

        except (AttributeError, IndexError, KeyError, TypeError) as e:
            logger.debug(f"Could not extract confidence: {e}")
            return 1.0  # Default to high confidence

    def _should_drop(self, text: str, confidence: float) -> Tuple[bool, str]:
        """
        Determine if transcription should be dropped.

        ONLY drops absolute garbage - no pattern matching for words.

        Args:
            text: Transcription text
            confidence: Confidence score

        Returns:
            Tuple of (should_drop, reason)
        """
        # 1. Low confidence - STT is unsure
        if confidence < self.confidence_threshold:
            return True, "low_confidence"

        # 2. Too short - single char is almost always noise
        if len(text) < self.min_length:
            return True, "too_short"

        # 3. Deepgram noise markers - explicitly labeled as non-speech
        if text.lower() in self.DEEPGRAM_NOISE_MARKERS:
            return True, "noise_marker"

        # 4. Punctuation-only - no actual words
        if self._is_only_punctuation(text):
            return True, "punctuation_only"

        # Everything else goes to LLM
        return False, ""

    def _is_only_punctuation(self, text: str) -> bool:
        """
        Check if text contains only punctuation/whitespace.

        Args:
            text: Text to check

        Returns:
            True if text has no alphanumeric characters
        """
        # Remove all alphanumeric (including Unicode)
        # If nothing remains, it's punctuation-only
        alphanumeric = re.sub(r"[\w]", "", text, flags=re.UNICODE)
        return alphanumeric.strip() == text.strip()

    def _is_system_trigger(self, text: str) -> bool:
        """
        Check if text is a system trigger that should always pass through.

        System triggers are internal messages (like [SYSTEM_GREETING]) that
        should bypass greeting protection and all other filters.

        Args:
            text: Text to check

        Returns:
            True if text starts with a system trigger prefix
        """
        return text.startswith(self.SYSTEM_TRIGGER_PREFIXES)

    def get_stats(self) -> dict:
        """Get filter statistics."""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        for key in self._stats:
            self._stats[key] = 0

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable filtering."""
        self.enabled = enabled
        logger.info(f"MinimalPreFilter {'enabled' if enabled else 'disabled'}")

    def set_confidence_threshold(self, threshold: float) -> None:
        """Update confidence threshold."""
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"MinimalPreFilter confidence threshold set to {self.confidence_threshold}")

    def disable_greeting_protection(self) -> None:
        """
        Disable greeting protection after first greeting completes.

        This should be called after the initial greeting audio starts playing
        to allow user interruptions.
        """
        if self._greeting_protection_active:
            self._greeting_protection_active = False
            logger.info("🛡️ [PREFILTER] Greeting protection DISABLED - user can now interrupt")

    def enable_greeting_protection(self) -> None:
        """Re-enable greeting protection (for testing/reset)."""
        self._greeting_protection_active = True
        logger.info("🛡️ [PREFILTER] Greeting protection ENABLED")

    def is_greeting_protection_active(self) -> bool:
        """Check if greeting protection is currently active."""
        return self._greeting_protection_active
