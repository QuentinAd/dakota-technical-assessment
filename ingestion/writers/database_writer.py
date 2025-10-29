"""
Database writers for persisting raw data to PostgreSQL.

This module provides async writers for EIA energy data and enrichment data,
storing them in the raw schema with full metadata tracking.
"""

import json
from contextlib import asynccontextmanager
from typing import Any

import asyncpg


# Custom exceptions
class DatabaseWriteError(Exception):
    """Base exception for database write errors."""

    pass


class DatabaseWriter:
    """
    Base class for async database writers using asyncpg.

    Provides connection management and common functionality for
    writing data to PostgreSQL.

    Example:
        async with DatabaseWriter(database_url="postgresql://...") as writer:
            # Use writer
            pass
    """

    def __init__(self, database_url: str):
        """
        Initialize database writer.

        Args:
            database_url: PostgreSQL connection URL (asyncpg format)

        Raises:
            ValueError: If database_url is empty
        """
        if not database_url or database_url.strip() == "":
            raise ValueError("database_url is required and cannot be empty")

        self.database_url = database_url.strip()
        self._pool: asyncpg.Pool | None = None

    async def __aenter__(self):
        """Async context manager entry - creates connection pool."""
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=10,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def _get_connection(self):
        """
        Get a database connection from the pool.

        Yields:
            Database connection
        """
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
            )

        async with self._pool.acquire() as connection:
            yield connection

    async def close(self):
        """Close the connection pool explicitly (if not using context manager)."""
        if self._pool:
            await self._pool.close()
            self._pool = None


class EIADataWriter(DatabaseWriter):
    """
    Writer for EIA energy data to raw.eia_energy_data table.

    Handles transformation of EIA API responses into database records
    with full metadata tracking.
    """

    async def write_record(self, eia_record: dict[str, Any]) -> None:
        """
        Write a single EIA record to the database.

        Args:
            eia_record: Dictionary with EIA API response data

        Raises:
            DatabaseWriteError: If write fails
        """
        try:
            async with self._get_connection() as conn:
                # Extract fields from EIA record - handle both test and real API formats
                series_id = eia_record.get("seriesId")  # Mock format
                if not series_id:
                    # Real API: construct from available fields
                    series_id = f"ELEC.GEN.{eia_record.get('location', 'NA')}"

                period = eia_record.get("period")

                # Use explicit None checks to preserve valid 0 values and empty strings
                value = eia_record.get("value")
                if value is None:
                    value = eia_record.get("generation")

                units = eia_record.get("units")
                if units is None:
                    units = eia_record.get("generation-units")

                location = eia_record.get("location")

                location_type = eia_record.get("locationType")
                if location_type is None:
                    location_type = eia_record.get("stateDescription")

                energy_source = eia_record.get("energySource")
                if energy_source is None:
                    energy_source = eia_record.get("fuelTypeDescription")

                sector = eia_record.get("sector")
                if sector is None:
                    sector = eia_record.get("sectorDescription")

                # Store full response as JSON
                raw_json = json.dumps(eia_record)

                # Insert into database
                query = """
                    INSERT INTO raw.eia_energy_data (
                        source,
                        series_id,
                        period,
                        value,
                        units,
                        location,
                        location_type,
                        energy_source,
                        sector,
                        raw_json
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """

                await conn.execute(
                    query,
                    "EIA",  # source
                    series_id,
                    period,
                    value,
                    units,
                    location,
                    location_type,
                    energy_source,
                    sector,
                    raw_json,
                )

        except Exception as e:
            raise DatabaseWriteError(f"Failed to write EIA record: {str(e)}") from e

    async def write_batch(self, eia_records: list[dict[str, Any]]) -> int:
        """
        Write multiple EIA records in batch for better performance.

        Args:
            eia_records: List of EIA record dictionaries

        Returns:
            Count of records inserted

        Raises:
            DatabaseWriteError: If batch write fails
        """
        if not eia_records:
            return 0

        try:
            async with self._get_connection() as conn:
                # Prepare batch data
                # Map actual EIA API v2 field names to database schema
                batch_data = []
                for record in eia_records:
                    # Handle both test mock format and real API format
                    series_id = record.get("seriesId")  # Mock format
                    if not series_id:
                        # Real API: construct from available fields
                        series_id = f"ELEC.GEN.{record.get('location', 'NA')}"

                    # Use explicit None checks to preserve valid 0 values and empty strings
                    value = record.get("value")
                    if value is None:
                        value = record.get("generation")

                    units = record.get("units")
                    if units is None:
                        units = record.get("generation-units")

                    location = record.get("location")

                    location_type = record.get("locationType")
                    if location_type is None:
                        location_type = record.get("stateDescription")

                    energy_source = record.get("energySource")
                    if energy_source is None:
                        energy_source = record.get("fuelTypeDescription")

                    sector = record.get("sector")
                    if sector is None:
                        sector = record.get("sectorDescription")

                    batch_data.append(
                        (
                            "EIA",  # source
                            series_id,
                            record.get("period"),
                            value,
                            units,
                            location,
                            location_type,
                            energy_source,
                            sector,
                            json.dumps(record),  # raw_json
                        )
                    )

                # Batch insert
                query = """
                    INSERT INTO raw.eia_energy_data (
                        source,
                        series_id,
                        period,
                        value,
                        units,
                        location,
                        location_type,
                        energy_source,
                        sector,
                        raw_json
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """

                await conn.executemany(query, batch_data)

                return len(eia_records)

        except Exception as e:
            raise DatabaseWriteError(f"Failed to write EIA batch: {str(e)}") from e


