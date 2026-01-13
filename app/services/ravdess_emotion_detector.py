"""
RAVDESS Emotion Detection Service

Uses wav2vec2-lg-xlsr model fine-tuned on RAVDESS dataset for natural speech emotion detection.
Better suited for real conversational speech than IEMOCAP-trained models.

RAVDESS emotions: angry, calm, disgust, fearful, happy, neutral, sad, surprised
Model: ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition

Key advantages:
- Trained on natural speech (not acted/exaggerated)
- 8 emotion categories for finer detection
- Better for conversational AI use cases
"""

import os
import time
from typing import Dict, Optional
from dataclasses import dataclass
from collections import deque

import torch
import numpy as np
from loguru import logger

# Lazy load model
_model = None
_processor = None
_model_loading = False


def get_ravdess_model():
    """Get or initialize the RAVDESS emotion classifier (lazy loading)."""
    global _model, _processor, _model_loading

    if _model is not None and _processor is not None:
        return _model, _processor

    if _model_loading:
        return None, None

    _model_loading = True
    try:
        from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor

        model_name = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
        logger.info(f"Loading RAVDESS emotion model: {model_name} (first time may take ~60s)...")

        _processor = Wav2Vec2FeatureExtractor.from_pretrained(model_name)
        _model = Wav2Vec2ForSequenceClassification.from_pretrained(model_name)
        _model.eval()  # Set to evaluation mode

        # Move to CPU for stability
        _model = _model.to("cpu")

        logger.info("RAVDESS wav2vec2-xlsr emotion model loaded successfully")
        return _model, _processor

    except Exception as e:
        logger.error(f"Failed to load RAVDESS model: {e}")
        _model_loading = False
        return None, None


# RAVDESS emotions to our tone mapping
# Model output labels: angry, calm, disgust, fearful, happy, neutral, sad, surprised
RAVDESS_EMOTIONS = ["angry", "calm", "disgust", "fearful", "happy", "neutral", "sad", "surprised"]

RAVDESS_TO_TONE = {
    "angry": "frustrated",
    "calm": "neutral",
    "disgust": "frustrated",
    "fearful": "sad",
    "happy": "excited",
    "neutral": "neutral",
    "sad": "sad",
    "surprised": "excited",
}

DEFAULT_TONE = "neutral"


@dataclass
class RAVDESSEmotionResult:
    """Result from RAVDESS emotion detection."""
    emotion: str                 # Raw emotion (angry, calm, happy, etc.)
    tone: str                    # Our mapped tone (neutral, excited, frustrated, sad)
    confidence: float            # Confidence score 0-1
    all_scores: Dict[str, float] # All emotion scores
    timestamp: float             # When detection occurred


