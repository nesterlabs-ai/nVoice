"""
TranscriptLoggerProcessor — logs complete conversation turns to CloudWatch.

Placed in the pipeline AFTER TextFilterProcessor so bot text is already
clean (markdown stripped, function-call syntax removed) before logging.

User turn strategy
──────────────────
TranscriptionFrames from Deepgram arrive as the user speaks. We accumulate
them in a buffer and flush as ONE log entry when LLMFullResponseStartFrame
fires — i.e. the moment the LLM starts generating a reply. This guarantees
we log the complete, coherent user utterance(s) that triggered the response,
not streaming fragments.

Bot turn strategy
─────────────────
TextFrames between LLMFullResponseStartFrame and LLMFullResponseEndFrame are
the clean, speech-ready tokens. We accumulate them and flush as ONE log entry
when LLMFullResponseEndFrame fires.

Turn indexing
─────────────
Each (user flush + bot flush) pair shares a turn counter that increments
after the bot turn, giving a clean numbered conversation transcript:

    turn=1  [USER] "What services does Nesterlabs offer?"
    turn=1  [BOT]  "We work across product design, AI engineering..."
    turn=2  [USER] "Do you do mobile apps?"
    turn=2  [BOT]  "Yes, that falls under our HUMAN pillar..."
"""

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.services.cloudwatch_transcript import SessionTranscriptLogger


class TranscriptLoggerProcessor(FrameProcessor):
    """
    Non-destructive frame processor that logs conversation transcript.

    All frames pass through unchanged — this processor only observes.

    Args:
        session_id: Used as the CloudWatch log stream suffix (transcript/{id})
    """

    def __init__(self, session_id: str):
        super().__init__()
        self._cw = SessionTranscriptLogger(session_id)
        self._turn = 1

        # Buffers — accumulated between frame boundaries
        self._user_buf: list[str] = []   # TranscriptionFrames since last LLM response
        self._bot_buf: list[str] = []    # TextFrames in current LLM response
        self._bot_active = False          # True between LLMFullResponseStart/End

        logger.info(f"[TranscriptLogger] Initialized for session {session_id}")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # ALWAYS pass frame through first — never block the pipeline
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            return

        # ── User: accumulate STT output ───────────────────────────────────
        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                self._user_buf.append(text)
                logger.debug(f"[TranscriptLogger] STT fragment: \"{text[:60]}\"")

        # ── LLM starts → flush user buffer, start bot buffer ─────────────
        elif isinstance(frame, LLMFullResponseStartFrame):
            # Flush accumulated user speech as one complete turn
            if self._user_buf:
                full_user_text = " ".join(self._user_buf).strip()
                self._user_buf = []
                self._cw.log_turn("user", full_user_text, self._turn)

            # Start collecting bot response
            self._bot_buf = []
            self._bot_active = True

        # ── Bot: accumulate clean TTS-ready tokens ────────────────────────
        elif isinstance(frame, TextFrame) and self._bot_active:
            if frame.text:
                self._bot_buf.append(frame.text)

        # ── LLM ends → flush bot buffer ───────────────────────────────────
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._bot_active = False
            full_bot_text = "".join(self._bot_buf).strip()
            self._bot_buf = []

            if full_bot_text:
                self._cw.log_turn("bot", full_bot_text, self._turn)
                self._turn += 1   # Increment only after complete user+bot pair
