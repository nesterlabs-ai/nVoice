# ConversationalBot - Voice RAG Assistant

A real-time voice conversational assistant that combines speech-to-text, text-to-speech, RAG (Retrieval-Augmented Generation), and LLM capabilities for natural voice interactions.

**Developed and open-sourced by [NesterLabs](https://nesterlabs.com)**

> **Latest Update**: Deployed with automated CI/CD pipeline using GitHub Container Registry (GHCR) for containerized deployments.

Optimized for ultra-low latency with response times of 1-1.5 seconds for seamless real-time conversations.

## 🎯 Features

- **Real-time Voice Conversation**: WebSocket-based audio streaming optimized for 1-1.5 second response times
- **Speech-to-Text**: Supports Deepgram and Whisper for accurate transcription
- **Text-to-Speech**: ElevenLabs integration for natural voice synthesis
- **Hinglish Support**: Native support for Hindi-English mixed language conversations
- **RAG Integration**: Knowledge retrieval system for context-aware responses (dummy implementation included)
- **LLM Integration**: Google LLM for intelligent conversation management
- **Latency Monitoring**: Built-in performance analysis and metrics
- **Flexible Deployment**: FastAPI server or standalone WebSocket server modes
- **Function Registration**: Easy registration of new functions as RAG tools

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Python Client  │    │  Mobile Client  │
│   (HTML/JS)     │    │                 │    │   (Future)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                        ┌─────────────────┐
                        │  WebSocket API  │
                        │   (FastAPI)     │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │ Voice Assistant │
                        │  Orchestrator   │
                        └─────────────────┘
                                 │
    ┌────────────────────────────┼────────────────────────────┐
    │                            │                            │
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│   STT   │    │   TTS   │    │   RAG   │    │   LLM   │    │ Latency │
│Service  │    │Service  │    │Service  │    │Manager  │    │Analyzer │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

> 📖 For detailed architecture documentation, see [docs/architecture/SYSTEM_ARCHITECTURE.md](docs/architecture/SYSTEM_ARCHITECTURE.md)

## 📁 Project Structure

```
nester-ai-voice-assistant/
├── app/              # Main application code
├── client/           # Frontend web application
├── data/             # Knowledge base data
├── docs/             # Documentation
├── deployment/       # Docker & AWS deployment configs
├── scripts/          # Utility scripts
└── .github/          # CI/CD workflows
```

> 📖 For complete project structure, see [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

## 🔄 CI/CD Pipeline

This project includes automated CI/CD pipelines for:
- **Automated Docker Image Building**: Container images are built automatically on every push
- **Automated Deployment**: Changes are automatically deployed to AWS Lightsail
- **GitHub Actions**: Workflows handle building and deployment processes

The CI/CD pipeline is configured in `.github/workflows/deploy.yml` and automatically triggers on pushes to the main branch.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Required API keys:
  - Deepgram API key (for speech-to-text and text-to-speech)
  - Google Gemini API key (for LLM)

### Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd ConversationalBot
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:
Copy the example file and configure your API keys:
```bash
cp env.example .env
```
Then edit `.env` with your actual API keys:
```bash
# Required API Keys
DEEPGRAM_API_KEY=your_deepgram_api_key
GOOGLE_API_KEY=your_google_gemini_api_key

# Optional: Server Configuration (defaults provided)
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=7860

# Optional: RAG Configuration (LightRAG)
LIGHTRAG_BASE_URL=your_lightrag_service_url
LIGHTRAG_MODE=mix  # Options: local, global, hybrid, mix
LIGHTRAG_TOP_K=6
```

4. **Run the server**:
```bash
# Set PYTHONPATH and run
export PYTHONPATH=/path/to/nester-ai-bot-opensource
python app/main.py
```

5. **Test the connection**:
See the [Client README](client/README.md) for detailed instructions on running and using the client applications.

## 📁 Project Structure

```
nester-ai-bot-opensource/
├── app/
│   ├── main.py                  # Main application entry point
│   ├── api/
│   │   ├── routes.py            # HTTP API routes
│   │   └── websocket.py         # WebSocket endpoint handler
│   ├── config/
│   │   ├── config.yaml          # Main configuration file
│   │   └── loader.py            # Configuration management
│   ├── core/
│   │   ├── voice_assistant.py   # Main orchestrator
│   │   ├── server.py            # Server instance
│   │   └── connection_manager.py # WebSocket session management
│   ├── services/
│   │   ├── stt.py               # Speech-to-Text service (Deepgram)
│   │   ├── tts.py               # Text-to-Speech service (Deepgram)
│   │   ├── rag.py               # RAG service (LightRAG)
│   │   ├── conversation.py      # LLM & conversation flow (Gemini)
│   │   ├── input_analyzer.py    # Input processing & pattern detection
│   │   └── latency.py           # Performance monitoring
│   ├── models/
│   │   └── schemas.py           # Data models and schemas
│   └── utils/
│       └── helpers.py           # Utility functions
├── client/
│   ├── index.html               # Web test client
│   ├── src/                     # React client source
│   └── package.json             # Client dependencies
├── scripts/
│   └── ingest_documents.py      # Document ingestion script
├── tests/                       # Test files
├── docs/                        # Documentation
├── requirements.txt             # Python dependencies
├── env.example                  # Environment variables template
└── README.md
```

## ⚙️ Configuration

The system uses a YAML configuration file (`app/config/config.yaml`) with environment variable substitution:

```yaml
# Speech-to-Text Configuration
stt:
  provider: "deepgram"
  config:
    api_key: "${DEEPGRAM_API_KEY}"
    model: "nova-2"
    smart_format: true
    endpointing: 300

# Text-to-Speech Configuration
tts:
  provider: "deepgram"
  config:
    api_key: "${DEEPGRAM_API_KEY}"
    model: "aura-2-athena-en"
    encoding: "linear16"
    sample_rate: 24000

# LLM Configuration
conversation:
  llm:
    provider: "google"
    model: "gemini-2.5-flash"
    api_key: "${GOOGLE_API_KEY}"

# RAG Configuration
rag:
  type: "lightrag"
  config:
    base_url: "${LIGHTRAG_BASE_URL}"
    mode: "mix"
    top_k: 6
    timeout: 20
```

## 🔧 Usage

### Client Usage

For detailed instructions on using the web client, please refer to the [Client README](client/README.md).

### API Endpoints

- **WebSocket**: `ws://localhost:7860/ws`
- **Connect**: `POST /connect` - Returns WebSocket URL and configuration
- **Health**: `GET /health` - Health check endpoint
- **Status**: `GET /status` - Server and service status

## 🏃‍♂️ Server Mode

The server runs in **FastAPI mode** which provides:
- HTTP API endpoints for status and health checks
- WebSocket endpoint at `/ws` for real-time voice communication
- CORS support for cross-origin requests
- Connection management for multiple concurrent sessions (max 20)
- Automatic session cleanup and heartbeat monitoring
- Recommended for production use

## 🎛️ Services

### Speech-to-Text Service
- **Provider**: Deepgram Nova-2
- **Features**: Real-time transcription, smart formatting, automatic punctuation
- **Configuration**: Model selection, endpointing settings (300ms)
- **Optimized**: Low-latency streaming for real-time conversations

### Text-to-Speech Service
- **Provider**: Deepgram Aura
- **Model**: aura-2-athena-en (natural female voice)
- **Features**: Ultra-low latency, natural voice synthesis
- **Configuration**: 24kHz sample rate, linear16 encoding
- **Performance**: ~1 second TTFB (Time To First Byte)

### RAG Service
- **Provider**: LightRAG (AWS hosted)
- **Features**: Graph-based knowledge retrieval with local, global, and hybrid search modes
- **Mode**: Mix mode (combines all search strategies)
- **Configuration**: Top-K=6, 20-second timeout
- **Function Integration**: Registered as LLM function call (`call_rag_system`) for dynamic knowledge retrieval

### Conversation Manager
- **LLM**: Google Gemini 2.5 Flash
- **Features**: Context management, conversation flow, function calling
- **Functions**:
  - `call_rag_system` - Knowledge retrieval
  - `end_conversation` - Graceful conversation termination with farewell
- **Optimization**: Streaming responses for low latency

### Latency Analyzer
- **Metrics**: STT, LLM, RAG, and TTS processing times
- **Target**: 1-1.5 second total response time
- **Monitoring**: Real-time TTFB tracking and performance analysis
- **Reporting**: Statistical analysis with component-level breakdowns

## 🌐 Conversation Features

### Automatic Greeting
- Bot greets users when they first speak: *"Hello! I'm the Nesterlabs voice assistant. How can I help you today?"*
- Configured via system prompt GREETING PROTOCOL

### Automatic Conversation Ending
- **Function**: `end_conversation`
- **Triggers**: goodbye, bye, end call, see you, etc.
- **Behavior**:
  1. LLM detects farewell intent via function calling
  2. Bot speaks: *"Goodbye! Thank you for visiting Nesterlabs."*
  3. Waits 3.5 seconds for TTS to complete
  4. Automatically disconnects WebSocket session
- **No manual intervention required** - fully automated

### Hinglish Support
- **Automatic Detection**: Understands both English and Hinglish inputs
- **Natural Responses**: Responds in the same language style as the user
- **Translation for RAG**: Automatically translates Hinglish queries to English for RAG processing
- **Configuration**: Enabled in `language_config.support_hinglish`

**Examples**:
- "weather kaisa h?" → "What is the weather like?"
- "aaj rainy weather h kya?" → "Is it rainy weather today?"
- "mujhe kaam ke baare mein batao" → "Tell me about work"

## 🔧 Function Registration as RAG

The system allows you to register custom functions as RAG tools that the LLM can call dynamically:

### 1. Create Your Service
```python
class CustomService:
    async def process_query(self, query: str) -> str:
        # Your custom logic here
        return "Custom response"
```

### 2. Register Function Handler
```python
# In app/services/conversation.py
async def _handle_custom_query(self, params: FunctionCallParams) -> None:
    query = params.arguments.get("query", "")
    result = await self.custom_service.process_query(query)
    await params.result_callback(result)

# Register in initialize_llm()
self.llm_service.register_function("custom_query", self._handle_custom_query)
```

### 3. Define Function Schema
```python
# In create_function_schemas()
custom_function = FunctionSchema(
    name="custom_query",
    description="Process custom queries",
    properties={
        "query": {"type": "string", "description": "User query"}
    },
    required=["query"]
)
```

### 4. Update Configuration
Add your service configuration to the config files and initialize it in the voice assistant.

## 🛠️ Development

### Adding New Services

1. Create a service class in `app/services/`
2. Implement the required interface methods
3. Register the service in `VoiceAssistant` (`app/core/voice_assistant.py`)
4. Update configuration in `app/config/config.yaml`

### Custom LLM Integration

Add support for additional LLM providers by extending the conversation manager's `initialize_llm` method in `app/services/conversation.py`.

## 📊 Monitoring

### Latency Optimization
- **Target Response Time**: 1-1.5 seconds end-to-end
- **Component-level Monitoring**: Processing time per service (STT, LLM, RAG, TTS)
- **Real-time Metrics**: Live performance tracking and bottleneck identification
- **Optimized Pipeline**: Streamlined processing flow for minimal latency

### Health Checks
- Service status monitoring
- Connection health
- Error tracking

### Logging
- Structured logging with Loguru
- Service-specific log levels
- Performance metrics logging

## 🐛 Troubleshooting

### Common Issues

1. **Connection Errors**:
   - Check API keys in `.env` file (copy from `env.example` if needed)
   - Verify all required API keys are set and valid
   - Verify network connectivity
   - Ensure ports are available

2. **Audio Issues**:
   - Check microphone permissions
   - Verify audio format compatibility
   - Test with different browsers

3. **Performance Issues**:
   - Monitor latency analyzer output
   - Check system resources
   - Optimize pipeline configuration

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export PYTHONPATH=/path/to/nester-ai-bot-opensource
python app/main.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 🏢 About NesterLabs

This project is developed and open-sourced by **[Nesterlabs](https://nesterlabs.com)**,
a technology company specializing in AI-powered systems
and conversational intelligence. At NesterLabs, we combine cutting-edge AI with our proprietary 
PGI (Perceptual, Goal-driven, Interactive) UX framework to craft user experiences that are 
not only intelligent and responsive but also deeply engaging and human-centric.

### Custom Implementation Services

For custom voice bot implementations, enterprise RAG systems, or tailored conversational AI solutions, contact NesterLabs:

- **Website**: [https://nesterlabs.com](https://nesterlabs.com)
- **Email**: contact@nesterlabs.com
- **Services**: Custom voice assistants, enterprise RAG implementations, AI integration consulting

## 📄 License

MIT License

Copyright (c) 2025 NesterLabs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 🙏 Acknowledgments

- Built with [pipecat-ai](https://github.com/pipecat-ai/pipecat) framework
- Speech services powered by Deepgram and ElevenLabs
- LLM integration via Google AI

## 📞 Support

For questions and support:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the configuration documentation
- For commercial support and custom implementations: **contact-dev@nesterlabs.com**

---

**Note**: This is a development framework. For production use, implement proper security measures, error handling, and scalability considerations.
README.md updated
# Trigger new build with latest code
