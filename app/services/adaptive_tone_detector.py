"""
Adaptive Voice Tone Detector with User Baseline Calibration

Uses Z-score normalization against user's baseline voice profile
for accurate emotional tone detection. Calibrates during first 15 seconds
of conversation to learn the user's natural speaking patterns.

Features:
- Real-time calibration (15 seconds / ~300 frames at 50ms intervals)
- Z-score normalization for user-adaptive thresholds
- Research-based weighted emotion scoring
- Low latency inference (~3ms)
"""

import time
import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from loguru import logger


@dataclass
class AudioFeatures:
    """Audio features received from frontend Web Audio API."""
    timestamp: float
    energy: float       # 0-1 normalized RMS
    pitch_var: float    # 0-1 pitch variance
    speech_rate: float  # 0-1 speech rate
    centroid: float     # 0-1 spectral centroid


class VoiceAdaptiveDetector:
    """Adaptive voice tone detector with user baseline calibration.

    Learns the user's natural voice patterns during calibration window,
    then uses Z-score normalization to detect emotional deviations.

    Attributes:
        calibration_window: Number of frames to collect for baseline (15 = ~15 seconds at 50ms)
        baseline: Rolling window of features for each metric
        calibrated: Whether baseline collection is complete
        weights: Importance weights for each feature
    """

    def __init__(self, calibration_window: int = 15):
        """Initialize the adaptive detector.

        Args:
            calibration_window: Number of feature frames for calibration (default 15 for ~15 seconds)
        """
        self.calibration_window = calibration_window
        self.calibrated = False

        # Baseline storage for each feature
        self.baseline: Dict[str, deque] = {
            "energy": deque(maxlen=calibration_window),
            "pitch_var": deque(maxlen=calibration_window),
            "speech_rate": deque(maxlen=calibration_window),
            "centroid": deque(maxlen=calibration_window),
        }

        # Feature importance weights
        self.weights = {
            "energy": 0.4,
            "pitch_var": 0.3,
            "speech_rate": 0.2,
            "centroid": 0.1
        }

        # Last detection for logging
        self.last_tone = "neutral"
        self.last_confidence = 0.0

        # Stats for debugging
        self.frames_received = 0
        self.calibration_start_time: Optional[float] = None

        logger.info(f"VoiceAdaptiveDetector initialized with {calibration_window} frame calibration window")

    def reset(self) -> None:
        """Reset detector state for new session."""
        self.calibrated = False
        for key in self.baseline:
            self.baseline[key].clear()
        self.last_tone = "neutral"
        self.last_confidence = 0.0
        self.frames_received = 0
        self.calibration_start_time = None
        logger.info("VoiceAdaptiveDetector reset for new session")

    def update_baseline(self, features: AudioFeatures) -> bool:
        """Update user voice baseline with new features.

        Args:
            features: Audio features from current frame

        Returns:
            True if calibration just completed, False otherwise
        """
        if self.calibration_start_time is None:
            self.calibration_start_time = time.time()

        self.frames_received += 1

        # Only update baseline with valid speech (energy > threshold)
        if features.energy < 0.05:
            return False

        # Add features to baseline
        self.baseline["energy"].append(features.energy)
        self.baseline["pitch_var"].append(features.pitch_var)
        self.baseline["speech_rate"].append(features.speech_rate)
        self.baseline["centroid"].append(features.centroid)

        # Check if calibration complete
        was_calibrated = self.calibrated
        self.calibrated = all(
            len(self.baseline[key]) >= self.calibration_window
            for key in self.weights
        )

        if self.calibrated and not was_calibrated:
            elapsed = time.time() - self.calibration_start_time
            logger.info(
                f"🎯 Voice baseline calibrated in {elapsed:.1f}s "
                f"(energy={np.mean(self.baseline['energy']):.2f}, "
                f"pitch_var={np.mean(self.baseline['pitch_var']):.2f}, "
                f"rate={np.mean(self.baseline['speech_rate']):.2f})"
            )
            return True

        return False

    def detect_tone(self, features: AudioFeatures) -> Tuple[str, float]:
        """Detect emotional tone using Z-score normalization.

        Uses research-based thresholds and weighted scoring for
        emotion classification. Inference time ~3ms.

        Args:
            features: Audio features from current frame

        Returns:
            Tuple of (tone, confidence) where tone is one of:
            "neutral", "excited", "frustrated", "sad"
        """
        start_time = time.time()

        # Not calibrated yet - return neutral
        if not self.calibrated:
            return "neutral", 0.0

        # Skip silent frames
        if features.energy < 0.05:
            return self.last_tone, self.last_confidence * 0.9

        # Calculate Z-scores for each feature
        z_scores = {}
        for key in self.weights:
            values = np.array(self.baseline[key])
            mu = np.mean(values)
            std = np.std(values)

            feature_value = getattr(features, key)
            z_scores[key] = (feature_value - mu) / (std + 1e-6)

        # Weighted emotion scores based on acoustic research
        # Z-score thresholds tuned for real speech:
        # - ±1.0 = noticeable change, ±1.5 = significant, ±2.0 = extreme
        emotion_scores = {
            "excited": (
                0.4 * max(0, z_scores["energy"] - 1.0) +       # Louder than baseline (1 std dev)
                0.3 * max(0, z_scores["pitch_var"] - 0.8) +    # More animated pitch
                0.2 * max(0, z_scores["centroid"] - 0.5) +     # Brighter voice
                0.1 * max(0, z_scores["speech_rate"] - 0.5)    # Faster speech
            ),
            "frustrated": (
                0.3 * max(0, z_scores["energy"] - 0.5) +        # Slightly louder
                0.3 * max(0, z_scores["speech_rate"] - 1.0) +   # Faster speech (agitated)
                0.2 * max(0, z_scores["pitch_var"] - 0.3) +     # Some variation
                0.2 * max(0, abs(z_scores["centroid"]) - 0.5)   # Changed timbre
            ),
            "sad": (
                # Require MORE extreme deviations for sad (was triggering too easily)
                0.4 * max(0, -z_scores["energy"] - 1.2) +       # Much quieter (1.2 std devs below)
                0.3 * max(0, -z_scores["pitch_var"] - 1.0) +    # Much flatter pitch
                0.2 * max(0, -z_scores["speech_rate"] - 0.8) +  # Noticeably slower
                0.1 * max(0, -z_scores["centroid"] - 0.5)       # Darker voice
            ),
            "neutral": 0.20  # Slightly higher base for neutral (sticky)
        }

        # Find highest scoring emotion
        tone = max(emotion_scores, key=emotion_scores.get)
        raw_confidence = emotion_scores[tone]

        # Normalize confidence to 0-1 range
        confidence = min(1.0, raw_confidence)

        # Require minimum confidence to override neutral
        if tone != "neutral" and confidence < 0.25:
            tone = "neutral"
            confidence = emotion_scores["neutral"]

        # Update last values
        self.last_tone = tone
        self.last_confidence = confidence

        # Log detection
        inference_ms = (time.time() - start_time) * 1000
        logger.debug(
            f"🎭 Adaptive tone: {tone} ({confidence:.2f}) "
            f"Z-scores: E={z_scores['energy']:.2f}, P={z_scores['pitch_var']:.2f}, "
            f"R={z_scores['speech_rate']:.2f}, C={z_scores['centroid']:.2f} [{inference_ms:.1f}ms]"
        )

        return tone, confidence

    def get_calibration_progress(self) -> float:
        """Get calibration progress as percentage.

        Returns:
            Progress from 0.0 to 1.0
        """
        if self.calibrated:
            return 1.0

        min_samples = min(len(self.baseline[key]) for key in self.weights)
        return min_samples / self.calibration_window

    def get_baseline_stats(self) -> Dict[str, Dict[str, float]]:
        """Get baseline statistics for debugging.

        Returns:
            Dictionary with mean and std for each feature
        """
        stats = {}
        for key in self.weights:
            if len(self.baseline[key]) > 0:
                values = np.array(self.baseline[key])
                stats[key] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                }
            else:
                stats[key] = {"mean": 0, "std": 0, "min": 0, "max": 0}
        return stats
