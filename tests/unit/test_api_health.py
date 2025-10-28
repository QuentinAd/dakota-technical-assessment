"""Unit tests for FastAPI health endpoint.

TDD Approach:
1. Write failing tests first
2. Implement minimal code to pass
3. Refactor as needed
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from api.app.main import app

    return TestClient(app)


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    def test_health_endpoint_exists(self, client: TestClient) -> None:
        """Test that /health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200, "Health endpoint should return 200 OK"

    def test_health_endpoint_returns_json(self, client: TestClient) -> None:
        """Test that /health endpoint returns JSON response."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"

    def test_health_endpoint_has_status_field(self, client: TestClient) -> None:
        """Test that /health response includes status field."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data, "Response should include 'status' field"
        assert data["status"] == "healthy", "Status should be 'healthy'"

    def test_health_endpoint_has_service_field(self, client: TestClient) -> None:
        """Test that /health response includes service name."""
        response = client.get("/health")
        data = response.json()
        assert "service" in data, "Response should include 'service' field"
        assert data["service"] == "enrichment-api", "Service name should be 'enrichment-api'"

    def test_health_endpoint_has_timestamp(self, client: TestClient) -> None:
        """Test that /health response includes timestamp."""
        response = client.get("/health")
        data = response.json()
        assert "timestamp" in data, "Response should include 'timestamp' field"
        # Verify timestamp is a valid ISO format string
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"])  # Should not raise

    def test_health_endpoint_method_not_allowed(self, client: TestClient) -> None:
        """Test that POST to /health returns 405 Method Not Allowed."""
        response = client.post("/health")
        assert response.status_code == 405, "POST to /health should return 405"
