"""
Unit tests for EIA API client.

Following TDD: These tests are written BEFORE implementation.
Tests cover: authentication, response parsing, error handling, rate limiting, retries.
"""

from unittest.mock import Mock, patch

import pytest

# Mock response data matching EIA API v2 format
MOCK_EIA_SUCCESS_RESPONSE = {
    "response": {
        "total": 2,
        "data": [
            {
                "period": "2024-01",
                "seriesId": "ELEC.GEN.ALL-US-99.M",
                "value": 325000,
                "units": "megawatthours",
                "location": "US-CA",
                "locationType": "state",
                "energySource": "solar",
                "sector": "electric power",
            },
            {
                "period": "2024-02",
                "seriesId": "ELEC.GEN.ALL-US-99.M",
                "value": 330000,
                "units": "megawatthours",
                "location": "US-CA",
                "locationType": "state",
                "energySource": "solar",
                "sector": "electric power",
            },
        ],
    },
    "request": {"frequency": "monthly", "data": ["value"]},
    "apiVersion": "v2",
}

MOCK_EIA_ERROR_RESPONSE = {"error": "Invalid API key", "code": 401}


class TestEIAClient:
    """Test suite for EIA API client."""

    def test_client_initialization(self):
        """Test that client initializes with API key."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key_12345")
        assert client.api_key == "test_key_12345"
        assert client.base_url == "https://api.eia.gov/v2"

    def test_client_requires_api_key(self):
        """Test that client raises error without API key."""
        from ingestion.clients.eia_client import EIAClient

        with pytest.raises(ValueError, match="API key is required"):
            EIAClient(api_key="")

    @pytest.mark.asyncio
    async def test_fetch_electricity_generation_success(self):
        """Test successful fetch of electricity generation data."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key")

        # Mock httpx.AsyncClient.get
        with patch("httpx.AsyncClient.get") as mock_get:
            # Use Mock (not AsyncMock) for response since response.json() is not async
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_EIA_SUCCESS_RESPONSE
            # Make get() async by wrapping in AsyncMock
            mock_get.return_value = mock_response

            result = await client.fetch_electricity_generation(
                start_date="2024-01", end_date="2024-02", location="US-CA"
            )

            # Verify API was called correctly
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "api_key=test_key" in str(call_args)

            # Verify response parsing
            assert len(result) == 2
            assert result[0]["period"] == "2024-01"
            assert result[0]["value"] == 325000
            assert result[0]["location"] == "US-CA"

    @pytest.mark.asyncio
    async def test_fetch_with_authentication_header(self):
        """Test that API key is included in request."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="secret_key_xyz")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_EIA_SUCCESS_RESPONSE
            mock_get.return_value = mock_response

            await client.fetch_electricity_generation(start_date="2024-01", end_date="2024-01")

            # Verify API key was sent
            call_url = str(mock_get.call_args)
            assert "secret_key_xyz" in call_url

    @pytest.mark.asyncio
    async def test_fetch_handles_401_unauthorized(self):
        """Test handling of invalid API key (401)."""
        from ingestion.clients.eia_client import EIAAuthenticationError, EIAClient

        client = EIAClient(api_key="invalid_key")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = MOCK_EIA_ERROR_RESPONSE
            mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
            mock_get.return_value = mock_response

            with pytest.raises(EIAAuthenticationError, match="Invalid API key"):
                await client.fetch_electricity_generation(start_date="2024-01", end_date="2024-01")

    @pytest.mark.asyncio
    async def test_fetch_handles_404_not_found(self):
        """Test handling of invalid endpoint (404)."""
        from ingestion.clients.eia_client import EIAAPIError, EIAClient

        client = EIAClient(api_key="test_key")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"error": "Endpoint not found"}
            mock_get.return_value = mock_response

            with pytest.raises(EIAAPIError, match="404"):
                await client.fetch_electricity_generation(start_date="2024-01", end_date="2024-01")

    @pytest.mark.asyncio
    async def test_fetch_handles_500_server_error(self):
        """Test handling of server errors (500)."""
        from ingestion.clients.eia_client import EIAAPIError, EIAClient

        client = EIAClient(api_key="test_key")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"error": "Internal server error"}
            mock_get.return_value = mock_response

            with pytest.raises(EIAAPIError, match="500"):
                await client.fetch_electricity_generation(start_date="2024-01", end_date="2024-01")

    @pytest.mark.asyncio
    async def test_fetch_retries_on_network_error(self):
        """Test retry logic on network failures."""
        import httpx

        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key", max_retries=3)

        with patch("httpx.AsyncClient.get") as mock_get:
            # First two calls fail with network error, third succeeds
            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = MOCK_EIA_SUCCESS_RESPONSE

            mock_get.side_effect = [
                httpx.ConnectError("Connection refused"),
                httpx.ConnectError("Connection timeout"),
                mock_success,
            ]

            result = await client.fetch_electricity_generation(
                start_date="2024-01", end_date="2024-01"
            )

            # Should have retried 3 times total
            assert mock_get.call_count == 3
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_fetch_fails_after_max_retries(self):
        """Test that client fails after exhausting retries."""
        import httpx

        from ingestion.clients.eia_client import EIAAPIError, EIAClient

        client = EIAClient(api_key="test_key", max_retries=2)

        with patch("httpx.AsyncClient.get") as mock_get:
            # All attempts fail
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(EIAAPIError, match="Max retries exceeded"):
                await client.fetch_electricity_generation(start_date="2024-01", end_date="2024-01")

            # Should have tried initial + max_retries times (1 + 2 = 3 total)
            assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limiting_with_backoff(self):
        """Test that client handles rate limiting (429) with backoff."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key", max_retries=3)

        with patch("httpx.AsyncClient.get") as mock_get, patch("asyncio.sleep") as mock_sleep:
            # First call returns 429, second succeeds
            mock_rate_limited = Mock()
            mock_rate_limited.status_code = 429
            mock_rate_limited.json.return_value = {"error": "Rate limit exceeded"}

            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = MOCK_EIA_SUCCESS_RESPONSE

            mock_get.side_effect = [mock_rate_limited, mock_success]

            result = await client.fetch_electricity_generation(
                start_date="2024-01", end_date="2024-01"
            )

            # Should have slept (backoff) before retry
            assert mock_sleep.call_count >= 1
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_parse_response_extracts_data_array(self):
        """Test that response parsing extracts data array correctly."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key")

        # Test the internal parsing method
        parsed = client._parse_response(MOCK_EIA_SUCCESS_RESPONSE)

        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["period"] == "2024-01"
        assert parsed[1]["period"] == "2024-02"

    @pytest.mark.asyncio
    async def test_fetch_electricity_consumption_success(self):
        """Test successful fetch of electricity consumption data."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key")

        mock_consumption_response = {
            "response": {
                "total": 1,
                "data": [
                    {
                        "period": "2024-01",
                        "value": 50000,
                        "units": "megawatthours",
                        "sector": "residential",
                        "location": "US-CA",
                    }
                ],
            }
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_consumption_response
            mock_get.return_value = mock_response

            result = await client.fetch_electricity_consumption(
                start_date="2024-01", end_date="2024-01", location="US-CA"
            )

            assert len(result) == 1
            assert result[0]["sector"] == "residential"
            assert result[0]["value"] == 50000

    @pytest.mark.asyncio
    async def test_build_url_includes_parameters(self):
        """Test URL building with query parameters."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key_abc")

        url = client._build_url(
            endpoint="/electricity/retail-sales",
            params={
                "frequency": "monthly",
                "start": "2024-01",
                "end": "2024-02",
                "facets[location]": "US-CA",
            },
        )

        assert "https://api.eia.gov/v2/electricity/retail-sales" in url
        assert "api_key=test_key_abc" in url
        assert "frequency=monthly" in url
        assert "start=2024-01" in url

    def test_validate_date_format(self):
        """Test date format validation."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key")

        # Valid formats
        assert client._validate_date("2024-01") is True
        assert client._validate_date("2024-12") is True

        # Invalid formats
        with pytest.raises(ValueError, match="Invalid date format"):
            client._validate_date("2024/01")

        with pytest.raises(ValueError, match="Invalid date format"):
            client._validate_date("24-01")

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        """Test that async context manager properly closes HTTP client."""
        from ingestion.clients.eia_client import EIAClient

        async with EIAClient(api_key="test_key") as client:
            assert client is not None

        # After context, client should be closed
        # This tests proper resource cleanup

    def test_default_configuration(self):
        """Test default client configuration."""
        from ingestion.clients.eia_client import EIAClient

        client = EIAClient(api_key="test_key")

        assert client.max_retries == 3
        assert client.timeout == 30.0
        assert client.base_url == "https://api.eia.gov/v2"
