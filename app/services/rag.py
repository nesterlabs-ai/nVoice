"""
RAG (Retrieval Augmented Generation) service for the Voice Assistant.

This module provides RAG functionality using different backends:
- LightRAG: External LightRAG API integration
- Pinecone: Vector database with LangChain integration
- Mock: For testing purposes
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict

import httpx
from loguru import logger


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
                - mode: Query mode (mix, local, global, hybrid)
                - top_k: Number of results to retrieve
                - timeout: API timeout in seconds
        """
        self.config = config or {}
        self.api_url = self.config.get("api_url", "http://localhost:9621")
        self.api_key = self.config.get("api_key", "")
        self.mode = self.config.get("mode", "mix")
        self.top_k = self.config.get("top_k", 5)
        self.timeout = self.config.get("timeout", 30)

        logger.info(f"Initialized LightRAG Service with API URL: {self.api_url}")

    async def get_response(self, query: str) -> str:
        """Query the LightRAG API and get a response.

        Args:
            query: The user's question

        Returns:
            The RAG response string
        """
        try:
            logger.info(f"LightRAG query: {query}")

            payload = {"query": query, "mode": self.mode}

            headers = {
                "Content-Type": "application/json",
                "ngrok-skip-browser-warning": "true",
            }
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                response = await client.post(
                    f"{self.api_url}/query",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            answer = result.get("response", "")

            if "[no-context]" in answer:
                logger.warning("LightRAG: No context found for query")
                return "I don't have specific information about that in my knowledge base."

            logger.info(f"LightRAG response: {answer[:100]}...")
            return answer

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
            headers = {"ngrok-skip-browser-warning": "true"}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
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
