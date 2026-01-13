"""Audio Buffer Processor for collecting audio chunks for tone analysis.

This processor sits in the pipeline and buffers audio frames,
triggering acoustic analysis when enough audio is collected.
"""

import asyncio
import time
from typing import Optional, Callable, Awaitable
import numpy as np

from loguru import logger
from pipecat.frames.frames import Frame, AudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.services.audio_tone_analyzer import AudioToneAnalyzer, AudioFeatures


class AudioBufferProcessor(FrameProcessor):
    """Processor that buffers audio and triggers tone analysis.

    Collects audio chunks until enough data is available for analysis,
    then triggers the audio tone analyzer asynchronously.

    Attributes:
        analyzer: AudioToneAnalyzer instance
        buffer_duration: Seconds of audio to buffer before analysis
        sample_rate: Expected audio sample rate
        on_tone_detected: Callback when tone is detected
    """

    def __init__(
        self,
        analyzer: Optional[AudioToneAnalyzer] = None,
        buffer_duration: float = 1.5,
        sample_rate: int = 16000,
        on_tone_detected: Optional[Callable[[str, float, Optional[AudioFeatures]], Awaitable[None]]] = None,
        **kwargs
    ):
        """Initialize the Audio Buffer Processor.

        Args:
            analyzer: AudioToneAnalyzer instance (created if None)
            buffer_duration: Seconds of audio to buffer (default 1.5s)
            sample_rate: Expected sample rate (default 16kHz)
            on_tone_detected: Async callback(tone, confidence, features) when tone detected
            **kwargs: Additional args for FrameProcessor
        """
        super().__init__(**kwargs)

        self.analyzer = analyzer or AudioToneAnalyzer(sample_rate=sample_rate)
        self.buffer_duration = buffer_duration
        self.sample_rate = sample_rate
        self.on_tone_detected = on_tone_detected

        # Audio buffer state
        self._audio_buffer: list = []
        self._buffer_samples = 0
        self._target_samples = int(buffer_duration * sample_rate)

        # Analysis state
        self._last_analysis_time = 0.0
        self._analysis_cooldown = 2.0  # Minimum seconds between analyses
        self._analyzing = False

        # Latest results (accessible by other processors)
        self.latest_tone: str = "neutral"
        self.latest_confidence: float = 0.0
        self.latest_features: Optional[AudioFeatures] = None

        logger.info(
            f"AudioBufferProcessor initialized "
            f"(buffer={buffer_duration}s, target_samples={self._target_samples})"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames, buffering audio for analysis.

        Args:
            frame: The frame to process
            direction: Direction of frame flow
        """
        await super().process_frame(frame, direction)

        # Only process incoming audio frames
        if isinstance(frame, AudioRawFrame) and direction == FrameDirection.DOWNSTREAM:
            await self._buffer_audio(frame)

        # Always pass frame downstream
        await self.push_frame(frame, direction)

    async def _buffer_audio(self, frame: AudioRawFrame) -> None:
        """Buffer audio data and trigger analysis when ready.

        Args:
            frame: Audio frame containing raw audio data
        """
        try:
            # Convert bytes to numpy array
            audio_data = np.frombuffer(frame.audio, dtype=np.int16).astype(np.float32)
            # Normalize to -1 to 1 range
            audio_data = audio_data / 32768.0

            self._audio_buffer.append(audio_data)
            self._buffer_samples += len(audio_data)

            # Check if we have enough samples and cooldown passed
            current_time = time.time()
            if (
                self._buffer_samples >= self._target_samples
                and not self._analyzing
                and (current_time - self._last_analysis_time) >= self._analysis_cooldown
            ):
                # Trigger analysis
                await self._analyze_buffer()

        except Exception as e:
            logger.error(f"Error buffering audio: {e}")

    async def _analyze_buffer(self) -> None:
        """Analyze buffered audio and emit results."""
        if not self._audio_buffer:
            return

        self._analyzing = True

        try:
            # Concatenate all buffered audio
            full_audio = np.concatenate(self._audio_buffer)

            # Clear buffer
            self._audio_buffer = []
            self._buffer_samples = 0

            # Run analysis asynchronously
            tone, confidence, features = await self.analyzer.analyze_async(full_audio)

            # Store latest results
            self.latest_tone = tone
            self.latest_confidence = confidence
            self.latest_features = features
            self._last_analysis_time = time.time()

            logger.info(
                f"🎵 Audio tone analysis: {tone} (confidence={confidence:.2f})"
            )

            # Call callback if registered
            if self.on_tone_detected and confidence > 0:
                await self.on_tone_detected(tone, confidence, features)

        except Exception as e:
            logger.error(f"Audio analysis failed: {e}")
        finally:
            self._analyzing = False

    def reset_buffer(self) -> None:
        """Clear the audio buffer."""
        self._audio_buffer = []
        self._buffer_samples = 0
        logger.debug("Audio buffer reset")

    def get_stats(self) -> dict:
        """Get processor statistics.

        Returns:
            Dictionary with buffer and analysis state
        """
        return {
            "buffer_duration": self.buffer_duration,
            "buffer_samples": self._buffer_samples,
            "target_samples": self._target_samples,
            "buffer_fill_percent": (self._buffer_samples / self._target_samples * 100) if self._target_samples > 0 else 0,
            "latest_tone": self.latest_tone,
            "latest_confidence": self.latest_confidence,
            "analyzing": self._analyzing,
            "time_since_analysis": time.time() - self._last_analysis_time if self._last_analysis_time > 0 else None,
        }
