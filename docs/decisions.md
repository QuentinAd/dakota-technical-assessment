# Technical Decisions and Architecture

This document records key technical decisions made during the Dakota Analytics pipeline implementation, along with rationale, trade-offs, and alternatives considered.

---

## Phase 1: Database Architecture

### Decision 1: Medallion Architecture (Bronze → Silver → Gold)

**Decision**: Implement a three-layer medallion architecture for data organization.

**Rationale**:
- **Bronze Layer (Raw)**: Stores unmodified data from sources with full audit trail
- **Silver Layer (Staging/Intermediate)**: Cleaned, typed, and business-logic-applied data
- **Gold Layer (Marts)**: Analytics-ready dimensional model optimized for reporting

**Benefits**:
- Clear separation of concerns at each layer
- Easy to debug and replay transformations
- Industry-standard pattern for data lakehouse architectures
- Supports both batch and incremental processing
- Enables time travel and data lineage tracking

**Trade-offs**:
- More storage space (data duplicated across layers)
- Additional transformation steps
- Slightly more complex ETL logic

**Alternatives Considered**:
1. **Single normalized schema**: Simpler but harder to maintain, poor query performance
2. **Star schema only**: Less flexible for raw data retention and reprocessing
3. **Data vault**: More complex, overkill for this use case

**Implementation Details**:
```
raw schema:           eia_energy_data, enrichment_data
staging schema:       stg_energy_generation, stg_energy_consumption, stg_enrichment
intermediate schema:  int_energy_combined
marts schema:         dim_time, dim_location, dim_energy_source, fct_energy_metrics
audit schema:         pipeline_runs, data_quality_checks
```

---

### Decision 2: Dimensional Model (Star Schema) for Analytics

**Decision**: Use a star schema in the marts layer with dimension and fact tables.

**Rationale**:
- Optimized for analytical queries (OLAP workloads)
- Easy to understand and query for business users
- Supports time-series analysis with dim_time
- Enables location-based analysis with dim_location
- Pre-aggregated metrics for fast reporting

**Benefits**:
- Fast query performance (fewer joins)
- Intuitive data model
- Supports common BI tools (Tableau, Power BI, Looker)
- Easy to add new dimensions without breaking existing queries

**Trade-offs**:
- Data duplication (denormalization)
- More complex ETL to maintain dimension tables
- Harder to model many-to-many relationships

**Alternatives Considered**:
1. **Normalized OLTP model**: Poor query performance for analytics
2. **Wide table (OBT)**: Harder to maintain, extreme duplication
3. **Snowflake schema**: More normalized but slower queries

---

### Decision 3: PostgreSQL as Data Warehouse

**Decision**: Use PostgreSQL 15 as the primary data warehouse.

**Rationale**:
- Mature, production-ready RDBMS
- Excellent support for JSONB (flexible raw data storage)
- Strong time-series capabilities with proper indexing
- Native support for window functions and CTEs
- Compatible with dbt for transformations
- Free and open-source

**Benefits**:
- No licensing costs
- Rich ecosystem of tools
- Strong ACID guarantees
- Excellent documentation
- Works well with Docker for development

**Trade-offs**:
- Not as scalable as cloud data warehouses (Snowflake, BigQuery)
- Manual index and partition management
- Limited columnar storage options

**Alternatives Considered**:
1. **Snowflake/BigQuery**: Better scalability but requires cloud accounts and costs
2. **DuckDB**: Great for analytics but less mature for production OLTP
3. **ClickHouse**: Excellent for time-series but steeper learning curve

---

### Decision 4: JSONB for Raw Data Flexibility

**Decision**: Store complete API responses in JSONB columns alongside structured fields.

**Rationale**:
- Preserves full API response for future analysis
- Allows schema evolution without migrations
- Enables debugging and data validation
- Supports semi-structured data from external APIs

**Benefits**:
- Future-proof against API schema changes
- Can query nested JSON data directly
- Audit trail of exact data received
- Supports flexible data ingestion

**Trade-offs**:
- Additional storage overhead
- Slower queries on JSON fields (but we have structured columns for common queries)
- Need to handle JSON parsing in queries

