"""
Integration tests for FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestAPIEndpoints:
    """Integration tests for API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        # Import here to avoid module-level import issues
        from app.main import app

        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_status_endpoint(self, client):
        """Test status endpoint."""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_connect_endpoint(self, client, mock_env_vars):
        """Test connection endpoint."""
        response = client.get("/connect")
        assert response.status_code == 200
        data = response.json()
        assert "websocket_url" in data
