"""FastAPI application for synthetic energy enrichment data generation.

This service provides synthetic data to enrich energy analytics, including:
- Weather data (temperature)
- Economic indicators (GDP, population)
- Industrial activity metrics
"""

from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from api.app.generator import (
    generate_gdp_per_capita,
    generate_industrial_activity_index,
    generate_population,
    generate_temperature,
)
from api.app.models import EnrichmentRequest, EnrichmentResponse

# Create FastAPI application
app = FastAPI(
    title="Energy Enrichment API",
    description="Synthetic data generation service for energy analytics enrichment",
    version="1.0.0",
)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    timestamp: str


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint for monitoring and orchestration.

    Returns:
        HealthResponse: Service health status with timestamp
    """
    return HealthResponse(
        status="healthy",
        service="enrichment-api",
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.post("/enrichment", response_model=EnrichmentResponse)
async def generate_enrichment(request: EnrichmentRequest) -> EnrichmentResponse:
    """Generate synthetic enrichment data for energy analytics.

    This endpoint generates deterministic synthetic data based on location and period.
    Same inputs always produce the same outputs (useful for testing and consistency).

    Args:
        request: EnrichmentRequest with location and period

    Returns:
        EnrichmentResponse with synthetic enrichment data including:
        - Temperature (weather data)
        - Population (demographic data)
        - GDP per capita (economic indicator)
        - Industrial activity index (economic indicator)
    """
    return EnrichmentResponse(
        location=request.location,
        period=request.period,
        temperature_fahrenheit=generate_temperature(request.location, request.period),
        population=generate_population(request.location),
        gdp_per_capita_usd=generate_gdp_per_capita(request.location, request.period),
        industrial_activity_index=generate_industrial_activity_index(
            request.location, request.period
        ),
    )
