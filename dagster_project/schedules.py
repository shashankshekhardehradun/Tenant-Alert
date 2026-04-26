"""Schedules for recurring jobs."""

from dagster import ScheduleDefinition

from dagster_project.jobs import ingestion_job, transform_job

daily_ingestion_schedule = ScheduleDefinition(
    job=ingestion_job,
    cron_schedule="0 6 * * *",
)

daily_transform_schedule = ScheduleDefinition(
    job=transform_job,
    cron_schedule="30 6 * * *",
)
