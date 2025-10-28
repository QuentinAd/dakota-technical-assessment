"""
Report generation Dagster asset.

Generates Jupyter notebook reports with visualizations and exports to PDF.
"""

import os
from pathlib import Path
from typing import Any

from dagster import AssetExecutionContext, AssetIn, MetadataValue, Output, asset

from reports.generators.report_generator import ReportGenerator


@asset(
    name="report_generation",
    description="Generate energy analytics report with visualizations and PDF export",
    group_name="reporting",
    compute_kind="jupyter",
    ins={
        "dbt_transformation": AssetIn(key="dbt_transformation"),
        "data_quality_check_marts": AssetIn(key="data_quality_check_marts"),
    },
)
async def report_generation(
    context: AssetExecutionContext,
    dbt_transformation: dict[str, Any],
    data_quality_check_marts: dict[str, Any],
) -> Output[dict[str, Any]]:
    """
    Dagster asset that generates energy analytics reports.

    This asset:
    - Depends on dbt transformation and quality checks completing
    - Executes Jupyter notebook with data from marts
    - Exports notebook to PDF for distribution
    - Stores outputs in reports/output directory

    Args:
        dbt_transformation: Results from dbt transformation asset
        data_quality_check_marts: Results from marts quality check asset

    Returns:
        Materialization with paths to generated notebook and PDF
    """
    # Get configuration from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Verify quality checks passed
    if data_quality_check_marts.get("status") != "pass":
        context.log.warning(f"Data quality checks did not pass: {data_quality_check_marts}")

    context.log.info("Starting report generation")
    context.log.info(f"dbt transformation status: {dbt_transformation.get('status')}")
    context.log.info(f"Data quality status: {data_quality_check_marts.get('status')}")

    # Paths (3 levels up from assets directory to get to /opt/dagster/app)
    project_root = Path(__file__).parent.parent.parent
    template_path = project_root / "reports" / "templates" / "energy_analytics_report.ipynb"
    output_dir = project_root / "reports" / "output"

    # Create report generator
    generator = ReportGenerator(database_url=database_url)

    # Generate report
    try:
        result = await generator.generate_report(template_path=template_path, output_dir=output_dir)

        context.log.info(f"Report generation completed: {result['data_rows']} rows analyzed")
        context.log.info(f"Notebook: {result['notebook_path']}")
        context.log.info(f"PDF: {result['pdf_path']}")

        # Return output with metadata
        return Output(
            value=result,
            metadata={
                "notebook_path": MetadataValue.text(result["notebook_path"]),
                "pdf_path": MetadataValue.text(result["pdf_path"]),
                "data_rows": MetadataValue.int(result["data_rows"]),
                "timestamp": MetadataValue.text(result["timestamp"]),
                "status": MetadataValue.text(result["status"]),
            },
        )

    except Exception as e:
        context.log.error(f"Report generation failed: {str(e)}")
        raise
