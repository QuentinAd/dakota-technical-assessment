"""Integration tests for database schema validation.

Tests verify that:
1. All schemas exist (raw, staging, intermediate, marts, audit)
2. All tables exist with correct structure
3. Indexes are created
4. Seed data is populated
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


class TestDatabaseSchemas:
    """Test that all required schemas exist."""

    def test_raw_schema_exists(self, db_engine: Engine) -> None:
        """Test that raw schema exists."""
        inspector = inspect(db_engine)
        schemas = inspector.get_schema_names()
        assert "raw" in schemas, "Raw schema should exist"

    def test_staging_schema_exists(self, db_engine: Engine) -> None:
        """Test that staging schema exists."""
        inspector = inspect(db_engine)
        schemas = inspector.get_schema_names()
        assert "staging" in schemas, "Staging schema should exist"

    def test_intermediate_schema_exists(self, db_engine: Engine) -> None:
        """Test that intermediate schema exists."""
        inspector = inspect(db_engine)
        schemas = inspector.get_schema_names()
        assert "intermediate" in schemas, "Intermediate schema should exist"

    def test_marts_schema_exists(self, db_engine: Engine) -> None:
        """Test that marts schema exists."""
        inspector = inspect(db_engine)
        schemas = inspector.get_schema_names()
        assert "marts" in schemas, "Marts schema should exist"

    def test_audit_schema_exists(self, db_engine: Engine) -> None:
        """Test that audit schema exists."""
        inspector = inspect(db_engine)
        schemas = inspector.get_schema_names()
        assert "audit" in schemas, "Audit schema should exist"


class TestRawTables:
    """Test that raw schema tables exist."""

    def test_eia_energy_data_table_exists(self, db_engine: Engine) -> None:
        """Test that eia_energy_data table exists in raw schema."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="raw")
        assert "eia_energy_data" in tables, "eia_energy_data table should exist"

    def test_enrichment_data_table_exists(self, db_engine: Engine) -> None:
        """Test that enrichment_data table exists in raw schema."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="raw")
        assert "enrichment_data" in tables, "enrichment_data table should exist"

    def test_eia_energy_data_columns(self, db_engine: Engine) -> None:
        """Test that eia_energy_data has required columns."""
        inspector = inspect(db_engine)
        columns = inspector.get_columns("eia_energy_data", schema="raw")
        column_names = [col["name"] for col in columns]

        required_columns = [
            "id",
            "source",
            "ingestion_timestamp",
            "series_id",
            "period",
            "value",
            "units",
            "location",
            "location_type",
            "energy_source",
            "sector",
            "raw_json",
        ]

        for col in required_columns:
            assert col in column_names, f"Column {col} should exist in eia_energy_data"


class TestStagingTables:
    """Test that staging schema tables exist."""

    def test_stg_energy_generation_exists(self, db_engine: Engine) -> None:
        """Test that stg_energy_generation table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="staging")
        assert "stg_energy_generation" in tables

    def test_stg_energy_consumption_exists(self, db_engine: Engine) -> None:
        """Test that stg_energy_consumption table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="staging")
        assert "stg_energy_consumption" in tables

    def test_stg_enrichment_exists(self, db_engine: Engine) -> None:
        """Test that stg_enrichment table or view exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="staging")
        views = inspector.get_view_names(schema="staging")
        all_relations = tables + views
        assert "stg_enrichment" in all_relations


class TestIntermediateTables:
    """Test that intermediate schema tables exist."""

    def test_int_energy_combined_exists(self, db_engine: Engine) -> None:
        """Test that int_energy_combined table or view exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="intermediate")
        views = inspector.get_view_names(schema="intermediate")
        all_relations = tables + views
        assert "int_energy_combined" in all_relations


class TestMartsTables:
    """Test that marts schema tables exist."""

    def test_dim_time_exists(self, db_engine: Engine) -> None:
        """Test that dim_time dimension table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="marts")
        assert "dim_time" in tables

    def test_dim_location_exists(self, db_engine: Engine) -> None:
        """Test that dim_location dimension table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="marts")
        assert "dim_location" in tables

    def test_dim_energy_source_exists(self, db_engine: Engine) -> None:
        """Test that dim_energy_source dimension table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="marts")
        assert "dim_energy_source" in tables

    def test_fct_energy_metrics_exists(self, db_engine: Engine) -> None:
        """Test that fct_energy_metrics fact table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="marts")
        assert "fct_energy_metrics" in tables

    def test_fct_energy_metrics_columns(self, db_engine: Engine) -> None:
        """Test that fct_energy_metrics has required columns."""
        inspector = inspect(db_engine)
        columns = inspector.get_columns("fct_energy_metrics", schema="marts")
        column_names = [col["name"] for col in columns]

        required_columns = [
            "metric_key",
            "time_key",
            "location_key",
            "total_generation_mwh",
            "total_consumption_mwh",
            "renewable_generation_mwh",
            "fossil_generation_mwh",
        ]

        for col in required_columns:
            assert col in column_names, f"Column {col} should exist in fct_energy_metrics"


class TestAuditTables:
    """Test that audit schema tables exist."""

    def test_pipeline_runs_exists(self, db_engine: Engine) -> None:
        """Test that pipeline_runs audit table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="audit")
        assert "pipeline_runs" in tables

    def test_data_quality_checks_exists(self, db_engine: Engine) -> None:
        """Test that data_quality_checks audit table exists."""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names(schema="audit")
        assert "data_quality_checks" in tables