class EnrichmentDataWriter(DatabaseWriter):
    """
    Writer for enrichment data to raw.enrichment_data table.

    Handles transformation of FastAPI enrichment responses into database records
    with metadata tracking.
    """

    async def write_record(self, enrichment_record: dict[str, Any]) -> None:
        """
        Write a single enrichment record to the database.

        Args:
            enrichment_record: Dictionary with enrichment API response data

        Raises:
            DatabaseWriteError: If write fails
        """
        try:
            async with self._get_connection() as conn:
                # Extract fields from enrichment record
                period = enrichment_record.get("period")
                location = enrichment_record.get("location")

                # Temperature field (from API is "temperature_fahrenheit")
                temperature_avg = enrichment_record.get("temperature_fahrenheit")
                temperature_unit = "fahrenheit" if temperature_avg is not None else None

                population = enrichment_record.get("population")
                # API returns "gdp_per_capita_usd", not "gdp_per_capita"
                gdp_per_capita = enrichment_record.get("gdp_per_capita_usd") or enrichment_record.get("gdp_per_capita")
                industrial_activity_index = enrichment_record.get("industrial_activity_index")

                # Store full response as JSON
                raw_json = json.dumps(enrichment_record)

                # Insert into database
                query = """
                    INSERT INTO raw.enrichment_data (
                        source,
                        period,
                        location,
                        temperature_avg,
                        temperature_unit,
                        population,
                        gdp_per_capita,
                        industrial_activity_index,
                        raw_json
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """

                await conn.execute(
                    query,
                    "FastAPI",  # source
                    period,
                    location,
                    temperature_avg,
                    temperature_unit,
                    population,
                    gdp_per_capita,
                    industrial_activity_index,
                    raw_json,
                )

        except Exception as e:
            raise DatabaseWriteError(f"Failed to write enrichment record: {str(e)}") from e

    async def write_batch(self, enrichment_records: list[dict[str, Any]]) -> int:
        """
        Write multiple enrichment records in batch for better performance.

        Args:
            enrichment_records: List of enrichment record dictionaries

        Returns:
            Count of records inserted

        Raises:
            DatabaseWriteError: If batch write fails
        """
        if not enrichment_records:
            return 0

        try:
            async with self._get_connection() as conn:
                # Prepare batch data
                batch_data = []
                for record in enrichment_records:
                    temperature_avg = record.get("temperature_fahrenheit")
                    temperature_unit = "fahrenheit" if temperature_avg is not None else None

                    batch_data.append(
                        (
                            "FastAPI",  # source
                            record.get("period"),
                            record.get("location"),
                            temperature_avg,
                            temperature_unit,
                            record.get("population"),
                            record.get("gdp_per_capita"),
                            record.get("industrial_activity_index"),
                            json.dumps(record),  # raw_json
                        )
                    )

                # Batch insert
                query = """
                    INSERT INTO raw.enrichment_data (
                        source,
                        period,
                        location,
                        temperature_avg,
                        temperature_unit,
                        population,
                        gdp_per_capita,
                        industrial_activity_index,
                        raw_json
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """

                await conn.executemany(query, batch_data)

                return len(enrichment_records)

        except Exception as e:
            raise DatabaseWriteError(f"Failed to write enrichment batch: {str(e)}") from e
