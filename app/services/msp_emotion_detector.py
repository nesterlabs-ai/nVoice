"""
MSP-PODCAST Emotion Detection Service

Uses wav2vec2-large-robust trained on MSP-PODCAST for natural conversational speech emotion detection.
This model outputs dimensional emotions (arousal, dominance, valence) which are better suited
for real podcast/conversational speech than categorical models trained on acted speech.

Model: audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim
Training data: MSP-Podcast v1.7 (real podcast conversations)

Output dimensions (0-1 scale):
- Arousal: Low (calm) to High (excited/energetic)
- Dominance: Low (submissive) to High (dominant/confident)
- Valence: Low (negative/sad) to High (positive/happy)

Emotion mapping strategy:
- High arousal + low valence = frustrated/angry
- High arousal + high valence = excited/happy
- Low arousal + low valence = sad
- Low arousal + high valence = calm/neutral
"""

import os
import time
from typing import Dict, Optional
from dataclasses import dataclass

import torch
import torch.nn as nn
import numpy as np
from loguru import logger

# Lazy load model
_model = None
_processor = None
_model_loading = False


class RegressionHead(nn.Module):
    """Regression head for dimensional emotion prediction."""

    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = features
        x = self.dropout(x)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        x = self.out_proj(x)
        return x


def get_msp_model():
    """Get or initialize the MSP-PODCAST emotion model (lazy loading)."""
    global _model, _processor, _model_loading

    if _model is not None and _processor is not None:
        return _model, _processor

    if _model_loading:
        return None, None

    _model_loading = True
    try:
        from transformers import Wav2Vec2Processor
        from transformers.models.wav2vec2.modeling_wav2vec2 import (
            Wav2Vec2Model,
            Wav2Vec2PreTrainedModel,
        )

        # Define the EmotionModel class
        class EmotionModel(Wav2Vec2PreTrainedModel):
            """Wav2Vec2 model with regression head for dimensional emotions."""

            def __init__(self, config):
                super().__init__(config)
                self.config = config
                self.wav2vec2 = Wav2Vec2Model(config)
                self.classifier = RegressionHead(config)
                self.init_weights()

            def forward(self, input_values):
                outputs = self.wav2vec2(input_values)
                hidden_states = outputs[0]
                hidden_states = torch.mean(hidden_states, dim=1)
                logits = self.classifier(hidden_states)
                return hidden_states, logits

        model_name = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
        logger.info(f"Loading MSP-PODCAST emotion model: {model_name} (first time may take ~60s)...")

        _processor = Wav2Vec2Processor.from_pretrained(model_name)
        _model = EmotionModel.from_pretrained(model_name)
        _model.eval()
        _model = _model.to("cpu")

        logger.info("MSP-PODCAST wav2vec2 emotion model loaded successfully")
        return _model, _processor

    except Exception as e:
        logger.error(f"Failed to load MSP-PODCAST model: {e}")
        import traceback
        traceback.print_exc()
        _model_loading = False
        return None, None


# Emotion mapping thresholds
# Based on dimensional emotion research:
# - Arousal > 0.55 = high energy
# - Valence > 0.55 = positive, < 0.45 = negative
# - Dominance > 0.55 = confident

DEFAULT_TONE = "neutral"


@dataclass
class MSPEmotionResult:
    """Result from MSP-PODCAST dimensional emotion detection."""
    arousal: float      # 0-1: calm to excited
    dominance: float    # 0-1: submissive to dominant
    valence: float      # 0-1: negative to positive
    emotion: str        # Mapped categorical emotion
    tone: str           # Our voice tone mapping
    confidence: float   # Confidence based on dimension clarity
    timestamp: float    # When detection occurred


def map_dimensions_to_emotion(arousal: float, dominance: float, valence: float) -> tuple:
    """Map dimensional emotions to categorical emotion and tone.

    Args:
        arousal: Energy level (0=calm, 1=excited)
        dominance: Confidence level (0=submissive, 1=dominant)
        valence: Positivity (0=negative, 1=positive)

    Returns:
        Tuple of (emotion, tone, confidence)
    """
    # Calculate confidence based on how clearly the emotion dimensions stand out
    # Higher confidence when values are more extreme (not near 0.5)
    arousal_clarity = abs(arousal - 0.5) * 2
    valence_clarity = abs(valence - 0.5) * 2
    confidence = (arousal_clarity + valence_clarity) / 2

    # Thresholds for emotion mapping
    HIGH_AROUSAL = 0.55
    LOW_AROUSAL = 0.45
    HIGH_VALENCE = 0.55
    LOW_VALENCE = 0.45

    # Map to emotions based on arousal-valence quadrants
    if arousal > HIGH_AROUSAL:
        if valence > HIGH_VALENCE:
            # High arousal + positive = excited/happy
            emotion = "happy"
            tone = "excited"
        else:
            # High arousal + negative = angry/frustrated
            emotion = "angry"
            tone = "frustrated"
    elif arousal < LOW_AROUSAL:
        if valence < LOW_VALENCE:
            # Low arousal + negative = sad
            emotion = "sad"
            tone = "sad"
        else:
            # Low arousal + positive = calm/relaxed
            emotion = "calm"
            tone = "neutral"
    else:
        # Medium arousal - check valence
        if valence > HIGH_VALENCE:
            emotion = "content"
            tone = "neutral"
        elif valence < LOW_VALENCE:
            emotion = "worried"
            tone = "sad"
        else:
            emotion = "neutral"
            tone = "neutral"

    return emotion, tone, confidence


