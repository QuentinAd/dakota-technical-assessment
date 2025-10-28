"""
EIA ingestion Dagster asset.

Fetches electricity generation data from EIA API and stores it in the raw schema.
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from dagster import AssetExecutionContext, MetadataValue, Output, asset

from ingestion.clients.eia_client import EIAClient
from ingestion.writers.database_writer import EIADataWriter


async def eia_ingestion_impl(
    client: EIAClient, writer: EIADataWriter, start_date: str, end_date: str
) -> dict[str, Any]:
    """
    Implementation logic for EIA ingestion.

    Args:
        client: EIA API client
        writer: Database writer for EIA data
        start_date: Start date in YYYY-MM format
        end_date: End date in YYYY-MM format

    Returns:
        Dictionary with ingestion results

    Raises:
        EIAAPIError: If API request fails
        DatabaseWriteError: If database write fails
    """
    # EIA API limits responses to 5000 records per request
    # To get all months in range, fetch each month individually
    from dateutil.relativedelta import relativedelta

    start_dt = datetime.strptime(start_date, "%Y-%m")
    end_dt = datetime.strptime(end_date, "%Y-%m")

    all_records = []
    current_date = start_dt
    months_fetched = 0

    # Fetch each month separately to avoid API pagination limits
    while current_date <= end_dt:
        month_str = current_date.strftime("%Y-%m")
        month_records = await client.fetch_electricity_generation(
            start_date=month_str, end_date=month_str
        )
        all_records.extend(month_records)
        months_fetched += 1
        current_date += relativedelta(months=1)

    # Write all records to database
    records_written = 0
    if all_records:
        records_written = await writer.write_batch(all_records)

    return {
        "records_written": records_written,
        "start_date": start_date,
        "end_date": end_date,
        "months_fetched": months_fetched,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@asset(
    name="eia_ingestion",
    description="Ingest electricity generation data from EIA API into raw schema",
    group_name="ingestion",
    compute_kind="python",
)
async def eia_ingestion(context: AssetExecutionContext) -> Output[dict[str, Any]]:
    """
    Dagster asset that ingests EIA electricity generation data.

    This asset:
    - Fetches daily electricity generation data from EIA API
    - Stores raw data in the PostgreSQL raw schema
    - Runs on a daily schedule
    - Includes retry logic and error handling

    Returns:
        Materialization with metadata about ingestion results
    """
    # Get configuration from environment
    api_key = os.getenv("EIA_API_KEY")
    database_url = os.getenv("DATABASE_URL")

    if not api_key:
        raise ValueError("EIA_API_KEY environment variable is required")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Calculate date range - EIA publishes monthly data with ~2 month lag
    # (utilities report → EIA validates → published ~60 days later)
    # Fetch the most recent 3 months of available data
    now = datetime.now(UTC)
    end_date = now - timedelta(days=60)  # 2 months ago (most recent available)
    start_date = end_date - timedelta(days=90)  # 3 months of data

    start_date_str = start_date.strftime("%Y-%m")
    end_date_str = end_date.strftime("%Y-%m")

    context.log.info(f"Starting EIA ingestion for {start_date_str} to {end_date_str}")

    # Create client and writer
    async with (
        EIAClient(api_key=api_key) as client,
        EIADataWriter(database_url=database_url) as writer,
    ):
        # Execute ingestion
        result = await eia_ingestion_impl(
            client=client, writer=writer, start_date=start_date_str, end_date=end_date_str
        )

    context.log.info(f"EIA ingestion completed: {result['records_written']} records written")

    # Return output with metadata
    return Output(
        value=result,
        metadata={
            "records_written": MetadataValue.int(result["records_written"]),
            "start_date": MetadataValue.text(result["start_date"]),
            "end_date": MetadataValue.text(result["end_date"]),
            "timestamp": MetadataValue.text(result["timestamp"]),
        },
    )
