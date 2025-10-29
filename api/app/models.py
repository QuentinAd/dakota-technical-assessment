"""Pydantic models for the enrichment API.

These models define the request/response schemas for synthetic data generation.
"""

from pydantic import BaseModel, ConfigDict, Field


class EnrichmentRequest(BaseModel):
    """Request model for enrichment data generation.

    Attributes:
        location: Location code (e.g., 'US-CA', 'US-TX', 'US')
        period: Date or period string (e.g., '2024-01-15', '2024-01')
    """

    location: str = Field(..., description="Location code for data generation")
    period: str = Field(..., description="Time period for data generation")


class EnrichmentResponse(BaseModel):
    """Response model for generated enrichment data.

    Contains synthetic data to enrich energy analytics:
    - Weather data (temperature)
    - Economic indicators (GDP, population)
    - Industrial activity metrics
    """

    location: str = Field(..., description="Location code")
    period: str = Field(..., description="Time period")

    # Weather data
    temperature_fahrenheit: float = Field(
        ...,
        description="Average temperature in Fahrenheit",
    )

    # Economic indicators
    population: int = Field(..., description="Population estimate", gt=0)
    gdp_per_capita_usd: float = Field(
        ...,
        description="GDP per capita in USD",
        gt=0,
    )

    # Industrial activity
    industrial_activity_index: float = Field(
        ...,
        description="Industrial activity index (base 100)",
        ge=0,
        le=200,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "location": "US-CA",
                "period": "2024-01-15",
                "temperature_fahrenheit": 65.5,
                "population": 39000000,
                "gdp_per_capita_usd": 85000.0,
                "industrial_activity_index": 105.3,
            }
        }
    )
