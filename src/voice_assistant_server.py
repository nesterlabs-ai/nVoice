"""Voice Assistant Server class for handling WebSocket connections."""

import asyncio
import os
from typing import Dict, Any

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.network.websocket_server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

from src.core.voice_assistant import VoiceAssistant


class VoiceAssistantServer:
    """Complete Voice Assistant server with FastAPI and WebSocket support.
    
    Supports multiple connect/disconnect cycles without server restart.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Voice Assistant server.
        
        Args:
            config: Configuration dictionary for the voice assistant and server
        """
        self.config = config or {}
        # Get server config with default values if not present
        self.server_config = self.config.get("server", {})
        self._apply_server_defaults()
        self.voice_assistant = None
        self.websocket_server_transport = None
        self._running = True

        logger.info("Initialized Voice Assistant Server")

    def _apply_server_defaults(self):
        """Apply default server configuration values."""
        defaults = {
            "fastapi_host": os.getenv("FASTAPI_HOST", "0.0.0.0"),
            "fastapi_port": int(os.getenv("FASTAPI_PORT", "7860")),
            "websocket_host": os.getenv("WEBSOCKET_HOST", "localhost"),
            "websocket_port": int(os.getenv("WEBSOCKET_PORT", "8765")),
            "session_timeout": int(os.getenv("SESSION_TIMEOUT", "180")),
            "audio_in_enabled": os.getenv("AUDIO_IN_ENABLED", "true").lower() == "true",
            "audio_out_enabled": os.getenv("AUDIO_OUT_ENABLED", "true").lower() == "true",
            "add_wav_header": os.getenv("ADD_WAV_HEADER", "false").lower() == "true",
            "vad": {}
        }

        # Apply defaults for missing keys
        for key, value in defaults.items():
            if key not in self.server_config:
                self.server_config[key] = value

    def create_websocket_transport(self) -> WebsocketServerTransport:
        """Create and configure the standalone WebSocket transport.
        
        Returns:
            Configured WebSocket transport for standalone server
        """
        # Get server configuration with defaults
        host = self.server_config.get("websocket_host", "localhost")
        port = self.server_config.get("websocket_port", 8765)
        session_timeout = self.server_config.get("session_timeout", 60 * 3)  # 3 minutes
        audio_in_enabled = self.server_config.get("audio_in_enabled", True)
        audio_out_enabled = self.server_config.get("audio_out_enabled", True)
        add_wav_header = self.server_config.get("add_wav_header", False)

        # Create VAD analyzer with noise-resistant settings
        from pipecat.audio.vad.vad_analyzer import VADParams
        
        vad_config = self.server_config.get("vad", {})
        # Apply noise-resistant defaults for background noise filtering
        vad_params = VADParams(
            confidence=vad_config.get("confidence", 0.85),      # Higher = stricter (default: 0.7)
            start_secs=vad_config.get("start_secs", 0.3),       # Longer speech needed to start
            stop_secs=vad_config.get("stop_secs", 0.6),         # Faster stop on silence
            min_volume=vad_config.get("min_volume", 0.75),      # Higher volume threshold
        )
        vad_analyzer = SileroVADAnalyzer(params=vad_params)
        logger.info(f"VAD configured: confidence={vad_params.confidence}, min_volume={vad_params.min_volume}, start_secs={vad_params.start_secs}")

        # Create transport parameters
        # Note: host and port must be passed directly to WebsocketServerTransport constructor,
        # not via WebsocketServerParams (which doesn't use them)
        transport_params = WebsocketServerParams(
            serializer=ProtobufFrameSerializer(),
            audio_in_enabled=audio_in_enabled,
            audio_out_enabled=audio_out_enabled,
            add_wav_header=add_wav_header,
            vad_analyzer=vad_analyzer,
            session_timeout=session_timeout,
        )

        self.websocket_server_transport = WebsocketServerTransport(
            params=transport_params,
            host=host,
            port=port,
        )

        logger.info(f"Created standalone WebSocket transport on {host}:{port}")
        return self.websocket_server_transport

    async def run_websocket_server(self) -> None:
        """Run the standalone WebSocket server with reconnection support.
        
        This method runs in a loop to allow multiple client connections
        without needing to restart the server.
        """
        logger.info("Starting standalone Voice Assistant WebSocket Server...")

        while self._running:
            try:
                # Create fresh voice assistant for each session
                voice_assistant = VoiceAssistant(self.config)

                # Create fresh transport for each session
                transport = self.create_websocket_transport()

                # Note: Transport handlers are set up inside voice_assistant.run()
                # Don't set up duplicate handlers here

                logger.info("Voice Assistant ready for new connection...")
                
                # Run the voice assistant with the transport
                await voice_assistant.run(transport, handle_sigint=False)

            except asyncio.CancelledError:
                logger.info("WebSocket server task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket Server session: {e}")
                # Small delay before accepting new connections
                await asyncio.sleep(1)
                logger.info("Restarting voice assistant for new connections...")
                continue
            
            # Small delay before accepting new connections after clean disconnect
            logger.info("Session ended, ready for new connection...")
            await asyncio.sleep(0.5)


    def get_server_status(self) -> Dict[str, Any]:
        """Get the status of the server and voice assistant."""
        status = {
            "server": {
                "mode": os.getenv("WEBSOCKET_SERVER", "fast_api"),
                "config": self.server_config
            }
        }

        if hasattr(self, 'voice_assistant') and self.voice_assistant:
            if hasattr(self.voice_assistant, 'get_service_status'):
                status["voice_assistant"] = self.voice_assistant.get_service_status()

        return status
