# ConversationalBot - Voice RAG Assistant

A real-time voice conversational assistant that combines speech-to-text, text-to-speech, RAG (Retrieval-Augmented Generation), and LLM capabilities for natural voice interactions.

**Developed and open-sourced by [NesterLabs](https://nesterlabs.com)**

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

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Required API keys:
  - Deepgram API key (for speech-to-text)
  - ElevenLabs API key (for text-to-speech)
  - Google API key (for LLM)

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
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_elevenlabs_voice_id
GOOGLE_API_KEY=your_google_api_key

# Optional: Server Configuration (defaults provided)
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=7860
WEBSOCKET_HOST=localhost
WEBSOCKET_PORT=8765
```

4. **Run the server**:
```bash
# FastAPI mode
cd ConversationalBot
export PYTHONPATH=$(pwd)
python websocket_server.py
```

5. **Test the connection**:
See the [Client README](src/client/README.md) for detailed instructions on running and using the client applications.

## 📁 Project Structure

```
ConversationalBot/
├── src/
│   ├── config/
│   │   ├── config.yaml          # Main configuration file
│   │   └── config.py            # Configuration management
│   ├── core/
│   │   └── voice_assistant.py   # Main orchestrator
│   ├── services/
│   │   ├── speech_to_text.py    # STT service
│   │   ├── text_to_speech.py    # TTS service
│   │   ├── rag_service.py       # RAG/knowledge service
│   │   ├── conversation_manager.py # LLM & conversation flow
│   │   ├── input_analyzer.py    # Input processing
│   │   └── latency_analyzer.py  # Performance monitoring
│   ├── client/
│   │   ├── test_client.html     # Web test client
│   │   └── simple_client.py     # Python test client
│   ├── websocket_server.py      # Main server application
│   └── voice_assistant_server.py # Server class
├── requirements.txt
├── env.example                  # Environment variables template
└── README.md
```

## ⚙️ Configuration

The system uses a YAML configuration file (`src/config/config.yaml`) with environment variable substitution:

```yaml
# Speech-to-Text Configuration
stt:
  provider: "deepgram"  # or "whisper"
  config:
    api_key: "${DEEPGRAM_API_KEY}"
    model: "small"
    no_speech_prob: 0.3

# Text-to-Speech Configuration
tts:
  provider: "elevenlabs"
  config:
    api_key: "${ELEVENLABS_API_KEY}"
    voice_id: "${ELEVENLABS_VOICE_ID}"

# LLM Configuration
conversation:
  llm:
    api_key: "${GOOGLE_API_KEY}"

# RAG Configuration
rag:
  type: "mock"  # Replace with your RAG system
  config: {}
```

## 🔧 Usage

### Client Usage

For detailed instructions on using the web client and Python client, please refer to the [Client README](src/client/README.md).

### API Endpoints

- **WebSocket**: `ws://localhost:7860/ws/{session_id}`
- **Connect**: `POST /connect` - Returns WebSocket URL
- **Status**: `GET /status` - Server and service status

## 🏃‍♂️ Server Modes

### FastAPI Mode (Default)
```bash
python websocket_server.py
```
- Provides both HTTP API and WebSocket endpoints
- Recommended for production use
- Includes CORS support and proper error handling

### Standalone WebSocket Mode
```bash
WEBSOCKET_SERVER=websocket_server python websocket_server.py
```
- Pure WebSocket server without HTTP overhead
- Better for dedicated voice applications
- Lower latency for real-time audio

## 🎛️ Services

### Speech-to-Text Service
- **Providers**: Deepgram, Whisper
- **Features**: Real-time transcription, noise suppression
- **Configuration**: Model selection, sensitivity settings

### Text-to-Speech Service
- **Providers**: ElevenLabs
- **Features**: Natural voice synthesis, voice cloning
- **Configuration**: Voice selection, audio quality

### RAG Service
- **Features**: Knowledge retrieval, context enhancement
- **Current Implementation**: Dummy/mock implementation with sample knowledge base
- **Extensible**: Replace with your actual RAG system (vector databases, document stores, etc.)
- **Function Integration**: Registered as LLM function call for dynamic knowledge retrieval

### Conversation Manager
- **Features**: Context management, conversation flow
- **LLM Integration**: Google LLM, OpenAI support
- **Function Calls**: Extensible tool integration

### Latency Analyzer
- **Metrics**: Processing time, response latency
- **Monitoring**: Real-time performance tracking
- **Reporting**: Statistical analysis and logging

## 🔧 Development

## 🌐 Hinglish Support

The system includes native support for Hinglish (Hindi-English mixed language) conversations:

- **Automatic Detection**: Understands both English and Hinglish inputs
- **Natural Responses**: Responds in the same language style as the user
- **Translation for RAG**: Automatically translates Hinglish queries to English for RAG system processing
- **Configuration**: Enable via `language_config.support_hinglish = true`

### Hinglish Examples
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
# In conversation_manager.py
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

1. Create a service class in `src/services/`
2. Implement the required interface methods
3. Register the service in `VoiceAssistant`
4. Update configuration as needed


### Custom LLM Integration

Add support for additional LLM providers by extending the conversation manager's `initialize_llm` method.

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
python websocket_server.py
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
