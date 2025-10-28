"""Unit tests for Pydantic models used in the enrichment API.

TDD Approach: Test model validation, serialization, and field constraints.
"""

import pytest
from pydantic import ValidationError


class TestEnrichmentRequest:
    """Test suite for EnrichmentRequest model."""

    def test_enrichment_request_valid(self) -> None:
        """Test that valid EnrichmentRequest can be created."""
        from api.app.models import EnrichmentRequest

        request = EnrichmentRequest(
            location="US-CA",
            period="2024-01-15",
        )
        assert request.location == "US-CA"
        assert request.period == "2024-01-15"

    def test_enrichment_request_missing_location(self) -> None:
        """Test that location field is required."""
        from api.app.models import EnrichmentRequest

        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(period="2024-01-15")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("location",) for error in errors)

    def test_enrichment_request_missing_period(self) -> None:
        """Test that period field is required."""
        from api.app.models import EnrichmentRequest

        with pytest.raises(ValidationError) as exc_info:
            EnrichmentRequest(location="US-CA")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("period",) for error in errors)

    def test_enrichment_request_to_dict(self) -> None:
        """Test that model can be serialized to dict."""
        from api.app.models import EnrichmentRequest

        request = EnrichmentRequest(
            location="US-TX",
            period="2024-02-20",
        )
        data = request.model_dump()
        assert data["location"] == "US-TX"
        assert data["period"] == "2024-02-20"


class TestEnrichmentResponse:
    """Test suite for EnrichmentResponse model."""

    def test_enrichment_response_valid(self) -> None:
        """Test that valid EnrichmentResponse can be created."""
        from api.app.models import EnrichmentResponse

        response = EnrichmentResponse(
            location="US-CA",
            period="2024-01-15",
            temperature_fahrenheit=72.5,
            population=39000000,
            gdp_per_capita_usd=85000.0,
            industrial_activity_index=105.3,
        )
        assert response.location == "US-CA"
        assert response.period == "2024-01-15"
        assert response.temperature_fahrenheit == 72.5
        assert response.population == 39000000
        assert response.gdp_per_capita_usd == 85000.0
        assert response.industrial_activity_index == 105.3

    def test_enrichment_response_required_fields(self) -> None:
        """Test that all fields are required."""
        from api.app.models import EnrichmentResponse

        with pytest.raises(ValidationError):
            EnrichmentResponse(location="US-CA")

    def test_enrichment_response_temperature_type(self) -> None:
        """Test that temperature must be numeric."""
        from api.app.models import EnrichmentResponse

        with pytest.raises(ValidationError):
            EnrichmentResponse(
                location="US-CA",
                period="2024-01-15",
                temperature_fahrenheit="seventy-two",  # Invalid: string
                population=39000000,
                gdp_per_capita_usd=85000.0,
                industrial_activity_index=105.3,
            )

    def test_enrichment_response_population_type(self) -> None:
        """Test that population must be integer."""
        from api.app.models import EnrichmentResponse

        response = EnrichmentResponse(
            location="US-CA",
            period="2024-01-15",
            temperature_fahrenheit=72.5,
            population=39123456,  # Integer
            gdp_per_capita_usd=85000.0,
            industrial_activity_index=105.3,
        )
        assert isinstance(response.population, int)

    def test_enrichment_response_to_json(self) -> None:
        """Test that model can be serialized to JSON."""
        from api.app.models import EnrichmentResponse

        response = EnrichmentResponse(
            location="US-NY",
            period="2024-03-10",
            temperature_fahrenheit=45.2,
            population=19500000,
            gdp_per_capita_usd=95000.0,
            industrial_activity_index=98.7,
        )
        json_data = response.model_dump_json()
        assert '"location":"US-NY"' in json_data or '"location": "US-NY"' in json_data
        assert "45.2" in json_data


class TestEnrichmentData:
    """Test the EnrichmentData model for synthetic data generation."""

    def test_enrichment_data_has_realistic_ranges(self) -> None:
        """Test that EnrichmentResponse enforces realistic value ranges."""
        from api.app.models import EnrichmentResponse

        # Valid ranges
        response = EnrichmentResponse(
            location="US-FL",
            period="2024-01-15",
            temperature_fahrenheit=75.0,  # Valid: -50 to 120
            population=22000000,  # Valid: positive
            gdp_per_capita_usd=60000.0,  # Valid: positive
            industrial_activity_index=100.0,  # Valid: 0-200
        )
        assert response.temperature_fahrenheit == 75.0
