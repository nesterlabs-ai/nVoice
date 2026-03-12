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
import threading
from typing import Optional

from loguru import logger

# Lazy boto3 import — not all environments have it
_cw_client = None
_cw_available = None
_lock = threading.Lock()

NAMESPACE = os.getenv("CLOUDWATCH_NAMESPACE", "NesterVoiceAI")
ENABLED = os.getenv("CLOUDWATCH_METRICS_ENABLED", "true").lower() == "true"

TAG = "[CLOUDWATCH-METRIC]"


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
            logger.info(f"{TAG} ✅ Client initialized — region={region}, namespace={NAMESPACE}, enabled={ENABLED}")
            return _cw_client
        except ImportError:
            _cw_available = False
            logger.warning(f"{TAG} ⚠️  boto3 not installed — metrics DISABLED")
            return None
        except Exception as e:
            _cw_available = False
            logger.error(f"{TAG} ❌ Failed to init client: {e}")
            return None


def _put_metric(metric_name: str, value: float, unit: str, dimensions: list = None):
    """Put a single metric data point to CloudWatch (non-blocking, with detailed logging)."""
    if not ENABLED:
        logger.debug(f"{TAG} SKIP {metric_name} — metrics disabled (CLOUDWATCH_METRICS_ENABLED=false)")
        return

    client = _get_client()
    if not client:
        logger.warning(f"{TAG} SKIP {metric_name} — no CloudWatch client available")
        return

    metric_data = {
        "MetricName": metric_name,
        "Value": value,
        "Unit": unit,
    }
    if dimensions:
        metric_data["Dimensions"] = dimensions

    dim_str = ", ".join(f"{d['Name']}={d['Value']}" for d in (dimensions or []))
    logger.info(f"{TAG} → SEND  {metric_name}={value} {unit}  [{dim_str}]  namespace={NAMESPACE}")

    try:
        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[metric_data],
        )
        logger.info(f"{TAG} ✅ OK   {metric_name}={value} {unit}")
    except Exception as e:
        logger.error(f"{TAG} ❌ FAIL {metric_name}={value} {unit} — {e}")


def emit_session_start(session_id: str, persona_id: str = ""):
    """Emit metrics when a new session starts."""
    env = os.getenv("ENVIRONMENT", "production")
    dims = [{"Name": "Environment", "Value": env}]
    if persona_id:
        dims.append({"Name": "PersonaId", "Value": persona_id})

    logger.info(f"{TAG} 🟢 Session START  session={session_id}  persona={persona_id or 'none'}  env={env}")
    _put_metric("SessionCount", 1, "Count", dims)

    # Also emit active session gauge from connection manager
    try:
        from app.core.connection_manager import connection_manager
        active = connection_manager.get_active_session_count()
        logger.info(f"{TAG} 📊 ActiveSessions={active}  (after session {session_id} connected)")
        _put_metric("ActiveSessions", active, "Count", [{"Name": "Environment", "Value": env}])
    except Exception as e:
        logger.warning(f"{TAG} ⚠️  Could not read active session count: {e}")


def emit_session_end_metrics(session_id: str, duration_secs: float, persona_id: str = ""):
    """Emit metrics when a session ends."""
    env = os.getenv("ENVIRONMENT", "production")
    dims = [{"Name": "Environment", "Value": env}]
    if persona_id:
        dims.append({"Name": "PersonaId", "Value": persona_id})

    logger.info(f"{TAG} 🔴 Session END    session={session_id}  duration={duration_secs:.1f}s  persona={persona_id or 'none'}")
    _put_metric("SessionDuration", duration_secs, "Seconds", dims)

    # Update active sessions
    try:
        from app.core.connection_manager import connection_manager
        active = connection_manager.get_active_session_count()
        logger.info(f"{TAG} 📊 ActiveSessions={active}  (after session {session_id} disconnected)")
        _put_metric("ActiveSessions", active, "Count", [{"Name": "Environment", "Value": env}])
    except Exception as e:
        logger.warning(f"{TAG} ⚠️  Could not read active session count: {e}")


def emit_error(error_type: str, session_id: str = ""):
    """Emit an application error metric."""
    env = os.getenv("ENVIRONMENT", "production")
    dims = [
        {"Name": "Environment", "Value": env},
        {"Name": "ErrorType", "Value": error_type},
    ]
    logger.info(f"{TAG} 🚨 ApplicationError  type={error_type}  session={session_id or 'none'}")
    _put_metric("ApplicationErrors", 1, "Count", dims)


def emit_rag_call(session_id: str, latency_ms: float, success: bool = True):
    """Emit RAG call metrics."""
    env = os.getenv("ENVIRONMENT", "production")
    dims = [{"Name": "Environment", "Value": env}]
    status = "✅ success" if success else "❌ failed"
    logger.info(f"{TAG} 🔍 RAG call  session={session_id}  latency={latency_ms:.0f}ms  status={status}")
    _put_metric("RAGCallCount", 1, "Count", dims)
    _put_metric("RAGLatency", latency_ms, "Milliseconds", dims)
    if not success:
        _put_metric("RAGErrors", 1, "Count", dims)


def emit_tts_latency(latency_ms: float):
    """Emit TTS latency metric."""
    env = os.getenv("ENVIRONMENT", "production")
    dims = [{"Name": "Environment", "Value": env}]
    logger.info(f"{TAG} 🔊 TTS latency={latency_ms:.0f}ms")
    _put_metric("TTSLatency", latency_ms, "Milliseconds", dims)


def emit_stt_latency(latency_ms: float):
    """Emit STT latency metric."""
    env = os.getenv("ENVIRONMENT", "production")
    dims = [{"Name": "Environment", "Value": env}]
    logger.info(f"{TAG} 🎤 STT latency={latency_ms:.0f}ms")
    _put_metric("STTLatency", latency_ms, "Milliseconds", dims)
