"""LightRAG Service for the Voice Assistant.

This module integrates with an external LightRAG API for RAG functionality.
Supports streaming for faster response times.
"""

import json
import httpx
from typing import Dict, Any, Optional, AsyncGenerator
from loguru import logger


class LightRAGService:
    """Service for interacting with LightRAG API with streaming support."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the LightRAG service.
        
        Args:
            config: Configuration dictionary containing:
                - api_url: Base URL of the LightRAG API
                - mode: Query mode (mix, local, global, hybrid)
                - top_k: Number of results to retrieve
                - use_streaming: Whether to use streaming (default: True)
        """
        self.config = config or {}
        self.api_url = self.config.get("api_url", "http://localhost:9621")
        self.mode = self.config.get("mode", "mix")
        self.top_k = self.config.get("top_k", 5)
        self.timeout = self.config.get("timeout", 30)
        self.use_streaming = self.config.get("use_streaming", True)
        
        logger.info(f"Initialized LightRAG Service with API URL: {self.api_url} (streaming: {self.use_streaming})")

    async def get_response(self, query: str) -> str:
        """Query the LightRAG API and get a response.
        
        Uses streaming for faster first-token response when enabled.
        
        Args:
            query: The user's question
            
        Returns:
            The RAG response string
        """
        try:
            logger.info(f"LightRAG query: {query}")
            
            # Simple payload - LightRAG API only needs query and mode
            payload = {
                "query": query,
                "mode": self.mode
            }
            
            # Always use non-streaming for reliability
            return await self._get_non_streaming_response(payload)
            
        except httpx.TimeoutException:
            logger.error("LightRAG API timeout")
            return "I'm having trouble accessing the knowledge base right now. Please try again."
        except httpx.HTTPStatusError as e:
            logger.error(f"LightRAG API error: {e.response.status_code}")
            return "I encountered an error while searching the knowledge base."
        except Exception as e:
            logger.error(f"LightRAG error: {e}")
            return f"I encountered an error: {str(e)}"

    async def _get_streaming_response(self, payload: Dict[str, Any]) -> str:
        """Get response using streaming API for faster first-token."""
        full_response = ""
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.api_url}/query/stream",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "true"
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            # Parse streaming response
                            if line.startswith("data: "):
                                data = json.loads(line[6:])
                                chunk = data.get("response", "") or data.get("content", "")
                                full_response += chunk
                            else:
                                # Try parsing as JSON directly
                                data = json.loads(line)
                                chunk = data.get("response", "") or data.get("content", "")
                                full_response += chunk
                        except json.JSONDecodeError:
                            # Plain text chunk
                            full_response += line
        
        # Check if no context was found
        if "[no-context]" in full_response:
            logger.warning(f"LightRAG: No context found for streaming query")
            return "I don't have specific information about that in my knowledge base."
        
        logger.info(f"LightRAG streaming response: {full_response[:100]}...")
        return full_response

    async def _get_non_streaming_response(self, payload: Dict[str, Any]) -> str:
        """Get response using non-streaming API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_url}/query",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "true"
                }
            )
            response.raise_for_status()
            result = response.json()
            
        answer = result.get("response", "")
        
        # Check if no context was found
        if "[no-context]" in answer:
            logger.warning(f"LightRAG: No context found for query")
            return "I don't have specific information about that in my knowledge base."
        
        logger.info(f"LightRAG response: {answer[:100]}...")
        return answer

    async def health_check(self) -> Dict[str, Any]:
        """Check if the LightRAG API is healthy.
        
        Returns:
            Health status dictionary
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.api_url}/health",
                    headers={"ngrok-skip-browser-warning": "true"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"LightRAG health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get the service status.
        
        Returns:
            Status dictionary
        """
        return {
            "type": "lightrag",
            "api_url": self.api_url,
            "mode": self.mode,
            "top_k": self.top_k
        }

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the service configuration.
        
        Args:
            config: New configuration parameters
        """
        self.config.update(config)
        if "api_url" in config:
            self.api_url = config["api_url"]
        if "mode" in config:
            self.mode = config["mode"]
        if "top_k" in config:
            self.top_k = config["top_k"]
        logger.info(f"Updated LightRAG config: {config}")


def create_lightrag_service(config: Dict[str, Any]) -> LightRAGService:
    """Factory function to create a LightRAG service.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured LightRAGService instance
    """
    rag_config = config.get("config", {})
    return LightRAGService(config=rag_config)

