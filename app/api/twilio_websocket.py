"""
Twilio Media Streams WebSocket endpoint.

This handles inbound phone calls placed to a Twilio number. Twilio connects a
bidirectional Media Stream WebSocket here (see the `/twilio/voice` TwiML webhook
in ``app/api/routes.py``) and streams 8 kHz mu-law (PCMU) audio.

Unlike the browser path (``app/api/websocket.py``), which uses a
``ProtobufFrameSerializer`` tailored to the Pipecat JS client, this endpoint
uses ``TwilioFrameSerializer``. That serializer resamples in both directions
(8 kHz mu-law <-> pipeline rate) and handles Twilio's start/media/clear/DTMF
events plus auto hang-up. Because the rest of the pipeline reads its sample
rates off the ``StartFrame``, we keep the internal pipeline at 16 kHz in /
24 kHz out (identical to the browser path) and let the serializer convert to
Twilio's telephony format — so STT, TTS, emotion detection and turn detection
need no changes.

Flow:
    Twilio opens WSS -> sends {"event":"connected"} then {"event":"start", ...}
    -> we read streamSid + callSid -> build TwilioFrameSerializer
    -> FastAPIWebsocketTransport -> voice_assistant.run(...)
"""

import json
import os
import time
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


async def twilio_websocket_endpoint(websocket: WebSocket) -> None:
    """FastAPI WebSocket endpoint for Twilio Media Streams (inbound calls).

    Args:
        websocket: FastAPI WebSocket connection opened by Twilio.
    """
    session_id = str(uuid.uuid4())[:8]
    logger.info(f"[Session {session_id}] New Twilio Media Stream connection attempt")

    from app.core.connection_manager import connection_manager

    # Capacity check BEFORE accepting (Twilio requires we accept before reading
    # the start event, so we can't reuse ConnectionManager.connect()).
    if not connection_manager.has_capacity():
        logger.warning(f"[Session {session_id}] Twilio call rejected: at capacity")
        await websocket.close(code=1008, reason="Server at capacity")
        return

    session_start_time = None
    try:
        await websocket.accept()

        # Twilio sends a "connected" frame, then a "start" frame carrying the
        # streamSid and callSid the serializer needs. Read both before building
        # the pipeline. (Occasionally the very first frame is "start"; tolerate
        # either ordering by looping until we see it.)
        stream_sid = None
        call_sid = None
        for _ in range(3):
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")
            if event == "start":
                start = msg.get("start", {})
                stream_sid = start.get("streamSid")
                call_sid = start.get("callSid")
                break
            logger.debug(f"[Session {session_id}] Twilio pre-start event: {event}")

        if not stream_sid:
            logger.error(f"[Session {session_id}] No Twilio 'start' event received; closing")
            await websocket.close(code=1002, reason="Missing Twilio start event")
            return

        logger.info(
            f"[Session {session_id}] Twilio stream started "
            f"(streamSid={stream_sid}, callSid={call_sid})"
        )

        # Register the (already-accepted) session for capacity tracking.
        connection_manager.register(websocket, session_id)
        session_start_time = time.time()

        # ===== Imports (deferred to match websocket.py and avoid circular imports) =====
        from app.core.server import voice_assistant_server
        from app.core.voice_assistant import VoiceAssistant
        from pipecat.transports.websocket.fastapi import (
            FastAPIWebsocketTransport,
            FastAPIWebsocketParams,
        )
        from pipecat.serializers.twilio import TwilioFrameSerializer
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.audio.vad.vad_analyzer import VADParams

        full_config = voice_assistant_server.config or {}
        server_config = full_config.get("server", {})
        vad_config = server_config.get("vad", {})

        is_flux = full_config.get("stt", {}).get("provider") == "deepgram_flux"

        # ===== VAD (skipped on the Deepgram Flux path, which owns speech detection) =====
        vad_analyzer = None
        if is_flux:
            logger.info(f"[Session {session_id}] 🎤 VAD: SKIPPED (Deepgram Flux owns speech detection)")
        else:
            vad_params = VADParams(
                confidence=vad_config.get("confidence", 0.75),
                start_secs=vad_config.get("start_secs", 0.2),
                stop_secs=vad_config.get("stop_secs", 0.5),
                min_volume=vad_config.get("min_volume", 0.65),
            )
            vad_analyzer = SileroVADAnalyzer(params=vad_params)
            logger.info(
                f"[Session {session_id}] 🎤 VAD configured: confidence={vad_params.confidence}, "
                f"start_secs={vad_params.start_secs}, stop_secs={vad_params.stop_secs}"
            )

        # ===== SmartTurn v3 (skipped on Flux, which owns end-of-turn detection) =====
        smart_turn_config = server_config.get("smart_turn", {})
        turn_analyzer = None
        if is_flux:
            logger.info(f"[Session {session_id}] 🧠 SmartTurn v3: SKIPPED (Deepgram Flux owns turn detection)")
        elif smart_turn_config.get("enabled", False):
            try:
                from app.processors.logging_turn_analyzer import LoggingSmartTurnAnalyzer
                turn_analyzer = LoggingSmartTurnAnalyzer(
                    cpu_count=smart_turn_config.get("cpu_count", 1),
                    session_id=session_id,
                    stop_secs=smart_turn_config.get("timeout"),
                )
                logger.info(f"[Session {session_id}] 🧠 SmartTurn v3: ENABLED on user aggregator")
            except Exception as e:
                logger.error(f"[Session {session_id}] 🧠 SmartTurn v3 init failed: {e}")

        # ===== Twilio serializer =====
        # auto_hang_up (default True) requires account_sid + auth_token so the
        # serializer can end the call via Twilio's REST API on EndFrame.
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        # auto_hang_up requires account_sid + auth_token (+ call_sid); the
        # serializer raises if it's on without them. Disable it when creds are
        # missing so the call still connects (hang-up then relies on the caller).
        can_hang_up = bool(account_sid and auth_token and call_sid)
        if not can_hang_up:
            logger.warning(
                f"[Session {session_id}] Twilio auto hang-up disabled — missing "
                f"account_sid/auth_token/call_sid (call end will rely on the caller)"
            )
        serializer = TwilioFrameSerializer(
            stream_sid=stream_sid,
            call_sid=call_sid,
            account_sid=account_sid,
            auth_token=auth_token,
            params=TwilioFrameSerializer.InputParams(auto_hang_up=can_hang_up),
        )

        # ===== Transport =====
        # Keep the internal pipeline rates identical to the browser path; the
        # serializer resamples to/from Twilio's 8 kHz mu-law.
        transport_params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
        )
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=transport_params,
        )

        logger.info(
            f"[Session {session_id}] 📞 Twilio transport configured "
            f"(8 kHz mu-law <-> 16 kHz in / 24 kHz out)"
        )

        try:
            from app.services.cloudwatch_metrics import emit_session_start
            emit_session_start(session_id)
        except Exception as e:
            logger.debug(f"[Session {session_id}] CloudWatch start metrics skipped: {e}")

        voice_assistant = VoiceAssistant(voice_assistant_server.config)
        logger.info(f"[Session {session_id}] VoiceAssistant instance created (Twilio)")

        # Run the pipeline; blocks until the call ends.
        await voice_assistant.run(
            transport,
            handle_sigint=False,
            vad_analyzer=vad_analyzer,
            turn_analyzer=turn_analyzer,
        )

        logger.info(f"[Session {session_id}] Twilio session completed normally")

    except WebSocketDisconnect:
        logger.info(f"[Session {session_id}] Twilio client disconnected")
    except Exception as e:
        logger.error(f"[Session {session_id}] Exception in Twilio WebSocket endpoint: {e}")
        try:
            from app.services.cloudwatch_metrics import emit_error
            emit_error(type(e).__name__, session_id)
        except Exception:
            pass
    finally:
        if session_start_time is not None:
            try:
                from app.services.cloudwatch_metrics import emit_session_end_metrics
                emit_session_end_metrics(session_id, time.time() - session_start_time)
            except Exception as e:
                logger.debug(f"[Session {session_id}] CloudWatch metrics skipped: {e}")

        connection_manager.disconnect(session_id)
        logger.info(
            f"[Session {session_id}] Twilio connection closed. "
            f"Active sessions: {connection_manager.get_active_session_count()}"
        )
