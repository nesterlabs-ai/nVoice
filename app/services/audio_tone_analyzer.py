"""Audio-based Tone Analyzer using librosa.

This module extracts acoustic features from audio to detect emotional tone,
providing more accurate tone detection than text-only analysis.

Features extracted:
- RMS Energy: Volume/intensity indicator
- Pitch (F0): Fundamental frequency analysis
- Speech Rate: Estimated from audio characteristics
- Spectral Centroid: Voice "brightness"
"""

import asyncio
import io
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List
import numpy as np

from loguru import logger

# Lazy import librosa to avoid startup delay
_librosa = None


def get_librosa():
    """Lazy load librosa to avoid slow startup."""
    global _librosa
    if _librosa is None:
        import librosa
        _librosa = librosa
        logger.info("librosa loaded successfully")
    return _librosa


@dataclass
class AudioFeatures:
    """Extracted audio features for tone analysis."""
    rms_energy: float  # 0-1 normalized energy level
    pitch_mean: float  # Mean pitch in Hz
    pitch_variance: float  # Pitch variation (0-1 normalized)
    spectral_centroid: float  # Voice brightness (0-1 normalized)
    speech_rate_estimate: float  # Estimated speech rate (0-1 normalized)
    duration_seconds: float  # Audio duration
    confidence: float  # Overall feature extraction confidence (0-1)


# Tone classification thresholds (tuned for real microphone input)
# With new normalization: energy is now 0.0-1.0 scale (RMS / 0.015)
# Typical WebRTC mic: quiet=0.05-0.10, normal=0.10-0.15, loud=0.15+
TONE_THRESHOLDS = {
    "excited": {
        "energy_min": 0.12,       # Above average loudness
        "pitch_var_min": 0.15,    # Some pitch variation (animated speech)
        "centroid_min": 0.10,     # Brighter voice
    },
    "frustrated": {
        "energy_min": 0.10,       # At least normal energy
        "speech_rate_min": 0.30,  # Fast speech (agitated)
        "pitch_var_min": 0.12,    # Some variation (not monotone)
    },
    "sad": {
        "energy_max": 0.08,       # Quiet, low energy speech
        "pitch_var_max": 0.10,    # Flat, monotone pitch
        "speech_rate_max": 0.25,  # Slow, deliberate speech
    },
}


