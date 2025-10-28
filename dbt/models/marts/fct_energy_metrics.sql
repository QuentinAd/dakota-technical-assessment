{{
    config(
        materialized='table',
        tags=['marts', 'fact_table'],
        post_hook=[
            "CREATE INDEX IF NOT EXISTS idx_fct_energy_metrics_time_key ON {{ this }} (time_key);",
            "CREATE INDEX IF NOT EXISTS idx_fct_energy_metrics_location_key ON {{ this }} (location_key);",
            "CREATE INDEX IF NOT EXISTS idx_fct_energy_metrics_time_location ON {{ this }} (time_key, location_key);",
            "ALTER TABLE {{ this }} DROP CONSTRAINT IF EXISTS fk_fct_energy_metrics_time;",
            "ALTER TABLE {{ this }} DROP CONSTRAINT IF EXISTS fk_fct_energy_metrics_location;",
            "ALTER TABLE {{ this }} ADD CONSTRAINT fk_fct_energy_metrics_time FOREIGN KEY (time_key) REFERENCES marts.dim_time(time_key);",
            "ALTER TABLE {{ this }} ADD CONSTRAINT fk_fct_energy_metrics_location FOREIGN KEY (location_key) REFERENCES marts.dim_location(location_key);"
        ]
    )
}}

/*
Fact table for energy metrics analytics.

This fact table combines energy generation (by source), consumption (by sector),
and enrichment data with dimension table foreign keys. Designed for efficient
analytical queries using a star schema pattern.

Note: Currently materialized as a table. For production with large data volumes,
consider changing to incremental materialization.
*/

with generation as (
    select
        period_date,
        location,
        energy_source,
        generation_mwh
    from {{ ref('stg_eia_energy_generation') }}
),

-- Pivot generation data by energy source
generation_pivoted as (
    select
        period_date,
        location,

        -- Generation by source
        sum(case when energy_source = 'coal' then generation_mwh else 0 end) as coal_generation_mwh,
        sum(case when energy_source = 'natural_gas' then generation_mwh else 0 end) as natural_gas_generation_mwh,
        sum(case when energy_source = 'nuclear' then generation_mwh else 0 end) as nuclear_generation_mwh,
        sum(case when energy_source = 'solar' then generation_mwh else 0 end) as solar_generation_mwh,
        sum(case when energy_source = 'wind' then generation_mwh else 0 end) as wind_generation_mwh,
        sum(case when energy_source = 'hydro' then generation_mwh else 0 end) as hydro_generation_mwh,
        sum(case when energy_source not in ('coal', 'natural_gas', 'nuclear', 'solar', 'wind', 'hydro')
            then generation_mwh else 0 end) as other_generation_mwh,

        -- Aggregated totals
        sum(generation_mwh) as total_generation_mwh,

        sum(case when energy_source in ('solar', 'wind', 'hydro')
            then generation_mwh else 0 end) as renewable_generation_mwh,

        sum(case when energy_source in ('coal', 'natural_gas')
            then generation_mwh else 0 end) as fossil_generation_mwh

    from generation
    group by period_date, location
),

consumption as (
    select
        period_date,
        location,
        sector,
        consumption_mwh
    from {{ ref('stg_eia_energy_consumption') }}
),

-- Pivot consumption data by sector
consumption_pivoted as (
    select
        period_date,
        location,

        sum(case when sector = 'residential' then consumption_mwh else 0 end) as residential_consumption_mwh,
        sum(case when sector = 'commercial' then consumption_mwh else 0 end) as commercial_consumption_mwh,
        sum(case when sector = 'industrial' then consumption_mwh else 0 end) as industrial_consumption_mwh,
        sum(case when sector = 'transportation' then consumption_mwh else 0 end) as transportation_consumption_mwh,

        sum(consumption_mwh) as total_consumption_mwh

    from consumption
    group by period_date, location
),

enrichment as (
    select
        period_date,
        location,
        temperature_fahrenheit,
        population,
        gdp_per_capita,
        industrial_activity_index
    from {{ ref('stg_enrichment') }}
),

-- Combine all metrics with proper dimension table lookups
combined as (
    select
        -- Look up actual keys from dimension tables
        dt.time_key,
        dl.location_key,

        g.period_date,
        g.location,

        -- Generation metrics by source
        coalesce(g.coal_generation_mwh, 0) as coal_generation_mwh,
        coalesce(g.natural_gas_generation_mwh, 0) as natural_gas_generation_mwh,
        coalesce(g.nuclear_generation_mwh, 0) as nuclear_generation_mwh,
        coalesce(g.solar_generation_mwh, 0) as solar_generation_mwh,
        coalesce(g.wind_generation_mwh, 0) as wind_generation_mwh,
        coalesce(g.hydro_generation_mwh, 0) as hydro_generation_mwh,
        coalesce(g.other_generation_mwh, 0) as other_generation_mwh,

        g.total_generation_mwh,
        coalesce(g.renewable_generation_mwh, 0) as renewable_generation_mwh,
        coalesce(g.fossil_generation_mwh, 0) as fossil_generation_mwh,

        -- Consumption metrics by sector
        coalesce(c.residential_consumption_mwh, 0) as residential_consumption_mwh,
        coalesce(c.commercial_consumption_mwh, 0) as commercial_consumption_mwh,
        coalesce(c.industrial_consumption_mwh, 0) as industrial_consumption_mwh,
        coalesce(c.transportation_consumption_mwh, 0) as transportation_consumption_mwh,
        coalesce(c.total_consumption_mwh, 0) as total_consumption_mwh,

        -- Calculated metrics
        case
            when g.total_generation_mwh > 0
            then round((g.renewable_generation_mwh / g.total_generation_mwh) * 100, 2)
            else 0
        end as renewable_percentage,

        g.total_generation_mwh - coalesce(c.total_consumption_mwh, 0) as net_generation_mwh,

        -- Enrichment data
        e.temperature_fahrenheit as avg_temperature_fahrenheit,
        e.population,
        e.gdp_per_capita as gdp_per_capita_usd,
        e.industrial_activity_index

    from generation_pivoted g

    -- Join with dimension tables to get proper foreign keys
    inner join marts.dim_time dt
        on g.period_date = dt.date

    inner join marts.dim_location dl
        on g.location = dl.location_code

    left join consumption_pivoted c
        on g.period_date = c.period_date
        and g.location = c.location

    left join enrichment e
        on g.period_date = e.period_date
        and g.location = e.location
)

select
    -- Generate surrogate key for fact table
    md5(
        coalesce(cast(time_key as text), '') || '|' ||
        coalesce(cast(location_key as text), '')
    ) as metric_key,

    -- Dimension foreign keys
    time_key,
    location_key,

    -- All metrics
    coal_generation_mwh,
    natural_gas_generation_mwh,
    nuclear_generation_mwh,
    solar_generation_mwh,
    wind_generation_mwh,
    hydro_generation_mwh,
    other_generation_mwh,

    total_generation_mwh,
    renewable_generation_mwh,
    fossil_generation_mwh,

    residential_consumption_mwh,
    commercial_consumption_mwh,
    industrial_consumption_mwh,
    transportation_consumption_mwh,
    total_consumption_mwh,

    renewable_percentage,
    net_generation_mwh,

    avg_temperature_fahrenheit,
    population,
    gdp_per_capita_usd,
    industrial_activity_index,

    -- Metadata
    current_timestamp as created_at,
    current_timestamp as updated_at

from combined

order by time_key desc, location_key
