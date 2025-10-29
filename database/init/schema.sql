-- Dakota Analytics Database Schema
-- Medallion Architecture: Raw (Bronze) -> Staging (Silver) -> Intermediate/Marts (Gold)
-- Created: 2025-10-27

-- ============================================================================
-- BRONZE LAYER: Raw Data (unchanged from source)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS raw;

-- Raw EIA API Data
-- Stores electricity generation, consumption, and pricing data from EIA
CREATE TABLE raw.eia_energy_data (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL DEFAULT 'EIA',
    ingestion_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Data fields (flexible schema to handle various EIA endpoints)
    series_id VARCHAR(255),
    period VARCHAR(50),
    value NUMERIC,
    units VARCHAR(100),

    -- Geographic information
    location VARCHAR(255),
    location_type VARCHAR(50), -- state, region, national

    -- Energy details
    energy_source VARCHAR(100), -- coal, natural_gas, nuclear, solar, wind, etc.
    sector VARCHAR(100), -- residential, commercial, industrial, transportation

    -- Metadata
    raw_json JSONB -- Full API response for flexibility
);

-- Create indexes for eia_energy_data
CREATE INDEX idx_eia_period ON raw.eia_energy_data(period);
CREATE INDEX idx_eia_location ON raw.eia_energy_data(location);
CREATE INDEX idx_eia_source ON raw.eia_energy_data(energy_source);
CREATE INDEX idx_eia_ingestion ON raw.eia_energy_data(ingestion_timestamp);

-- Raw Enrichment Data from FastAPI Service
-- Stores synthetic enrichment data (weather, economic indicators, etc.)
CREATE TABLE raw.enrichment_data (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL DEFAULT 'FastAPI',
    ingestion_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Time and location (to join with energy data)
    period VARCHAR(50),
    location VARCHAR(255),

    -- Enrichment fields (synthetic data)
    temperature_avg NUMERIC,
    temperature_unit VARCHAR(10),
    population BIGINT,
    gdp_per_capita NUMERIC,
    industrial_activity_index NUMERIC,

    -- Metadata
    raw_json JSONB
);

-- Create indexes for enrichment_data
CREATE INDEX idx_enrich_period ON raw.enrichment_data(period);
CREATE INDEX idx_enrich_location ON raw.enrichment_data(location);
CREATE INDEX idx_enrich_ingestion ON raw.enrichment_data(ingestion_timestamp);

-- ============================================================================
-- SILVER LAYER: Staging & Intermediate (cleaned, typed, business logic)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;

