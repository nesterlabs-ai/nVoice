# CLAUDE.md - NesterAIBot Project Guide

## Project Overview

**NesterVoiceAI** is a production-ready, real-time voice conversational assistant built by NesterLabs. It combines speech processing, emotion detection, knowledge retrieval (RAG), and dynamic visual UI generation (A2UI).

**Target latency:** 1-1.5 seconds end-to-end response time

## Architecture

```
Web Client (TypeScript/Vite)
    ↓ WebSocket
FastAPI + Pipecat Pipeline
    ↓
├─ STT (Deepgram Nova-3)
├─ LLM (Groq Llama-3.3-70b or Google Gemini)
├─ RAG (LightRAG with A2UI templates)
├─ TTS (Chatterbox/Resemble AI with emotion)
├─ Emotion Detection (MSP-PODCAST + Gemini hybrid)
└─ A2UI Visual Response Generation
```

## Quick Start

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add API keys
python app/main.py    # http://localhost:7860

# Frontend
cd client && npm install && npm run dev  # http://localhost:5173
```

## Directory Structure

```
app/
├── main.py                    # Entry point, FastAPI lifespan
├── core/
│   ├── server.py             # VoiceAssistantServer (WebSocket transport)
│   └── voice_assistant.py    # Pipeline orchestrator
├── api/
│   ├── routes.py             # HTTP endpoints (/connect, /health, /status)
│   └── websocket.py          # WebSocket handler with audio filters
├── services/
│   ├── stt.py                # Deepgram STT
│   ├── tts.py                # TTS wrapper
│   ├── chatterbox_tts.py     # Chatterbox with emotion control
│   ├── conversation.py       # LLM orchestration + function calling
│   ├── rag.py                # LightRAG integration
│   ├── msp_emotion_detector.py     # Audio emotion (wav2vec2)
│   ├── hybrid_emotion_detector.py  # Audio + text fusion
│   └── a2ui/                 # Visual response system
│       ├── orchestrator.py   # 3-tier template selection
│       ├── template_library.py
│       └── a2ui_rag_service.py
├── processors/               # Pipecat frame processors
│   ├── noise_handler.py           # Pattern-based noise detection + recovery
│   ├── minimal_prefilter.py       # Transcription-level noise filtering
│   ├── tone_aware_processor.py    # Emotion-based voice switching
│   ├── text_filter_processor.py   # Remove markdown for TTS
│   └── visual_hint_processor.py   # A2UI streaming
├── audio/
│   └── webrtc_ns_filter.py        # WebRTC noise suppression (Koala fallback)
└── config/
    ├── config.yaml           # Main configuration
    └── loader.py             # YAML loader with ${VAR} substitution

client/
├── src/
│   ├── app.ts               # Main application (VoiceScannerApp)
│   └── components/a2ui/     # A2UI template renderers
└── public/config.js         # Runtime configuration
```

## Configuration System

**Load order:** `.env` → `config.yaml` (with `${VAR}` substitution) → env overrides

### Key Environment Variables

```bash
# Required API Keys
DEEPGRAM_API_KEY=xxx          # STT
GROQ_API_KEY=xxx              # Primary LLM
GOOGLE_API_KEY=xxx            # Text sentiment + fallback LLM
RESEMBLE_API_KEY=xxx          # TTS
RESEMBLE_VOICE_UUID=xxx       # Voice ID
LIGHTRAG_API_KEY=xxx          # RAG
LIGHTRAG_BASE_URL=xxx         # LightRAG server (e.g., https://lightrag.nesterlabs.com/)

# Server
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=7860
PUBLIC_URL=https://yourdomain.com  # For WSS scheme
```

### config.yaml Key Sections

```yaml
stt:
  provider: "deepgram"
  config:
    model: "nova-3"
    endpointing: 1000      # ms to wait for complete thought

tts:
  provider: "chatterbox"
  config:
    voice: "neutral"       # Initial emotion state

rag:
  type: "lightrag"
  config:
    api_url: "${LIGHTRAG_BASE_URL}"  # Base URL, endpoints appended automatically
    mode: "mix"            # Entity-focused retrieval
    top_k: 10

a2ui:
  enabled: true
  config:
    tier_mode: "auto"      # Pattern + semantic matching
    default_template: "simple-card"

server:
  vad:
    confidence: 0.75       # Lower - noise filtered by processors
    start_secs: 0.4
    stop_secs: 0.8
  noise_handler:
    enabled: true
  prefilter:
    enabled: true
