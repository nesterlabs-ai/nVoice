"""
BERT-based text sentiment detector using boltuix/bert-emotion model.

This module provides fast, token-free emotion detection from text using a
pre-trained BERT model that outputs 13 emotion classes directly.

Model: boltuix/bert-emotion
Classes: joy, anger, sadness, fear, surprise, love, admiration, curiosity,
         disappointment, disgust, neutral, optimism, nervousness
Cost: $0 (runs locally, no API calls, no tokens)
Latency: 20-50ms
Accuracy: ~85-90%
"""

from typing import Dict, Optional
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from loguru import logger


class BERTTextSentiment:
    """Fast, token-free text sentiment detector using BERT."""

    # Map BERT 13 emotions to our 4 core emotions
    EMOTION_MAP = {
        # Frustrated emotions
        "anger": "frustrated",
        "annoyance": "frustrated",
        "disapproval": "frustrated",
        "disappointment": "frustrated",
        "disgust": "frustrated",

        # Excited emotions
        "joy": "excited",
        "admiration": "excited",
        "approval": "excited",
        "optimism": "excited",
        "love": "excited",
        "excitement": "excited",
        "amusement": "excited",
        "pride": "excited",

        # Sad emotions
        "sadness": "sad",
        "grief": "sad",
        "remorse": "sad",
        "embarrassment": "sad",
        "nervousness": "sad",
        "fear": "sad",

        # Neutral/other emotions
        "neutral": "neutral",
        "realization": "neutral",
        "confusion": "neutral",
        "curiosity": "neutral",
        "surprise": "neutral",
        "desire": "neutral",
        "caring": "neutral",
        "gratitude": "neutral",
        "relief": "neutral"
    }

    # Arousal/Valence scores for dimensional representation
    EMOTION_DIMENSIONS = {
        "frustrated": {"arousal": 0.75, "valence": 0.25},
        "excited": {"arousal": 0.80, "valence": 0.80},
        "sad": {"arousal": 0.30, "valence": 0.30},
        "neutral": {"arousal": 0.50, "valence": 0.50}
    }

    def __init__(self, model_name: str = "j-hartmann/emotion-english-distilroberta-base"):
        """Initialize the BERT sentiment detector.

        Args:
            model_name: Hugging Face model name (default: boltuxix/bert-emotion)
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._is_loaded = False

        logger.info(f"BERT Text Sentiment initialized (model: {model_name}, device: {self.device})")

    def load_model(self) -> None:
        """Load the BERT model and tokenizer (lazy loading)."""
        if self._is_loaded:
            return

        try:
            logger.info(f"Loading BERT emotion model: {self.model_name}")

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()  # Set to evaluation mode

            self._is_loaded = True
            logger.info(f"✅ BERT model loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load BERT model: {e}")
            raise

    def detect_emotion(self, text: str) -> Dict:
        """Detect emotion from text using BERT.

        Args:
            text: Input text to analyze

        Returns:
            Dictionary containing:
                - emotion: Mapped emotion (frustrated/excited/sad/neutral)
                - raw_emotion: Original BERT emotion label
                - confidence: Prediction confidence (0-1)
                - arousal: Arousal score (0-1)
                - valence: Valence score (0-1)
                - all_scores: All emotion probabilities
                - method: Detection method ("bert")
                - tokens_used: 0 (no LLM API calls)
        """
        # Lazy load model
        if not self._is_loaded:
            self.load_model()

        if not text or not text.strip():
            return self._neutral_result("Empty text")

        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)

            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

            # Get all scores
            scores = predictions[0].cpu().numpy()
            emotion_labels = self.model.config.id2label

            # Create all_scores dictionary
            all_scores = {
                emotion_labels[i]: float(scores[i])
                for i in range(len(scores))
            }

            # Get top emotion
            top_idx = scores.argmax()
            raw_emotion = emotion_labels[top_idx]
            confidence = float(scores[top_idx])

            # Map to our 4 core emotions
            mapped_emotion = self.EMOTION_MAP.get(raw_emotion, "neutral")

            # Get dimensional scores
            dimensions = self.EMOTION_DIMENSIONS[mapped_emotion]

            logger.debug(
                f"BERT sentiment: '{text[:50]}...' → {mapped_emotion} "
                f"(raw: {raw_emotion}, conf: {confidence:.2f})"
            )

            return {
                "emotion": mapped_emotion,
                "raw_emotion": raw_emotion,
                "confidence": confidence,
                "arousal": dimensions["arousal"],
                "valence": dimensions["valence"],
                "dominance": 0.5,  # BERT doesn't predict dominance
                "all_scores": all_scores,
                "method": "bert",
                "tokens_used": 0,
                "latency_ms": 0  # Filled by caller if needed
            }

        except Exception as e:
            logger.error(f"BERT emotion detection failed: {e}")
            return self._neutral_result(f"Error: {str(e)}")

    def _neutral_result(self, reason: str) -> Dict:
        """Return neutral emotion result."""
        return {
            "emotion": "neutral",
            "raw_emotion": "neutral",
            "confidence": 1.0,
            "arousal": 0.5,
            "valence": 0.5,
            "dominance": 0.5,
            "all_scores": {"neutral": 1.0},
            "method": "bert_fallback",
            "tokens_used": 0,
            "reason": reason
        }

    def batch_detect(self, texts: list[str]) -> list[Dict]:
        """Detect emotions for multiple texts in batch (more efficient).

        Args:
            texts: List of text strings to analyze

        Returns:
            List of emotion dictionaries
        """
        if not self._is_loaded:
            self.load_model()

        try:
            # Tokenize all texts
            inputs = self.tokenizer(
                texts,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)

            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

            # Process each result
            results = []
            for i, text in enumerate(texts):
                scores = predictions[i].cpu().numpy()
                emotion_labels = self.model.config.id2label

                top_idx = scores.argmax()
                raw_emotion = emotion_labels[top_idx]
                confidence = float(scores[top_idx])

                mapped_emotion = self.EMOTION_MAP.get(raw_emotion, "neutral")
                dimensions = self.EMOTION_DIMENSIONS[mapped_emotion]

                results.append({
                    "emotion": mapped_emotion,
                    "raw_emotion": raw_emotion,
                    "confidence": confidence,
                    "arousal": dimensions["arousal"],
                    "valence": dimensions["valence"],
                    "dominance": 0.5,
                    "method": "bert_batch",
                    "tokens_used": 0
                })

            return results

        except Exception as e:
            logger.error(f"BERT batch detection failed: {e}")
            return [self._neutral_result(str(e)) for _ in texts]

    def get_status(self) -> Dict:
        """Get detector status."""
        return {
            "model": self.model_name,
            "device": self.device,
            "loaded": self._is_loaded,
            "cost": "$0 (local inference)",
            "tokens_used": 0
        }


# Global instance for reuse
_bert_detector: Optional[BERTTextSentiment] = None


def get_bert_detector() -> BERTTextSentiment:
    """Get or create global BERT detector instance."""
    global _bert_detector
    if _bert_detector is None:
        _bert_detector = BERTTextSentiment()
    return _bert_detector
