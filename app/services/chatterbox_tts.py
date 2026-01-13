"""
Chatterbox TTS Service using Resemble AI Cloud API.

This module provides text-to-speech functionality using Resemble AI's
Chatterbox model with emotion control via exaggeration and cfg_weight parameters.

Compatible with Pipecat pipeline framework.
"""

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
        logger.debug(
            f"ChatterboxTTSService: Generating TTS [{text}] "
            f"(emotion={self._current_emotion})"
        )

        try:
            # Signal TTS started
            yield TTSStartedFrame()

            # Get emotion parameters
            params = self.get_emotion_params()

            payload = {
                "voice_uuid": self._voice_uuid,
                "data": text,
                "exaggeration": params["exaggeration"],
                "cfg_weight": params["cfg_weight"],
                "sample_rate": self._sample_rate,
                "precision": "PCM_16",
            }

            session = await self._get_session()

            # Use streaming endpoint for lower latency
            async with session.post(self._stream_url, json=payload) as response:
                if response.status == 200:
                    # Accumulate full response since we need to strip WAV header
                    audio_data = await response.read()

                    # Strip WAV header (44 bytes standard, but check for RIFF header)
                    if audio_data[:4] == b'RIFF':
                        # Find 'data' chunk
                        data_index = audio_data.find(b'data')
                        if data_index != -1:
                            # Skip 'data' + 4 bytes for chunk size
                            header_size = data_index + 8
                            audio_data = audio_data[header_size:]
                        else:
                            # Fallback to standard 44-byte header
                            audio_data = audio_data[44:]

                    # Yield raw PCM audio in chunks
                    chunk_size = 4096
                    for i in range(0, len(audio_data), chunk_size):
                        chunk = audio_data[i:i + chunk_size]
                        if chunk:
                            yield TTSAudioRawFrame(
                                audio=chunk,
                                sample_rate=self._sample_rate,
                                num_channels=1,
                            )
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Chatterbox stream failed: {response.status} - {error_text}"
                    )
                    yield ErrorFrame(f"Chatterbox TTS failed: {response.status}")

            # Signal TTS stopped
            yield TTSStoppedFrame()

        except aiohttp.ClientError as e:
            logger.error(f"Chatterbox API error: {e}")
            yield ErrorFrame(f"Chatterbox API error: {e}")
            yield TTSStoppedFrame()

        except Exception as e:
            logger.error(f"Chatterbox TTS error: {e}")
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
