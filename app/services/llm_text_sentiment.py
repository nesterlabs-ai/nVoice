"""
LLM-based text sentiment detector (provider-configurable).

Contextual emotion detection from text via any OpenAI-compatible chat API.
Preferred provider is Gemini (GOOGLE_API_KEY — same key as graph keywords);
Groq (GROQ_API_KEY) is the fallback for backwards compatibility.

Classes: frustrated, excited, sad, neutral
Latency: ~100-300ms for flash/instant-class models
"""

import os
from typing import Dict, Optional
from loguru import logger
import httpx

# OpenAI-compatible chat completion endpoints per provider
PROVIDER_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}


class LLMTextSentiment:
    """Contextual text sentiment detector via an OpenAI-compatible API."""

    # Map LLM emotions to our 4 core emotions with dimensional scores
    EMOTION_DIMENSIONS = {
        "frustrated": {"arousal": 0.75, "valence": 0.25},
        "excited": {"arousal": 0.80, "valence": 0.80},
        "sad": {"arousal": 0.30, "valence": 0.30},
        "neutral": {"arousal": 0.50, "valence": 0.50}
    }

    PROMPT = (
        "You are an emotion detection expert. Analyze the emotional tone of the user message.\n"
        "Respond with ONLY ONE WORD from these options: frustrated, excited, sad, neutral\n\n"
        "Examples:\n"
        '- "This is really annoying!" → frustrated\n'
        '- "I love this so much!" → excited\n'
        '- "I\'m feeling down today" → sad\n'
        '- "Okay, thanks" → neutral\n\n'
        "Analyze the emotion in this text: \"{text}\"\n\n"
        "Your response (one word only):"
    )

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
        provider: str = "groq",
    ):
        """Initialize the LLM sentiment detector.

        Args:
            api_key: API key for the provider
            model: Model name at the provider
            provider: "gemini" or "groq" (any OpenAI-compatible endpoint in PROVIDER_URLS)
        """
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.url = PROVIDER_URLS[provider]
        # AsyncClient is CRITICAL here: this runs inside the voice pipeline's
        # event loop. A sync httpx call froze the ENTIRE loop (including the
        # OpenAI Responses WebSocket receive) for 1-5s per turn — observed live
        # as a 5.2s LLM "TTFB" that unblocked 2ms after a sentiment timeout.
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=5.0,
        )
        logger.info(f"LLM Text Sentiment initialized (model: {model}, provider: {provider})")

    async def detect_emotion(self, text: str) -> Dict:
        """Detect emotion from text using the LLM (non-blocking).

        Args:
            text: Input text to analyze

        Returns:
            Dictionary with emotion, confidence, arousal, valence, etc.
        """
        if not text or not text.strip():
            return self._neutral_result("Empty text")

        try:
            resp = await self._client.post(
                self.url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": self.PROMPT.format(text=text)}
                    ],
                    "max_tokens": 5,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()

            raw_response = resp.json()["choices"][0]["message"]["content"].strip().lower()
            tokens_used = resp.json().get("usage", {}).get("total_tokens", 0)

            # Parse emotion — first match wins
            detected_emotion = "neutral"
            for emotion in ["frustrated", "excited", "sad", "neutral"]:
                if emotion in raw_response:
                    detected_emotion = emotion
                    break

            dimensions = self.EMOTION_DIMENSIONS[detected_emotion]
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
                "dominance": 0.5,
                "raw_response": raw_response,
                "method": "llm",
                "tokens_used": tokens_used,
                "latency_ms": 0,
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

    async def batch_detect(self, texts: list[str]) -> list[Dict]:
        """Detect emotions for multiple texts (sequential calls for now).

        Args:
            texts: List of text strings to analyze

        Returns:
            List of emotion dictionaries
        """
        results = []
        for text in texts:
            results.append(await self.detect_emotion(text))
        return results

    def get_status(self) -> Dict:
        """Get detector status."""
        return {
            "model": self.model,
            "provider": self.provider,
            "available": self._client is not None,
            "tokens_per_detection": "~20-50"
        }


# Global instance for reuse
_llm_detector: Optional[LLMTextSentiment] = None


def get_llm_detector(api_key: str = None) -> LLMTextSentiment:
    """Get or create global LLM detector instance.

    Prefers Gemini (GOOGLE_API_KEY) — the same key already used for graph
    keywords — and falls back to Groq (GROQ_API_KEY or the passed api_key,
    kept for backwards compatibility).
    """
    global _llm_detector
    if _llm_detector is None:
        gemini_key = os.getenv("GOOGLE_API_KEY")
        groq_key = api_key or os.getenv("GROQ_API_KEY")
        if gemini_key:
            _llm_detector = LLMTextSentiment(
                api_key=gemini_key, model="gemini-2.5-flash-lite", provider="gemini"
            )
        elif groq_key:
            _llm_detector = LLMTextSentiment(api_key=groq_key)
        else:
            raise ValueError(
                "GOOGLE_API_KEY or GROQ_API_KEY env var required to initialize LLM detector"
            )
    return _llm_detector
