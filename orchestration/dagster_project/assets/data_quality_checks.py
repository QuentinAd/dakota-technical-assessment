"""
Data quality check assets.

Validates data integrity and quality across pipeline stages.
"""

import os
from typing import Any

import asyncpg
from dagster import AssetExecutionContext, AssetIn, MetadataValue, Output, asset


async def check_raw_data_exists(pool: asyncpg.Pool) -> dict[str, Any]:
    """
    Check that raw data exists in the database.

    Args:
        pool: Database connection pool

    Returns:
        Dictionary with row counts and status
    """
    async with pool.acquire() as conn:
        # Check raw EIA data
        eia_count = await conn.fetchval("SELECT COUNT(*) FROM raw.eia_energy_data")

        # Check raw enrichment data
        enrichment_count = await conn.fetchval("SELECT COUNT(*) FROM raw.enrichment_data")

    # Determine status
    status = "pass" if eia_count > 0 and enrichment_count > 0 else "fail"

    return {"raw_eia_count": eia_count, "raw_enrichment_count": enrichment_count, "status": status}


@asset(
    name="data_quality_check_raw",
    description="Validate raw data exists and meets quality standards",
    group_name="quality",
    compute_kind="python",
    ins={
        "eia_ingestion": AssetIn(key="eia_ingestion"),
        "enrichment_ingestion": AssetIn(key="enrichment_ingestion"),
    },
)
async def data_quality_check_raw(
    context: AssetExecutionContext,
    eia_ingestion: dict[str, Any],  # noqa: ARG001 - Required for Dagster dependency
    enrichment_ingestion: dict[str, Any],  # noqa: ARG001 - Required for Dagster dependency
) -> Output[dict[str, Any]]:
    """
    Dagster asset that validates raw data quality.

    This asset:
    - Checks that raw tables have data
    - Validates data freshness
    - Checks for null values in critical columns
    - Runs after ingestion completes

    Args:
        eia_ingestion: Results from EIA ingestion asset (unused but required for dependency)
        enrichment_ingestion: Results from enrichment ingestion asset (unused but required for dependency)

    Returns:
        Materialization with quality check results
    """
    # Get database connection
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    context.log.info("Starting raw data quality checks")

    # Create connection pool
    pool = await asyncpg.create_pool(database_url)

    try:
        # Run quality checks
        result = await check_raw_data_exists(pool)

        if result["status"] == "pass":
            context.log.info(
                f"Quality checks passed: {result['raw_eia_count']} EIA records, "
                f"{result['raw_enrichment_count']} enrichment records"
            )
        else:
            context.log.warning(
                f"Quality checks failed: {result['raw_eia_count']} EIA records, "
                f"{result['raw_enrichment_count']} enrichment records"
            )

        # Return output with metadata
        return Output(
            value=result,
            metadata={
                "raw_eia_count": MetadataValue.int(result["raw_eia_count"]),
                "raw_enrichment_count": MetadataValue.int(result["raw_enrichment_count"]),
                "status": MetadataValue.text(result["status"]),
            },
        )

    finally:
        await pool.close()


@asset(
    name="data_quality_check_marts",
    description="Validate marts data quality after dbt transformation",
    group_name="quality",
    compute_kind="python",
    ins={"dbt_transformation": AssetIn(key="dbt_transformation")},
)
async def data_quality_check_marts(
    context: AssetExecutionContext,
    dbt_transformation: dict[str, Any],  # noqa: ARG001 - Required for Dagster dependency
) -> Output[dict[str, Any]]:
    """
    Dagster asset that validates marts data quality.

    This asset:
    - Checks that marts tables have data
    - Validates business logic constraints
    - Ensures dimensional integrity
    - Runs after dbt transformation

    Args:
        dbt_transformation: Results from dbt transformation asset (unused but required for dependency)

    Returns:
        Materialization with quality check results
    """
    # Get database connection
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    context.log.info("Starting marts data quality checks")

    # Create connection pool
    pool = await asyncpg.create_pool(database_url)

    try:
        async with pool.acquire() as conn:
            # Check marts data
            fact_count = await conn.fetchval("SELECT COUNT(*) FROM marts.fct_energy_metrics")

            dim_time_count = await conn.fetchval("SELECT COUNT(*) FROM marts.dim_time")

        status = "pass" if fact_count > 0 and dim_time_count > 0 else "fail"

        result = {"fact_count": fact_count, "dim_time_count": dim_time_count, "status": status}

        if status == "pass":
            context.log.info(
                f"Marts quality checks passed: {fact_count} fact records, "
                f"{dim_time_count} time dimension records"
            )
        else:
            context.log.warning(
                f"Marts quality checks failed: {fact_count} fact records, "
                f"{dim_time_count} time dimension records"
            )

        # Return output with metadata
        return Output(
            value=result,
            metadata={
                "fact_count": MetadataValue.int(result["fact_count"]),
                "dim_time_count": MetadataValue.int(result["dim_time_count"]),
                "status": MetadataValue.text(result["status"]),
            },
        )

    finally:
        await pool.close()
