"""
Feedback questions configuration for NesterVoiceAI.

Defines the feedback questions shown to users when they end a conversation.
"""

from typing import List, Dict, Any


FEEDBACK_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "overall_experience",
        "question": "How was your overall experience?",
        "options": [
            {"label": "Excellent", "value": "excellent", "emoji": "😊"},
            {"label": "Good", "value": "good", "emoji": "🙂"},
            {"label": "Okay", "value": "okay", "emoji": "😐"},
            {"label": "Poor", "value": "poor", "emoji": "😞"}
        ]
    },
    {
        "id": "information_helpful",
        "question": "Did you find the information helpful?",
        "options": [
            {"label": "Very Helpful", "value": "very_helpful"},
            {"label": "Somewhat", "value": "somewhat"},
            {"label": "Not Really", "value": "not_really"},
            {"label": "Not at All", "value": "not_at_all"}
        ]
    },
    {
        "id": "voice_quality",
        "question": "How was the voice quality?",
        "options": [
            {"label": "Clear & Natural", "value": "clear"},
            {"label": "Mostly Clear", "value": "mostly_clear"},
            {"label": "Hard to Understand", "value": "hard_to_understand"}
        ]
    },
    {
        "id": "would_use_again",
        "question": "Would you use this service again?",
        "options": [
            {"label": "Definitely", "value": "definitely"},
            {"label": "Probably", "value": "probably"},
            {"label": "Maybe", "value": "maybe"},
            {"label": "No", "value": "no"}
        ]
    }
]


def get_feedback_questions() -> List[Dict[str, Any]]:
    """Return feedback questions for A2UI component."""
    return FEEDBACK_QUESTIONS
