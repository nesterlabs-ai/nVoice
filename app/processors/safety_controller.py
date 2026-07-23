"""Runtime safety/off-topic controller — the loop-proof half of the guardrails.

Phase-0 benchmark finding: the model reliably calls a guardrail tool ONCE on
detection, but not every turn — so relying on it to re-call the tool leaves the
crisis loop intact. This controller moves the counting, escalation, and
disengagement into the runtime, driven by app.services.safety_policy.

It runs as two lightweight processor roles sharing one per-session state dict on
the ConversationManager (`_guardrail_state`):

  role="inject"  — placed BEFORE context_aggregator.user(). On each user turn in
                   safety mode it advances the round and injects the round's
                   directive as a tail system message, so the model's reply is
                   shaped even though the model did not re-call the tool.
  role="end"     — placed AFTER the LLM. When the injector has armed an end
                   (final_end round), it waits for the farewell line's TTS and
                   pushes EndFrame — the deterministic close.

The report_safety_concern tool handler (conversation.py) sets safety mode and
severity on first detection; everything after is decided here.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    EndFrame,
    Frame,
    LLMFullResponseEndFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.services.safety_policy import decide

SAFETY_MARK = "[SAFETY_DIRECTIVE]"


class SafetyController(FrameProcessor):
    def __init__(self, conversation_manager: Any, role: str):
        super().__init__()
        self.cm = conversation_manager
        self.role = role  # "inject" or "end"

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Base class must run first (StartFrame bookkeeping); otherwise every
        # downstream frame is silently dropped. Matches QuestionCardContextProcessor.
        await super().process_frame(frame, direction)

        state = getattr(self.cm, "_guardrail_state", None)
        if state is not None:
            if self.role == "inject" and isinstance(frame, TranscriptionFrame):
                self._advance_safety(state)
            elif self.role == "end" and isinstance(frame, LLMFullResponseEndFrame):
                if state.get("pending_end"):
                    state["pending_end"] = False
                    await self._force_end()

        await self.push_frame(frame, direction)

    def _advance_safety(self, state: dict) -> None:
        """On a user turn already in safety mode, drive the next round's directive."""
        if not state.get("safety_mode"):
            return
        state["round"] = state.get("round", 1) + 1
        action, directive = decide(state.get("severity", "moderate"), state["round"])

        context = getattr(self.cm, "context", None)
        messages = getattr(context, "messages", None)
        if messages is not None:
            # keep exactly one safety directive live, at the tail
            messages[:] = [
                m for m in messages
                if not (isinstance(m, dict) and isinstance(m.get("content"), str)
                        and m["content"].startswith(SAFETY_MARK))
            ]
            messages.append({
                "role": "system",
                "content": f"{SAFETY_MARK} round {state['round']} · severity {state['severity']}: {directive}",
            })

        logger.warning(
            f"🛟 Safety escalation: round={state['round']} severity={state['severity']} action={action}"
        )
        self._emit(state.get("severity", "moderate"), state["round"], action)

        if action == "final_end":
            state["pending_end"] = True  # role='end' will close after the farewell line

    async def _force_end(self) -> None:
        """Deterministically end the call after the model's final caring line."""
        logger.warning("🛑 Safety controller forcing session end (runtime, not model)")
        try:
            # The model already spoke the final line this turn; just close.
            await self.cm.trigger_session_end(self.push_frame, speak_farewell=False)
        except Exception as e:
            logger.error(f"Safety force-end failed, sending EndFrame directly: {e}")
            await asyncio.sleep(3.0)
            await self.push_frame(EndFrame(), FrameDirection.UPSTREAM)

    def _emit(self, severity: str, rnd: int, action: str) -> None:
        try:
            from app.services.cloudwatch_metrics import emit_safety_event
            asyncio.get_running_loop().create_task(
                asyncio.to_thread(emit_safety_event, severity, rnd, action)
            )
        except Exception as e:
            logger.debug(f"Safety metric emit skipped: {e}")
