"""
Unit tests for Dagster orchestration assets.

Tests asset definitions, dependencies, and execution logic using mocks.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEIAIngestionAsset:
    """Tests for the EIA ingestion Dagster asset."""

    @pytest.mark.asyncio
    async def test_eia_ingestion_asset_exists(self):
        """Test that the EIA ingestion asset is properly defined."""
        from dagster import AssetsDefinition
        from dagster_project.assets.eia_ingestion import eia_ingestion

        # Asset should be a Dagster AssetsDefinition
        assert isinstance(eia_ingestion, AssetsDefinition)

    @pytest.mark.asyncio
    async def test_eia_ingestion_calls_client_and_writer(self):
        """Test that EIA ingestion fetches data and writes to database."""
        from dagster_project.assets.eia_ingestion import eia_ingestion_impl

        # Mock the EIA client - it returns a LIST directly (not a dict with response/data)
        mock_client = AsyncMock()
        mock_data = [{"period": "2024-01", "location": "US-CA", "value": 1000.0, "units": "MWh"}]
        mock_client.fetch_electricity_generation.return_value = mock_data

        # Mock the database writer
        mock_writer = AsyncMock()
        mock_writer.write_batch.return_value = 12  # 12 months * 1 record each

        # Execute the asset implementation
        result = await eia_ingestion_impl(
            client=mock_client, writer=mock_writer, start_date="2024-01", end_date="2024-12"
        )

        # Verify client was called once per month (12 times for 2024-01 to 2024-12)
        assert mock_client.fetch_electricity_generation.call_count == 12

        # Verify it fetched each month individually
        calls = mock_client.fetch_electricity_generation.call_args_list
        assert calls[0][1] == {"start_date": "2024-01", "end_date": "2024-01"}
        assert calls[11][1] == {"start_date": "2024-12", "end_date": "2024-12"}

        # Verify writer was called with all data
        mock_writer.write_batch.assert_called_once()
        assert result["records_written"] > 0
        assert result["months_fetched"] == 12

    @pytest.mark.asyncio
    async def test_eia_ingestion_handles_empty_response(self):
        """Test that EIA ingestion handles empty data gracefully."""
        from dagster_project.assets.eia_ingestion import eia_ingestion_impl

        mock_client = AsyncMock()
        # Client returns an empty list directly
        mock_client.fetch_electricity_generation.return_value = []

        mock_writer = AsyncMock()
        mock_writer.write_batch.return_value = 0

        result = await eia_ingestion_impl(
            client=mock_client, writer=mock_writer, start_date="2024-01", end_date="2024-12"
        )

        assert result["records_written"] == 0

    @pytest.mark.asyncio
    async def test_eia_ingestion_handles_client_error(self):
        """Test that EIA ingestion handles client errors properly."""
        from dagster_project.assets.eia_ingestion import eia_ingestion_impl

        from ingestion.clients.eia_client import EIAAPIError

        mock_client = AsyncMock()
        mock_client.fetch_electricity_generation.side_effect = EIAAPIError("API Error")

        mock_writer = AsyncMock()

        with pytest.raises(EIAAPIError):
            await eia_ingestion_impl(
                client=mock_client, writer=mock_writer, start_date="2024-01", end_date="2024-12"
            )


class TestEnrichmentIngestionAsset:
    """Tests for the enrichment ingestion Dagster asset."""

    @pytest.mark.asyncio
    async def test_enrichment_ingestion_asset_exists(self):
        """Test that the enrichment ingestion asset is properly defined."""
        from dagster import AssetsDefinition
        from dagster_project.assets.enrichment_ingestion import enrichment_ingestion

        # Asset should be a Dagster AssetsDefinition
        assert isinstance(enrichment_ingestion, AssetsDefinition)

    @pytest.mark.asyncio
    async def test_enrichment_ingestion_calls_client_and_writer(self):
        """Test that enrichment ingestion fetches data for multiple months."""
        from dagster_project.assets.enrichment_ingestion import enrichment_ingestion_impl

        # Mock the enrichment client
        mock_client = AsyncMock()
        mock_data = {
            "location": "US-CA",
            "date": "2024-01-01",
            "temperature_fahrenheit": 65.5,
            "population": 39000000,
        }
        mock_client.fetch_enrichment_data.return_value = [mock_data]

        # Mock the database writer
        mock_writer = AsyncMock()
        mock_writer.write_batch.return_value = 4  # 4 locations

        # Execute the asset implementation (3 months: Jan, Feb, Mar)
        result = await enrichment_ingestion_impl(
            client=mock_client,
            writer=mock_writer,
            locations=["US-CA", "US-TX", "US-NY", "US-FL"],
            start_date=date(2024, 1, 15),
            end_date=date(2024, 3, 15),
        )

        # Verify client was called for each month (3 times)
        assert mock_client.fetch_enrichment_data.call_count == 3

        # Verify writer was called with data for each month
        assert mock_writer.write_batch.call_count == 3
        assert result["records_written"] == 12  # 4 locations * 3 months
        assert result["months"] == ["2024-01", "2024-02", "2024-03"]

    @pytest.mark.asyncio
    async def test_enrichment_ingestion_handles_empty_response(self):
        """Test that enrichment ingestion handles empty data gracefully."""
        from dagster_project.assets.enrichment_ingestion import enrichment_ingestion_impl

        mock_client = AsyncMock()
        mock_client.fetch_enrichment_data.return_value = []

        mock_writer = AsyncMock()
        mock_writer.write_batch.return_value = 0

        result = await enrichment_ingestion_impl(
            client=mock_client,
            writer=mock_writer,
            locations=["US-CA"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        assert result["records_written"] == 0


class TestDbtTransformationAsset:
    """Tests for the dbt transformation Dagster asset."""

    def test_dbt_transformation_asset_exists(self):
        """Test that the dbt transformation asset is properly defined."""
        from dagster import AssetsDefinition
        from dagster_project.assets.dbt_transformation import dbt_transformation

        # Asset should be a Dagster AssetsDefinition
        assert isinstance(dbt_transformation, AssetsDefinition)

    @pytest.mark.asyncio
    async def test_dbt_transformation_runs_dbt_models(self):
        """Test that dbt transformation runs dbt models successfully."""
        from dagster_project.assets.dbt_transformation import dbt_transformation_impl

        # Mock subprocess run for dbt command
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Done.")

            result = await dbt_transformation_impl()

            # Verify dbt run was called (using uv run dbt)
            mock_run.assert_called_once()
            command_list = mock_run.call_args[0][0]
            assert "dbt" in command_list, f"Expected 'dbt' in command list but got: {command_list}"
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_dbt_transformation_handles_failure(self):
        """Test that dbt transformation handles dbt command failures."""
        from dagster_project.assets.dbt_transformation import (
            DbtTransformationError,
            dbt_transformation_impl,
        )

        # Mock subprocess run to fail
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="Error", stderr="dbt failed")

            with pytest.raises(DbtTransformationError):
                await dbt_transformation_impl()


class TestDataQualityChecks:
    """Tests for data quality check assets."""

    @pytest.mark.asyncio
    async def test_data_quality_check_validates_row_counts(self):
        """Test that data quality checks validate row counts."""
        from unittest.mock import MagicMock

        from dagster_project.assets.data_quality_checks import check_raw_data_exists

        # Mock database connection properly
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(
            side_effect=[100, 100]
        )  # EIA count, then enrichment count

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await check_raw_data_exists(mock_pool)

        assert result["raw_eia_count"] == 100
        assert result["raw_enrichment_count"] == 100
        assert result["status"] == "pass"

    @pytest.mark.asyncio
    async def test_data_quality_check_fails_on_zero_rows(self):
        """Test that data quality checks fail when no data exists."""
        from unittest.mock import MagicMock

        from dagster_project.assets.data_quality_checks import check_raw_data_exists

        # Mock database connection with zero rows
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(side_effect=[0, 0])  # No rows for either table

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await check_raw_data_exists(mock_pool)

        assert result["raw_eia_count"] == 0
        assert result["raw_enrichment_count"] == 0
        assert result["status"] == "fail"


class TestSchedules:
    """Tests for Dagster schedules."""

    def test_daily_eia_schedule_exists(self):
        """Test that daily EIA ingestion schedule exists."""
        from dagster import ScheduleDefinition
        from dagster_project.schedules.daily_batch import daily_eia_schedule

        # Schedule should be a Dagster ScheduleDefinition
        assert isinstance(daily_eia_schedule, ScheduleDefinition)

    def test_hourly_enrichment_schedule_exists(self):
        """Test that hourly enrichment schedule exists."""
        from dagster import ScheduleDefinition
        from dagster_project.schedules.daily_batch import hourly_enrichment_schedule

        # Schedule should be a Dagster ScheduleDefinition
        assert isinstance(hourly_enrichment_schedule, ScheduleDefinition)
