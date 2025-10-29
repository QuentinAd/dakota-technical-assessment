"""
End-to-end tests for the complete energy analytics pipeline.

Tests the full data flow from ingestion through transformation to reporting.
"""

import os
from datetime import date
from pathlib import Path

import asyncpg
import pytest


@pytest.fixture
def database_url():
    """Get database connection URL from environment."""
    db_name = os.getenv("POSTGRES_DB", "energy_analytics")
    db_user = os.getenv("POSTGRES_USER", "dakota_user")
    db_password = os.getenv("POSTGRES_PASSWORD", "change_me")
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_eia_ingestion_to_raw(database_url):
    """Test EIA data can be ingested into raw schema."""
    from ingestion.clients.eia_client import EIAClient
    from ingestion.writers.database_writer import EIADataWriter

    api_key = os.getenv("EIA_API_KEY")
    if not api_key:
        pytest.skip("EIA_API_KEY not set")

    # Ingest data
    async with (
        EIAClient(api_key=api_key) as client,
        EIADataWriter(database_url=database_url) as writer,
    ):
        # Fetch small amount of data
        data = await client.fetch_electricity_generation(start_date="2024-01", end_date="2024-01")

        records = data.get("response", {}).get("data", [])
        if records:
            count = await writer.write_batch(records[:10])  # Write only first 10
            assert count > 0

    # Verify data in raw schema
    pool = await asyncpg.create_pool(database_url)
    try:
        async with pool.acquire() as conn:
            row_count = await conn.fetchval("SELECT COUNT(*) FROM raw.eia_energy_data")
            assert row_count > 0
    finally:
        await pool.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_enrichment_ingestion_to_raw(database_url):
    """Test enrichment data can be ingested into raw schema."""
    from ingestion.clients.enrichment_client import EnrichmentClient
    from ingestion.writers.database_writer import EnrichmentDataWriter

    api_url = os.getenv("ENRICHMENT_API_URL", "http://localhost:8000")

    # Ingest data
    async with EnrichmentClient(base_url=api_url) as client:
        # Check API is available
        is_healthy = await client.health_check()
        if not is_healthy:
            pytest.skip("Enrichment API not available")

        async with EnrichmentDataWriter(database_url=database_url) as writer:
            # Fetch enrichment data
            data = await client.fetch_enrichment_data(locations=["US-CA"], date=date.today())

            if data:
                count = await writer.write_batch(data)
                assert count > 0

    # Verify data in raw schema
    pool = await asyncpg.create_pool(database_url)
    try:
        async with pool.acquire() as conn:
            row_count = await conn.fetchval("SELECT COUNT(*) FROM raw.enrichment_data")
            assert row_count > 0
    finally:
        await pool.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_raw_to_staging_transformation(database_url):
    """Test dbt transforms raw data into staging schema."""
    import subprocess

    # Ensure we have raw data
    pool = await asyncpg.create_pool(database_url)
    try:
        async with pool.acquire() as conn:
            eia_count = await conn.fetchval("SELECT COUNT(*) FROM raw.eia_energy_data")
            enrichment_count = await conn.fetchval("SELECT COUNT(*) FROM raw.enrichment_data")

            if eia_count == 0 or enrichment_count == 0:
                pytest.skip("No raw data available for transformation")
    finally:
        await pool.close()

    # Run dbt models
    dbt_dir = Path(__file__).parent.parent.parent / "dbt"
    result = subprocess.run(
        ["dbt", "run", "--select", "staging.*"], cwd=dbt_dir, capture_output=True, text=True
    )

    assert result.returncode == 0, f"dbt run failed: {result.stderr}"

    # Verify staging data exists
    pool = await asyncpg.create_pool(database_url)
    try:
        async with pool.acquire() as conn:
            staging_eia_count = await conn.fetchval(
                "SELECT COUNT(*) FROM staging.stg_eia_energy_generation"
            )
            assert staging_eia_count > 0

            staging_enrichment_count = await conn.fetchval(
                "SELECT COUNT(*) FROM staging.stg_enrichment_data"
            )
            assert staging_enrichment_count > 0
    finally:
        await pool.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_staging_to_marts_transformation(database_url):
    """Test dbt transforms staging data into marts schema."""
    import subprocess

    # Ensure we have staging data
    pool = await asyncpg.create_pool(database_url)
    try:
        async with pool.acquire() as conn:
            staging_count = await conn.fetchval(
                "SELECT COUNT(*) FROM staging.stg_eia_energy_generation"
            )

            if staging_count == 0:
                pytest.skip("No staging data available for transformation")
    finally:
        await pool.close()

    # Run dbt models
    dbt_dir = Path(__file__).parent.parent.parent / "dbt"
    result = subprocess.run(
        ["dbt", "run", "--select", "marts.*"], cwd=dbt_dir, capture_output=True, text=True
    )

    assert result.returncode == 0, f"dbt run failed: {result.stderr}"

    # Verify marts data exists
    pool = await asyncpg.create_pool(database_url)
    try:
        async with pool.acquire() as conn:
            fact_count = await conn.fetchval("SELECT COUNT(*) FROM marts.fct_energy_metrics")
            assert fact_count > 0

            dim_time_count = await conn.fetchval("SELECT COUNT(*) FROM marts.dim_time")
            assert dim_time_count > 0
    finally:
        await pool.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_pipeline_flow(database_url):
    """
    Test the complete pipeline from ingestion to marts.

    This is the master end-to-end test that verifies the entire data flow.
    """
    pool = await asyncpg.create_pool(database_url)

    try:
        async with pool.acquire() as conn:
            # Verify all schemas exist
            schemas = await conn.fetch(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('raw', 'staging', 'intermediate', 'marts', 'audit')"
            )
            schema_names = {row["schema_name"] for row in schemas}
            assert "raw" in schema_names
            assert "staging" in schema_names
            assert "marts" in schema_names
            assert "audit" in schema_names

            # Verify raw tables exist and have structure
            raw_tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
            )
            raw_table_names = {row["table_name"] for row in raw_tables}
            assert "eia_energy_data" in raw_table_names
            assert "enrichment_data" in raw_table_names

            # Verify staging tables exist
            staging_tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'staging'"
            )
            staging_table_names = {row["table_name"] for row in staging_tables}
            assert "stg_eia_energy_generation" in staging_table_names
            assert "stg_enrichment_data" in staging_table_names

            # Verify marts tables exist
            marts_tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'marts'"
            )
            marts_table_names = {row["table_name"] for row in marts_tables}
            assert "fct_energy_metrics" in marts_table_names
            assert "dim_time" in marts_table_names

            # Verify dim_time has seed data
            dim_time_count = await conn.fetchval("SELECT COUNT(*) FROM marts.dim_time")
            assert dim_time_count > 0, "dim_time should have seed data"

    finally:
        await pool.close()


