"""
CloudWatch Logs transcript logger for NesterVoiceAI.

Writes complete conversation turns (one entry per user utterance, one per bot
response) to AWS CloudWatch Logs so sessions can be replayed and searched.

Log group : $CLOUDWATCH_LOG_GROUP  (default: /nester-ai/{ENVIRONMENT})
Log stream : transcript/{session_id}

Each log event is a JSON object:
    {
        "session_id": "a9990938",
        "turn":       3,          # monotonically increasing per session
        "role":       "user",     # or "bot"
        "text":       "...",      # complete turn text (not streaming fragments)
        "ts_ms":      1773302892536
    }

Falls back silently if boto3 is unavailable or AWS credentials are missing.
"""

import json
import os
import threading
import time
from typing import Optional

from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────

LOG_GROUP = os.getenv(
    "CLOUDWATCH_LOG_GROUP",
    f"/nester-ai/{os.getenv('ENVIRONMENT', 'production')}",
)
ENABLED = os.getenv("CLOUDWATCH_METRICS_ENABLED", "true").lower() == "true"

# ── Lazy client (shared across all sessions) ──────────────────────────────────

_client = None
_available: Optional[bool] = None
_init_lock = threading.Lock()


def _get_client():
    """Return a boto3 CloudWatch Logs client, or None if unavailable."""
    global _client, _available

    if _available is False:
        return None

    with _init_lock:
        if _client is not None:
            return _client
        if _available is False:
            return None
        try:
            import boto3
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
            _client = boto3.client("logs", region_name=region)
            _available = True
            logger.info(
                f"[Transcript] CloudWatch Logs client ready — "
                f"group={LOG_GROUP}  region={region}"
            )
            return _client
        except ImportError:
            _available = False
            logger.warning("[Transcript] boto3 not installed — transcript logging disabled")
            return None
        except Exception as exc:
            _available = False
            logger.warning(f"[Transcript] Failed to init Logs client: {exc}")
            return None


# ── Per-session logger ────────────────────────────────────────────────────────

class SessionTranscriptLogger:
    """
    Logs one CloudWatch Logs event per conversation turn.

    Thread-safe: all CloudWatch calls happen in a background daemon thread
    so they never block the voice pipeline.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.stream_name = f"transcript/{session_id}"
        self._stream_ready = False
        self._write_lock = threading.Lock()   # serialize background writes

    # ── Stream / group creation ───────────────────────────────────────────────

    def _ensure_stream(self, client) -> bool:
        """Create the log group + stream if they don't exist yet (idempotent)."""
        if self._stream_ready:
            return True

        # 1. Create log group (no-op if already exists)
        try:
            client.create_log_group(logGroupName=LOG_GROUP)
            logger.debug(f"[Transcript] Created log group {LOG_GROUP}")
        except client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as exc:
            logger.warning(f"[Transcript] Could not create log group: {exc}")
            return False

        # 2. Create log stream
        try:
            client.create_log_stream(
                logGroupName=LOG_GROUP,
                logStreamName=self.stream_name,
            )
            logger.info(
                f"[Transcript] Stream ready: {LOG_GROUP}/{self.stream_name}"
            )
        except client.exceptions.ResourceAlreadyExistsException:
            logger.debug(f"[Transcript] Reusing existing stream {self.stream_name}")
        except Exception as exc:
            logger.warning(f"[Transcript] Could not create log stream: {exc}")
            return False

        self._stream_ready = True
        return True

    # ── Public API ────────────────────────────────────────────────────────────

    def log_turn(self, role: str, text: str, turn_index: int) -> None:
        """
        Queue a transcript turn for async CloudWatch publishing.

        Args:
            role:        "user" or "bot"
            text:        The complete spoken/heard text for this turn
            turn_index:  Monotonically increasing turn counter for this session
        """
        if not ENABLED or not text.strip():
            return

        client = _get_client()
        if client is None:
            return

        preview = text[:70] + ("…" if len(text) > 70 else "")
        logger.info(
            f"[Transcript] turn={turn_index} [{role.upper()}] \"{preview}\""
        )

        threading.Thread(
            target=self._write,
            args=(client, role, text.strip(), turn_index),
            daemon=True,
        ).start()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _write(self, client, role: str, text: str, turn_index: int) -> None:
        """Background thread: put one log event to CloudWatch."""
        with self._write_lock:          # keep put_log_events calls ordered
            if not self._ensure_stream(client):
                return

            event = {
                "session_id": self.session_id,
                "turn":       turn_index,
                "role":       role,
                "text":       text,
                "ts_ms":      int(time.time() * 1000),
            }
            try:
                client.put_log_events(
                    logGroupName=LOG_GROUP,
                    logStreamName=self.stream_name,
                    logEvents=[{
                        "timestamp": event["ts_ms"],
                        "message":   json.dumps(event),
                    }],
                )
                logger.debug(
                    f"[Transcript] ✅ turn={turn_index} [{role.upper()}] written"
                )
            except Exception as exc:
                logger.warning(
                    f"[Transcript] ❌ turn={turn_index} [{role.upper()}] "
                    f"write failed: {exc}"
                )
