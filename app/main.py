"""
Main entry point for the NesterVoiceAI application.

This module initializes and runs the Voice Assistant server with both
FastAPI HTTP endpoints and WebSocket server for real-time voice communication.
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Reconfigure loguru BEFORE importing app modules (they log at import time).
# The default sink is a SYNCHRONOUS stderr write at DEBUG level: during long
# bot answers the per-word debug flood blocked the asyncio event loop whenever
# the terminal fell behind, stalling WebSocket audio receive (observed live:
# Flux "No audio received for 500 ms" watchdogs, mic frames at half rate, then
# a burst of queued turns interrupting the bot). enqueue=True moves writes to a
# background thread; INFO default kills the flood. LOG_LEVEL=DEBUG re-enables.
logger.remove()
logger.add(sys.stderr, level=os.getenv("LOG_LEVEL", "INFO"), enqueue=True)

# Dedicated conversation transcript: records logged via
# logger.bind(transcript=True) (see STT user turns and SubtitleSyncProcessor
# bot turns) land BOTH on the console and in logs/transcript.log, giving a
# clean spoken-dialogue record per run without the pipeline noise.
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/transcript.log",
    level="INFO",
    enqueue=True,
    rotation="10 MB",
    retention=10,
    filter=lambda record: record["extra"].get("transcript", False),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
)

from app.api.routes import router
from app.api.websocket import websocket_endpoint
from app.api.twilio_websocket import twilio_websocket_endpoint
from app.config.loader import get_assistant_config
from app.core.server import voice_assistant_server


def _prewarm_semantic_selector():
    """Pre-warm the semantic template selector model.

    Loads the Sentence Transformer model (~80MB) and pre-computes template
    embeddings at startup, avoiding a 4-second delay on the first A2UI query.
    """
    try:
        from app.services.a2ui.semantic_selector import get_semantic_selector, is_semantic_available

        if is_semantic_available():
            logger.info("🧠 Pre-warming semantic template selector...")
            selector = get_semantic_selector()
            if selector:
                logger.info("✅ Semantic template selector ready")
            else:
                logger.warning("⚠️ Semantic selector initialization returned None")
        else:
            logger.info("📋 Semantic selector not available (sentence-transformers not installed)")
    except ImportError:
        logger.info("📋 Semantic selector not available (module not found)")
    except Exception as e:
        logger.warning(f"⚠️ Failed to pre-warm semantic selector: {e}")
        logger.warning("   A2UI will fall back to keyword-based template selection")


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

            # Log audio filter configuration
            noise_config = config.get("noise_suppression", {})
            aic_config = config.get("speech_enhancement", {})

            logger.info("=" * 60)
            logger.info("🎙️  AUDIO FILTER CONFIGURATION")
            logger.info("=" * 60)

            # Noise suppression status
            if noise_config.get("enabled", False):
                provider = noise_config.get("provider", "none")
                logger.info(f"🔇 Noise Suppression: {provider.upper()} ENABLED")
            else:
                logger.info("🔇 Noise Suppression: DISABLED (raw audio input)")

            # AIC status
            if aic_config.get("enabled", False):
                logger.info(f"🔊 AIC Speech Enhancement: ENABLED")
            else:
                logger.info(f"🔊 AIC Speech Enhancement: DISABLED")

            # SmartTurn v3 status - ML-based end-of-turn detection
            server_config = config.get("server", {})
            smart_turn_config = server_config.get("smart_turn", {})
            if smart_turn_config.get("enabled", False):
                cpu_count = smart_turn_config.get("cpu_count", 1)
                timeout = smart_turn_config.get("timeout", 0.5)
                logger.info(f"🧠 SmartTurn v3 End-of-Turn Detection: ENABLED")
                logger.info(f"   ├─ ONNX model: LocalSmartTurnAnalyzerV3")
                logger.info(f"   ├─ CPU threads: {cpu_count}")
                logger.info(f"   ├─ Turn timeout: {timeout}s")
                logger.info(f"   └─ Integration: user-aggregator turn strategy (pipecat 1.x)")

                # Check if SmartTurn v3 module is available
                try:
                    from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
                    logger.info(f"   ✅ SmartTurn v3 module loaded successfully")
                except ImportError as e:
                    logger.warning(f"   ⚠️ SmartTurn v3 module not available: {e}")
                    logger.warning(f"   💡 Run: pip install 'pipecat-ai[local-smart-turn-v3]'")
            else:
                logger.info(f"🧠 SmartTurn v3: DISABLED (using transcription-based detection)")

            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    # Pre-warm semantic template selector in background thread (avoids blocking startup)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.submit(_prewarm_semantic_selector)

    # Pre-warm the MSP-PODCAST emotion model (~661MB, ~4.5s load). It's a
    # process-global singleton, but previously loaded lazily inside the FIRST
    # session's pipeline creation — delaying that caller's greeting by ~4.5s.
    # Warming it here means session startup only does a cached lookup.
    emotion_enabled = (voice_assistant_server.config or {}).get("server", {}).get(
        "emotion_detection_enabled", True
    )
    if emotion_enabled:
        try:
            from app.services.msp_emotion_detector import init_msp_detector
            asyncio.create_task(init_msp_detector())
            logger.info("🎭 MSP-PODCAST emotion model pre-warm started (background)")
        except Exception as e:
            logger.warning(f"⚠️ MSP pre-warm failed (will lazy-load per session): {e}")

    # Pre-warm the CloudWatch boto3 client: lazily creating it inside the first
    # session's setup path cost ~2.2s of connect→greeting time. It's sync, so
    # warm it off-loop.
    try:
        from app.services.cloudwatch_metrics import _get_client
        asyncio.create_task(asyncio.to_thread(_get_client))
        logger.info("📊 CloudWatch client pre-warm started (background)")
    except Exception as e:
        logger.debug(f"CloudWatch pre-warm skipped: {e}")

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

    # Twilio Media Streams WebSocket endpoint (inbound phone calls)
    app.add_api_websocket_route("/twilio/ws", twilio_websocket_endpoint)

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
