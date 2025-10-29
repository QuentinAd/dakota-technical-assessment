"""
Enrichment API Client for fetching synthetic enrichment data.

This client handles communication with the FastAPI enrichment service,
including retries, error handling, and batch operations.
"""

import asyncio
from typing import Any

import httpx


# Custom exceptions
class EnrichmentAPIError(Exception):
    """Base exception for Enrichment API errors."""

    pass


class EnrichmentClient:
    """
    Async client for internal Enrichment API service.

    Features:
    - Automatic retries with exponential backoff
    - Batch operations for multiple locations
    - Health check support for orchestration
    - Proper error handling

    Example:
        async with EnrichmentClient() as client:
            data = await client.fetch_enrichment(
                location="US-CA",
                period="2024-01-15"
            )
    """

    def __init__(
        self,
        base_url: str = "http://enrichment-api:8000",
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        """
        Initialize Enrichment API client.

        Args:
            base_url: Base URL for enrichment service (Docker service name by default)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
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

    async def _make_request_with_retry(
        self, url: str, json_data: dict[str, Any], attempt: int = 0
    ) -> dict[str, Any]:
        """
        Make HTTP POST request with retry logic and exponential backoff.

        Args:
            url: Complete URL to request
            json_data: JSON body for POST request
            attempt: Current attempt number (for recursion)

        Returns:
            Parsed JSON response

        Raises:
            EnrichmentAPIError: On errors or max retries exceeded
        """
        client = self._get_client()

        try:
            response = await client.post(url, json=json_data)

            # Handle different status codes
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 404:
                error_data = response.json()
                raise EnrichmentAPIError(
                    f"Endpoint not found (404): {error_data.get('detail', 'Not found')}"
                )

            elif response.status_code == 422:
                error_data = response.json()
                raise EnrichmentAPIError(
                    f"Validation error (422): {error_data.get('detail', 'Invalid request')}"
                )

            elif response.status_code == 500:
                error_data = response.json()
                raise EnrichmentAPIError(
                    f"Server error (500): {error_data.get('detail', 'Internal server error')}"
                )

            else:
                raise EnrichmentAPIError(f"HTTP {response.status_code}: {response.text}")

        except httpx.ConnectError as e:
            # Network error - retry
            if attempt < self.max_retries:
                backoff_time = 2**attempt  # Exponential backoff: 1, 2, 4 seconds
                await asyncio.sleep(backoff_time)
                return await self._make_request_with_retry(url, json_data, attempt + 1)
            else:
                raise EnrichmentAPIError(
                    f"Max retries exceeded after {attempt} attempts: {str(e)}"
                ) from e

        except httpx.TimeoutException as e:
            if attempt < self.max_retries:
                backoff_time = 2**attempt
                await asyncio.sleep(backoff_time)
                return await self._make_request_with_retry(url, json_data, attempt + 1)
            else:
                raise EnrichmentAPIError(
                    f"Max retries exceeded after {attempt} attempts: {str(e)}"
                ) from e

        except EnrichmentAPIError:
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            raise EnrichmentAPIError(f"Unexpected error: {str(e)}") from e

    async def fetch_enrichment(self, location: str, period: str) -> dict[str, Any]:
        """
        Fetch enrichment data for a single location and period.

        Args:
            location: Location code (e.g., "US-CA")
            period: Period date (e.g., "2024-01-15")

        Returns:
            Dictionary with enrichment data

        Raises:
            ValueError: If location or period is empty
            EnrichmentAPIError: On API errors
        """
        # Validate inputs
        if not location or location.strip() == "":
            raise ValueError("location is required and cannot be empty")

        if not period or period.strip() == "":
            raise ValueError("period is required and cannot be empty")

        # Build request
        url = f"{self.base_url}/enrichment"
        json_data = {"location": location.strip(), "period": period.strip()}

        # Make request with retry logic
        return await self._make_request_with_retry(url, json_data)

    async def fetch_enrichment_batch(
        self, locations_periods: list[tuple[str, str]]
    ) -> list[dict[str, Any]]:
        """
        Fetch enrichment data for multiple location-period pairs.

        This method makes concurrent requests for better performance.

        Args:
            locations_periods: List of (location, period) tuples

        Returns:
            List of enrichment data dictionaries

        Example:
            results = await client.fetch_enrichment_batch([
                ("US-CA", "2024-01-15"),
                ("US-NY", "2024-01-15"),
                ("US-TX", "2024-01-15")
            ])
        """
        # Create tasks for concurrent fetching
        tasks = [self.fetch_enrichment(location, period) for location, period in locations_periods]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)

        return list(results)

    async def fetch_enrichment_data(self, locations: list[str], date: Any) -> list[dict[str, Any]]:
        """
        Fetch enrichment data for multiple locations on a specific date.

        This is a convenience method that formats inputs for batch fetching.

        Args:
            locations: List of location codes (e.g., ["US-CA", "US-TX"])
            date: Date object (will be converted to string)

        Returns:
            List of enrichment data dictionaries

        Example:
            from datetime import date
            data = await client.fetch_enrichment_data(
                locations=["US-CA", "US-TX"],
                date=date(2024, 1, 15)
            )
        """
        # Convert date to string format
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)

        # Create location-period pairs
        locations_periods = [(loc, date_str) for loc in locations]

        # Fetch using batch method
        return await self.fetch_enrichment_batch(locations_periods)

    async def health_check(self) -> bool:
        """
        Check if the enrichment service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        client = self._get_client()
        url = f"{self.base_url}/health"

        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "healthy"
            return False
        except Exception:
            # Any error means service is not healthy
            return False

    async def close(self):
        """Close the HTTP client (if not using context manager)."""
        if self._client:
            await self._client.aclose()
            self._client = None