class AudioToneAnalyzer:
    """Analyzes audio to detect emotional tone using acoustic features.

    Uses librosa for feature extraction with optimized settings for
    real-time voice analysis (~50-100ms processing time).

    Attributes:
        sample_rate: Expected audio sample rate (default 16000 Hz)
        min_duration: Minimum audio duration for reliable analysis
        feature_cache: Cache for recent feature extractions
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        min_duration: float = 0.5,
        cache_size: int = 5
    ):
        """Initialize the Audio Tone Analyzer.

        Args:
            sample_rate: Expected sample rate of audio (default 16kHz)
            min_duration: Minimum seconds of audio needed for analysis
            cache_size: Number of recent analyses to cache
        """
        self.sample_rate = sample_rate
        self.min_duration = min_duration
        self._cache: List[Tuple[float, AudioFeatures]] = []
        self._cache_size = cache_size
        self._initialized = False

        logger.info(f"AudioToneAnalyzer initialized (sr={sample_rate}, min_dur={min_duration}s)")

    def _ensure_initialized(self) -> bool:
        """Ensure librosa is loaded."""
        if not self._initialized:
            try:
                get_librosa()
                self._initialized = True
            except ImportError as e:
                logger.error(f"librosa not available: {e}")
                return False
        return True

    def extract_features(self, audio_data: np.ndarray) -> Optional[AudioFeatures]:
        """Extract acoustic features from audio data.

        Args:
            audio_data: Audio samples as numpy array (mono, float32)

        Returns:
            AudioFeatures object or None if extraction fails
        """
        if not self._ensure_initialized():
            return None

        librosa = get_librosa()
        start_time = time.time()

        try:
            # Ensure correct format
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Calculate original RMS before normalization (for energy comparison)
            max_val = np.abs(audio_data).max()
            if max_val < 0.001:  # Near silence
                logger.debug("Audio too quiet for analysis (near silence)")
                return None

            # Get RMS energy from ORIGINAL audio (before normalization)
            # This captures the actual loudness of the speaker
            rms_original = librosa.feature.rms(y=audio_data, frame_length=2048, hop_length=512)[0]
            rms_original_mean = float(np.mean(rms_original))

            # Now normalize audio for pitch/spectral analysis (need consistent levels)
            audio_normalized = audio_data / max_val * 0.9

            duration = len(audio_data) / self.sample_rate

            if duration < self.min_duration:
                logger.debug(f"Audio too short: {duration:.2f}s < {self.min_duration}s")
                return None

            # 1. RMS Energy (volume indicator) - use RELATIVE energy
            # WebRTC mics typically output very low RMS (0.001-0.01 range)
            # Use dynamic range based on the audio's own variance
            rms_std = float(np.std(rms_original))

            # Log raw RMS for debugging
            logger.debug(f"🔊 Raw RMS: mean={rms_original_mean:.4f}, std={rms_std:.4f}, max={float(np.max(rms_original)):.4f}")

            # Normalize energy relative to typical WebRTC levels (0.001-0.02 range)
            # This gives better discrimination for quiet microphones
            rms_normalized = min(1.0, rms_original_mean / 0.015)

            # Also calculate energy variance (loud parts vs quiet parts)
            # High variance = dynamic speech, low variance = monotone
            energy_variance = min(1.0, rms_std / rms_original_mean) if rms_original_mean > 0 else 0

            # 2. Pitch (F0) Analysis using pyin for accuracy
            # Use normalized audio for consistent pitch detection
            f0, voiced_flag, voiced_probs = librosa.pyin(
                audio_normalized,
                fmin=librosa.note_to_hz('C2'),  # ~65 Hz
                fmax=librosa.note_to_hz('C6'),  # ~1047 Hz
                sr=self.sample_rate,
                frame_length=2048
            )

            # Filter to voiced frames only
            voiced_f0 = f0[voiced_flag]
            if len(voiced_f0) > 0:
                pitch_mean = float(np.nanmean(voiced_f0))
                pitch_std = float(np.nanstd(voiced_f0))
                # Normalize variance (typical range 10-100 Hz std)
                pitch_variance = min(1.0, pitch_std / 80.0)
            else:
                pitch_mean = 0.0
                pitch_variance = 0.0

            # 3. Spectral Centroid (voice brightness)
            # Use normalized audio for consistent spectral analysis
            centroid = librosa.feature.spectral_centroid(
                y=audio_normalized,
                sr=self.sample_rate,
                n_fft=2048,
                hop_length=512
            )[0]
            centroid_mean = float(np.mean(centroid))
            # Normalize (typical speech centroid 1000-4000 Hz)
            centroid_normalized = min(1.0, (centroid_mean - 500) / 3500)
            centroid_normalized = max(0.0, centroid_normalized)

            # 4. Speech Rate Estimate (using zero crossing rate as proxy)
            # Use normalized audio for consistent ZCR
            zcr = librosa.feature.zero_crossing_rate(audio_normalized, frame_length=2048, hop_length=512)[0]
            zcr_mean = float(np.mean(zcr))
            # Higher ZCR often correlates with faster speech
            # Normalize (typical ZCR for speech: 0.02-0.15)
            speech_rate = min(1.0, zcr_mean / 0.12)

            # 5. Calculate confidence based on voiced ratio and duration
            voiced_ratio = np.sum(voiced_flag) / len(voiced_flag) if len(voiced_flag) > 0 else 0
            duration_factor = min(1.0, duration / 2.0)  # Full confidence at 2s
            confidence = float(voiced_ratio * 0.7 + duration_factor * 0.3)

            features = AudioFeatures(
                rms_energy=rms_normalized,
                pitch_mean=pitch_mean,
                pitch_variance=pitch_variance,
                spectral_centroid=centroid_normalized,
                speech_rate_estimate=speech_rate,
                duration_seconds=duration,
                confidence=confidence
            )

            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                f"🎵 Audio features: energy={rms_normalized:.2f} (var={energy_variance:.2f}), "
                f"pitch_var={pitch_variance:.2f}, rate={speech_rate:.2f}, conf={confidence:.2f}"
            )

            # Cache the result
            self._cache.append((time.time(), features))
            if len(self._cache) > self._cache_size:
                self._cache.pop(0)

            return features

        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None

    async def extract_features_async(self, audio_data: np.ndarray) -> Optional[AudioFeatures]:
        """Async wrapper for feature extraction.

        Runs extraction in executor to avoid blocking event loop.

        Args:
            audio_data: Audio samples as numpy array

        Returns:
            AudioFeatures object or None
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.extract_features, audio_data)

    def classify_tone_from_features(self, features: AudioFeatures) -> Tuple[str, float]:
        """Classify emotional tone from audio features.

        Args:
            features: Extracted audio features

        Returns:
            Tuple of (tone, confidence) where tone is one of:
            "neutral", "frustrated", "excited", "sad"
        """
        scores = {
            "neutral": 0.3,  # Base score for neutral
            "excited": 0.0,
            "frustrated": 0.0,
            "sad": 0.0,
        }

        # Score excited: high energy + high pitch variance + bright voice
        if features.rms_energy > TONE_THRESHOLDS["excited"]["energy_min"]:
            scores["excited"] += 0.3
        if features.pitch_variance > TONE_THRESHOLDS["excited"]["pitch_var_min"]:
            scores["excited"] += 0.4
        if features.spectral_centroid > TONE_THRESHOLDS["excited"]["centroid_min"]:
            scores["excited"] += 0.2

        # Score frustrated: high energy + fast speech + some pitch variance
        if features.rms_energy > TONE_THRESHOLDS["frustrated"]["energy_min"]:
            scores["frustrated"] += 0.35
        if features.speech_rate_estimate > TONE_THRESHOLDS["frustrated"]["speech_rate_min"]:
            scores["frustrated"] += 0.35
        if features.pitch_variance > TONE_THRESHOLDS["frustrated"]["pitch_var_min"]:
            scores["frustrated"] += 0.2

        # Score sad: low energy + flat pitch + slow speech
        if features.rms_energy < TONE_THRESHOLDS["sad"]["energy_max"]:
            scores["sad"] += 0.35
        if features.pitch_variance < TONE_THRESHOLDS["sad"]["pitch_var_max"]:
            scores["sad"] += 0.35
        if features.speech_rate_estimate < TONE_THRESHOLDS["sad"]["speech_rate_max"]:
            scores["sad"] += 0.2

        # Find highest scoring tone
        best_tone = max(scores, key=scores.get)
        best_score = scores[best_tone]

        # Require minimum score threshold to override neutral
        if best_tone != "neutral" and best_score < 0.5:
            best_tone = "neutral"
            best_score = scores["neutral"]

        # Adjust confidence based on feature confidence
        final_confidence = best_score * features.confidence

        logger.debug(f"🎭 Audio tone scores: {scores} → {best_tone} ({final_confidence:.2f})")

        return best_tone, final_confidence

    def analyze(self, audio_data: np.ndarray) -> Tuple[str, float, Optional[AudioFeatures]]:
        """Full analysis: extract features and classify tone.

        Args:
            audio_data: Audio samples as numpy array

        Returns:
            Tuple of (tone, confidence, features)
            Returns ("neutral", 0.0, None) if analysis fails
        """
        features = self.extract_features(audio_data)

        if features is None:
            return "neutral", 0.0, None

        tone, confidence = self.classify_tone_from_features(features)
        return tone, confidence, features

    async def analyze_async(self, audio_data: np.ndarray) -> Tuple[str, float, Optional[AudioFeatures]]:
        """Async full analysis.

        Args:
            audio_data: Audio samples as numpy array

        Returns:
            Tuple of (tone, confidence, features)
        """
        features = await self.extract_features_async(audio_data)

        if features is None:
            return "neutral", 0.0, None

        tone, confidence = self.classify_tone_from_features(features)
        return tone, confidence, features

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics.

        Returns:
            Dictionary with analyzer state info
        """
        return {
            "sample_rate": self.sample_rate,
            "min_duration": self.min_duration,
            "initialized": self._initialized,
            "cache_size": len(self._cache),
        }
