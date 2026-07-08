"""Inject matched NesterAI question cards into the LLM context per user turn."""

from __future__ import annotations

from typing import Any

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.services.question_cards import NesterQuestionCardRouter


class QuestionCardContextProcessor(FrameProcessor):
    """Adds compact house-answer guidance before the LLM answers a user turn.

    This processor must run after final STT transcription is produced and before
    `context_aggregator.user()` consumes it. It removes the previous dynamic
    card and appends a fresh system note for the latest user question.
    """

    def __init__(self, conversation_manager: Any, enabled: bool = True):
        super().__init__()
        self.conversation_manager = conversation_manager
        self.enabled = enabled
        self.router = NesterQuestionCardRouter()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # MUST call super() first so the base FrameProcessor handles StartFrame
        # (sets __started = True and creates the internal process task). Without
        # this, push_frame silently drops every frame because _check_started
        # returns False, and the pipeline downstream of this processor stalls.
        await super().process_frame(frame, direction)

        if self.enabled and isinstance(frame, TranscriptionFrame):
            await self._inject_question_card(frame.text)

        await self.push_frame(frame, direction)

    async def _inject_question_card(self, text: str) -> None:
        prompt = self.router.build_prompt(text)
        context = getattr(self.conversation_manager, "context", None)
        messages = getattr(context, "messages", None)

        # Routing analytics (fire-and-forget, off the hot path): matched card ids,
        # or "unmatched" — the measured card-authoring backlog.
        self._emit_card_analytics(text)

        if not prompt or messages is None:
            return

        # Keep only one dynamic card active so the latest user question wins.
        messages[:] = [
            message for message in messages
            if not (
                isinstance(message, dict)
                and isinstance(message.get("content"), str)
                and message["content"].startswith(NesterQuestionCardRouter.MARKER)
            )
        ]
        messages.append({"role": "system", "content": prompt})

        matches = self.router.match_all(text)
        card_ids = ", ".join(match.card.id for match in matches) if matches else "unknown"
        logger.info(f"🧭 NesterAI question cards injected: {card_ids}")

    def _emit_card_analytics(self, text: str) -> None:
        """Emit matched/unmatched card ids to CloudWatch without blocking the pipeline."""
        try:
            import asyncio
            from app.services.cloudwatch_metrics import emit_question_card_match

            card_ids = [m.card.id for m in self.router.match_all(text)]
            if not card_ids:
                logger.info(f"🧭 No question card matched: '{text[:60]}'")
            # boto3 put_metric_data is a sync HTTP call — run it off-loop.
            asyncio.get_running_loop().create_task(
                asyncio.to_thread(emit_question_card_match, card_ids)
            )
        except Exception as e:
            logger.debug(f"Card analytics emit skipped: {e}")
