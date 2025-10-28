{{
    config(
        materialized='view',
        tags=['intermediate', 'combined']
    )
}}

/*
Intermediate model combining energy generation, consumption, and enrichment data.

This model joins the three staging layers to create a unified view of energy
metrics enriched with weather and economic indicators. Includes business logic
for calculating renewable percentages, efficiency ratios, and correlation metrics.

Business Logic:
- Aggregate generation by location and period (across all energy sources)
- Calculate renewable vs non-renewable generation percentages
- Join with consumption data where available
- Join with enrichment data for contextual analysis
- Handle cases where not all data types are available
*/

with generation as (
    select
        period_date,
        location,
        location_type,
        energy_source,
        generation_mwh,
        data_source as generation_source,
        ingestion_timestamp as generation_ingested_at
    from {{ ref('stg_eia_energy_generation') }}
),

-- Aggregate generation by location and period
generation_aggregated as (
    select
        period_date,
        location,
        location_type,

        -- Total generation
        sum(generation_mwh) as total_generation_mwh,

        -- Renewable generation (solar, wind, hydro)
        sum(case
            when energy_source in ('solar', 'wind', 'hydro')
            then generation_mwh
            else 0
        end) as renewable_generation_mwh,

        -- Fossil generation (coal, natural_gas)
        sum(case
            when energy_source in ('coal', 'natural_gas')
            then generation_mwh
            else 0
        end) as fossil_generation_mwh,

        -- Nuclear generation
        sum(case
            when energy_source = 'nuclear'
            then generation_mwh
            else 0
        end) as nuclear_generation_mwh,

        -- Other generation
        sum(case
            when energy_source not in ('solar', 'wind', 'hydro', 'coal', 'natural_gas', 'nuclear')
            then generation_mwh
            else 0
        end) as other_generation_mwh,

        -- Count of energy sources
        count(distinct energy_source) as energy_source_count,

        -- Latest ingestion timestamp
        max(generation_ingested_at) as generation_ingested_at

    from generation
    group by period_date, location, location_type
),

consumption as (
    select
        period_date,
        location,
        sector,
        consumption_mwh,
        data_source as consumption_source,
        ingestion_timestamp as consumption_ingested_at
    from {{ ref('stg_eia_energy_consumption') }}
),

-- Aggregate consumption by location and period
consumption_aggregated as (
    select
        period_date,
        location,

        -- Total consumption
        sum(consumption_mwh) as total_consumption_mwh,

        -- By sector
        sum(case when sector = 'residential' then consumption_mwh else 0 end) as residential_consumption_mwh,
        sum(case when sector = 'commercial' then consumption_mwh else 0 end) as commercial_consumption_mwh,
        sum(case when sector = 'industrial' then consumption_mwh else 0 end) as industrial_consumption_mwh,
        sum(case when sector = 'transportation' then consumption_mwh else 0 end) as transportation_consumption_mwh,

        -- Count of sectors
        count(distinct sector) as sector_count,

        -- Latest ingestion timestamp
        max(consumption_ingested_at) as consumption_ingested_at

    from consumption
    group by period_date, location
),

enrichment as (
    select
        period_date,
        location,
        temperature_fahrenheit,
        temperature_category,
        population,
        population_category,
        gdp_per_capita,
        industrial_activity_index,
        industrial_activity_category,
        data_source as enrichment_source,
        ingestion_timestamp as enrichment_ingested_at
    from {{ ref('stg_enrichment') }}
),

combined as (
    select
        -- Use generation as the base (required for energy analytics)
        g.period_date,
        g.location,
        g.location_type,

        -- Generation metrics
        g.total_generation_mwh,
        g.renewable_generation_mwh,
        g.fossil_generation_mwh,
        g.nuclear_generation_mwh,
        g.other_generation_mwh,
        g.energy_source_count,

        -- Calculate renewable percentage
        case
            when g.total_generation_mwh > 0
            then round((g.renewable_generation_mwh / g.total_generation_mwh) * 100, 2)
            else 0
        end as renewable_percentage,

        -- Calculate fossil percentage
        case
            when g.total_generation_mwh > 0
            then round((g.fossil_generation_mwh / g.total_generation_mwh) * 100, 2)
            else 0
        end as fossil_percentage,

        -- Consumption metrics (may be null if no consumption data)
        c.total_consumption_mwh,
        c.residential_consumption_mwh,
        c.commercial_consumption_mwh,
        c.industrial_consumption_mwh,
        c.transportation_consumption_mwh,
        c.sector_count,

        -- Calculate generation vs consumption ratio (efficiency indicator)
        case
            when c.total_consumption_mwh is not null and c.total_consumption_mwh > 0
            then round(g.total_generation_mwh / c.total_consumption_mwh, 4)
            else null
        end as generation_to_consumption_ratio,

        -- Enrichment data (may be null if no enrichment data)
        e.temperature_fahrenheit,
        e.temperature_category,
        e.population,
        e.population_category,
        e.gdp_per_capita,
        e.industrial_activity_index,
        e.industrial_activity_category,

        -- Calculate per capita metrics (if population available)
        case
            when e.population is not null and e.population > 0
            then round(g.total_generation_mwh / e.population * 1000000, 2)  -- MWh per million people
            else null
        end as generation_per_capita_mwh,

        case
            when e.population is not null and e.population > 0 and c.total_consumption_mwh is not null
            then round(c.total_consumption_mwh / e.population * 1000000, 2)  -- MWh per million people
            else null
        end as consumption_per_capita_mwh,

        -- Data quality flags
        case when c.total_consumption_mwh is not null then true else false end as has_consumption_data,
        case when e.temperature_fahrenheit is not null then true else false end as has_enrichment_data,

        -- Metadata timestamps
        g.generation_ingested_at,
        c.consumption_ingested_at,
        e.enrichment_ingested_at

    from generation_aggregated g

    -- Left join to preserve all generation records
    left join consumption_aggregated c
        on g.period_date = c.period_date
        and g.location = c.location

    left join enrichment e
        on g.period_date = e.period_date
        and g.location = e.location
)

select
    -- Generate surrogate key for intermediate layer
    md5(
        coalesce(cast(period_date as text), '') || '|' ||
        coalesce(location, '')
    ) as energy_combined_key,
    *
from combined

order by period_date desc, location
