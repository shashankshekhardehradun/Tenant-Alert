"""Dagster assets for ingestion."""

from __future__ import annotations

import datetime as dt

from dagster import AssetExecutionContext, DailyPartitionsDefinition, Output, asset
from ingestion.nyc311.jobs import run_311_partition_etl

from tenant_alert.config import settings

nyc311_partitions = DailyPartitionsDefinition(start_date="2024-01-01")


@asset(partitions_def=nyc311_partitions, group_name="ingestion")
def nyc311_raw_partition(context: AssetExecutionContext) -> Output[int]:
    """Pull one day of 311 data, land parquet, and optionally load bronze."""
    partition_date = dt.date.fromisoformat(context.partition_key)
    result = run_311_partition_etl(
        partition_date,
        app_token=settings.soda_app_token or None,
        upload_to_gcs=settings.etl_upload_to_gcs,
        load_to_bigquery=settings.etl_load_to_bigquery,
    )
    return Output(
        result.row_count,
        metadata={
            "rows": result.row_count,
            "local_path": str(result.local_path),
            "gcs_uri": result.gcs_uri or "",
            "bigquery_table": result.bigquery_table or "",
        },
    )
