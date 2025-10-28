"""
Dagster assets for the energy analytics pipeline.

This module exports all data pipeline assets:
- eia_ingestion: Fetch EIA electricity generation data
- enrichment_ingestion: Fetch enrichment data from FastAPI service
- dbt_transformation: Run dbt models
- data_quality_check_raw: Validate raw data quality
- data_quality_check_marts: Validate marts data quality
- report_generation: Generate Jupyter notebook reports with PDF export
"""

from dagster_project.assets.data_quality_checks import (
    data_quality_check_marts,
    data_quality_check_raw,
)
from dagster_project.assets.dbt_transformation import dbt_transformation
from dagster_project.assets.eia_ingestion import eia_ingestion
from dagster_project.assets.enrichment_ingestion import enrichment_ingestion
from dagster_project.assets.report_generation import report_generation

__all__ = [
    "eia_ingestion",
    "enrichment_ingestion",
    "dbt_transformation",
    "data_quality_check_raw",
    "data_quality_check_marts",
    "report_generation",
]
