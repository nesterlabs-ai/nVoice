"""
RAG (Retrieval Augmented Generation) service for the Voice Assistant.

This module provides RAG functionality using different backends:
- LightRAG: External LightRAG API integration
- Pinecone: Vector database with LangChain integration
- Mock: For testing purposes
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx
from loguru import logger

# Shared HTTP client for connection pooling and reuse
_shared_client: Optional[httpx.AsyncClient] = None


def get_shared_client(timeout: float = 30.0, verify: bool = False) -> httpx.AsyncClient:
    """Get or create a shared HTTP client with connection pooling.
    
    Args:
        timeout: Request timeout in seconds
        verify: Whether to verify SSL certificates
        
    Returns:
        Shared httpx.AsyncClient instance
    """
    global _shared_client
    
    if _shared_client is None or _shared_client.is_closed:
        # Check if HTTP/2 is available (requires h2 package)
        try:
            import h2
            use_http2 = True
        except ImportError:
            use_http2 = False
            logger.warning("h2 package not installed, HTTP/2 disabled. Install with: pip install httpx[http2]")
        
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5.0, read=timeout),
            verify=verify,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=60.0,  # Increased to 60 seconds for better connection reuse
            ),
            http2=use_http2,  # Use HTTP/2 if available, otherwise HTTP/1.1
        )
        logger.debug(f"Created shared HTTP client with connection pooling (HTTP/2: {use_http2})")
    
    return _shared_client


class BaseRAGService(ABC):
    """Abstract base class for RAG services."""

    @abstractmethod
    async def get_response(self, query: str) -> str:
        """Query the RAG service and get a response.

        Args:
            query: The user's question

        Returns:
            The RAG response string
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get the service status.

        Returns:
            Status dictionary
        """
        pass

    @abstractmethod
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the service configuration.

        Args:
            config: New configuration parameters
        """
        pass


class RAGService(BaseRAGService):
    """Mock RAG service for testing and development."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the mock RAG service.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        logger.info("Initialized Mock RAG Service")

    async def get_response(self, query: str) -> str:
        """Return a mock response.

        Args:
            query: The user's question

        Returns:
            Mock response string
        """
        logger.info(f"Mock RAG query: {query}")
        return f"This is a mock response for: {query}"

    def get_status(self) -> Dict[str, Any]:
        """Get mock service status."""
        return {"type": "mock", "status": "active"}

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update configuration."""
        self.config.update(config)


