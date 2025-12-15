"""
WebSocket endpoint handler for FastAPI.

This module provides the WebSocket endpoint for real-time voice communication
when running in FastAPI mode (alternative to standalone WebSocket server).
"""

from fastapi import WebSocket
from loguru import logger


async def websocket_endpoint(websocket: WebSocket) -> None:
    """FastAPI WebSocket endpoint for Voice Assistant.

    This endpoint handles WebSocket connections for the voice assistant
    when running in FastAPI mode. For production, the standalone WebSocket
    server (port 8765) is typically used instead.

    Args:
        websocket: FastAPI WebSocket connection
    """
    await websocket.accept()
    logger.info("Voice Assistant WebSocket connection accepted")

    try:
        # Import here to avoid circular imports
        from app.core.server import voice_assistant_server
        from app.core.voice_assistant import VoiceAssistant

        # Create voice assistant for this connection
        voice_assistant = VoiceAssistant(voice_assistant_server.config)
        logger.info("Voice Assistant WebSocket connection established")

        # Keep connection alive and handle messages
        while True:
            try:
                message = await websocket.receive_text()
                logger.debug(f"Received message: {message[:100]}...")
                # Message processing would be handled by the voice assistant pipeline
            except Exception as e:
                logger.error(f"Error in WebSocket message handling: {e}")
                break

    except Exception as e:
        logger.error(f"Exception in Voice Assistant WebSocket endpoint: {e}")
    finally:
        logger.info("Voice Assistant WebSocket connection closed")
