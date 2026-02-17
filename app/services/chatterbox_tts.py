"""
Chatterbox TTS Service using Resemble AI Cloud API.

This module provides text-to-speech functionality using Resemble AI's
Chatterbox model with emotion control via exaggeration and cfg_weight parameters.

Compatible with Pipecat pipeline framework.
"""

import time
import aiohttp
from typing import Optional, Dict, Any, AsyncGenerator

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    ErrorFrame,
)
from pipecat.services.tts_service import TTSService


# Emotion to Chatterbox parameter mapping
# Exaggeration: 0.25-2.0 (higher = more emotional)
# CFG Weight: 0.0-1.0 (lower = faster, more expressive)
EMOTION_TO_PARAMS = {
    "neutral": {"exaggeration": 0.4, "cfg_weight": 0.5},
    "sad": {"exaggeration": 0.6, "cfg_weight": 0.4},        # Softer, empathetic
    "frustrated": {"exaggeration": 0.5, "cfg_weight": 0.5}, # Calm, patient
    "excited": {"exaggeration": 0.9, "cfg_weight": 0.3},    # Energetic, fast
    "happy": {"exaggeration": 0.8, "cfg_weight": 0.35},     # Warm, upbeat
    "angry": {"exaggeration": 0.7, "cfg_weight": 0.4},      # Controlled intensity
    "fear": {"exaggeration": 0.5, "cfg_weight": 0.45},      # Gentle, calming
    "content": {"exaggeration": 0.4, "cfg_weight": 0.5},    # Relaxed, neutral
}

# Voice name to emotion mapping (for compatibility with existing voice switching)
VOICE_TO_EMOTION = {
    "aura-2-athena-en": "neutral",
    "aura-2-vesta-en": "sad",
    "aura-2-neptune-en": "frustrated",
    "aura-2-thalia-en": "excited",
    "aura-2-luna-en": "fear",
    "neutral": "neutral",
    "sad": "sad",
    "frustrated": "frustrated",
    "excited": "excited",
    "happy": "happy",
    "angry": "angry",
}

DEFAULT_PARAMS = {"exaggeration": 0.5, "cfg_weight": 0.5}


