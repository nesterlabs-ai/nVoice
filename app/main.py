"""
Main entry point for the NesterVoiceAI application.

This module initializes and runs the Voice Assistant server with both
FastAPI HTTP endpoints and WebSocket server for real-time voice communication.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes import router
from app.api.websocket import websocket_endpoint
from app.config.loader import get_assistant_config
from app.core.server import voice_assistant_server


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("Starting NesterVoiceAI application...")

    # Load configuration if not already loaded
    if not voice_assistant_server.config:
        try:
            config = get_assistant_config()
            voice_assistant_server.config = config
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    yield
    logger.info("Shutting down NesterVoiceAI application...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="NesterVoiceAI",
        description="Voice Assistant API with RAG capabilities",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router)

    # WebSocket endpoint (emotion detection now handled by Hume AI server-side)
    app.add_api_websocket_route("/ws", websocket_endpoint)

    return app


# Create FastAPI app instance
app = create_app()


async def main():
    """Main function to run the Voice Assistant server."""
    server_mode = os.getenv("WEBSOCKET_SERVER", "fast_api")

    # Load configuration
    try:
        config = get_assistant_config()
        voice_assistant_server.config = config
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    tasks = []

    try:
        if server_mode == "websocket_server":
            logger.info("Starting in WebSocket server mode")
            tasks.append(voice_assistant_server.run_websocket_server())
        else:
            logger.info("Starting in FastAPI mode")

        # Start FastAPI server
        fastapi_config = uvicorn.Config(
            app,
            host=config.get("server", {}).get("fastapi_host", "0.0.0.0"),
            port=config.get("server", {}).get("fastapi_port", 7860),
        )
        server = uvicorn.Server(fastapi_config)
        tasks.append(server.serve())

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    except asyncio.CancelledError:
        logger.info("Server tasks cancelled")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
