"""
Dagster project for energy analytics pipeline.

This module defines all Dagster objects (assets, jobs, schedules, sensors)
for the energy data pipeline.
"""

from dagster import Definitions, define_asset_job, load_assets_from_modules
from dagster_project import assets
from dagster_project.schedules.daily_batch import daily_eia_schedule, hourly_enrichment_schedule

# Load all assets from the assets module
all_assets = load_assets_from_modules([assets])

# Define jobs for each major pipeline component
eia_ingestion_job = define_asset_job(name="eia_ingestion_job", selection=["eia_ingestion"])

enrichment_ingestion_job = define_asset_job(
    name="enrichment_ingestion_job", selection=["enrichment_ingestion"]
)

dbt_transformation_job = define_asset_job(
    name="dbt_transformation_job", selection=["dbt_transformation"]
)

quality_check_job = define_asset_job(
    name="quality_check_job", selection=["data_quality_check_raw", "data_quality_check_marts"]
)

# Full pipeline job (runs everything in order)
full_pipeline_job = define_asset_job(name="full_pipeline_job", selection="*")

# Create Dagster definitions
defs = Definitions(
    assets=all_assets,
    jobs=[
        eia_ingestion_job,
        enrichment_ingestion_job,
        dbt_transformation_job,
        quality_check_job,
        full_pipeline_job,
    ],
    schedules=[daily_eia_schedule, hourly_enrichment_schedule],
)
