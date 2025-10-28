"""
EIA API Client for fetching energy data.

This client handles authentication, rate limiting, retries, and error handling
for the U.S. Energy Information Administration (EIA) API v2.

Documentation: https://www.eia.gov/opendata/documentation.php
"""

import asyncio
import re
from typing import Any
from urllib.parse import urlencode

import httpx


# Custom exceptions
class EIAAPIError(Exception):
    """Base exception for EIA API errors."""

    pass


class EIAAuthenticationError(EIAAPIError):
    """Raised when API authentication fails."""

    pass


class EIAClient:
    """
    Async client for EIA API v2.

    Features:
    - Automatic retries with exponential backoff
    - Rate limiting handling (429 responses)
    - Proper error handling and custom exceptions
    - Context manager support for resource cleanup

    Example:
        async with EIAClient(api_key="your_key") as client:
            data = await client.fetch_electricity_generation(
                start_date="2024-01",
                end_date="2024-12"
            )
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.eia.gov/v2",
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        """
        Initialize EIA API client.

        Args:
            api_key: EIA API key (required)
            base_url: Base URL for EIA API v2
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds

        Raises:
            ValueError: If api_key is empty
        """
        if not api_key or api_key.strip() == "":
            raise ValueError("API key is required")

        self.api_key = api_key.strip()
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _build_url(self, endpoint: str, params: dict[str, Any]) -> str:
        """
        Build complete URL with query parameters.

        Args:
            endpoint: API endpoint path (e.g., "/electricity/retail-sales")
            params: Query parameters dictionary

        Returns:
            Complete URL with encoded parameters
        """
        # Add API key to parameters
        params["api_key"] = self.api_key

        # Build URL
        query_string = urlencode(params)
        return f"{self.base_url}{endpoint}?{query_string}"

    def _validate_date(self, date_str: str) -> bool:
        """
        Validate date format (YYYY-MM).

        Args:
            date_str: Date string to validate

        Returns:
            True if valid

        Raises:
            ValueError: If date format is invalid
        """
        pattern = r"^\d{4}-\d{2}$"
        if not re.match(pattern, date_str):
            raise ValueError(f"Invalid date format: {date_str}. Expected format: YYYY-MM")
        return True

    def _parse_response(self, response_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parse EIA API response and extract data array.

        Args:
            response_data: Full API response JSON

        Returns:
            List of data records
        """
        if "response" in response_data and "data" in response_data["response"]:
            return response_data["response"]["data"]
        return []

    async def _make_request_with_retry(self, url: str, attempt: int = 0) -> dict[str, Any]:
        """
        Make HTTP request with retry logic and exponential backoff.

        Args:
            url: Complete URL to request
            attempt: Current attempt number (for recursion)

        Returns:
            Parsed JSON response

        Raises:
            EIAAuthenticationError: On 401 errors
            EIAAPIError: On other errors or max retries exceeded
        """
        client = self._get_client()

        try:
            response = await client.get(url)

            # Handle different status codes
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                error_data = response.json()
                raise EIAAuthenticationError(
                    f"Invalid API key: {error_data.get('error', 'Authentication failed')}"
                )

            elif response.status_code == 429:
                # Rate limited - retry with backoff
                if attempt < self.max_retries:
                    backoff_time = 2**attempt  # Exponential backoff: 1, 2, 4 seconds
                    await asyncio.sleep(backoff_time)
                    return await self._make_request_with_retry(url, attempt + 1)
                else:
                    raise EIAAPIError(f"Rate limit exceeded (429) after {attempt} retries")

            elif response.status_code == 404:
                error_data = response.json()
                raise EIAAPIError(
                    f"Endpoint not found (404): {error_data.get('error', 'Not found')}"
                )

            elif response.status_code == 500:
                error_data = response.json()
                raise EIAAPIError(
                    f"Server error (500): {error_data.get('error', 'Internal server error')}"
                )

            else:
                raise EIAAPIError(f"HTTP {response.status_code}: {response.text}")

        except httpx.ConnectError as e:
            # Network error - retry
            if attempt < self.max_retries:
                backoff_time = 2**attempt
                await asyncio.sleep(backoff_time)
                return await self._make_request_with_retry(url, attempt + 1)
            else:
                raise EIAAPIError(f"Max retries exceeded after {attempt} attempts: {str(e)}") from e

        except httpx.TimeoutException as e:
            if attempt < self.max_retries:
                backoff_time = 2**attempt
                await asyncio.sleep(backoff_time)
                return await self._make_request_with_retry(url, attempt + 1)
            else:
                raise EIAAPIError(f"Max retries exceeded after {attempt} attempts: {str(e)}") from e

        except (EIAAuthenticationError, EIAAPIError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            raise EIAAPIError(f"Unexpected error: {str(e)}") from e

    async def fetch_electricity_generation(
        self,
        start_date: str,
        end_date: str,
        location: str | None = None,
        frequency: str = "monthly",
    ) -> list[dict[str, Any]]:
        """
        Fetch electricity generation data from EIA API.

        Args:
            start_date: Start date in YYYY-MM format
            end_date: End date in YYYY-MM format
            location: Optional location filter (e.g., "US-CA")
            frequency: Data frequency (default: "monthly")

        Returns:
            List of generation records

        Raises:
            ValueError: If date format is invalid
            EIAAuthenticationError: If API key is invalid
            EIAAPIError: On other API errors
        """
        # Validate dates
        self._validate_date(start_date)
        self._validate_date(end_date)

        # Build request parameters
        # For electric-power-operational-data endpoint, data[] must be the dataset name (e.g., 'generation')
        params = {
            "frequency": frequency,
            "data[]": "generation",
            "start": start_date,
            "end": end_date,
        }

        if location:
            params["facets[location]"] = location

        # Build URL and make request
        url = self._build_url("/electricity/electric-power-operational-data/data", params)
        response_data = await self._make_request_with_retry(url)

        # Parse and return data
        return self._parse_response(response_data)

    async def fetch_electricity_consumption(
        self,
        start_date: str,
        end_date: str,
        location: str | None = None,
        frequency: str = "monthly",
    ) -> list[dict[str, Any]]:
        """
        Fetch electricity consumption/sales data from EIA API.

        Args:
            start_date: Start date in YYYY-MM format
            end_date: End date in YYYY-MM format
            location: Optional location filter (e.g., "US-CA")
            frequency: Data frequency (default: "monthly")

        Returns:
            List of consumption records

        Raises:
            ValueError: If date format is invalid
            EIAAuthenticationError: If API key is invalid
            EIAAPIError: On other API errors
        """
        # Validate dates
        self._validate_date(start_date)
        self._validate_date(end_date)

        # Build request parameters
        params = {
            "frequency": frequency,
            "data[]": "value",
            "start": start_date,
            "end": end_date,
        }

        if location:
            params["facets[location]"] = location

        # Build URL and make request
        # EIA API v2 requires /data suffix to get actual data (not metadata)
        url = self._build_url("/electricity/retail-sales/sales/data", params)
        response_data = await self._make_request_with_retry(url)

        # Parse and return data
        return self._parse_response(response_data)

    async def close(self):
        """Close the HTTP client (if not using context manager)."""
        if self._client:
            await self._client.aclose()
            self._client = None
