"""
CloudWatch Logs transcript logger for NesterVoiceAI.

Sends structured conversation transcript entries (user speech + bot responses)
to AWS CloudWatch Logs so sessions can be replayed and searched in the console.

Log group: configured via CLOUDWATCH_LOG_GROUP env var (default: /nester-ai/production)
Log stream: one per session — "transcript/{session_id}"

Falls back silently if boto3 is unavailable or AWS credentials are missing.
"""

import json
import os
import time
import threading
from typing import Optional

from loguru import logger

# ── State ────────────────────────────────────────────────────────────────────
_logs_client = None
_logs_available: Optional[bool] = None
_lock = threading.Lock()

LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP", f"/nester-ai/{os.getenv('ENVIRONMENT', 'production')}")
ENABLED = os.getenv("CLOUDWATCH_METRICS_ENABLED", "true").lower() == "true"

TAG = "[CLOUDWATCH-METRIC]"


# ── Client init ───────────────────────────────────────────────────────────────

def _get_client():
    """Lazy-initialize CloudWatch Logs client (thread-safe)."""
    global _logs_client, _logs_available

    if _logs_available is False:
        return None

    with _lock:
        if _logs_client is not None:
            return _logs_client
        if _logs_available is False:
            return None

        try:
            import boto3
            region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
            _logs_client = boto3.client("logs", region_name=region)
            _logs_available = True
            logger.info(f"{TAG} ✅ Logs client ready — group={LOG_GROUP}  region={region}  enabled={ENABLED}")
            return _logs_client
        except ImportError:
            _logs_available = False
            logger.warning(f"{TAG} ⚠️  boto3 not installed — transcript logging DISABLED")
            return None
        except Exception as e:
            _logs_available = False
            logger.error(f"{TAG} ❌ Failed to init Logs client: {e}")
            return None


# ── Per-session stream ────────────────────────────────────────────────────────

class SessionTranscriptLogger:
    """
    Logs transcript turns for a single session to CloudWatch Logs.

    Creates a log stream named "transcript/{session_id}" on first use.
    Subsequent calls append to it using the sequence token returned by AWS.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.stream_name = f"transcript/{session_id}"
        self._sequence_token: Optional[str] = None
        self._stream_created = False

    def _ensure_log_group(self, client) -> bool:
        """Create the log group if it doesn't exist yet."""
        try:
            client.create_log_group(logGroupName=LOG_GROUP)
            logger.info(f"{TAG} 📁 Created log group: {LOG_GROUP}")
            return True
        except client.exceptions.ResourceAlreadyExistsException:
            return True
        except Exception as e:
            logger.error(f"{TAG} ❌ Could not create log group {LOG_GROUP}: {e}")
            return False

    def _ensure_stream(self, client) -> bool:
        """Create the log group + stream if they don't exist yet."""
        if self._stream_created:
            return True
        try:
            client.create_log_stream(
                logGroupName=LOG_GROUP,
                logStreamName=self.stream_name,
            )
            self._stream_created = True
            logger.info(f"{TAG} 📂 Created log stream: {LOG_GROUP}/{self.stream_name}")
            return True
        except client.exceptions.ResourceAlreadyExistsException:
            self._stream_created = True
            logger.info(f"{TAG} 📂 Reusing log stream:  {LOG_GROUP}/{self.stream_name}")
            return True
        except client.exceptions.ResourceNotFoundException:
            # Log group doesn't exist — create it, then retry stream creation
            logger.warning(f"{TAG} ⚠️  Log group {LOG_GROUP} not found, creating it...")
            if self._ensure_log_group(client):
                return self._ensure_stream(client)
            return False
        except Exception as e:
            logger.error(f"{TAG} ❌ Could not create log stream {self.stream_name}: {e}")
            return False

    def log_turn(self, role: str, text: str, extra: dict = None):
        """
        Append a transcript turn to CloudWatch Logs (non-blocking, best-effort).

        Args:
            role: "user" or "bot"
            text: The spoken/generated text
            extra: Optional dict of extra fields (emotion, persona, etc.)
        """
        if not ENABLED:
            logger.debug(f"{TAG} SKIP transcript turn — logging disabled")
            return

        client = _get_client()
        if not client:
            logger.warning(f"{TAG} SKIP transcript turn — no Logs client")
            return

        preview = text[:60] + ("…" if len(text) > 60 else "")
        logger.info(f"{TAG} 📝 QUEUE  [{role.upper()}]  session={self.session_id}  text=\"{preview}\"")

        # Offload to thread so we never block the pipeline
        thread = threading.Thread(
            target=self._put_log_event,
            args=(client, role, text, extra or {}),
            daemon=True,
        )
        thread.start()

    def _put_log_event(self, client, role: str, text: str, extra: dict):
        """Internal: put log event (runs in background thread)."""
        if not self._ensure_stream(client):
            return

        payload = {
            "session_id": self.session_id,
            "role": role,
            "text": text,
            **extra,
        }

        kwargs = dict(
            logGroupName=LOG_GROUP,
            logStreamName=self.stream_name,
            logEvents=[{
                "timestamp": int(time.time() * 1000),
                "message": json.dumps(payload),
            }],
        )
        if self._sequence_token:
            kwargs["sequenceToken"] = self._sequence_token

        preview = text[:60] + ("…" if len(text) > 60 else "")
        try:
            resp = client.put_log_events(**kwargs)
            self._sequence_token = resp.get("nextSequenceToken")
            logger.info(
                f"{TAG} ✅ SENT   [{role.upper()}]  session={self.session_id}  "
                f"stream={self.stream_name}  text=\"{preview}\""
            )
        except Exception as e:
            logger.error(
                f"{TAG} ❌ FAIL   [{role.upper()}]  session={self.session_id}  "
                f"stream={self.stream_name}  error={e}"
            )
