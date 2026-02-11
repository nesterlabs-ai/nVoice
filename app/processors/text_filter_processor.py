"""Text Filter Processor for cleaning LLM output before TTS.

This processor removes markdown formatting and other unwanted symbols
that TTS would read aloud (e.g., asterisks, hashtags, brackets).
It also filters out raw function call syntax that Groq/Llama sometimes
outputs as text instead of proper tool calls.
"""

import re
from typing import Optional

from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame, StartFrame, EndFrame, CancelFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class TextFilterProcessor(FrameProcessor):
    """Processor that filters markdown and unwanted symbols from text before TTS.

    This processor sits in the pipeline between LLM and TTS to clean up
    markdown formatting that would otherwise be read aloud as words like
    "star star" or "hashtag".

    It also handles function call syntax that arrives across multiple streaming
    chunks by tracking state (dropping all text between <function= and </function>).

    Attributes:
        enabled: Whether filtering is enabled
    """

    def __init__(self, enabled: bool = True):
        """Initialize the Text Filter Processor.

        Args:
            enabled: Whether text filtering is enabled
        """
        super().__init__()
        self.enabled = enabled
        self._started = False
        # State for tracking function call syntax across streaming chunks
        self._in_function_call = False
        self._pending_text = ""  # Buffer for text that might be start of <function=
        logger.info(f"TextFilterProcessor initialized (enabled={enabled})")

    def clean_text_for_speech(self, text: str) -> str:
        """Clean text by removing markdown and unwanted symbols.

        Removes:
        - Bold markers: **text** or __text__ -> text
        - Italic markers: *text* or _text_ -> text
        - Bullet points: * item or - item -> item
        - Headers: ## Header -> Header
        - Links: [text](url) -> text
        - Code blocks: `code` -> code
        - Strikethrough: ~~text~~ -> text
        - Function call syntax: <function=...>...</function>

        Args:
            text: Original text with markdown formatting

        Returns:
            Cleaned text suitable for TTS
        """
        if not text:
            return text

        original_text = text

        # Remove function call syntax (handles complete tags in single chunk)
        text = re.sub(r'<function=[^>]*>.*?</function>', '', text, flags=re.DOTALL)
        text = re.sub(r'<function=[^>]*>.*', '', text, flags=re.DOTALL)

        # Remove code blocks (```code```)
        text = re.sub(r'```[\s\S]*?```', '', text)

        # Remove inline code (`code`)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove links but keep link text: [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove bold: **text** or __text__ -> text
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)

        # Remove italic: *text* or _text_ -> text
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)

        # Remove strikethrough: ~~text~~ -> text
        text = re.sub(r'~~([^~]+)~~', r'\1', text)

        # Remove headers: ## Header -> Header
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove bullet points at start of lines: * item or - item -> item
        text = re.sub(r'^\s*[\*\-]\s+', '', text, flags=re.MULTILINE)

        # Remove remaining standalone asterisks
        text = re.sub(r'\*+', '', text)

        # Remove standalone underscores but preserve word boundaries
        # Only remove underscores that are not between word characters
        text = re.sub(r'(?<!\w)_+(?!\w)', '', text)

        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Clean up multiple newlines
        text = re.sub(r'\n\s*\n', '\n', text)

        # Escape XML/SSML special characters to prevent TTS errors
        text = text.replace('&', ' and ')
        text = text.replace('<', ' ')
        text = text.replace('>', ' ')

        # Clean up multiple spaces (again, after bracket removal)
        text = re.sub(r'\s+', ' ', text)

        # Strip leading/trailing whitespace
        text = text.strip()

        if text != original_text:
            logger.debug(f"Filtered text: '{original_text[:50]}...' -> '{text[:50]}...'")

        return text

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames and filter TextFrames.

        Handles function call syntax that arrives across multiple streaming chunks
        by maintaining state. When <function= is detected, all subsequent text is
        dropped until </function> is seen (or response ends).

        Args:
            frame: The frame to process
            direction: The direction of frame processing
        """
        # Handle lifecycle frames
        await super().process_frame(frame, direction)

        # Reset function call tracking state on new LLM response
        if isinstance(frame, LLMFullResponseStartFrame):
            self._in_function_call = False
            self._pending_text = ""
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            # Flush any pending text that wasn't a function call
            if self._pending_text and not self._in_function_call:
                cleaned = self.clean_text_for_speech(self._pending_text)
                if cleaned:
                    await self.push_frame(TextFrame(cleaned), direction)
            self._in_function_call = False
            self._pending_text = ""
            await self.push_frame(frame, direction)
            return

        # Only filter text frames going downstream (to TTS)
        if isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
            if self.enabled and frame.text:
                text = frame.text

                # If we're already inside a function call, drop everything
                if self._in_function_call:
                    # Check if function call ends in this chunk
                    if '</function>' in text:
                        self._in_function_call = False
                        # Extract any text after </function>
                        after = text.split('</function>', 1)[1]
                        if after.strip():
                            cleaned = self.clean_text_for_speech(after)
                            if cleaned:
                                await self.push_frame(TextFrame(cleaned), direction)
                    else:
                        logger.debug(f"Dropping function call chunk: '{text[:40]}...'")
                    return

                # Check if this chunk starts a function call
                if '<function=' in text or '<function' in text:
                    self._in_function_call = True
                    # Extract text before the function call tag
                    before = re.split(r'<function', text, 1)[0]
                    if before.strip():
                        cleaned = self.clean_text_for_speech(before)
                        if cleaned:
                            await self.push_frame(TextFrame(cleaned), direction)
                    # Check if function call also ends in this chunk
                    if '</function>' in text:
                        self._in_function_call = False
                        after = text.split('</function>', 1)[1]
                        if after.strip():
                            cleaned = self.clean_text_for_speech(after)
                            if cleaned:
                                await self.push_frame(TextFrame(cleaned), direction)
                    return

                # Check for partial "<" that could be start of <function=
                # Buffer it to check with next chunk
                if text.endswith('<') or text.endswith('<f') or text.endswith('<fu'):
                    self._pending_text += text
                    return

                # Flush any pending text + current text
                if self._pending_text:
                    text = self._pending_text + text
                    self._pending_text = ""

                # Normal text - clean and pass through
                cleaned_text = self.clean_text_for_speech(text)
                if cleaned_text:
                    await self.push_frame(TextFrame(cleaned_text), direction)
            else:
                await self.push_frame(frame, direction)
        else:
            # Pass all other frames through unchanged
            await self.push_frame(frame, direction)

    def enable(self) -> None:
        """Enable text filtering."""
        self.enabled = True
        logger.info("TextFilterProcessor enabled")

    def disable(self) -> None:
        """Disable text filtering."""
        self.enabled = False
        logger.info("TextFilterProcessor disabled")
