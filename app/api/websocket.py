"""
WebSocket endpoint handler for FastAPI.

This module provides the WebSocket endpoint for real-time voice communication
supporting multiple concurrent user connections.
"""

import uuid
from fastapi import WebSocket
from loguru import logger


async def websocket_endpoint(websocket: WebSocket) -> None:
    """FastAPI WebSocket endpoint for Voice Assistant with concurrent connection support.

    This endpoint handles multiple WebSocket connections simultaneously.
    Each connection gets its own VoiceAssistant instance and pipeline.

    Args:
        websocket: FastAPI WebSocket connection
    """
    session_id = str(uuid.uuid4())[:8]
    logger.info(f"[Session {session_id}] New WebSocket connection")

    try:
        # Import here to avoid circular imports
        from app.core.server import voice_assistant_server
        from app.core.voice_assistant import VoiceAssistant
        from pipecat.transports.network.fastapi_websocket import (
            FastAPIWebsocketTransport,
            FastAPIWebsocketParams,
        )
        from pipecat.serializers.protobuf import ProtobufFrameSerializer
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.audio.vad.vad_analyzer import VADParams

        # Get VAD configuration
        server_config = voice_assistant_server.server_config
        vad_config = server_config.get("vad", {})
        vad_params = VADParams(
            confidence=vad_config.get("confidence", 0.7),
            start_secs=vad_config.get("start_secs", 0.2),
            stop_secs=vad_config.get("stop_secs", 0.8),
            min_volume=vad_config.get("min_volume", 0.6),
        )
        vad_analyzer = SileroVADAnalyzer(params=vad_params)

        logger.info(
            f"[Session {session_id}] VAD configured: confidence={vad_params.confidence}, "
            f"start_secs={vad_params.start_secs}, stop_secs={vad_params.stop_secs}"
        )

        # Create transport parameters for this connection
        transport_params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=vad_analyzer,
            vad_audio_passthrough=True,
            serializer=ProtobufFrameSerializer(),
        )

        # Create transport for this specific connection
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=transport_params,
        )

        # Create dedicated VoiceAssistant instance for this session
        voice_assistant = VoiceAssistant(voice_assistant_server.config)
        logger.info(f"[Session {session_id}] VoiceAssistant instance created")

        # Run the voice assistant pipeline for this connection
        # This will block until the connection closes
        await voice_assistant.run(transport, handle_sigint=False)

        logger.info(f"[Session {session_id}] Session completed normally")

    except Exception as e:
        logger.error(f"[Session {session_id}] Exception in WebSocket endpoint: {e}")
    finally:
        logger.info(f"[Session {session_id}] Connection closed")
