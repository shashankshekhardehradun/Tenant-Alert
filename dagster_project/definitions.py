"""Dagster definitions entrypoint."""

from dagster import Definitions
from dagster_dbt import DbtCliResource

from dagster_project.assets.dbt_assets import tenant_alert_dbt_assets
from dagster_project.assets.ingestion_assets import nyc311_raw_partition
from dagster_project.jobs import ingestion_job, transform_job
from dagster_project.schedules import daily_ingestion_schedule, daily_transform_schedule

defs = Definitions(
    assets=[nyc311_raw_partition, tenant_alert_dbt_assets],
    jobs=[ingestion_job, transform_job],
    schedules=[daily_ingestion_schedule, daily_transform_schedule],
    resources={"dbt": DbtCliResource(project_dir="dbt", profiles_dir="dbt")},
)
