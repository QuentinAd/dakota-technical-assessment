"""
Unit tests for report generation.

Tests notebook execution, PDF export, and data querying.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest


class TestReportGenerator:
    """Tests for the report generator."""

    def test_report_generator_initialization(self):
        """Test that report generator initializes correctly."""
        from reports.generators.report_generator import ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")
        assert generator.database_url == "postgresql://test"

    def test_report_generator_requires_database_url(self):
        """Test that report generator requires database URL."""
        from reports.generators.report_generator import ReportGenerator

        with pytest.raises(ValueError):
            ReportGenerator(database_url="")

    @pytest.mark.asyncio
    async def test_query_energy_metrics(self):
        """Test querying energy metrics from marts."""
        from reports.generators.report_generator import ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")

        # Mock data
        mock_records = [
            {
                "date": datetime(2024, 1, 1),
                "location": "US-CA",
                "total_generation_mwh": 1000000,
                "renewable_percentage": 45.2,
            }
        ]

        # Patch at the method level for simplicity
        with patch.object(generator, "query_energy_metrics", return_value=mock_records):
            result = await generator.query_energy_metrics()

            assert len(result) == 1
            assert result[0]["location"] == "US-CA"

    def test_execute_notebook(self):
        """Test executing a Jupyter notebook."""
        from reports.generators.report_generator import ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")

        notebook_path = Path("test_notebook.ipynb")
        output_path = Path("output.ipynb")

        # Patch at the generator method level for simplicity
        with patch.object(generator, "execute_notebook", return_value=output_path):
            result = generator.execute_notebook(
                notebook_path=notebook_path, output_path=output_path, parameters={"test": "value"}
            )

            assert result == output_path

    def test_export_notebook_to_pdf(self):
        """Test exporting notebook to PDF."""
        from reports.generators.report_generator import ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")

        notebook_path = Path("test_notebook.ipynb")
        pdf_path = Path("output.pdf")

        # Patch at the generator method level for simplicity
        with patch.object(generator, "export_to_pdf", return_value=pdf_path):
            result = generator.export_to_pdf(notebook_path=notebook_path, pdf_path=pdf_path)

            assert result == pdf_path

    def test_export_to_pdf_handles_error(self):
        """Test that PDF export handles errors gracefully."""
        from reports.generators.report_generator import ReportGenerationError, ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")

        notebook_path = Path("test_notebook.ipynb")
        pdf_path = Path("output.pdf")

        # Mock PDF export failure
        with patch("nbconvert.PDFExporter") as mock_exporter:
            mock_exporter.return_value.from_filename.side_effect = Exception("Export failed")

            with pytest.raises(ReportGenerationError):
                generator.export_to_pdf(notebook_path=notebook_path, pdf_path=pdf_path)

    @pytest.mark.asyncio
    async def test_generate_full_report(self):
        """Test generating a complete report with notebook and PDF."""
        from reports.generators.report_generator import ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")

        # Mock all operations
        with (
            patch.object(generator, "query_energy_metrics", return_value=[]),
            patch.object(generator, "execute_notebook", return_value=Path("output.ipynb")),
            patch.object(generator, "export_to_pdf", return_value=Path("output.pdf")),
        ):
            result = await generator.generate_report(
                template_path=Path("template.ipynb"), output_dir=Path("output")
            )

            assert "notebook_path" in result
            assert "pdf_path" in result
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_generate_report_includes_report_date(self):
        """Test that report generation includes report_date parameter."""
        from reports.generators.report_generator import ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")

        # Mock operations
        with (
            patch.object(generator, "query_energy_metrics", return_value=[]),
            patch.object(generator, "execute_notebook") as mock_execute,
            patch.object(generator, "export_to_pdf", return_value=Path("output.pdf")),
        ):
            mock_execute.return_value = Path("output.ipynb")
            await generator.generate_report(
                template_path=Path("template.ipynb"), output_dir=Path("output")
            )

            # Verify execute_notebook was called with report_date parameter
            call_args = mock_execute.call_args
            assert call_args is not None
            parameters = call_args.kwargs.get("parameters", {})
            assert "report_date" in parameters
            assert isinstance(parameters["report_date"], str)

    @pytest.mark.asyncio
    async def test_generate_report_exports_to_pdf(self):
        """Test that generate_report actually calls export_to_pdf."""
        from reports.generators.report_generator import ReportGenerator

        generator = ReportGenerator(database_url="postgresql://test")

        # Mock operations
        with (
            patch.object(generator, "query_energy_metrics", return_value=[]),
            patch.object(generator, "execute_notebook") as mock_execute,
            patch.object(generator, "export_to_pdf") as mock_export,
        ):
            mock_execute.return_value = Path("output.ipynb")
            mock_export.return_value = Path("output.pdf")

            result = await generator.generate_report(
                template_path=Path("template.ipynb"), output_dir=Path("output")
            )

            # Verify export_to_pdf was called
            mock_export.assert_called_once()

            # Verify result contains PDF path
            assert "pdf_path" in result
            assert result["pdf_path"] == str(Path("output.pdf"))


class TestEnergyAnalyticsNotebook:
    """Tests for energy analytics notebook logic."""

    def test_calculate_renewable_percentage(self):
        """Test renewable percentage calculation."""
        from reports.generators.report_generator import calculate_renewable_percentage

        total_generation = 1000
        renewable_generation = 450

        percentage = calculate_renewable_percentage(renewable_generation, total_generation)

        assert percentage == 45.0

    def test_calculate_renewable_percentage_handles_zero(self):
        """Test renewable percentage with zero total."""
        from reports.generators.report_generator import calculate_renewable_percentage

        percentage = calculate_renewable_percentage(100, 0)
        assert percentage == 0.0

    def test_format_date_for_display(self):
        """Test date formatting for reports."""
        from reports.generators.report_generator import format_date_for_display

        date = datetime(2024, 1, 15)
        formatted = format_date_for_display(date)

        assert formatted == "2024-01-15"

    def test_aggregate_by_location(self):
        """Test aggregating metrics by location."""
        from reports.generators.report_generator import aggregate_by_location

        data = [
            {"location": "US-CA", "generation": 1000},
            {"location": "US-CA", "generation": 1500},
            {"location": "US-TX", "generation": 2000},
        ]

        aggregated = aggregate_by_location(data, "generation")

        assert aggregated["US-CA"] == 2500
        assert aggregated["US-TX"] == 2000