class LightRAGService(BaseRAGService):
    """Service for interacting with LightRAG API.

    Attributes:
        api_url: Base URL of the LightRAG API
        mode: Query mode (mix, local, global, hybrid)
        top_k: Number of results to retrieve
        timeout: API timeout in seconds
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the LightRAG service.

        Args:
            config: Configuration dictionary containing:
                - api_url: Base URL of the LightRAG API
                - mode: Query mode (mix, local, global, hybrid, naive)
                    - "local": Fastest, entity-focused (recommended for speed)
                    - "naive": Vector search only (fastest but less accurate)
                    - "global": Slower, pattern analysis
                    - "mix": Balanced but slower
                - top_k: Number of results to retrieve (lower = faster)
                - timeout: API timeout in seconds
                - use_connection_pooling: Use shared HTTP client (default: True)
        """
        self.config = config or {}
        api_url_raw = self.config.get("api_url", "http://localhost:9621")
        # Remove trailing slash to avoid double slashes when appending paths
        self.api_url = api_url_raw.rstrip("/")
        self.api_key = self.config.get("api_key", "")
        # Use "local" mode for faster responses (entity-focused retrieval)
        self.mode = self.config.get("mode", "local")
        # Lower top_k for faster retrieval (3 is optimal balance)
        self.top_k = self.config.get("top_k", 3)
        self.chunk_top_k = self.config.get("chunk_top_k", 10)
        self.max_entity_tokens = self.config.get("max_entity_tokens", 600)
        self.max_relation_tokens = self.config.get("max_relation_tokens", 600)
        self.max_total_tokens = self.config.get("max_total_tokens", 1000)
        # Reduced timeout for faster failure detection
        self.timeout = self.config.get("timeout", 20)
        self.use_connection_pooling = self.config.get("use_connection_pooling", True)

        logger.info(
            f"Initialized LightRAG Service: {self.api_url}, "
            f"mode={self.mode}, top_k={self.top_k}, chunk_top_k={self.chunk_top_k}, "
            f"max_entity_tokens={self.max_entity_tokens}, max_relation_tokens={self.max_relation_tokens}, "
            f"max_total_tokens={self.max_total_tokens}, timeout={self.timeout}s"
        )

    async def get_response(self, query: str) -> str:
        """Query the LightRAG API and get a response using streaming for faster first-token.

        Optimizations applied:
        - Connection pooling for reduced latency
        - Streaming for faster first-token response
        - Optimized payload (top_k, mode)
        - Early error detection

        Args:
            query: The user's question

        Returns:
            The RAG response string
        """
        import time
        start_time = time.time()
        try:
            logger.info(f"🔍 RAG START: Query='{query}' at {start_time}")
            logger.debug(f"LightRAG query: {query}")

            # Optimized payload: include all RAG parameters
            payload = {
                "query": query,
                "mode": self.mode,
                "stream": True,
                "top_k": self.top_k,  # Number of top results to retrieve
                "chunk_top_k": self.chunk_top_k,  # Number of top chunks to retrieve
                "max_entity_tokens": self.max_entity_tokens,  # Maximum tokens for entity extraction
                "max_relation_tokens": self.max_relation_tokens,  # Maximum tokens for relation extraction
                "max_total_tokens": self.max_total_tokens,  # Maximum total tokens for response
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/x-ndjson",
                "ngrok-skip-browser-warning": "true",
                "Connection": "keep-alive",  # Reuse connections
            }
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            # Use shared client for connection pooling (faster subsequent requests)
            if self.use_connection_pooling:
                client = get_shared_client(timeout=self.timeout, verify=False)
            else:
                client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=5.0),
                    verify=False,
                    limits=httpx.Limits(max_connections=1),
                )

            # Use streaming endpoint for faster first-token response
            full_response = ""
            first_chunk_time = None
            try:
                async with client.stream(
                    "POST",
                    f"{self.api_url}/query/stream",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()

                    # Parse NDJSON streaming response
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                # Parse each JSON line (NDJSON format)
                                data = json.loads(line)

                                # Skip references line, get response chunks
                                if "response" in data:
                                    chunk = data.get("response", "")
                                    if chunk and first_chunk_time is None:
                                        first_chunk_time = time.time()
                                        logger.info(f"⚡ RAG FIRST CHUNK: {first_chunk_time - start_time:.3f}s")
                                    full_response += chunk
                                elif "error" in data:
                                    logger.error(f"LightRAG streaming error: {data.get('error')}")
                                    return "I encountered an error while searching the knowledge base."
                            except json.JSONDecodeError:
                                # Skip non-JSON lines (like empty lines)
                                continue
            finally:
                # Only close if we created a new client (not shared)
                if not self.use_connection_pooling:
                    await client.aclose()

            end_time = time.time()
            total_time = end_time - start_time
            logger.info(f"✅ RAG COMPLETE: Total={total_time:.3f}s, Length={len(full_response)} chars")

            if "[no-context]" in full_response:
                logger.warning("LightRAG: No context found for query")
                return "I don't have specific information about that in my knowledge base."

            logger.debug(f"LightRAG response length: {len(full_response)} chars")
            return full_response

        except httpx.TimeoutException:
            logger.error("LightRAG API timeout")
            return "I'm having trouble accessing the knowledge base. Please try again."
        except httpx.HTTPStatusError as e:
            logger.error(f"LightRAG API error: {e.response.status_code}")
            return "I encountered an error while searching the knowledge base."
        except Exception as e:
            logger.error(f"LightRAG error: {e}")
            return f"I encountered an error: {str(e)}"

    async def health_check(self) -> Dict[str, Any]:
        """Check if the LightRAG API is healthy.

        Returns:
            Health status dictionary
        """
        try:
            headers = {
                "ngrok-skip-browser-warning": "true",
                "Connection": "keep-alive",
            }
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            
            # Use shared client for faster health checks
            client = get_shared_client(timeout=10.0, verify=False)
            response = await client.get(
                f"{self.api_url}/health",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"LightRAG health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get the service status."""
        return {
            "type": "lightrag",
            "api_url": self.api_url,
            "mode": self.mode,
            "top_k": self.top_k,
        }

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the service configuration."""
        self.config.update(config)
        if "api_url" in config:
            self.api_url = config["api_url"]
        if "mode" in config:
            self.mode = config["mode"]
        if "top_k" in config:
            self.top_k = config["top_k"]
        logger.info(f"Updated LightRAG config: {config}")


def create_rag_service(config: Dict[str, Any]) -> BaseRAGService:
    """Factory function to create the appropriate RAG service.

    Args:
        config: Configuration dictionary with 'type' field

    Returns:
        Configured RAG service instance
    """
    rag_type = config.get("type", "mock")
    rag_config = config.get("config", {})

    if rag_type == "lightrag":
        logger.info("Creating LightRAG Service")
        return LightRAGService(config=rag_config)
    elif rag_type == "pinecone":
        logger.info("Creating Pinecone RAG Service")
        # Import here to avoid circular imports and optional dependency
        from app.services.pinecone_rag import PineconeRAGService

        return PineconeRAGService(config=rag_config)
    else:
        logger.info("Creating Mock RAG Service")
        return RAGService(config=rag_config)
