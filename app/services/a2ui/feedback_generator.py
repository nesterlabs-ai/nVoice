"""
Feedback A2UI Generator for NesterVoiceAI.

Generates A2UI document for feedback collection when user ends conversation.
"""

import time
from typing import Dict, Any

from app.config.feedback_questions import FEEDBACK_QUESTIONS


def generate_feedback_a2ui(session_id: str = "") -> Dict[str, Any]:
    """
    Generate A2UI document for feedback form.

    This creates a feedback form that the frontend will render when
    the user says goodbye. The form collects quick feedback before
    closing the session.

    Args:
        session_id: The session ID for tracking feedback

    Returns:
        A2UI document dict for the feedback form
    """
    return {
        "template": "feedback-form",
        "title": "Quick Feedback",
        "subtitle": "Help us improve your experience",
        "questions": FEEDBACK_QUESTIONS,
        "config": {
            "submitButtonText": "Submit Feedback",
            "skipButtonText": "Skip",
            "timeoutSeconds": 45,
            "showProgressBar": True,
            "theme": "dark"
        },
        "session_id": session_id,
        "timestamp": int(time.time() * 1000)
    }


def generate_feedback_message(session_id: str = "") -> Dict[str, Any]:
    """
    Generate the complete feedback request message to send to frontend.

    Args:
        session_id: The session ID for tracking feedback

    Returns:
        Complete message dict with message_type and a2ui payload
    """
    return {
        "message_type": "feedback_request",
        "a2ui": generate_feedback_a2ui(session_id),
        "session_id": session_id,
        "timestamp": time.time(),
    }
