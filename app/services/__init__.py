"""Services package.

Keep this package initializer lightweight. Eagerly importing every service pulls
in live voice dependencies such as Deepgram and Pipecat, which makes simple unit
tests and utility imports fail in environments that do not have the full runtime
stack installed.
"""

__all__ = [
    "SpeechToTextService",
    "TextToSpeechService",
    "RAGService",
    "LightRAGService",
    "A2UIResponse",
    "create_rag_service",
    "ConversationManager",
    "InputAnalyzer",
    "LatencyAnalyzer",
]


def __getattr__(name):
    """Lazily expose common service classes for legacy package-level imports."""
    if name == "SpeechToTextService":
        from app.services.stt import SpeechToTextService
        return SpeechToTextService
    if name == "TextToSpeechService":
        from app.services.tts import TextToSpeechService
        return TextToSpeechService
    if name in {"RAGService", "LightRAGService", "A2UIResponse", "create_rag_service"}:
        from app.services.rag import A2UIResponse, LightRAGService, RAGService, create_rag_service
        return {
            "RAGService": RAGService,
            "LightRAGService": LightRAGService,
            "A2UIResponse": A2UIResponse,
            "create_rag_service": create_rag_service,
        }[name]
    if name == "ConversationManager":
        from app.services.conversation import ConversationManager
        return ConversationManager
    if name == "InputAnalyzer":
        from app.services.input_analyzer import InputAnalyzer
        return InputAnalyzer
    if name == "LatencyAnalyzer":
        from app.services.latency import LatencyAnalyzer
        return LatencyAnalyzer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
