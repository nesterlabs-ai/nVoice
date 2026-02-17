"""
Feedback Storage Module

Provides in-memory storage for feedback data.
Separated to avoid circular imports between routes and conversation modules.
"""

from typing import Dict, Any

# In-memory feedback storage (use database in production)
feedback_store: Dict[str, Dict] = {}


def get_feedback_by_session(session_id: str) -> Dict[str, Any] | None:
    """Get feedback data for a session."""
    return feedback_store.get(session_id)


def store_feedback(session_id: str, feedback_data: Dict[str, Any]) -> None:
    """Store feedback data for a session."""
    feedback_store[session_id] = feedback_data


def list_all_feedback() -> list:
    """List all stored feedback."""
    return list(feedback_store.values())


def feedback_count() -> int:
    """Get count of stored feedback."""
    return len(feedback_store)
