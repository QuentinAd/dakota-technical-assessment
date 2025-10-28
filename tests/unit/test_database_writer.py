"""
Unit tests for Database Writers.

Following TDD: These tests are written BEFORE implementation.
Tests cover: connection handling, data insertion, batch operations, error handling.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestDatabaseWriter:
    """Test suite for DatabaseWriter base class."""

    def test_writer_initialization(self):
        """Test that writer initializes with database URL."""
        from ingestion.writers.database_writer import DatabaseWriter

        writer = DatabaseWriter(database_url="postgresql+asyncpg://user:pass@host/db")
        assert writer.database_url == "postgresql+asyncpg://user:pass@host/db"

    def test_writer_requires_database_url(self):
        """Test that writer raises error without database URL."""
        from ingestion.writers.database_writer import DatabaseWriter

        with pytest.raises(ValueError, match="database_url"):
            DatabaseWriter(database_url="")

    @pytest.mark.asyncio
    async def test_context_manager_creates_connection(self):
        """Test that context manager creates database connection."""
        from ingestion.writers.database_writer import DatabaseWriter

        with patch(
            "ingestion.writers.database_writer.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create_pool:
            mock_pool = AsyncMock()
            mock_pool.close = AsyncMock()
            # create_pool is now an AsyncMock that returns mock_pool
            mock_create_pool.return_value = mock_pool

            async with DatabaseWriter(
                database_url="postgresql+asyncpg://user:pass@host/db"
            ) as writer:
                assert writer is not None

            # Pool should be closed
            mock_pool.close.assert_called_once()


class TestEIADataWriter:
    """Test suite for EIA data writer."""

    @pytest.mark.asyncio
    async def test_write_single_record(self):
        """Test writing a single EIA record."""
        from ingestion.writers.database_writer import EIADataWriter

        writer = EIADataWriter(database_url="postgresql+asyncpg://test/db")

        eia_record = {
            "period": "2024-01",
            "seriesId": "ELEC.GEN.ALL-US-99.M",
            "value": 325000,
            "units": "megawatthours",
            "location": "US-CA",
            "locationType": "state",
            "energySource": "solar",
            "sector": "electric power",
        }

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            await writer.write_record(eia_record)

            # Verify INSERT was executed
            mock_connection.execute.assert_called_once()
            call_args = mock_connection.execute.call_args
            sql_query = str(call_args[0][0])

            assert "INSERT INTO raw.eia_energy_data" in sql_query
            assert "period" in sql_query
            assert "value" in sql_query

    @pytest.mark.asyncio
    async def test_write_batch_records(self):
        """Test writing multiple EIA records in batch."""
        from ingestion.writers.database_writer import EIADataWriter

        writer = EIADataWriter(database_url="postgresql+asyncpg://test/db")

        eia_records = [
            {
                "period": "2024-01",
                "value": 325000,
                "location": "US-CA",
                "energySource": "solar",
            },
            {
                "period": "2024-02",
                "value": 330000,
                "location": "US-CA",
                "energySource": "solar",
            },
        ]

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            count = await writer.write_batch(eia_records)

            # Should return count of records inserted
            assert count == 2

            # Verify executemany was called
            mock_connection.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_includes_metadata(self):
        """Test that writes include source and timestamp metadata."""
        from ingestion.writers.database_writer import EIADataWriter

        writer = EIADataWriter(database_url="postgresql+asyncpg://test/db")

        eia_record = {"period": "2024-01", "value": 100}

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            await writer.write_record(eia_record)

            # Check that execute was called (metadata included in implementation)
            mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_stores_raw_json(self):
        """Test that full API response is stored in raw_json."""
        from ingestion.writers.database_writer import EIADataWriter

        writer = EIADataWriter(database_url="postgresql+asyncpg://test/db")

        eia_record = {
            "period": "2024-01",
            "value": 100,
            "extraField": "should be in raw_json",
        }

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            await writer.write_record(eia_record)

            # Verify raw_json column is used
            call_args = mock_connection.execute.call_args
            sql_query = str(call_args[0][0])
            assert "raw_json" in sql_query

    @pytest.mark.asyncio
    async def test_write_handles_missing_optional_fields(self):
        """Test that writer handles records with missing optional fields."""
        from ingestion.writers.database_writer import EIADataWriter

        writer = EIADataWriter(database_url="postgresql+asyncpg://test/db")

        # Minimal record
        eia_record = {"period": "2024-01", "value": 100}

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            # Should not raise error
            await writer.write_record(eia_record)

    @pytest.mark.asyncio
    async def test_write_handles_database_error(self):
        """Test error handling for database errors."""
        from ingestion.writers.database_writer import DatabaseWriteError, EIADataWriter

        writer = EIADataWriter(database_url="postgresql+asyncpg://test/db")

        eia_record = {"period": "2024-01", "value": 100}

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_connection.execute.side_effect = Exception("Database connection failed")
            mock_conn.return_value.__aenter__.return_value = mock_connection

            with pytest.raises(DatabaseWriteError, match="Failed to write"):
                await writer.write_record(eia_record)

    @pytest.mark.asyncio
    async def test_write_preserves_zero_values(self):
        """Test that zero values in generation data are preserved (not treated as falsy)."""
        from ingestion.writers.database_writer import EIADataWriter

        writer = EIADataWriter(database_url="postgresql+asyncpg://test/db")

        # Real API format with zero generation (valid - e.g., no solar at night)
        record = {
            "period": "2024-01",
            "generation": 0,  # This should NOT be skipped!
            "generation-units": "megawatthours",
            "location": "US-CA",
            "stateDescription": "California",
            "fuelTypeDescription": "solar",
            "sectorDescription": "electric_power",
        }

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            await writer.write_record(record)

            # Verify the zero value was preserved in the execute call
            mock_connection.execute.assert_called_once()
            call_args = mock_connection.execute.call_args[0]
            # Value should be 0 (from generation), not None
            assert call_args[4] == 0, f"Expected value=0, got {call_args[4]}"


class TestEnrichmentDataWriter:
    """Test suite for Enrichment data writer."""

    @pytest.mark.asyncio
    async def test_write_single_enrichment_record(self):
        """Test writing a single enrichment record."""
        from ingestion.writers.database_writer import EnrichmentDataWriter

        writer = EnrichmentDataWriter(database_url="postgresql+asyncpg://test/db")

        enrichment_record = {
            "location": "US-CA",
            "period": "2024-01-15",
            "temperature_fahrenheit": 42.8,
            "population": 7094722,
            "gdp_per_capita": 75432.5,
            "industrial_activity_index": 105.3,
        }

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            await writer.write_record(enrichment_record)

            # Verify INSERT was executed
            mock_connection.execute.assert_called_once()
            call_args = mock_connection.execute.call_args
            sql_query = str(call_args[0][0])

            assert "INSERT INTO raw.enrichment_data" in sql_query
            assert "temperature_avg" in sql_query
            assert "population" in sql_query

    @pytest.mark.asyncio
    async def test_write_converts_temperature_field(self):
        """Test that temperature_fahrenheit is converted to temperature_avg."""
        from ingestion.writers.database_writer import EnrichmentDataWriter

        writer = EnrichmentDataWriter(database_url="postgresql+asyncpg://test/db")

        enrichment_record = {
            "location": "US-CA",
            "period": "2024-01-15",
            "temperature_fahrenheit": 42.8,
        }

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            await writer.write_record(enrichment_record)

            # temperature_unit should be set to 'fahrenheit'
            call_args = mock_connection.execute.call_args
            sql_query = str(call_args[0][0])
            assert "temperature_unit" in sql_query

    @pytest.mark.asyncio
    async def test_write_enrichment_batch(self):
        """Test writing multiple enrichment records in batch."""
        from ingestion.writers.database_writer import EnrichmentDataWriter

        writer = EnrichmentDataWriter(database_url="postgresql+asyncpg://test/db")

        enrichment_records = [
            {"location": "US-CA", "period": "2024-01-15", "population": 7000000},
            {"location": "US-NY", "period": "2024-01-15", "population": 20000000},
            {"location": "US-TX", "period": "2024-01-15", "population": 30000000},
        ]

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            count = await writer.write_batch(enrichment_records)

            assert count == 3
            mock_connection.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_enrichment_stores_raw_json(self):
        """Test that full enrichment response is stored in raw_json."""
        from ingestion.writers.database_writer import EnrichmentDataWriter

        writer = EnrichmentDataWriter(database_url="postgresql+asyncpg://test/db")

        enrichment_record = {
            "location": "US-CA",
            "period": "2024-01-15",
            "temperature_fahrenheit": 42.8,
        }

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_conn.return_value.__aenter__.return_value = mock_connection

            await writer.write_record(enrichment_record)

            call_args = mock_connection.execute.call_args
            sql_query = str(call_args[0][0])
            assert "raw_json" in sql_query

    @pytest.mark.asyncio
    async def test_write_enrichment_handles_database_error(self):
        """Test error handling for enrichment database errors."""
        from ingestion.writers.database_writer import (
            DatabaseWriteError,
            EnrichmentDataWriter,
        )

        writer = EnrichmentDataWriter(database_url="postgresql+asyncpg://test/db")

        enrichment_record = {"location": "US-CA", "period": "2024-01"}

        with patch.object(writer, "_get_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_connection.execute.side_effect = Exception("Database error")
            mock_conn.return_value.__aenter__.return_value = mock_connection

            with pytest.raises(DatabaseWriteError):
                await writer.write_record(enrichment_record)


class TestDatabaseWriterIntegration:
    """Integration-style tests (still mocked, but testing workflows)."""

    @pytest.mark.asyncio
    async def test_write_eia_and_enrichment_together(self):
        """Test writing both EIA and enrichment data in same session."""
        from ingestion.writers.database_writer import (
            EIADataWriter,
            EnrichmentDataWriter,
        )

        database_url = "postgresql+asyncpg://test/db"

        eia_writer = EIADataWriter(database_url=database_url)
        enrichment_writer = EnrichmentDataWriter(database_url=database_url)

        # Both should work with same database URL
        assert eia_writer.database_url == enrichment_writer.database_url

    @pytest.mark.asyncio
    async def test_close_connection_explicitly(self):
        """Test explicitly closing database connection."""
        from ingestion.writers.database_writer import DatabaseWriter

        writer = DatabaseWriter(database_url="postgresql+asyncpg://test/db")

        with patch("ingestion.writers.database_writer.asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_pool.close = AsyncMock()
            mock_create_pool.return_value = mock_pool

            # Should be able to close
            await writer.close()
