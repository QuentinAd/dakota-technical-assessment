"""
Report generator for energy analytics.

Executes Jupyter notebooks with data from the marts layer and exports to PDF.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import nbformat
from nbconvert import PDFExporter
from nbconvert.preprocessors import ExecutePreprocessor


class ReportGenerationError(Exception):
    """Exception raised when report generation fails."""

    pass


class ReportGenerator:
    """
    Generate reports from Jupyter notebooks with data from the database.

    Features:
    - Query data from marts layer
    - Execute Jupyter notebooks with parameters
    - Export notebooks to PDF
    - Handle errors gracefully
    """

    def __init__(self, database_url: str):
        """
        Initialize report generator.

        Args:
            database_url: PostgreSQL connection URL

        Raises:
            ValueError: If database_url is empty
        """
        if not database_url or database_url.strip() == "":
            raise ValueError("database_url is required and cannot be empty")

        self.database_url = database_url.strip()

    async def query_energy_metrics(self) -> list[dict[str, Any]]:
        """
        Query energy metrics from the marts layer.

        Returns:
            List of energy metrics records

        Raises:
            Exception: If database query fails
        """
        query = """
        SELECT
            time_key,
            location_key,
            total_generation_mwh,
            renewable_percentage,
            avg_temperature_fahrenheit
        FROM marts.fct_energy_metrics
        ORDER BY time_key DESC
        LIMIT 1000
        """

        pool = await asyncpg.create_pool(self.database_url)
        try:
            async with pool.acquire() as conn:
                records = await conn.fetch(query)
                return [dict(record) for record in records]
        finally:
            await pool.close()

    def execute_notebook(
        self, notebook_path: Path, output_path: Path, parameters: dict[str, Any] = None
    ) -> Path:
        """
        Execute a Jupyter notebook with optional parameters.

        Args:
            notebook_path: Path to template notebook
            output_path: Path to save executed notebook
            parameters: Dictionary of parameters to inject into notebook

        Returns:
            Path to executed notebook

        Raises:
            Exception: If notebook execution fails
        """
        # Read the notebook
        with open(notebook_path, encoding="utf-8") as f:
            nb = nbformat.read(f, as_version=4)

        # Inject parameters if provided
        if parameters:
            # Create a new cell with parameters
            param_cell = nbformat.v4.new_code_cell(
                source="\n".join([f"{key} = {repr(value)}" for key, value in parameters.items()])
            )
            nb.cells.insert(0, param_cell)

        # Execute the notebook
        ep = ExecutePreprocessor(timeout=600, kernel_name="python3")
        ep.preprocess(nb, {"metadata": {"path": str(notebook_path.parent)}})

        # Write the executed notebook
        with open(output_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        return output_path

    def export_to_pdf(self, notebook_path: Path, pdf_path: Path) -> Path:
        """
        Export a Jupyter notebook to PDF.

        Args:
            notebook_path: Path to executed notebook
            pdf_path: Path to save PDF

        Returns:
            Path to exported PDF

        Raises:
            ReportGenerationError: If PDF export fails
        """
        try:
            # Create PDF exporter
            pdf_exporter = PDFExporter()

            # Export to PDF
            (body, resources) = pdf_exporter.from_filename(str(notebook_path))

            # Write PDF file
            with open(pdf_path, "wb") as f:
                f.write(body)

            return pdf_path
        except Exception as e:
            raise ReportGenerationError(f"Failed to export PDF: {e}") from e

    async def generate_report(self, template_path: Path, output_dir: Path) -> dict[str, Any]:
        """
        Generate a complete report with notebook execution and PDF export.

        Args:
            template_path: Path to template notebook
            output_dir: Directory to save outputs

        Returns:
            Dictionary with paths to generated files and status

        Raises:
            Exception: If report generation fails
        """
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Query data
        data = await self.query_energy_metrics()

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Execute notebook
        notebook_path = output_dir / f"energy_analytics_{timestamp}.ipynb"
        executed_notebook = self.execute_notebook(
            notebook_path=template_path,
            output_path=notebook_path,
            parameters={"data_count": len(data), "report_date": report_date},
        )

        # Export to PDF
        pdf_path = output_dir / f"energy_analytics_{timestamp}.pdf"
        exported_pdf = self.export_to_pdf(notebook_path=executed_notebook, pdf_path=pdf_path)

        return {
            "status": "success",
            "notebook_path": str(executed_notebook),
            "pdf_path": str(exported_pdf),
            "data_rows": len(data),
            "timestamp": timestamp,
        }


# Helper functions for notebook usage


def calculate_renewable_percentage(renewable_generation: float, total_generation: float) -> float:
    """
    Calculate renewable energy percentage.

    Args:
        renewable_generation: Renewable generation in MWh
        total_generation: Total generation in MWh

    Returns:
        Percentage of renewable energy (0-100)
    """
    if total_generation == 0:
        return 0.0
    return (renewable_generation / total_generation) * 100


def format_date_for_display(date: datetime) -> str:
    """
    Format date for display in reports.

    Args:
        date: Date to format

    Returns:
        Formatted date string (YYYY-MM-DD)
    """
    return date.strftime("%Y-%m-%d")


def aggregate_by_location(data: list[dict[str, Any]], metric: str) -> dict[str, float]:
    """
    Aggregate metrics by location.

    Args:
        data: List of data records
        metric: Metric field to aggregate

    Returns:
        Dictionary mapping location to aggregated value
    """
    aggregated = {}
    for record in data:
        location = record["location"]
        value = record[metric]

        if location in aggregated:
            aggregated[location] += value
        else:
            aggregated[location] = value

    return aggregated