class MSPEmotionDetector:
    """Emotion detection using wav2vec2 trained on MSP-PODCAST.

    Better for natural conversational speech than acted speech models.
    Outputs dimensional emotions (arousal, dominance, valence) then maps to tones.

    Attributes:
        model: Wav2Vec2 EmotionModel
        processor: Wav2Vec2Processor
        enabled: Whether detection is available
        last_result: Most recent emotion detection result
    """

    def __init__(self):
        """Initialize the MSP-PODCAST emotion detector."""
        self.enabled = True
        self.is_connected = False
        self.model = None
        self.processor = None
        self.device = "cpu"

        # Result tracking
        self.last_result: Optional[MSPEmotionResult] = None

        logger.info("MSP-PODCAST emotion detector initialized (model loads on first use)")

    async def connect(self) -> bool:
        """Initialize the MSP-PODCAST model.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.model, self.processor = get_msp_model()
            if self.model is not None and self.processor is not None:
                self.is_connected = True
                logger.info("MSP-PODCAST emotion detection ready (natural conversation)")
                return True
            else:
                self.is_connected = False
                return False
        except Exception as e:
            logger.error(f"Failed to initialize MSP-PODCAST: {e}")
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """Clean up resources."""
        self.is_connected = False
        logger.info("MSP-PODCAST detector disconnected")

    async def process_audio(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000
    ) -> Optional[MSPEmotionResult]:
        """Process audio chunk and detect dimensional emotions.

        Args:
            audio_bytes: Raw PCM audio bytes (16-bit, mono)
            sample_rate: Audio sample rate (default 16000 Hz)

        Returns:
            MSPEmotionResult with arousal/dominance/valence and mapped tone, or None if failed
        """
        if not self.enabled or not self.is_connected or self.model is None:
            return None

        # Need at least 0.5 seconds of audio for meaningful detection
        min_bytes = int(sample_rate * 2 * 0.5)
        if len(audio_bytes) < min_bytes:
            return None

        try:
            # Convert bytes to numpy array (16-bit PCM)
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            audio_np = audio_np / 32768.0  # Normalize to [-1, 1]

            # Resample to 16kHz if needed
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
                input_values = inputs['input_values'].to(self.device)
                _, logits = self.model(input_values)

            # Get predictions (arousal, dominance, valence)
            predictions = logits[0].cpu().numpy()
            arousal = float(predictions[0])
            dominance = float(predictions[1])
            valence = float(predictions[2])

            # Map to emotion and tone
            emotion, tone, confidence = map_dimensions_to_emotion(arousal, dominance, valence)

            result = MSPEmotionResult(
                arousal=arousal,
                dominance=dominance,
                valence=valence,
                emotion=emotion,
                tone=tone,
                confidence=confidence,
                timestamp=time.time()
            )

            self.last_result = result

            # Log detection
            logger.info(
                f"MSP: A={arousal:.2f} D={dominance:.2f} V={valence:.2f} -> "
                f"{emotion}({confidence:.0%}) -> {tone}"
            )

            return result

        except Exception as e:
            logger.error(f"MSP-PODCAST processing error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def reset(self) -> None:
        """Reset detector state."""
        self.last_result = None
        logger.info("MSP-PODCAST emotion detector reset")

    def get_stats(self) -> Dict:
        """Get detector statistics."""
        return {
            "enabled": self.enabled,
            "connected": self.is_connected,
            "model_loaded": self.model is not None,
            "last_arousal": self.last_result.arousal if self.last_result else None,
            "last_dominance": self.last_result.dominance if self.last_result else None,
            "last_valence": self.last_result.valence if self.last_result else None,
            "last_emotion": self.last_result.emotion if self.last_result else None,
            "last_tone": self.last_result.tone if self.last_result else None,
            "last_confidence": self.last_result.confidence if self.last_result else None,
        }


# Global instance
_msp_detector: Optional[MSPEmotionDetector] = None


def get_msp_detector() -> MSPEmotionDetector:
    """Get or create the global MSP-PODCAST detector instance."""
    global _msp_detector
    if _msp_detector is None:
        _msp_detector = MSPEmotionDetector()
    return _msp_detector


async def init_msp_detector() -> bool:
    """Initialize and connect the global MSP-PODCAST detector.

    Returns:
        True if initialization successful
    """
    detector = get_msp_detector()
    return await detector.connect()
