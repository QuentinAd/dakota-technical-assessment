{{
    config(
        materialized='view',
        tags=['staging', 'enrichment']
    )
}}

/*
Staging model for enrichment data from FastAPI service.

This model cleans and types raw enrichment data including weather (temperature),
demographic (population), and economic indicators (GDP, industrial activity).

Transformations:
- Parse period string to DATE
- Standardize temperature to Fahrenheit
- Cast numeric fields with proper typing
- Clean and standardize location codes
- Handle nulls appropriately
- Add metadata for lineage tracking
*/

with source as (
    select * from {{ source('raw', 'enrichment_data') }}
),

enrichment_cleaned as (
    select
        -- Primary key and metadata
        id as source_id,
        source as data_source,
        ingestion_timestamp,

        -- Time dimension
        case
            when period ~ '^\d{4}-\d{2}-\d{2}$' then
                to_date(period, 'YYYY-MM-DD')
            when period ~ '^\d{4}-\d{2}$' then
                to_date(period || '-01', 'YYYY-MM-DD')
            else null
        end as period_date,

        period as period_raw,

        -- Location dimension (standardize to match EIA format - remove US- prefix)
        trim(upper(regexp_replace(location, '^US-', ''))) as location,

        -- Weather data
        temperature_avg as temperature_fahrenheit,
        trim(upper(temperature_unit)) as temperature_unit,

        -- Validate temperature is in reasonable range
        case
            when temperature_avg between {{ var('min_temperature_f') }} and {{ var('max_temperature_f') }}
                then temperature_avg
            else null
        end as temperature_fahrenheit_validated,

        -- Demographic data
        population,

        -- Economic indicators
        gdp_per_capita,
        industrial_activity_index,

        -- Metadata
        raw_json

    from source

    where
        -- Basic data quality filters
        period is not null
        and location is not null
        and temperature_avg is not null
        and population is not null
)

select
    -- Generate surrogate key
    md5(
        coalesce(cast(source_id as text), '') || '|' ||
        coalesce(cast(period_date as text), '') || '|' ||
        coalesce(location, '')
    ) as enrichment_key,

    -- All fields
    source_id,
    data_source,
    ingestion_timestamp,
    period_date,
    period_raw,
    location,

    -- Use validated temperature if available, otherwise use original
    coalesce(temperature_fahrenheit_validated, temperature_fahrenheit) as temperature_fahrenheit,
    temperature_unit,

    population,
    gdp_per_capita,
    industrial_activity_index,

    -- Add derived fields
    -- Categorize temperature
    case
        when temperature_fahrenheit < 32 then 'freezing'
        when temperature_fahrenheit between 32 and 50 then 'cold'
        when temperature_fahrenheit between 50 and 70 then 'moderate'
        when temperature_fahrenheit between 70 and 85 then 'warm'
        when temperature_fahrenheit > 85 then 'hot'
        else 'unknown'
    end as temperature_category,

    -- Categorize population
    case
        when population < 1000000 then 'small'
        when population between 1000000 and 5000000 then 'medium'
        when population between 5000000 and 15000000 then 'large'
        when population > 15000000 then 'very_large'
        else 'unknown'
    end as population_category,

    -- Categorize economic activity (base 100)
    case
        when industrial_activity_index < 90 then 'low'
        when industrial_activity_index between 90 and 110 then 'normal'
        when industrial_activity_index > 110 then 'high'
        else 'unknown'
    end as industrial_activity_category,

    raw_json

from enrichment_cleaned

-- Final data quality filters
where period_date is not null
  and location is not null
  and temperature_fahrenheit is not null

order by period_date desc, location
