"""Text Filter Processor for cleaning LLM output before TTS.

This processor removes markdown formatting and other unwanted symbols
that TTS would read aloud (e.g., asterisks, hashtags, brackets).
"""

import re
from typing import Optional

from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, StartFrame, EndFrame, CancelFrame, LLMFullResponseStartFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Phrases that signal laughter — bot will inject [laughter] before the next word
_LAUGHTER_TRIGGERS = re.compile(
    r'\b('
    r'ha ha|haha|hehe|he he|lol|lmao|hah|heeh|'
    r'that\'?s funny|how funny|pretty funny|quite funny|rather funny|'
    r'that\'?s hilarious|how hilarious|absolutely hilarious|'
    r'that\'?s amusing|how amusing|'
    r'can\'?t help (but )?laugh|have to laugh|can\'?t stop laughing|'
    r'laugh(ing)? at that|burst(ing)? out laughing|'
    r'tickles? me|that cracks? me up|quite the joke|'
    r'joke(s|d)?|joking aside|in all seriousness.*just kidding'
    r')\b',
    re.IGNORECASE
)


class TextFilterProcessor(FrameProcessor):
    """Processor that filters markdown and unwanted symbols from text before TTS.

    This processor sits in the pipeline between LLM and TTS to clean up
    markdown formatting that would otherwise be read aloud as words like
    "star star" or "hashtag".

    When using Cartesia TTS, it also injects [laughter] tags automatically
    when the bot response contains humorous language.

    Attributes:
        enabled: Whether filtering is enabled
        inject_laughter: Whether to inject [laughter] tags for Cartesia TTS
    """

    # Opening markers that signal the start of a Llama-native function call block.
    # These appear when Groq/Llama emits a tool call as plain text instead of a
    # structured tool_calls field — e.g. <function=call_rag_system>{"question":"..."}
    _FN_OPEN_MARKERS = ["<function=", "<|python_tag|>"]
    _FN_CLOSE_MARKER = "</function>"

    def __init__(self, enabled: bool = True, inject_laughter: bool = False):
        """Initialize the Text Filter Processor.

        Args:
            enabled: Whether text filtering is enabled
            inject_laughter: Inject [laughter] tags when bot says something funny
                             (Cartesia sonic-3 only — other TTS will read it aloud)
        """
        super().__init__()
        self.enabled = enabled
        self.inject_laughter = inject_laughter
        self._started = False
        # Stateful function-call-leak tracking — persists across streaming chunks
        self._fn_active = False   # True while inside a <function=...> block
        self._fn_partial = ""     # Trailing text that might be the start of a tag
        logger.info(f"TextFilterProcessor initialized (enabled={enabled}, inject_laughter={inject_laughter})")

    def clean_text_for_speech(self, text: str) -> str:
        """Clean text by removing markdown and unwanted symbols.

        Removes:
        - Bold markers: **text** or __text__ → text
        - Italic markers: *text* or _text_ → text
        - Bullet points: * item or - item → item
        - Headers: ## Header → Header
        - Links: [text](url) → text
        - Code blocks: `code` → code
        - Strikethrough: ~~text~~ → text

        Args:
            text: Original text with markdown formatting

        Returns:
            Cleaned text suitable for TTS
        """
        if not text:
            return text

        original_text = text

        # Remove code blocks (```code```)
        text = re.sub(r'```[\s\S]*?```', '', text)

        # Remove inline code (`code`)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove links but keep link text: [text](url) → text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove bold: **text** or __text__ → text
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)

        # Remove italic: *text* or _text_ → text
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)

        # Remove strikethrough: ~~text~~ → text
        text = re.sub(r'~~([^~]+)~~', r'\1', text)

        # Remove headers: ## Header → Header
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove bullet points at start of lines: * item or - item → item
        text = re.sub(r'^\s*[\*\-]\s+', '', text, flags=re.MULTILINE)

        # Remove remaining standalone asterisks or underscores
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'_+', '', text)

        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Clean up multiple newlines
        text = re.sub(r'\n\s*\n', '\n', text)

        # Escape XML/SSML special characters to prevent TTS errors
        # The & character must be escaped FIRST (before other escapes that use &)
        text = text.replace('&', ' and ')  # Replace & with "and" for natural speech
        text = text.replace('<', ' ')  # Replace < with space (preserves word boundaries)
        text = text.replace('>', ' ')  # Replace > with space (preserves word boundaries)

        # Clean up multiple spaces (again, after bracket removal may have added extra spaces)
        text = re.sub(r'\s+', ' ', text)

        # Strip trailing whitespace only — preserve leading spaces for word separation
        # in streaming mode (LLM tokens arrive as " word" with leading space)
        text = text.rstrip()

        if text != original_text:
            logger.debug(f"Filtered text: '{original_text[:50]}...' → '{text[:50]}...'")

        # Inject [laughter] tag for Cartesia TTS when bot says something funny
        if self.inject_laughter and text:
            text = self._inject_laughter_tags(text)

        return text

    def _strip_function_calls(self, text: str) -> str:
        """Statefully strip Llama-native function call syntax from streaming chunks.

        Handles the case where <function=...>...</function> is split across
        multiple TextFrames during LLM streaming.  State (_fn_active, _fn_partial)
        persists between calls so partial tags at chunk boundaries are handled
        correctly.

        Args:
            text: Raw text chunk from LLM (may be a partial streaming token)

        Returns:
            Text with any function-call syntax removed; may be empty string.
        """
        # Prepend any buffered partial opening tag from the previous chunk
        text = self._fn_partial + text
        self._fn_partial = ""

        result: list[str] = []
        remaining = text

        while remaining:
            if self._fn_active:
                # Inside a function-call block — discard until we see </function>
                close_idx = remaining.find(self._FN_CLOSE_MARKER)
                if close_idx >= 0:
                    remaining = remaining[close_idx + len(self._FN_CLOSE_MARKER):]
                    self._fn_active = False
                    logger.debug("TextFilter: exited function-call block")
                else:
                    # Entire remaining chunk is still inside the block — discard
                    remaining = ""
            else:
                # Find the earliest opening marker in the remaining text
                trigger_pos = -1
                trigger_len = 0
                for marker in self._FN_OPEN_MARKERS:
                    idx = remaining.find(marker)
                    if idx >= 0 and (trigger_pos < 0 or idx < trigger_pos):
                        trigger_pos = idx
                        trigger_len = len(marker)

                if trigger_pos >= 0:
                    # Emit safe text before the marker, then enter blocked state
                    result.append(remaining[:trigger_pos])
                    remaining = remaining[trigger_pos + trigger_len:]
                    self._fn_active = True
                    logger.debug(
                        f"TextFilter: entered function-call block, "
                        f"dropped marker at pos {trigger_pos}"
                    )
                else:
                    # No complete opening marker found — check for a *partial* one
                    # at the very end of the chunk (e.g. chunk ends with "<func")
                    partial_start = self._find_partial_open_tag(remaining)
                    if partial_start >= 0:
                        result.append(remaining[:partial_start])
                        self._fn_partial = remaining[partial_start:]
                    else:
                        result.append(remaining)
                    remaining = ""

        return "".join(result)

    def _find_partial_open_tag(self, text: str) -> int:
        """Find the start index of a possible partial opening marker at end of text.

        Returns -1 if the tail of *text* cannot be the beginning of any known
        function-call opening marker; otherwise returns the start index of the
        potential partial match.

        We only consider partial matches at the very end of the chunk (up to the
        length of the longest marker minus one character).
        """
        max_scan = max(len(m) for m in self._FN_OPEN_MARKERS) - 1
        # Scan from the back, checking each possible suffix
        for start in range(len(text) - 1, max(len(text) - max_scan - 1, -1), -1):
            suffix = text[start:]
            for marker in self._FN_OPEN_MARKERS:
                if marker.startswith(suffix) and len(suffix) >= 1:
                    return start
        return -1

    def reset_stream_state(self) -> None:
        """Reset stateful streaming filters.  Call at the start of each LLM turn."""
        self._fn_active = False
        self._fn_partial = ""

    def _inject_laughter_tags(self, text: str) -> str:
        """Inject Cartesia [laughter] nonverbalism tag when humorous phrases are detected.

        Inserts [laughter] immediately after the triggering phrase so Cartesia
        produces a natural laugh at that point in the audio stream.

        Args:
            text: Cleaned TTS text

        Returns:
            Text with [laughter] tags injected where appropriate
        """
        def _insert_after_match(m: re.Match) -> str:
            return m.group(0) + " [laughter]"

        result = _LAUGHTER_TRIGGERS.sub(_insert_after_match, text)
        if result != text:
            logger.info(f"[LAUGHTER] Injected [laughter] tag: '{text[:60]}...' → '{result[:70]}...'")
        return result

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames and filter TextFrames.

        Args:
            frame: The frame to process
            direction: The direction of frame processing
        """
        # Handle lifecycle frames (StartFrame, EndFrame, etc.)
        await super().process_frame(frame, direction)

        if direction == FrameDirection.DOWNSTREAM:
            # Reset stateful function-call filter at the start of each LLM turn
            if isinstance(frame, LLMFullResponseStartFrame):
                self.reset_stream_state()
                await self.push_frame(frame, direction)

            # Filter text frames going downstream (to TTS)
            elif isinstance(frame, TextFrame):
                if self.enabled and frame.text:
                    # 1. Strip Llama-native function call syntax (stateful, cross-chunk)
                    stripped = self._strip_function_calls(frame.text)
                    # 2. Apply markdown / SSML cleanup
                    cleaned_text = self.clean_text_for_speech(stripped) if stripped else ""
                    if cleaned_text:
                        await self.push_frame(TextFrame(cleaned_text), direction)
                    # else: drop the frame entirely (it was pure function-call syntax)
                else:
                    await self.push_frame(frame, direction)
            else:
                await self.push_frame(frame, direction)
        else:
            # Pass all upstream frames through unchanged
            await self.push_frame(frame, direction)

    def enable(self) -> None:
        """Enable text filtering."""
        self.enabled = True
        logger.info("TextFilterProcessor enabled")

    def disable(self) -> None:
        """Disable text filtering."""
        self.enabled = False
        logger.info("TextFilterProcessor disabled")
