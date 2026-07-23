"""
CloudWatch custom metrics for NesterVoiceAI session analytics.

Emits metrics to AWS CloudWatch for monitoring:
- SessionCount: Total sessions started
- SessionDuration: Duration of each session in seconds
- ActiveSessions: Current concurrent session count
- ApplicationErrors: Exception count
- RAGCallCount: Number of RAG function calls
- RAGLatency: RAG call latency in milliseconds

All metrics are published under the "NesterVoiceAI" namespace.
Requires AWS credentials (auto-detected from IAM role on Lightsail, or env vars).

Falls back gracefully if boto3 is not installed or AWS credentials are missing.
"""

import os
import time
import threading
from typing import Optional

from loguru import logger

# Lazy boto3 import — not all environments have it
_cw_client = None
_cw_available = None
_lock = threading.Lock()

NAMESPACE = os.getenv("CLOUDWATCH_NAMESPACE", "NesterVoiceAI")
ENABLED = os.getenv("CLOUDWATCH_METRICS_ENABLED", "true").lower() == "true"


def _get_client():
    """Lazy-initialize CloudWatch client (thread-safe)."""
    global _cw_client, _cw_available

    if _cw_available is False:
        return None

    with _lock:
        if _cw_client is not None:
            return _cw_client
        if _cw_available is False:
            return None

        try:
            import boto3
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
            _cw_client = boto3.client("cloudwatch", region_name=region)
            _cw_available = True
            logger.info(f"[CloudWatch] Client initialized (region={region}, namespace={NAMESPACE})")
            return _cw_client
        except ImportError:
            _cw_available = False
            logger.info("[CloudWatch] boto3 not installed — metrics disabled")
            return None
        except Exception as e:
            _cw_available = False
            logger.warning(f"[CloudWatch] Failed to init client: {e}")
            return None


def _put_metric(metric_name: str, value: float, unit: str, dimensions: list = None):
    """Put a single metric data point to CloudWatch (non-blocking)."""
    if not ENABLED:
        return

    client = _get_client()
    if not client:
        return

    metric_data = {
        "MetricName": metric_name,
        "Value": value,
        "Unit": unit,
    }
    if dimensions:
        metric_data["Dimensions"] = dimensions

    try:
        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[metric_data],
        )
    except Exception as e:
        logger.debug(f"[CloudWatch] Failed to put {metric_name}: {e}")


def emit_session_start(session_id: str, persona_id: str = ""):
    """Emit metrics when a new session starts."""
    dims = [{"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}]
    if persona_id:
        dims.append({"Name": "PersonaId", "Value": persona_id})

    _put_metric("SessionCount", 1, "Count", dims)

    # Also emit active session gauge from connection manager
    try:
        from app.core.connection_manager import connection_manager
        active = connection_manager.get_active_session_count()
        _put_metric("ActiveSessions", active, "Count", [
            {"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}
        ])
    except Exception:
        pass


def emit_session_end_metrics(session_id: str, duration_secs: float, persona_id: str = ""):
    """Emit metrics when a session ends."""
    dims = [{"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}]
    if persona_id:
        dims.append({"Name": "PersonaId", "Value": persona_id})

    _put_metric("SessionDuration", duration_secs, "Seconds", dims)

    # Update active sessions
    try:
        from app.core.connection_manager import connection_manager
        active = connection_manager.get_active_session_count()
        _put_metric("ActiveSessions", active, "Count", [
            {"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}
        ])
    except Exception:
        pass


def emit_error(error_type: str, session_id: str = ""):
    """Emit an application error metric."""
    dims = [
        {"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")},
        {"Name": "ErrorType", "Value": error_type},
    ]
    _put_metric("ApplicationErrors", 1, "Count", dims)


def emit_rag_call(session_id: str, latency_ms: float, success: bool = True):
    """Emit RAG call metrics."""
    dims = [{"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}]

    _put_metric("RAGCallCount", 1, "Count", dims)
    _put_metric("RAGLatency", latency_ms, "Milliseconds", dims)

    if not success:
        _put_metric("RAGErrors", 1, "Count", dims)


def emit_safety_event(severity: str, round_n: int, action: str):
    """Emit a guardrail safety-handoff metric (observability for the crisis path).

    One data point per safety turn — lets us see how often the safety guardrail
    fires in production and at what severity, which prose guardrails never surfaced.
    """
    dims = [
        {"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")},
        {"Name": "Severity", "Value": severity},
        {"Name": "Action", "Value": action},
    ]
    _put_metric("SafetyHandoff", 1, "Count", dims)


def emit_tts_latency(latency_ms: float):
    """Emit TTS latency metric."""
    dims = [{"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}]
    _put_metric("TTSLatency", latency_ms, "Milliseconds", dims)


def emit_stt_latency(latency_ms: float):
    """Emit STT latency metric."""
    dims = [{"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}]
    _put_metric("STTLatency", latency_ms, "Milliseconds", dims)


def emit_turn_latency(latency_ms: float, session_id: str = ""):
    """Emit end-to-end turn latency: final user transcript → bot audio start.

    This is the user-perceived responsiveness number; regressions here are the
    first thing to alarm on.
    """
    dims = [{"Name": "Environment", "Value": os.getenv("ENVIRONMENT", "production")}]
    _put_metric("TurnLatency", latency_ms, "Milliseconds", dims)


def emit_question_card_match(card_ids: list, session_id: str = ""):
    """Emit question-card routing analytics.

    One count per matched card id, plus an 'unmatched' count when no card fired —
    unmatched questions are the card-authoring backlog, measured from real traffic.
    """
    env = os.getenv("ENVIRONMENT", "production")
    if not card_ids:
        _put_metric(
            "QuestionCardMatch", 1, "Count",
            [{"Name": "Environment", "Value": env}, {"Name": "CardId", "Value": "unmatched"}],
        )
        return
    for card_id in card_ids:
        _put_metric(
            "QuestionCardMatch", 1, "Count",
            [{"Name": "Environment", "Value": env}, {"Name": "CardId", "Value": card_id}],
        )