-- Staging: Cleaned and typed energy generation data
CREATE TABLE staging.stg_energy_generation (
    generation_id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES raw.eia_energy_data(id),

    period_date DATE NOT NULL,
    period_type VARCHAR(20), -- daily, monthly, annual

    location VARCHAR(255) NOT NULL,
    location_type VARCHAR(50),

    energy_source VARCHAR(100) NOT NULL,
    generation_mwh NUMERIC NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for stg_energy_generation
CREATE INDEX idx_stg_gen_period ON staging.stg_energy_generation(period_date);
CREATE INDEX idx_stg_gen_location ON staging.stg_energy_generation(location);
CREATE INDEX idx_stg_gen_source ON staging.stg_energy_generation(energy_source);

-- Staging: Cleaned and typed energy consumption data
CREATE TABLE staging.stg_energy_consumption (
    consumption_id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES raw.eia_energy_data(id),

    period_date DATE NOT NULL,
    period_type VARCHAR(20),

    location VARCHAR(255) NOT NULL,
    sector VARCHAR(100) NOT NULL,

    consumption_mwh NUMERIC NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for stg_energy_consumption
CREATE INDEX idx_stg_cons_period ON staging.stg_energy_consumption(period_date);
CREATE INDEX idx_stg_cons_location ON staging.stg_energy_consumption(location);
CREATE INDEX idx_stg_cons_sector ON staging.stg_energy_consumption(sector);

-- Staging: Cleaned enrichment data
CREATE TABLE staging.stg_enrichment (
    enrichment_id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES raw.enrichment_data(id),

    period_date DATE NOT NULL,
    location VARCHAR(255) NOT NULL,

    temperature_fahrenheit NUMERIC,
    population INTEGER,
    gdp_per_capita_usd NUMERIC,
    industrial_activity_index NUMERIC,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for stg_enrichment
CREATE INDEX idx_stg_enrich_period ON staging.stg_enrichment(period_date);
CREATE INDEX idx_stg_enrich_location ON staging.stg_enrichment(location);

-- Intermediate: Combined energy metrics with enrichment
CREATE TABLE intermediate.int_energy_combined (
    combined_id BIGSERIAL PRIMARY KEY,

    period_date DATE NOT NULL,
    location VARCHAR(255) NOT NULL,

    -- Generation metrics
    total_generation_mwh NUMERIC,
    renewable_generation_mwh NUMERIC,
    fossil_generation_mwh NUMERIC,
    nuclear_generation_mwh NUMERIC,

    -- Consumption metrics
    total_consumption_mwh NUMERIC,
    residential_consumption_mwh NUMERIC,
    commercial_consumption_mwh NUMERIC,
    industrial_consumption_mwh NUMERIC,

    -- Enrichment data
    temperature_fahrenheit NUMERIC,
    population INTEGER,
    gdp_per_capita_usd NUMERIC,
    industrial_activity_index NUMERIC,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for int_energy_combined
CREATE INDEX idx_int_combined_period ON intermediate.int_energy_combined(period_date);
CREATE INDEX idx_int_combined_location ON intermediate.int_energy_combined(location);

-- ============================================================================
-- GOLD LAYER: Marts (analytics-ready, dimensional model)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS marts;

-- Dimension: Time
CREATE TABLE marts.dim_time (
    time_key INTEGER PRIMARY KEY,
    date DATE NOT NULL UNIQUE,

    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    week_of_year INTEGER NOT NULL,

    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for dim_time
CREATE INDEX idx_dim_time_year_month ON marts.dim_time(year, month);
CREATE INDEX idx_dim_time_quarter ON marts.dim_time(year, quarter);

-- Dimension: Location
CREATE TABLE marts.dim_location (
    location_key SERIAL PRIMARY KEY,
    location_code VARCHAR(50) NOT NULL UNIQUE,
    location_name VARCHAR(255) NOT NULL,
    location_type VARCHAR(50) NOT NULL, -- state, region, national

    region VARCHAR(100),
    timezone VARCHAR(50),
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Dimension: Energy Source
CREATE TABLE marts.dim_energy_source (
    energy_source_key SERIAL PRIMARY KEY,
    energy_source_code VARCHAR(50) NOT NULL UNIQUE,
    energy_source_name VARCHAR(255) NOT NULL,

    category VARCHAR(50) NOT NULL, -- renewable, fossil, nuclear
    is_renewable BOOLEAN NOT NULL,
    carbon_intensity_kg_per_mwh NUMERIC,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Fact Table: Energy Metrics
-- Main analytics table with all metrics joined and aggregated
CREATE TABLE marts.fct_energy_metrics (
    metric_key BIGSERIAL PRIMARY KEY,

    -- Foreign keys to dimensions
    time_key INTEGER NOT NULL REFERENCES marts.dim_time(time_key),
    location_key INTEGER NOT NULL REFERENCES marts.dim_location(location_key),

    -- Generation metrics by source
    coal_generation_mwh NUMERIC,
    natural_gas_generation_mwh NUMERIC,
    nuclear_generation_mwh NUMERIC,
    solar_generation_mwh NUMERIC,
    wind_generation_mwh NUMERIC,
    hydro_generation_mwh NUMERIC,
    other_generation_mwh NUMERIC,

    total_generation_mwh NUMERIC NOT NULL,
    renewable_generation_mwh NUMERIC,
    fossil_generation_mwh NUMERIC,

    -- Consumption metrics by sector
    residential_consumption_mwh NUMERIC,
    commercial_consumption_mwh NUMERIC,
    industrial_consumption_mwh NUMERIC,
    transportation_consumption_mwh NUMERIC,

    total_consumption_mwh NUMERIC NOT NULL,

    -- Calculated metrics
    renewable_percentage NUMERIC,
    net_generation_mwh NUMERIC, -- generation - consumption

    -- Enrichment data
    avg_temperature_fahrenheit NUMERIC,
    population INTEGER,
    gdp_per_capita_usd NUMERIC,
    industrial_activity_index NUMERIC,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for fct_energy_metrics
CREATE INDEX idx_fct_time_location ON marts.fct_energy_metrics(time_key, location_key);
CREATE INDEX idx_fct_time ON marts.fct_energy_metrics(time_key);
CREATE INDEX idx_fct_location ON marts.fct_energy_metrics(location_key);

-- ============================================================================
-- DATA QUALITY AND AUDIT
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS audit;

-- Audit table for tracking data pipeline runs
CREATE TABLE audit.pipeline_runs (
    run_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    run_status VARCHAR(50) NOT NULL, -- success, failed, running

    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds INTEGER,

    rows_processed INTEGER,
    rows_inserted INTEGER,
    rows_updated INTEGER,
    rows_failed INTEGER,

    error_message TEXT,
    metadata JSONB
);

-- Create indexes for pipeline_runs
CREATE INDEX idx_pipeline_runs_name_time ON audit.pipeline_runs(pipeline_name, start_time);
CREATE INDEX idx_pipeline_runs_status ON audit.pipeline_runs(run_status);

-- Data quality metrics
CREATE TABLE audit.data_quality_checks (
    check_id BIGSERIAL PRIMARY KEY,
    check_name VARCHAR(100) NOT NULL,
    table_schema VARCHAR(50) NOT NULL,
    table_name VARCHAR(100) NOT NULL,

    check_type VARCHAR(50) NOT NULL, -- null_check, unique_check, range_check, etc.
    check_result VARCHAR(50) NOT NULL, -- passed, failed, warning

    rows_checked INTEGER,
    rows_failed INTEGER,
    failure_percentage NUMERIC,

    check_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    details JSONB
);

-- Create indexes for data_quality_checks
CREATE INDEX idx_dq_table ON audit.data_quality_checks(table_schema, table_name);
CREATE INDEX idx_dq_timestamp ON audit.data_quality_checks(check_timestamp);

-- ============================================================================
-- INITIAL SEED DATA
-- ============================================================================

-- Seed time dimension with dates (2020-2030)
INSERT INTO marts.dim_time (time_key, date, year, quarter, month, month_name,
                            day_of_month, day_of_week, day_name, week_of_year, is_weekend)
SELECT
    TO_CHAR(date, 'YYYYMMDD')::INTEGER as time_key,
    date,
    EXTRACT(YEAR FROM date)::INTEGER as year,
    EXTRACT(QUARTER FROM date)::INTEGER as quarter,
    EXTRACT(MONTH FROM date)::INTEGER as month,
    TO_CHAR(date, 'Month') as month_name,
    EXTRACT(DAY FROM date)::INTEGER as day_of_month,
    EXTRACT(ISODOW FROM date)::INTEGER as day_of_week,
    TO_CHAR(date, 'Day') as day_name,
    EXTRACT(WEEK FROM date)::INTEGER as week_of_year,
    CASE WHEN EXTRACT(ISODOW FROM date) IN (6, 7) THEN TRUE ELSE FALSE END as is_weekend
FROM generate_series('2020-01-01'::DATE, '2030-12-31'::DATE, '1 day'::INTERVAL) date
ON CONFLICT (time_key) DO NOTHING;

-- Seed energy source dimension
INSERT INTO marts.dim_energy_source (energy_source_code, energy_source_name, category, is_renewable, carbon_intensity_kg_per_mwh)
VALUES
    ('COAL', 'Coal', 'fossil', FALSE, 820),
    ('NG', 'Natural Gas', 'fossil', FALSE, 490),
    ('NUC', 'Nuclear', 'nuclear', FALSE, 12),
    ('SUN', 'Solar', 'renewable', TRUE, 45),
    ('WND', 'Wind', 'renewable', TRUE, 11),
    ('HYD', 'Hydroelectric', 'renewable', TRUE, 24),
    ('OTH', 'Other', 'other', FALSE, 100)
ON CONFLICT (energy_source_code) DO NOTHING;

-- Seed location dimension with sample US regions
INSERT INTO marts.dim_location (location_code, location_name, location_type, region)
VALUES
    ('US', 'United States', 'national', 'National'),
    ('US-NE', 'Northeast', 'region', 'Northeast'),
    ('US-MW', 'Midwest', 'region', 'Midwest'),
    ('US-S', 'South', 'region', 'South'),
    ('US-W', 'West', 'region', 'West'),
    ('US-CA', 'California', 'state', 'West'),
    ('US-TX', 'Texas', 'state', 'South'),
    ('US-NY', 'New York', 'state', 'Northeast'),
    ('US-FL', 'Florida', 'state', 'South'),
    ('US-IL', 'Illinois', 'state', 'Midwest')
ON CONFLICT (location_code) DO NOTHING;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON SCHEMA raw IS 'Bronze layer: Raw data as ingested from sources';
COMMENT ON SCHEMA staging IS 'Silver layer: Cleaned and typed data';
COMMENT ON SCHEMA intermediate IS 'Silver layer: Business logic applied';
COMMENT ON SCHEMA marts IS 'Gold layer: Analytics-ready dimensional model';
COMMENT ON SCHEMA audit IS 'Data quality and pipeline audit logs';

COMMENT ON TABLE raw.eia_energy_data IS 'Raw energy data from EIA API';
COMMENT ON TABLE raw.enrichment_data IS 'Raw enrichment data from FastAPI service';
COMMENT ON TABLE marts.fct_energy_metrics IS 'Main fact table for energy analytics';
