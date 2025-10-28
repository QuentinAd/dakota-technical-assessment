"""Unit tests for /enrichment endpoint.

TDD Approach: Test the synthetic data generation endpoint.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from api.app.main import app

    return TestClient(app)


class TestEnrichmentEndpoint:
    """Test suite for /enrichment endpoint."""

    def test_enrichment_endpoint_exists(self, client: TestClient) -> None:
        """Test that /enrichment endpoint returns 200 OK."""
        response = client.post(
            "/enrichment",
            json={"location": "US-CA", "period": "2024-01-15"},
        )
        assert response.status_code == 200, "Enrichment endpoint should return 200 OK"

    def test_enrichment_endpoint_returns_json(self, client: TestClient) -> None:
        """Test that /enrichment endpoint returns JSON response."""
        response = client.post(
            "/enrichment",
            json={"location": "US-CA", "period": "2024-01-15"},
        )
        assert response.headers["content-type"] == "application/json"

    def test_enrichment_response_structure(self, client: TestClient) -> None:
        """Test that /enrichment response has required fields."""
        response = client.post(
            "/enrichment",
            json={"location": "US-TX", "period": "2024-02-20"},
        )
        data = response.json()

        # Check all required fields exist
        required_fields = [
            "location",
            "period",
            "temperature_fahrenheit",
            "population",
            "gdp_per_capita_usd",
            "industrial_activity_index",
        ]
        for field in required_fields:
            assert field in data, f"Response should include '{field}' field"

    def test_enrichment_echoes_request_params(self, client: TestClient) -> None:
        """Test that response echoes back location and period."""
        response = client.post(
            "/enrichment",
            json={"location": "US-NY", "period": "2024-03-10"},
        )
        data = response.json()
        assert data["location"] == "US-NY"
        assert data["period"] == "2024-03-10"

    def test_enrichment_generates_realistic_temperature(self, client: TestClient) -> None:
        """Test that temperature is in a realistic range."""
        response = client.post(
            "/enrichment",
            json={"location": "US-FL", "period": "2024-01-15"},
        )
        data = response.json()
        temp = data["temperature_fahrenheit"]
        assert isinstance(temp, (int, float)), "Temperature should be numeric"
        assert -50 <= temp <= 120, "Temperature should be in realistic range (-50 to 120°F)"

    def test_enrichment_generates_positive_population(self, client: TestClient) -> None:
        """Test that population is positive."""
        response = client.post(
            "/enrichment",
            json={"location": "US-CA", "period": "2024-01-15"},
        )
        data = response.json()
        population = data["population"]
        assert isinstance(population, int), "Population should be an integer"
        assert population > 0, "Population should be positive"

    def test_enrichment_generates_positive_gdp(self, client: TestClient) -> None:
        """Test that GDP per capita is positive."""
        response = client.post(
            "/enrichment",
            json={"location": "US-CA", "period": "2024-01-15"},
        )
        data = response.json()
        gdp = data["gdp_per_capita_usd"]
        assert isinstance(gdp, (int, float)), "GDP should be numeric"
        assert gdp > 0, "GDP per capita should be positive"

    def test_enrichment_industrial_index_range(self, client: TestClient) -> None:
        """Test that industrial activity index is in valid range."""
        response = client.post(
            "/enrichment",
            json={"location": "US-IL", "period": "2024-01-15"},
        )
        data = response.json()
        index = data["industrial_activity_index"]
        assert isinstance(index, (int, float)), "Industrial index should be numeric"
        assert 0 <= index <= 200, "Industrial index should be between 0 and 200"

    def test_enrichment_different_locations_vary_data(self, client: TestClient) -> None:
        """Test that different locations generate different data."""
        response_ca = client.post(
            "/enrichment",
            json={"location": "US-CA", "period": "2024-01-15"},
        )
        response_ny = client.post(
            "/enrichment",
            json={"location": "US-NY", "period": "2024-01-15"},
        )

        data_ca = response_ca.json()
        data_ny = response_ny.json()

        # Data should differ for different locations
        # (at least temperature should be different due to hash-based generation)
        assert (
            data_ca["temperature_fahrenheit"] != data_ny["temperature_fahrenheit"]
            or data_ca["population"] != data_ny["population"]
        ), "Different locations should generate different data"

    def test_enrichment_same_inputs_same_output(self, client: TestClient) -> None:
        """Test that same inputs generate same output (deterministic)."""
        input_data = {"location": "US-TX", "period": "2024-01-15"}

        response1 = client.post("/enrichment", json=input_data)
        response2 = client.post("/enrichment", json=input_data)

        data1 = response1.json()
        data2 = response2.json()

        # Same inputs should produce same outputs (deterministic)
        assert data1 == data2, "Same inputs should generate identical outputs"

    def test_enrichment_missing_location(self, client: TestClient) -> None:
        """Test that missing location returns 422 Unprocessable Entity."""
        response = client.post(
            "/enrichment",
            json={"period": "2024-01-15"},
        )
        assert response.status_code == 422, "Missing location should return 422"

    def test_enrichment_missing_period(self, client: TestClient) -> None:
        """Test that missing period returns 422 Unprocessable Entity."""
        response = client.post(
            "/enrichment",
            json={"location": "US-CA"},
        )
        assert response.status_code == 422, "Missing period should return 422"

    def test_enrichment_get_not_allowed(self, client: TestClient) -> None:
        """Test that GET to /enrichment returns 405 Method Not Allowed."""
        response = client.get("/enrichment")
        assert response.status_code == 405, "GET to /enrichment should return 405"
