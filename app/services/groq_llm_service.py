"""Groq-compatible LLM service with consecutive user message merging.

Groq's streaming tool-calling is more sensitive than OpenAI's to consecutive
user messages in the context.  When the STT splits a single utterance across
multiple frames (e.g. "The thing is I want to build" + "an agent for my
company"), pipecat's context aggregator appends each as a separate user
message.  Sending those back-to-back to Groq occasionally triggers:

    "Failed to call a function. Please adjust your prompt."

This subclass overrides build_chat_completion_params to merge any consecutive
user messages into a single message before the request leaves the client.  The
merge is purely cosmetic — semantically identical to what the user said —
and only affects the outbound API payload, not the stored context.
"""

import re
from typing import Any, Dict, List, Optional

from loguru import logger
from openai import APIError
from pipecat.services.openai.llm import OpenAILLMService

from pipecat.adapters.services.open_ai_adapter import OpenAILLMInvocationParams

# Functions registered on the LLM service (must stay in sync with conversation.py)
_KNOWN_FUNCTIONS = frozenset({
    "call_rag_system",
    "end_conversation",
    "start_appointment_booking",
    "submit_appointment",
})

_MALFORMED_TOOL_RE = re.compile(
    r"attempted to call tool '([^']+)' which was not in request\.tools"
)


def _extract_real_function(error_str: str) -> Optional[str]:
    """Return the real function name when Llama encodes args inside the tool name.

    Llama sometimes generates a tool call with the function name field set to
    something like ``call_rag_system={"question": "..."}`` instead of separating
    the name and arguments.  Groq rejects this because that composite string is
    not a registered tool name.

    If the malformed name starts with a known function name we return that name
    so the caller can retry with tool_choice forced to the correct function.
    """
    m = _MALFORMED_TOOL_RE.search(error_str)
    if not m:
        return None
    malformed = m.group(1)
    for fn in _KNOWN_FUNCTIONS:
        # Llama uses several separators between the name and the args:
        #   call_rag_system={"question": "..."}   (equals sign)
        #   call_rag_system {"question": "..."}   (space)
        #   call_rag_system{"question": "..."}    (no separator)
        if (
            malformed.startswith(fn + "=")
            or malformed.startswith(fn + " ")
            or malformed.startswith(fn + "{")
        ):
            return fn
    return None


def _merge_consecutive_user_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge consecutive user messages into single messages.

    Only merges messages whose content is a plain string.  Messages with
    structured content (e.g. image payloads represented as lists) are left
    untouched.

    Args:
        messages: List of OpenAI-format message dicts.

    Returns:
        New list with consecutive user messages merged.
    """
    if not messages:
        return messages

    merged: List[Dict[str, Any]] = [messages[0]]

    for msg in messages[1:]:
        prev = merged[-1]
        # Merge only when both are plain-string user messages
        if (
            prev.get("role") == "user"
            and msg.get("role") == "user"
            and isinstance(prev.get("content"), str)
            and isinstance(msg.get("content"), str)
        ):
            prev["content"] = prev["content"].rstrip() + " " + msg["content"].lstrip()
            logger.debug(
                f"Merged consecutive user messages → "
                f"'{prev['content'][:80]}...'"
            )
        else:
            merged.append(msg)

    return merged


class GroqLLMService(OpenAILLMService):
    """OpenAI-compatible LLM service tuned for Groq.

    Identical to OpenAILLMService except that consecutive user messages are
    merged before each API call, preventing the intermittent
    "Failed to call a function" streaming error from Groq.
    """

    def __init__(self, *, model: str = "llama-3.3-70b-versatile", **kwargs):
        # Groq base URL is mandatory; allow caller to override
        kwargs.setdefault("base_url", "https://api.groq.com/openai/v1")
        super().__init__(model=model, **kwargs)

    def build_chat_completion_params(self, params_from_context: OpenAILLMInvocationParams) -> dict:
        """Build params, merging consecutive user messages first."""
        params = super().build_chat_completion_params(params_from_context)

        # Llama models on Groq don't reliably handle parallel tool calls
        if params.get("tools"):
            params["parallel_tool_calls"] = False

        # params["messages"] comes from the context; merge in place
        if "messages" in params:
            original_count = len(params["messages"])
            params["messages"] = _merge_consecutive_user_messages(params["messages"])
            merged_count = len(params["messages"])
            if merged_count < original_count:
                logger.info(
                    f"GroqLLMService: merged {original_count - merged_count} "
                    f"consecutive user message(s) "
                    f"({original_count} → {merged_count} messages)"
                )

        return params

    async def _process_context(self, context):
        """Process context with smart retry on Groq/Llama function-call errors.

        Two error classes are handled:

        1. **Malformed tool name** — Llama encodes args inside the function name
           (e.g. ``call_rag_system={"question": "..."}``).  Groq rejects this
           because the composite string isn't a registered tool.  We detect
           which real function was intended and retry with tool_choice forced to
           that function so the model generates a correctly-structured call.

        2. **Generic failure / null tool** — "Failed to call a function", null
           tool name, etc.  We retry with tool_choice="none" so the model falls
           back to a plain text response rather than crashing the session.
        """
        try:
            await super()._process_context(context)
        except (APIError, Exception) as e:
            error_str = str(e)
            retryable_errors = [
                "Failed to call a function",
                "attempted to call tool 'null'",
                "which was not in request.tools",
                "tool call validation failed",
            ]
            if not any(err in error_str for err in retryable_errors):
                raise  # Re-raise unrelated errors

            original_tool_choice = context.tool_choice

            # ── Strategy 1: malformed tool name ──────────────────────────────
            # Llama put args inside the function name field.  We know which
            # function was intended, so force it to retry that call correctly.
            real_fn = _extract_real_function(error_str)
            if real_fn:
                logger.warning(
                    f"GroqLLMService: Malformed tool name detected "
                    f"(intended '{real_fn}') — retrying with forced tool_choice "
                    f"(error: {error_str[:120]})"
                )
                context.set_tool_choice({"type": "function", "function": {"name": real_fn}})
                try:
                    await super()._process_context(context)
                    return
                except Exception as retry_err:
                    logger.warning(
                        f"GroqLLMService: Forced tool_choice retry also failed "
                        f"({retry_err!s:.80}) — falling back to tool_choice=none"
                    )
                finally:
                    context.set_tool_choice(original_tool_choice)

            # ── Strategy 2: generic fallback — plain text response ────────────
            logger.warning(
                f"GroqLLMService: Groq/Llama function-call error — retrying "
                f"with tool_choice=none (error: {error_str[:100]})"
            )
            context.set_tool_choice("none")
            try:
                await super()._process_context(context)
            finally:
                context.set_tool_choice(original_tool_choice)
