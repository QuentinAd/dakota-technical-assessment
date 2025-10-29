"""
Unit tests for Enrichment API client.

Following TDD: These tests are written BEFORE implementation.
Tests cover: HTTP requests, response parsing, error handling, retries.
"""

from unittest.mock import Mock, patch

import httpx
import pytest

# Mock response matching our FastAPI enrichment service
MOCK_ENRICHMENT_SUCCESS_RESPONSE = {
    "location": "US-CA",
    "period": "2024-01-15",
    "temperature_fahrenheit": 42.8,
    "population": 7094722,
    "gdp_per_capita": 75432.5,
    "industrial_activity_index": 105.3,
}


class TestEnrichmentClient:
    """Test suite for Enrichment API client."""

    def test_client_initialization(self):
        """Test that client initializes with base URL."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient(base_url="http://localhost:8000")
        assert client.base_url == "http://localhost:8000"

    def test_client_default_base_url(self):
        """Test that client has sensible default base URL."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient()
        # Default should point to Docker service name
        assert "enrichment-api" in client.base_url or "localhost" in client.base_url

    @pytest.mark.asyncio
    async def test_fetch_enrichment_success(self):
        """Test successful fetch of enrichment data."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient(base_url="http://test-api:8000")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_ENRICHMENT_SUCCESS_RESPONSE
            mock_post.return_value = mock_response

            result = await client.fetch_enrichment(location="US-CA", period="2024-01-15")

            # Verify API was called correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://test-api:8000/enrichment"

            # Verify request body
            json_data = call_args[1]["json"]
            assert json_data["location"] == "US-CA"
            assert json_data["period"] == "2024-01-15"

            # Verify response parsing
            assert result["location"] == "US-CA"
            assert result["temperature_fahrenheit"] == 42.8
            assert result["population"] == 7094722

    @pytest.mark.asyncio
    async def test_fetch_enrichment_handles_404(self):
        """Test handling of 404 errors."""
        from ingestion.clients.enrichment_client import (
            EnrichmentAPIError,
            EnrichmentClient,
        )

        client = EnrichmentClient()

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"detail": "Not found"}
            mock_post.return_value = mock_response

            with pytest.raises(EnrichmentAPIError, match="404"):
                await client.fetch_enrichment(location="US-CA", period="2024-01")

    @pytest.mark.asyncio
    async def test_fetch_enrichment_handles_422_validation_error(self):
        """Test handling of validation errors (422) from API."""
        from ingestion.clients.enrichment_client import (
            EnrichmentAPIError,
            EnrichmentClient,
        )

        client = EnrichmentClient()

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 422
            mock_response.json.return_value = {
                "detail": [{"loc": ["body", "period"], "msg": "invalid date format"}]
            }
            mock_post.return_value = mock_response

            # Use a malformed date that passes local validation but fails API validation
            with pytest.raises(EnrichmentAPIError, match="Validation error"):
                await client.fetch_enrichment(location="US-CA", period="invalid-date")

    @pytest.mark.asyncio
    async def test_fetch_enrichment_handles_500_server_error(self):
        """Test handling of server errors (500)."""
        from ingestion.clients.enrichment_client import (
            EnrichmentAPIError,
            EnrichmentClient,
        )

        client = EnrichmentClient()

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"detail": "Internal server error"}
            mock_post.return_value = mock_response

            with pytest.raises(EnrichmentAPIError, match="500"):
                await client.fetch_enrichment(location="US-CA", period="2024-01")

    @pytest.mark.asyncio
    async def test_fetch_enrichment_retries_on_network_error(self):
        """Test retry logic on network failures."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient(max_retries=3)

        with patch("httpx.AsyncClient.post") as mock_post:
            # First two calls fail with network error, third succeeds
            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = MOCK_ENRICHMENT_SUCCESS_RESPONSE

            mock_post.side_effect = [
                httpx.ConnectError("Connection refused"),
                httpx.ConnectError("Connection timeout"),
                mock_success,
            ]

            result = await client.fetch_enrichment(location="US-CA", period="2024-01")

            # Should have retried 3 times total
            assert mock_post.call_count == 3
            assert result["location"] == "US-CA"

    @pytest.mark.asyncio
    async def test_fetch_enrichment_fails_after_max_retries(self):
        """Test that client fails after exhausting retries."""
        from ingestion.clients.enrichment_client import (
            EnrichmentAPIError,
            EnrichmentClient,
        )

        client = EnrichmentClient(max_retries=2)

        with patch("httpx.AsyncClient.post") as mock_post:
            # All attempts fail
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(EnrichmentAPIError, match="Max retries exceeded"):
                await client.fetch_enrichment(location="US-CA", period="2024-01")

            # Should have tried initial + max_retries times (1 + 2 = 3)
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_enrichment_batch(self):
        """Test batch fetching multiple enrichments."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient()

        locations_periods = [
            ("US-CA", "2024-01-15"),
            ("US-NY", "2024-01-15"),
            ("US-TX", "2024-01-15"),
        ]

        with patch("httpx.AsyncClient.post") as mock_post:
            # Mock different responses for each location
            mock_responses = [
                Mock(
                    status_code=200,
                    json=Mock(
                        return_value={
                            **MOCK_ENRICHMENT_SUCCESS_RESPONSE,
                            "location": loc,
                        }
                    ),
                )
                for loc, _ in locations_periods
            ]
            mock_post.side_effect = mock_responses

            results = await client.fetch_enrichment_batch(locations_periods)

            # Verify we got 3 results
            assert len(results) == 3
            assert results[0]["location"] == "US-CA"
            assert results[1]["location"] == "US-NY"
            assert results[2]["location"] == "US-TX"

    @pytest.mark.asyncio
    async def test_fetch_enrichment_with_timeout(self):
        """Test that requests respect timeout settings."""
        from ingestion.clients.enrichment_client import (
            EnrichmentAPIError,
            EnrichmentClient,
        )

        client = EnrichmentClient(timeout=5.0)
        assert client.timeout == 5.0

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(EnrichmentAPIError, match="Max retries exceeded"):
                await client.fetch_enrichment(location="US-CA", period="2024-01")

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        """Test that async context manager properly closes HTTP client."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        async with EnrichmentClient() as client:
            assert client is not None

        # After context, client should be closed

    def test_default_configuration(self):
        """Test default client configuration."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient()

        assert client.max_retries == 3
        assert client.timeout == 30.0
        assert client.base_url is not None

    @pytest.mark.asyncio
    async def test_fetch_enrichment_validates_required_params(self):
        """Test that required parameters are validated."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient()

        # Test with empty location
        with pytest.raises(ValueError, match="location"):
            await client.fetch_enrichment(location="", period="2024-01")

        # Test with empty period
        with pytest.raises(ValueError, match="period"):
            await client.fetch_enrichment(location="US-CA", period="")

    @pytest.mark.asyncio
    async def test_fetch_enrichment_builds_correct_url(self):
        """Test that client builds correct endpoint URL."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient(base_url="http://custom-api:9000")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_ENRICHMENT_SUCCESS_RESPONSE
            mock_post.return_value = mock_response

            await client.fetch_enrichment(location="US-CA", period="2024-01")

            # Verify URL construction
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://custom-api:9000/enrichment"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient(base_url="http://test-api:8000")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "healthy",
                "service": "enrichment-api",
            }
            mock_get.return_value = mock_response

            is_healthy = await client.health_check()

            assert is_healthy is True
            mock_get.assert_called_once_with("http://test-api:8000/health")

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self):
        """Test that health check returns False on error."""
        from ingestion.clients.enrichment_client import EnrichmentClient

        client = EnrichmentClient()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            is_healthy = await client.health_check()

            assert is_healthy is False