```

## LightRAG Integration

**Base URL:** Set via `LIGHTRAG_BASE_URL` env var (e.g., `https://lightrag.nesterlabs.com/`)

**Endpoints called by the service:**
- `POST /query/stream` - Streaming queries (line 281 in rag.py)
- `POST /query` - Non-streaming with A2UI (line 413)
- `GET /health` - Health check (line 524)

The URL is stripped of trailing slashes and endpoints are appended.

## A2UI System

**Purpose:** Generate dynamic visual UI components from voice queries

**3-Tier Selection:**
1. **Explicit** - User says "show me a contact card"
2. **Semantic** - Query intent matched via MiniLM embeddings
3. **Fallback** - Default "simple-card"

**Available Templates:** simple-card, template-grid, timeline, contact-card, comparison-chart, stats-flow-layout, team-flip-cards, service-hover-reveal, magazine-hero, faq-accordion, image-gallery, video-gallery

## Emotion Detection

**Hybrid system (70% audio + 30% text):**
- **Audio:** MSP-PODCAST wav2vec2 model → arousal, dominance, valence
- **Text:** Google Gemini sentiment analysis
- **Output:** neutral, excited, frustrated, sad → TTS voice tone

## Voice Pipeline Flow

```
Audio Input
    ↓
[Koala/WebRTC Noise Suppression] ← Audio-level filtering
    ↓
[Silero VAD] ← Voice activity detection (conf=0.75)
    ↓
[NoiseHandlerProcessor] ← Pattern detection, false start recovery
    ↓
[Deepgram STT Nova-3]
    ↓
[MinimalPreFilter] ← Drop low-confidence, noise markers
    ↓
[ToneAwareProcessor] ← Emotion detection (MSP-PODCAST + Gemini)
    ↓
[LLM (Groq)] → [call_rag_system() if needed]
    ↓
[TTS (Chatterbox)] → Audio Output
```

## Noise Handling (Multi-Layer Approach)

**Multi-layer approach:**
1. **Audio Filter:** Koala (preferred) or WebRTC (fallback) - removes background noise
2. **VAD:** More permissive (0.75 confidence) - lets processors handle filtering
3. **NoiseHandler:** Detects false starts, enters 2s recovery mode after 3 consecutive
4. **PreFilter:** Drops transcriptions with <50% confidence or noise markers

**Config in `config.yaml`:**
```yaml
server:
  vad:
    confidence: 0.75       # Lower - noise filtered at processor level
    start_secs: 0.4
    stop_secs: 0.8
  noise_handler:
    enabled: true
    max_false_starts: 3
    recovery_delay: 2.0
  prefilter:
    enabled: true
    confidence_threshold: 0.5
```

## Deployment

**Target:** AWS Lightsail ($7/month: 1GB RAM, 2 vCPU)

**Stack:**
- Docker + Docker Compose
- Caddy (reverse proxy, auto HTTPS)
- CPU-only PyTorch (saves ~1.7GB)
- 2GB swap for burst handling

**CI/CD:** GitHub Actions → GHCR → SSH deploy to Lightsail

**Ports:** 22 (SSH), 80/443 (HTTP/S), 7860 (API), 8765 (WebSocket)

## Common Tasks

### Update LightRAG URL
Edit `app/config/config.yaml` line 49:
```yaml
api_url: "${LIGHTRAG_BASE_URL}"
```
Then set `LIGHTRAG_BASE_URL` in `.env` or deployment secrets.

### Add new A2UI template
1. Add template definition to `app/services/a2ui/template_library.py`
2. Add keywords to `orchestrator.py` tier detection
3. Add renderer in `client/src/components/a2ui/A2UIRenderer.ts`

### Test emotion detection
```python
from app.services.msp_emotion_detector import get_msp_detector
detector = get_msp_detector()
emotion = detector.detect_emotion(audio_bytes)
```

## Key Design Decisions

1. **CPU-only PyTorch** - Fits 4GB RAM constraint
2. **INT8 quantization** - MSP-PODCAST model optimization
3. **Silero VAD over Deepgram VAD** - Better local control
4. **Streaming everything** - Minimizes perceived latency
5. **Connection pooling** - Shared httpx client for LightRAG
6. **Multi-layer noise handling** - Strict VAD + NoiseHandler + PreFilter processors
7. **WebRTC fallback** - Free noise suppression when Koala unavailable

## Known Issues

- AIC Speech Enhancement disabled (SDK version mismatch)
- MSP-PODCAST model may fail with newer transformers (uses text fallback)
- 4GB RAM requires swap + CPU-only torch
- Koala requires API key - WebRTC used as fallback
