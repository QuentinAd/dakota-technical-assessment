"""
Enrichment data ingestion Dagster asset.

Fetches enrichment data from FastAPI service and stores it in the raw schema.
"""

import os
from datetime import UTC, date, datetime, timedelta
from typing import Any

from dagster import AssetExecutionContext, MetadataValue, Output, asset

from ingestion.clients.enrichment_client import EnrichmentClient
from ingestion.writers.database_writer import EnrichmentDataWriter


async def enrichment_ingestion_impl(
    client: EnrichmentClient,
    writer: EnrichmentDataWriter,
    locations: list[str],
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Implementation logic for enrichment data ingestion.

    Fetches enrichment data for multiple months to match EIA data availability.

    Args:
        client: Enrichment API client
        writer: Database writer for enrichment data
        locations: List of location codes to fetch data for
        start_date: Start date for data fetching
        end_date: End date for data fetching

    Returns:
        Dictionary with ingestion results

    Raises:
        EnrichmentAPIError: If API request fails
        DatabaseWriteError: If database write fails
    """
    # Generate list of first day of each month in the date range
    current = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)

    total_records_written = 0
    months_processed = []

    while current <= end_month:
        # Fetch data for this month's first day (for all locations)
        records = await client.fetch_enrichment_data(locations=locations, date=current)

        # Write to database
        if records:
            records_written = await writer.write_batch(records)
            total_records_written += records_written

        months_processed.append(current.strftime("%Y-%m"))

        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return {
        "records_written": total_records_written,
        "locations": locations,
        "months": months_processed,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@asset(
    name="enrichment_ingestion",
    description="Ingest enrichment data from FastAPI service into raw schema",
    group_name="ingestion",
    compute_kind="python",
)
async def enrichment_ingestion(context: AssetExecutionContext) -> Output[dict[str, Any]]:
    """
    Dagster asset that ingests enrichment data from FastAPI service.

    This asset:
    - Fetches enrichment data (weather, economic indicators, etc.)
    - Stores raw data in the PostgreSQL raw schema
    - Runs on an hourly schedule
    - Includes retry logic and error handling

    Returns:
        Materialization with metadata about ingestion results
    """
    # Get configuration from environment
    api_url = os.getenv("ENRICHMENT_API_URL", "http://enrichment-api:8000")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Match EIA date range calculation: 2 months ago for end, 3 months of data
    # This ensures enrichment data aligns with EIA data availability
    now = datetime.now(UTC)
    end_date = (now - timedelta(days=60)).date()  # 2 months ago
    start_date = end_date - timedelta(days=90)  # 3 months of data

    # Locations WITH "US-" prefix to match dim_location table
    # The dimension tables use standardized "US-XX" format
    locations = ["US-CA", "US-TX", "US-NY", "US-FL"]

    context.log.info(
        f"Starting enrichment ingestion for {len(locations)} locations from {start_date} to {end_date}"
    )

    # Create client and writer
    async with (
        EnrichmentClient(base_url=api_url) as client,
        EnrichmentDataWriter(database_url=database_url) as writer,
    ):
        # Execute ingestion
        result = await enrichment_ingestion_impl(
            client=client,
            writer=writer,
            locations=locations,
            start_date=start_date,
            end_date=end_date,
        )

    context.log.info(
        f"Enrichment ingestion completed: {result['records_written']} records "
        f"for months {', '.join(result['months'])}"
    )

    # Return output with metadata
    return Output(
        value=result,
        metadata={
            "records_written": MetadataValue.int(result["records_written"]),
            "locations": MetadataValue.text(", ".join(result["locations"])),
            "months": MetadataValue.text(", ".join(result["months"])),
            "start_date": MetadataValue.text(result["start_date"]),
            "end_date": MetadataValue.text(result["end_date"]),
            "timestamp": MetadataValue.text(result["timestamp"]),
        },
    )
