"""
Dagster schedules for the energy analytics pipeline.

Defines schedules for:
- Daily EIA ingestion (once per day at 2 AM)
- Hourly enrichment ingestion (every hour)
"""

from dagster import RunRequest, schedule


@schedule(
    name="daily_eia_schedule",
    cron_schedule="0 2 * * *",  # Daily at 2 AM
    job_name="eia_ingestion_job",
    execution_timezone="UTC",
)
def daily_eia_schedule():
    """
    Schedule for daily EIA data ingestion.

    Runs once per day at 2 AM UTC to fetch electricity generation data
    from the EIA API. This respects rate limits and fetches the previous
    day's data.

    Returns:
        RunRequest for the EIA ingestion job
    """
    return RunRequest(run_key=None, tags={"schedule": "daily_eia", "data_source": "eia_api"})


@schedule(
    name="hourly_enrichment_schedule",
    cron_schedule="0 * * * *",  # Every hour at minute 0
    job_name="enrichment_ingestion_job",
    execution_timezone="UTC",
)
def hourly_enrichment_schedule():
    """
    Schedule for hourly enrichment data ingestion.

    Runs every hour to fetch fresh enrichment data (weather, economic
    indicators, etc.) from the FastAPI service.

    Returns:
        RunRequest for the enrichment ingestion job
    """
    return RunRequest(
        run_key=None, tags={"schedule": "hourly_enrichment", "data_source": "enrichment_api"}
    )
