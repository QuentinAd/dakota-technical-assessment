{{
    config(
        materialized='view',
        tags=['staging', 'eia', 'generation']
    )
}}

/*
Staging model for EIA energy generation data.

This model cleans and types raw EIA API data, focusing on electricity generation metrics.
Generation data is identified by series containing generation-related keywords or by
having non-null energy_source values indicating generation activity.

Transformations:
- Parse period string (YYYY-MM format) to DATE
- Cast numeric fields with proper typing
- Clean and standardize text fields
- Handle nulls appropriately
- Add metadata for lineage tracking
*/

with source as (
    select * from {{ source('raw', 'eia_energy_data') }}
),

generation_data as (
    select
        -- Primary key and metadata
        id as source_id,
        source as data_source,
        ingestion_timestamp,

        -- Time dimension
        -- Parse period string to date (assuming YYYY-MM format, use first day of month)
        case
            when period ~ '^\d{4}-\d{2}$' then
                to_date(period || '-01', 'YYYY-MM-DD')
            when period ~ '^\d{4}-\d{2}-\d{2}$' then
                to_date(period, 'YYYY-MM-DD')
            else null
        end as period_date,

        -- Determine period type from format
        case
            when period ~ '^\d{4}-\d{2}-\d{2}$' then 'daily'
            when period ~ '^\d{4}-\d{2}$' then 'monthly'
            when period ~ '^\d{4}$' then 'annual'
            else 'unknown'
        end as period_type,

        period as period_raw,

        -- Location dimension (add US- prefix for state codes to match dim_location)
        case
            when length(trim(location)) = 2
                and location_type not in ('pacific', 'east south central', 'west south central',
                                          'east north central', 'west north central',
                                          'mountain', 'new england', 'middle atlantic', 'south atlantic')
            then 'US-' || trim(upper(location))
            else trim(upper(location))
        end as location,
        trim(lower(location_type)) as location_type,

        -- Energy attributes
        trim(lower(energy_source)) as energy_source,
        trim(lower(sector)) as sector,

        -- Fact/Measure
        -- Assuming value represents generation in MWh or needs conversion based on units
        value as generation_value,
        trim(lower(units)) as units,

        -- Calculate standardized generation in MWh
        case
            when lower(units) like '%mwh%' then value
            when lower(units) like '%thousand mwh%' then value * 1000
            when lower(units) like '%gwh%' then value * 1000
            when lower(units) like '%kwh%' then value / 1000
            else value  -- default: assume MWh
        end as generation_mwh,

        -- API metadata
        series_id,
        raw_json

    from source

    where
        -- Filter for generation data
        -- Include records with valid energy source (generation always has this)
        energy_source is not null
        and value is not null
        and value >= 0  -- generation values should be non-negative

        -- Exclude records that are clearly consumption/sales
        and (
            series_id not ilike '%sales%'
            and series_id not ilike '%consumption%'
            and series_id not ilike '%revenue%'
        )
)

select
    -- Generate surrogate key (simple MD5 hash approach)
    md5(
        coalesce(cast(source_id as text), '') || '|' ||
        coalesce(cast(period_date as text), '') || '|' ||
        coalesce(location, '') || '|' ||
        coalesce(energy_source, '')
    ) as generation_key,
    *
from generation_data

-- Data quality filters
where period_date is not null
  and location is not null
  and energy_source is not null
  and generation_mwh is not null

order by period_date desc, location, energy_source
