"""
FastAPI routes for the Voice Assistant API.

This module defines the HTTP endpoints for:
- WebSocket connection management
- Health checks and status
- Configuration endpoints
"""

import os
from typing import Any, Dict

from fastapi import APIRouter, Request
from loguru import logger

router = APIRouter(tags=["voice-assistant"])


def get_server_instance():
    """Get the global server instance (lazy import to avoid circular imports)."""
    from app.core.server import voice_assistant_server
    return voice_assistant_server


@router.post("/connect")
async def connect(request: Request) -> Dict[str, Any]:
    """Get WebSocket connection URL.

    Returns the appropriate WebSocket URL based on server configuration
    and deployment environment (development vs production).

    Returns:
        Dict containing the WebSocket URL
    """
    server = get_server_instance()
    server_mode = os.getenv("WEBSOCKET_SERVER", "fast_api")
    public_url = os.getenv("PUBLIC_URL", "")

    if public_url:
        # Production: Use configured public URL
        ws_scheme = "wss" if public_url.startswith("https") else "ws"
        public_host = public_url.replace("https://", "").replace("http://", "").rstrip("/")
        ws_url = f"{ws_scheme}://{public_host}/ws"
    elif server_mode == "websocket_server":
        # Development: Standalone WebSocket server
        host = server.server_config.get("websocket_host", "localhost")
        port = server.server_config.get("websocket_port", 8765)
        ws_url = f"ws://{host}:{port}"
    else:
        # Development: FastAPI WebSocket endpoint
        host = server.server_config.get("fastapi_host", "localhost")
        port = server.server_config.get("fastapi_port", 7860)
        ws_url = f"ws://{host}:{port}/ws"

    logger.info(f"Returning WebSocket URL: {ws_url} (mode: {server_mode})")
    return {"ws_url": ws_url}


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get server and voice assistant status.

    Returns:
        Dict containing server status and configuration
    """
    server = get_server_instance()
    return server.get_server_status()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for load balancers and monitoring.

    Returns:
        Dict with health status
    """
    return {"status": "healthy"}


@router.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint with API information.

    Returns:
        Dict with API information
    """
    return {
        "name": "NesterVoiceAI",
        "version": "1.0.0",
        "description": "Voice Assistant API with RAG capabilities",
        "docs": "/docs",
    }