class RAVDESSEmotionDetector:
    """Emotion detection using wav2vec2-xlsr trained on RAVDESS.

    Better for natural conversational speech than IEMOCAP models.
    Maps 8 emotions to our 4 voice tones.

    Attributes:
        model: Wav2Vec2 model
        processor: Feature extractor
        enabled: Whether detection is available
        last_result: Most recent emotion detection result
    """

    EMOTIONS = RAVDESS_EMOTIONS

    def __init__(self):
        """Initialize the RAVDESS emotion detector."""
        self.enabled = True
        self.is_connected = False
        self.model = None
        self.processor = None

        # Result tracking
        self.last_result: Optional[RAVDESSEmotionResult] = None
        self.emotion_history: deque = deque(maxlen=10)

        # Stability tracking
        self._stability_counter = 0
        self._stability_last_tone = "neutral"
        self._last_switch_time = 0.0
        self._switch_cooldown = 1.5
        self._confidence_threshold = 0.35  # Lower threshold for RAVDESS
        self._stability_frames_required = 1

        logger.info("RAVDESS emotion detector initialized (model loads on first use)")

    async def connect(self) -> bool:
        """Initialize the RAVDESS model.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.model, self.processor = get_ravdess_model()
            if self.model is not None and self.processor is not None:
                self.is_connected = True
                logger.info("RAVDESS emotion detection ready")
                return True
            else:
                self.is_connected = False
                return False
        except Exception as e:
            logger.error(f"Failed to initialize RAVDESS: {e}")
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """Clean up resources."""
        self.is_connected = False
        logger.info("RAVDESS detector disconnected")

    async def process_audio(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000
    ) -> Optional[RAVDESSEmotionResult]:
        """Process audio chunk and detect emotions.

        Args:
            audio_bytes: Raw PCM audio bytes (16-bit, mono)
            sample_rate: Audio sample rate (default 16000 Hz)

        Returns:
            RAVDESSEmotionResult with detected emotion and confidence, or None if failed
        """
        if not self.enabled or not self.is_connected or self.model is None:
            return None

        # Need at least 0.3 seconds of audio
        min_bytes = int(sample_rate * 2 * 0.3)
        if len(audio_bytes) < min_bytes:
            return None

        try:
            # Convert bytes to numpy array (16-bit PCM)
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            audio_np = audio_np / 32768.0  # Normalize to [-1, 1]

            # Resample to 16kHz if needed (model expects 16kHz)
            if sample_rate != 16000:
                import librosa
                audio_np = librosa.resample(audio_np, orig_sr=sample_rate, target_sr=16000)

            # Process through feature extractor
            inputs = self.processor(
                audio_np,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True
            )

            # Run inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)

            # Get predictions
            probs_np = probs[0].cpu().numpy()
            predicted_idx = np.argmax(probs_np)
            confidence = float(probs_np[predicted_idx])

            # Get emotion label
            emotion = self.EMOTIONS[predicted_idx] if predicted_idx < len(self.EMOTIONS) else "neutral"

            # Map to our tone system
            tone = RAVDESS_TO_TONE.get(emotion, DEFAULT_TONE)

            # Build all scores dict
            all_scores = {self.EMOTIONS[i]: float(probs_np[i]) for i in range(len(self.EMOTIONS))}

            result = RAVDESSEmotionResult(
                emotion=emotion,
                tone=tone,
                confidence=confidence,
                all_scores=all_scores,
                timestamp=time.time()
            )

            self.last_result = result
            self.emotion_history.append(result)

            # Log detection
            top_3 = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            logger.info(
                f"RAVDESS: {emotion}({confidence:.2f}) -> {tone} | "
                f"Top3: {', '.join(f'{k}:{v:.2f}' for k, v in top_3)}"
            )

            return result

        except Exception as e:
            logger.error(f"RAVDESS processing error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def reset(self) -> None:
        """Reset detector state."""
        self.last_result = None
        self.emotion_history.clear()
        self._stability_counter = 0
        self._stability_last_tone = "neutral"
        self._last_switch_time = 0.0
        logger.info("RAVDESS emotion detector reset")

    def get_stats(self) -> Dict:
        """Get detector statistics."""
        return {
            "enabled": self.enabled,
            "connected": self.is_connected,
            "model_loaded": self.model is not None,
            "last_emotion": self.last_result.emotion if self.last_result else None,
            "last_tone": self.last_result.tone if self.last_result else None,
            "last_confidence": self.last_result.confidence if self.last_result else None,
            "stability_counter": self._stability_counter,
            "history_size": len(self.emotion_history),
        }


# Global instance
_ravdess_detector: Optional[RAVDESSEmotionDetector] = None


def get_ravdess_detector() -> RAVDESSEmotionDetector:
    """Get or create the global RAVDESS detector instance."""
    global _ravdess_detector
    if _ravdess_detector is None:
        _ravdess_detector = RAVDESSEmotionDetector()
    return _ravdess_detector


async def init_ravdess_detector() -> bool:
    """Initialize and connect the global RAVDESS detector.

    Returns:
        True if initialization successful
    """
    detector = get_ravdess_detector()
    return await detector.connect()
