"""
TranscriptLoggerProcessor — Pipecat frame processor that logs conversation
transcript to CloudWatch Logs.

Intercepts:
  - TranscriptionFrame  → user speech (final STT output)
  - TextFrame           → bot LLM response chunks (accumulated into full turns)

Does NOT affect the pipeline frame flow — all frames are passed through
via super().process_frame() as required by the Pipecat processor pattern.
"""

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    TextFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from app.services.cloudwatch_transcript import SessionTranscriptLogger


class TranscriptLoggerProcessor(FrameProcessor):
    """
    Logs user speech and bot responses to CloudWatch Logs.

    Place anywhere after the STT in the pipeline and before/after the LLM —
    it intercepts frames non-destructively.

    Args:
        session_id: Unique session identifier (used as CloudWatch stream name suffix)
        persona_id: Optional persona name to attach to log entries
    """

    def __init__(self, session_id: str, persona_id: str = ""):
        super().__init__()
        self._cw = SessionTranscriptLogger(session_id)
        self._persona_id = persona_id
        self._bot_text_buffer: list[str] = []  # Accumulate streaming bot tokens
        self._bot_speaking = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # ALWAYS call super first — handles all lifecycle frames
        await super().process_frame(frame, direction)

        # ── User utterance ────────────────────────────────────────────────
        if isinstance(frame, TranscriptionFrame) and frame.text and frame.text.strip():
            text = frame.text.strip()
            logger.debug(f"[TranscriptLogger] USER: {text[:80]}")
            extra = {}
            if self._persona_id:
                extra["persona_id"] = self._persona_id
            self._cw.log_turn("user", text, extra)

        # ── Bot response: accumulate tokens ──────────────────────────────
        elif isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            self._bot_text_buffer = []

        elif isinstance(frame, TextFrame) and self._bot_speaking:
            if frame.text:
                self._bot_text_buffer.append(frame.text)

        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            full_text = "".join(self._bot_text_buffer).strip()
            if full_text:
                logger.debug(f"[TranscriptLogger] BOT: {full_text[:80]}")
                extra = {}
                if self._persona_id:
                    extra["persona_id"] = self._persona_id
                self._cw.log_turn("bot", full_text, extra)
            self._bot_text_buffer = []