class ChatterboxTTSService(TTSService):
    """Pipecat-compatible Chatterbox TTS service using Resemble AI Cloud API.

    This service provides emotion-aware text-to-speech using Chatterbox's
    exaggeration and cfg_weight parameters to control emotional expression.
    """

    def __init__(
        self,
        *,
        api_key: str,
        voice_uuid: str,
        synthesis_url: str = "https://f.cluster.resemble.ai/synthesize",
        stream_url: str = "https://f.cluster.resemble.ai/stream",
        sample_rate: int = 24000,
        voice: str = "neutral",
        **kwargs,
    ):
        """Initialize the Chatterbox TTS service.

        Args:
            api_key: Resemble AI API key
            voice_uuid: Resemble AI voice UUID (required for API authentication)
            synthesis_url: URL for synthesis endpoint
            stream_url: URL for streaming endpoint
            sample_rate: Audio sample rate (default 24000)
            voice: Initial voice/emotion (default "neutral")
            **kwargs: Additional arguments for parent class
        """
        super().__init__(sample_rate=sample_rate, **kwargs)

        self._api_key = api_key
        self._voice_uuid = voice_uuid
        self._synthesis_url = synthesis_url
        self._stream_url = stream_url
        self._sample_rate = sample_rate
        self._voice_id = voice
        self._current_emotion = VOICE_TO_EMOTION.get(voice, "neutral")
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(
            f"ChatterboxTTSService initialized "
            f"(synthesis: {synthesis_url}, voice_uuid: {voice_uuid}, emotion: {self._current_emotion})"
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # Resemble AI uses Bearer token authentication
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    def set_voice(self, voice: str) -> None:
        """Set voice/emotion for TTS output.

        Maps voice names to emotions for Chatterbox.

        Args:
            voice: Voice name or emotion identifier
        """
        self._voice_id = voice
        self._current_emotion = VOICE_TO_EMOTION.get(voice, "neutral")
        params = EMOTION_TO_PARAMS.get(self._current_emotion, DEFAULT_PARAMS)
        logger.info(
            f"Chatterbox voice set: {voice} -> emotion={self._current_emotion} "
            f"(exaggeration={params['exaggeration']}, cfg_weight={params['cfg_weight']})"
        )

    def set_emotion(self, emotion: str) -> None:
        """Directly set emotion for TTS.

        Args:
            emotion: Emotion name (neutral, sad, frustrated, excited, etc.)
        """
        if emotion in EMOTION_TO_PARAMS:
            self._current_emotion = emotion
            params = EMOTION_TO_PARAMS[emotion]
            logger.info(
                f"Chatterbox emotion set: {emotion} "
                f"(exaggeration={params['exaggeration']}, cfg_weight={params['cfg_weight']})"
            )
        else:
            logger.warning(f"Unknown emotion '{emotion}', using neutral")
            self._current_emotion = "neutral"

    def get_emotion_params(self) -> Dict[str, float]:
        """Get Chatterbox parameters for current emotion.

        Returns:
            Dict with exaggeration and cfg_weight values
        """
        return EMOTION_TO_PARAMS.get(self._current_emotion, DEFAULT_PARAMS)

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        """Run text-to-speech synthesis with emotion control.

        This is the main method called by Pipecat pipeline.

        Args:
            text: Text to synthesize

        Yields:
            Pipecat frames (TTSStartedFrame, TTSAudioRawFrame, TTSStoppedFrame)
        """
        params = self.get_emotion_params()
        logger.info(
            f"🔊 Chatterbox TTS request: text='{text[:80]}{'...' if len(text) > 80 else ''}' "
            f"emotion={self._current_emotion} exaggeration={params['exaggeration']} "
            f"cfg_weight={params['cfg_weight']}"
        )

        try:
            # Signal TTS started
            yield TTSStartedFrame()

            payload = {
                "voice_uuid": self._voice_uuid,
                "data": text,
                "exaggeration": params["exaggeration"],
                "cfg_weight": params["cfg_weight"],
                "sample_rate": self._sample_rate,
                "precision": "PCM_16",
            }

            # Log full request details for debugging
            logger.info(
                f"🔊 Chatterbox API call: url={self._stream_url} "
                f"voice_uuid={self._voice_uuid[:8]}...{self._voice_uuid[-4:]} "
                f"sample_rate={self._sample_rate} precision=PCM_16"
            )

            session = await self._get_session()
            start_time = time.time()

            # Try streaming endpoint first (lower latency)
            async with session.post(self._stream_url, json=payload) as response:
                latency_ms = (time.time() - start_time) * 1000

                # If streaming fails with 500, try non-streaming synthesis endpoint
                if response.status == 500:
                    error_text = await response.text()
                    logger.warning(
                        f"🔊 Chatterbox stream endpoint failed (500), trying synthesis endpoint... "
                        f"error={error_text[:100]}"
                    )

                    # Retry with non-streaming synthesis endpoint
                    start_time_retry = time.time()
                    async with session.post(self._synthesis_url, json=payload) as retry_response:
                        latency_ms = (time.time() - start_time_retry) * 1000
                        response = retry_response  # Use retry response for the rest of the code

                if response.status == 200:
                    logger.info(f"🔊 Chatterbox TTS: streaming started (ttfb={latency_ms:.0f}ms)")

                    # Stream audio chunks as they arrive (word-by-word playback)
                    header_stripped = False
                    header_buffer = b''
                    chunks_sent = 0
                    total_bytes = 0
                    first_chunk_time = None

                    async for chunk in response.content.iter_chunked(4096):
                        if not chunk:
                            continue

                        if first_chunk_time is None:
                            first_chunk_time = time.time()

                        total_bytes += len(chunk)

                        # Strip WAV header from first chunk(s) only
                        if not header_stripped:
                            header_buffer += chunk

                            # Check if we have enough data to detect and strip WAV header
                            if len(header_buffer) >= 44:
                                if header_buffer[:4] == b'RIFF':
                                    # Find 'data' chunk marker
                                    data_index = header_buffer.find(b'data')
                                    if data_index != -1:
                                        # Skip 'data' + 4 bytes for chunk size
                                        header_size = data_index + 8
                                        chunk = header_buffer[header_size:]
                                        header_buffer = b''
                                        header_stripped = True
                                        logger.debug(f"🔊 Stripped WAV header ({header_size} bytes)")
                                    else:
                                        # Haven't found 'data' marker yet, keep buffering
                                        continue
                                else:
                                    # No WAV header (already PCM)
                                    chunk = header_buffer
                                    header_buffer = b''
                                    header_stripped = True

                        # Yield audio chunk immediately for streaming playback
                        if chunk:
                            yield TTSAudioRawFrame(
                                audio=chunk,
                                sample_rate=self._sample_rate,
                                num_channels=1,
                            )
                            chunks_sent += 1

                    total_ms = (time.time() - start_time) * 1000
                    audio_duration_secs = total_bytes / (self._sample_rate * 2)
                    logger.info(
                        f"🔊 Chatterbox TTS complete: total={total_ms:.0f}ms "
                        f"audio={total_bytes} bytes ({audio_duration_secs:.1f}s) "
                        f"chunks={chunks_sent}"
                    )
                else:
                    error_text = await response.text()
                    logger.error(
                        f"🔊 Chatterbox TTS FAILED: status={response.status} "
                        f"latency={latency_ms:.0f}ms error={error_text[:200]}"
                    )
                    yield ErrorFrame(f"Chatterbox TTS failed: {response.status}")

            # Signal TTS stopped
            yield TTSStoppedFrame()
            logger.info(f"🔊 Chatterbox TTS complete for: '{text[:50]}...'")

        except aiohttp.ClientError as e:
            logger.error(f"🔊 Chatterbox API connection error: {e}")
            yield ErrorFrame(f"Chatterbox API error: {e}")
            yield TTSStoppedFrame()

        except Exception as e:
            logger.error(f"🔊 Chatterbox TTS unexpected error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield ErrorFrame(f"Chatterbox TTS error: {e}")
            yield TTSStoppedFrame()

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("ChatterboxTTSService session closed")
        await super().cleanup()


def create_chatterbox_tts_service(
    api_key: str,
    voice_uuid: str,
    synthesis_url: str = "https://f.cluster.resemble.ai/synthesize",
    stream_url: str = "https://f.cluster.resemble.ai/stream",
    sample_rate: int = 24000,
    voice: str = "neutral",
) -> ChatterboxTTSService:
    """Create a Chatterbox TTS service instance.

    Args:
        api_key: Resemble AI API key
        voice_uuid: Resemble AI voice UUID
        synthesis_url: Synthesis endpoint URL
        stream_url: Streaming endpoint URL
        sample_rate: Audio sample rate
        voice: Initial voice/emotion

    Returns:
        ChatterboxTTSService instance
    """
    return ChatterboxTTSService(
        api_key=api_key,
        voice_uuid=voice_uuid,
        synthesis_url=synthesis_url,
        stream_url=stream_url,
        sample_rate=sample_rate,
        voice=voice,
    )
