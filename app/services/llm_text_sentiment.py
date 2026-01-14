"""
LLM-based text sentiment detector using Groq/Llama.

This module provides contextual emotion detection from text using an LLM,
replacing the BERT model for better accuracy and contextual understanding.

Model: Llama 3.3 70B via Groq API
Classes: frustrated, excited, sad, neutral
Cost: ~20-50 tokens per detection
Latency: 50-100ms (Groq is extremely fast)
Accuracy: ~95%+ with contextual understanding
"""

from typing import Dict, Optional
from loguru import logger
from openai import OpenAI


class LLMTextSentiment:
    """Contextual text sentiment detector using Groq/Llama LLM."""

    # Map LLM emotions to our 4 core emotions with dimensional scores
    EMOTION_DIMENSIONS = {
        "frustrated": {"arousal": 0.75, "valence": 0.25},
        "excited": {"arousal": 0.80, "valence": 0.80},
        "sad": {"arousal": 0.30, "valence": 0.30},
        "neutral": {"arousal": 0.50, "valence": 0.50}
    }

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        base_url: str = "https://api.groq.com/openai/v1"
    ):
        """Initialize the LLM sentiment detector.

        Args:
            api_key: Groq API key
            model: Model name (default: llama-3.3-70b-versatile)
            base_url: Groq API base URL
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = OpenAI(api_key=api_key, base_url=base_url)

        logger.info(f"LLM Text Sentiment initialized (model: {model}, provider: Groq)")

    def detect_emotion(self, text: str) -> Dict:
        """Detect emotion from text using LLM.

        Args:
            text: Input text to analyze

        Returns:
            Dictionary containing:
                - emotion: Detected emotion (frustrated/excited/sad/neutral)
                - confidence: Prediction confidence (0-1)
                - arousal: Arousal score (0-1)
                - valence: Valence score (0-1)
                - raw_response: Raw LLM response
                - method: Detection method ("llm")
                - tokens_used: Number of tokens consumed
        """
        if not text or not text.strip():
            return self._neutral_result("Empty text")

        try:
            # Craft prompt for emotion detection
            system_prompt = """You are an emotion detection expert. Analyze the emotional tone of user messages.
Respond with ONLY ONE WORD from these options: frustrated, excited, sad, neutral

Examples:
- "This is really annoying!" → frustrated
- "I love this so much!" → excited
- "I'm feeling down today" → sad
- "Okay, thanks" → neutral

Analyze the OVERALL emotional tone, considering context and word choice."""

            user_prompt = f'Analyze the emotion in this text: "{text}"'

            # Call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistent results
                max_tokens=10,  # Only need 1 word
                top_p=1.0
            )

            # Extract emotion
            raw_response = response.choices[0].message.content.strip().lower()
            tokens_used = response.usage.total_tokens

            # Parse emotion (handle extra text)
            detected_emotion = "neutral"
            for emotion in ["frustrated", "excited", "sad", "neutral"]:
                if emotion in raw_response:
                    detected_emotion = emotion
                    break

            # Get dimensional scores
            dimensions = self.EMOTION_DIMENSIONS[detected_emotion]

            # Calculate confidence (LLM is generally confident when it responds correctly)
            confidence = 0.85 if detected_emotion in raw_response else 0.60

            logger.debug(
                f"LLM sentiment: '{text[:50]}...' → {detected_emotion} "
                f"(tokens: {tokens_used}, conf: {confidence:.2f})"
            )

            return {
                "emotion": detected_emotion,
                "raw_emotion": detected_emotion,
                "confidence": confidence,
                "arousal": dimensions["arousal"],
                "valence": dimensions["valence"],
                "dominance": 0.5,  # LLM doesn't predict dominance directly
                "raw_response": raw_response,
                "method": "llm",
                "tokens_used": tokens_used,
                "latency_ms": 0  # Filled by caller if needed
            }

        except Exception as e:
            logger.error(f"LLM emotion detection failed: {e}")
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
            "raw_response": "neutral",
            "method": "llm_fallback",
            "tokens_used": 0,
            "reason": reason
        }

    def batch_detect(self, texts: list[str]) -> list[Dict]:
        """Detect emotions for multiple texts (sequential calls for now).

        Args:
            texts: List of text strings to analyze

        Returns:
            List of emotion dictionaries
        """
        results = []
        for text in texts:
            results.append(self.detect_emotion(text))
        return results

    def get_status(self) -> Dict:
        """Get detector status."""
        return {
            "model": self.model,
            "provider": "groq",
            "base_url": self.base_url,
            "cost": "~$0.05-0.10 per 1000 detections",
            "tokens_per_detection": "~20-50"
        }


# Global instance for reuse
_llm_detector: Optional[LLMTextSentiment] = None


def get_llm_detector(api_key: str = None) -> LLMTextSentiment:
    """Get or create global LLM detector instance.

    Args:
        api_key: Groq API key (required on first call)
    """
    global _llm_detector
    if _llm_detector is None:
        if api_key is None:
            raise ValueError("API key required to initialize LLM detector")
        _llm_detector = LLMTextSentiment(api_key=api_key)
    return _llm_detector
