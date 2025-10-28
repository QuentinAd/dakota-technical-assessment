{{
    config(
        materialized='view',
        tags=['staging', 'eia', 'consumption']
    )
}}

/*
Staging model for EIA energy consumption/sales data.

This model cleans and types raw EIA API data, focusing on electricity consumption
and sales metrics by sector (residential, commercial, industrial, transportation).

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

consumption_data as (
    select
        -- Primary key and metadata
        id as source_id,
        source as data_source,
        ingestion_timestamp,

        -- Time dimension
        case
            when period ~ '^\d{4}-\d{2}$' then
                to_date(period || '-01', 'YYYY-MM-DD')
            when period ~ '^\d{4}-\d{2}-\d{2}$' then
                to_date(period, 'YYYY-MM-DD')
            else null
        end as period_date,

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

        -- Sector dimension (key for consumption data)
        trim(lower(sector)) as sector,

        -- Energy attributes (may be null for consumption data)
        trim(lower(energy_source)) as energy_source,

        -- Fact/Measure
        value as consumption_value,
        trim(lower(units)) as units,

        -- Calculate standardized consumption in MWh
        case
            when lower(units) like '%mwh%' then value
            when lower(units) like '%thousand mwh%' then value * 1000
            when lower(units) like '%gwh%' then value * 1000
            when lower(units) like '%kwh%' then value / 1000
            else value  -- default: assume MWh
        end as consumption_mwh,

        -- API metadata
        series_id,
        raw_json

    from source

    where
        -- Filter for consumption/sales data
        value is not null
        and value >= 0

        -- Include records with consumption/sales indicators
        and (
            series_id ilike '%sales%'
            or series_id ilike '%consumption%'
            or sector is not null  -- consumption data typically includes sector
        )

        -- Exclude generation-specific series
        and (
            series_id not ilike '%generation%'
            or sector is not null  -- but keep if sector is specified
        )
)

select
    -- Generate surrogate key (simple concatenation approach)
    md5(
        coalesce(cast(source_id as text), '') || '|' ||
        coalesce(cast(period_date as text), '') || '|' ||
        coalesce(location, '') || '|' ||
        coalesce(sector, '')
    ) as consumption_key,
    *
from consumption_data

-- Data quality filters
where period_date is not null
  and location is not null
  and consumption_mwh is not null

order by period_date desc, location, sector
