"""
WebSocket endpoint handler for FastAPI.

This module provides the WebSocket endpoint for real-time voice communication
supporting multiple concurrent user connections with capacity management.

Features (strict VAD-style noise handling):
- Strict Silero VAD (confidence=0.9, min_volume=0.8)
- NoiseHandler processor for false start detection
- MinimalPreFilter for transcription-level noise filtering
- Emotion detection via MSP-PODCAST + Gemini
"""

import uuid
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


async def websocket_endpoint(websocket: WebSocket) -> None:
    """FastAPI WebSocket endpoint for Voice Assistant with concurrent connection support.

    This endpoint handles multiple WebSocket connections simultaneously with:
    - Connection capacity limits (20 max for Lightsail)
    - Session tracking and management
    - Heartbeat monitoring for stale connections
    - Isolated VoiceAssistant instance per connection
    - strict VAD-style noise handling (strict VAD + processors, no audio filter)

    Args:
        websocket: FastAPI WebSocket connection
    """
    session_id = str(uuid.uuid4())[:8]
    logger.info(f"[Session {session_id}] New WebSocket connection attempt")

    # Import connection manager
    from app.core.connection_manager import connection_manager

    # Try to accept connection (may reject if at capacity)
    await connection_manager.connect(websocket, session_id)

    # If we reach here, connection was accepted
    try:
        # Import here to avoid circular imports
        from app.core.server import voice_assistant_server
        from app.core.voice_assistant import VoiceAssistant
        from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport
        from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
        from pipecat.serializers.protobuf import ProtobufFrameSerializer
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.audio.vad.vad_analyzer import VADParams
        # Get configuration from config.yaml
        server_config = voice_assistant_server.server_config
        vad_config = server_config.get("vad", {})

        # Log raw config for debugging
        logger.info(f"[Session {session_id}] 📋 Raw vad_config: {vad_config}")

        # ===== VAD CONFIGURATION (Matching strict VAD) =====
        # strict VAD uses strict VAD + NoiseHandler + PreFilter - NO audio_in_filter
        # This approach is proven to work well for noise handling
        vad_params = VADParams(
            confidence=vad_config.get("confidence", 0.9),      # STRICT - matches strict VAD
            start_secs=vad_config.get("start_secs", 0.3),      # Quick start once confidence met
            stop_secs=vad_config.get("stop_secs", 1.2),        # LONGER - 1.2s silence to confirm end
            min_volume=vad_config.get("min_volume", 0.8),      # STRICT - matches strict VAD
        )
        vad_analyzer = SileroVADAnalyzer(params=vad_params)

        logger.info(
            f"[Session {session_id}] 🎤 VAD configured (strict VAD-style): confidence={vad_params.confidence}, "
            f"start_secs={vad_params.start_secs}, stop_secs={vad_params.stop_secs}, "
            f"min_volume={vad_params.min_volume}"
        )

        # Create transport parameters for this connection
        # NOTE: Matching strict VAD's simpler configuration - no deprecated params, no interruption_strategy
        # strict VAD relies on strict VAD + NoiseHandler + PreFilter instead of transport-level filtering
        transport_params = FastAPIWebsocketParams(
            serializer=ProtobufFrameSerializer(),
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=vad_analyzer,
            # Removed deprecated: vad_enabled, vad_audio_passthrough
            # Removed: audio_in_filter (strict VAD doesn't use it - relies on strict VAD)
            # Removed: interruption_strategy (handled in PipelineParams, not transport)
        )

        logger.info(f"[Session {session_id}] 🔧 Transport configured (strict VAD-style: strict VAD, no audio filter)")

        # Create transport for this specific connection
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=transport_params,
        )

        # Create dedicated VoiceAssistant instance for this session
        voice_assistant = VoiceAssistant(voice_assistant_server.config)
        logger.info(f"[Session {session_id}] VoiceAssistant instance created")

        # Log complete audio processing pipeline (strict VAD-style)
        logger.info(
            f"[Session {session_id}] 📊 AUDIO PIPELINE SUMMARY (strict VAD-style):\n"
            f"  ┌─ Input: Microphone\n"
            f"  ├─ VAD: Silero STRICT (conf={vad_params.confidence}, start={vad_params.start_secs}s, stop={vad_params.stop_secs}s, vol={vad_params.min_volume})\n"
            f"  ├─ NoiseHandler: Pattern detection + recovery mode\n"
            f"  ├─ STT: Deepgram Nova-3\n"
            f"  ├─ PreFilter: Confidence threshold + noise markers\n"
            f"  ├─ Emotion: MSP-PODCAST + Gemini (hybrid)\n"
            f"  ├─ LLM: Groq Llama-3.3-70b\n"
            f"  └─ TTS: Chatterbox (24kHz, emotion-aware)"
        )

        # Run the voice assistant pipeline for this connection
        # This will block until the connection closes
        await voice_assistant.run(transport, handle_sigint=False)

        logger.info(f"[Session {session_id}] Session completed normally")

    except WebSocketDisconnect:
        logger.info(f"[Session {session_id}] Client disconnected")
    except Exception as e:
        logger.error(f"[Session {session_id}] Exception in WebSocket endpoint: {e}")
    finally:
        # Clean up connection in manager
        connection_manager.disconnect(session_id)
        logger.info(
            f"[Session {session_id}] Connection closed. "
            f"Active sessions: {connection_manager.get_active_session_count()}"
        )
