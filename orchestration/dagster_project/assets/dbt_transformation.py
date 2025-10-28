"""
dbt transformation Dagster asset.

Runs dbt models to transform raw data into analytics-ready tables.
"""

import os
import subprocess
from typing import Any

from dagster import AssetExecutionContext, AssetIn, MetadataValue, Output, asset


class DbtTransformationError(Exception):
    """Exception raised when dbt transformation fails."""

    pass


async def dbt_transformation_impl() -> dict[str, Any]:
    """
    Implementation logic for dbt transformation.

    Runs dbt models in the correct directory with proper configuration.

    Returns:
        Dictionary with transformation results

    Raises:
        DbtTransformationError: If dbt command fails
    """
    # Change to dbt directory (2 levels up from assets directory)
    dbt_dir = os.path.join(os.path.dirname(__file__), "..", "..", "dbt")
    dbt_dir = os.path.abspath(dbt_dir)

    # Run dbt models using uv with full path
    result = subprocess.run(
        ["/usr/local/bin/uv", "run", "dbt", "run"],
        cwd=dbt_dir,
        capture_output=True,
        text=True,
        timeout=180,  # 3 minute timeout
    )

    if result.returncode != 0:
        error_msg = f"dbt run failed with return code {result.returncode}:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        raise DbtTransformationError(error_msg)

    return {"status": "success", "output": result.stdout}


@asset(
    name="dbt_transformation",
    description="Transform raw data using dbt models",
    group_name="transformation",
    compute_kind="dbt",
    ins={
        "eia_ingestion": AssetIn(key="eia_ingestion"),
        "enrichment_ingestion": AssetIn(key="enrichment_ingestion"),
    },
)
async def dbt_transformation(
    context: AssetExecutionContext,
    eia_ingestion: dict[str, Any],
    enrichment_ingestion: dict[str, Any],
) -> Output[dict[str, Any]]:
    """
    Dagster asset that runs dbt transformations.

    This asset:
    - Depends on both ingestion assets completing
    - Runs all dbt models (staging → intermediate → marts)
    - Executes data quality tests
    - Creates analytics-ready tables

    Args:
        eia_ingestion: Results from EIA ingestion asset
        enrichment_ingestion: Results from enrichment ingestion asset

    Returns:
        Materialization with metadata about transformation results
    """
    context.log.info("Starting dbt transformation")
    context.log.info(f"EIA records available: {eia_ingestion.get('records_written', 0)}")
    context.log.info(
        f"Enrichment records available: {enrichment_ingestion.get('records_written', 0)}"
    )

    # Execute dbt transformation
    result = await dbt_transformation_impl()

    context.log.info("dbt transformation completed successfully")

    # Return output with metadata
    return Output(
        value=result,
        metadata={
            "status": MetadataValue.text(result["status"]),
            "dbt_output": MetadataValue.md(f"```\n{result['output']}\n```"),
        },
    )