class TestSeedData:
    """Test that seed data was populated."""

    def test_dim_time_has_data(self, db_session: Session) -> None:
        """Test that dim_time dimension has seed data."""
        result = db_session.execute(text("SELECT COUNT(*) FROM marts.dim_time"))
        count = result.scalar()
        assert count > 0, "dim_time should have seed data"
        # Should have dates from 2020-2030 (roughly 4000 days)
        assert count > 3650, "dim_time should have at least 10 years of data"

    def test_dim_energy_source_has_data(self, db_session: Session) -> None:
        """Test that dim_energy_source has seed data."""
        result = db_session.execute(text("SELECT COUNT(*) FROM marts.dim_energy_source"))
        count = result.scalar()
        assert count >= 7, "dim_energy_source should have at least 7 energy sources"

    def test_dim_location_has_data(self, db_session: Session) -> None:
        """Test that dim_location has seed data."""
        result = db_session.execute(text("SELECT COUNT(*) FROM marts.dim_location"))
        count = result.scalar()
        assert count >= 10, "dim_location should have at least 10 locations"

    def test_energy_sources_contain_renewables(self, db_session: Session) -> None:
        """Test that energy sources include renewable sources."""
        result = db_session.execute(
            text("SELECT COUNT(*) FROM marts.dim_energy_source WHERE is_renewable = TRUE")
        )
        count = result.scalar()
        assert count >= 3, "Should have at least 3 renewable energy sources"


class TestIndexes:
    """Test that indexes are created for performance."""

    def test_eia_energy_data_has_indexes(self, db_engine: Engine) -> None:
        """Test that eia_energy_data table has indexes."""
        inspector = inspect(db_engine)
        indexes = inspector.get_indexes("eia_energy_data", schema="raw")
        assert len(indexes) > 0, "eia_energy_data should have indexes"

    def test_fct_energy_metrics_has_indexes(self, db_engine: Engine) -> None:
        """Test that fct_energy_metrics fact table has indexes."""
        inspector = inspect(db_engine)
        indexes = inspector.get_indexes("fct_energy_metrics", schema="marts")
        assert len(indexes) > 0, "fct_energy_metrics should have indexes"


class TestForeignKeys:
    """Test that foreign key relationships exist."""

    def test_stg_energy_generation_fk(self, db_engine: Engine) -> None:
        """Test that stg_energy_generation has foreign key to raw table."""
        inspector = inspect(db_engine)
        fks = inspector.get_foreign_keys("stg_energy_generation", schema="staging")
        assert len(fks) > 0, "stg_energy_generation should have foreign keys"

    def test_fct_energy_metrics_fk_to_dim_time(self, db_engine: Engine) -> None:
        """Test that fct_energy_metrics has foreign key to dim_time."""
        inspector = inspect(db_engine)
        fks = inspector.get_foreign_keys("fct_energy_metrics", schema="marts")

        # Check that time_key foreign key exists
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["time_key"] in fk_columns, "fct_energy_metrics should have FK to dim_time"

    def test_fct_energy_metrics_fk_to_dim_location(self, db_engine: Engine) -> None:
        """Test that fct_energy_metrics has foreign key to dim_location."""
        inspector = inspect(db_engine)
        fks = inspector.get_foreign_keys("fct_energy_metrics", schema="marts")

        # Check that location_key foreign key exists
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["location_key"] in fk_columns, "fct_energy_metrics should have FK to dim_location"