@pytest.mark.e2e
def test_dagster_definitions_load():
    """Test that all Dagster definitions can be loaded successfully."""
    from dagster_project import defs

    # Verify definitions object exists
    assert defs is not None

    # Verify assets are defined
    assert len(defs.assets) > 0

    # Verify jobs are defined
    assert len(defs.jobs) > 0

    # Verify schedules are defined
    assert len(defs.schedules) > 0


@pytest.mark.e2e
def test_report_template_exists():
    """Test that report template exists and is valid."""
    template_path = (
        Path(__file__).parent.parent.parent
        / "reports"
        / "templates"
        / "energy_analytics_report.ipynb"
    )

    assert template_path.exists(), "Report template should exist"
    assert template_path.suffix == ".ipynb", "Template should be Jupyter notebook"

    # Verify it's valid JSON (notebooks are JSON)
    import json

    with open(template_path) as f:
        notebook = json.load(f)

    assert "cells" in notebook, "Notebook should have cells"
    assert len(notebook["cells"]) > 0, "Notebook should have at least one cell"


@pytest.mark.e2e
def test_docker_compose_configuration():
    """Test that docker-compose.yml is properly configured."""
    import yaml

    compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml should exist"

    with open(compose_path) as f:
        config = yaml.safe_load(f)

    # Verify all required services are defined
    assert "services" in config
    assert "postgres" in config["services"]
    assert "enrichment-api" in config["services"]
    assert "dagster" in config["services"]

    # Verify network configuration
    assert "networks" in config
    assert "dakota_network" in config["networks"]

    # Verify volumes
    assert "volumes" in config
    assert "postgres_data" in config["volumes"]