---

### Decision 5: Time Dimension Pre-populated (2020-2030)

**Decision**: Seed dim_time with 11 years of dates upfront.

**Rationale**:
- Common data warehouse pattern
- Enables easy date-based analysis
- Includes metadata (weekend, quarter, week of year)
- Avoids INSERT on every fact load

**Benefits**:
- Consistent time_key format (YYYYMMDD as integer)
- Fast joins (no date parsing)
- Can add holidays, fiscal periods later
- Works with incremental models

**Trade-offs**:
- Fixed date range (but 11 years is sufficient)
- Small storage overhead (4000 rows)

---

### Decision 6: Indexes on Time-Series Columns

**Decision**: Create B-tree indexes on period, location, and timestamp columns.

**Rationale**:
- Time-series data is frequently queried by date ranges
- Location-based filtering is common
- Ingestion timestamp enables data quality checks

**Benefits**:
- Fast query performance for common patterns
- Supports WHERE, ORDER BY, and JOIN operations
- Minimal write overhead (batch inserts)

**Trade-offs**:
- Slower INSERT operations (acceptable for batch processing)
- Index maintenance overhead

---

### Decision 7: Audit Schema for Data Quality

**Decision**: Create dedicated audit schema with pipeline_runs and data_quality_checks tables.

**Rationale**:
- Production data pipelines require observability
- Track pipeline success/failure for alerting
- Monitor data quality metrics over time
- Support SLA monitoring and debugging

**Benefits**:
- Operational visibility into pipeline health
- Historical tracking of data quality
- Supports automated alerting
- Helps debug failed runs

**Trade-offs**:
- Additional tables to maintain
- Need to instrument pipeline code

---

## Testing Strategy

### Decision 8: Integration Tests for Database Schema

**Decision**: Write comprehensive integration tests that validate database structure.

**Rationale**:
- Schema is the foundation of the entire pipeline
- Catch schema drift early
- Verify constraints and relationships
- Validate seed data

**Test Coverage**:
- ✅ All schemas exist
- ✅ All tables exist with correct columns
- ✅ Indexes are created
- ✅ Foreign keys are defined
- ✅ Seed data is populated

---

## Build and Dependency Management

### Decision 9: uv for Dependency Management

**Decision**: Use `uv` instead of pip for all Python dependency management.

**Rationale**:
- **Mandatory per CLAUDE.md** project requirements
- 10-100x faster than pip
- Built-in lockfile (uv.lock) for reproducibility
- Better dependency resolution
- Simplified virtual environment management

**Benefits**:
- Extremely fast dependency installation
- Reproducible builds across environments
- Automatic pyproject.toml updates
- No manual requirements.txt maintenance

**Commands Used**:
```bash
uv add <package>           # Add runtime dependency
uv add --dev <package>     # Add dev dependency
uv sync --all-extras      # Install all dependencies
uv run <command>          # Run command in venv
```

---

### Decision 10: Hatchling Build Backend

**Decision**: Use Hatchling with explicit package configuration.

**Rationale**:
- Modern Python build backend
- Required for uv compatibility
- Explicit package declaration avoids build errors

**Configuration**:
```toml
[tool.hatch.build.targets.wheel]
packages = ["api", "ingestion", "orchestration", "reports"]
```

---

## Next Phases

### Upcoming Decisions:
1. **Phase 2**: FastAPI framework and synthetic data generation strategy
2. **Phase 3**: EIA API client design and rate limiting approach
3. **Phase 4**: dbt model organization and incremental strategies
4. **Phase 5**: Orchestrator choice (Dagster vs. Airflow vs. Prefect)
5. **Phase 6**: Report generation format and scheduling

---

## Summary

Phase 1 established a solid foundation with:
- ✅ Medallion architecture for clear data lineage
- ✅ Dimensional model for efficient analytics
- ✅ PostgreSQL with JSONB for flexibility
- ✅ Comprehensive schema validation tests
- ✅ Production-ready audit and quality tracking
- ✅ Fast dependency management with uv

The architecture balances **production-readiness**, **maintainability**, and **performance** while following industry best practices for modern data pipelines.
