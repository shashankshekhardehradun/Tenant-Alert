"""Dagster assets for ingestion."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from dagster import AssetExecutionContext, DailyPartitionsDefinition, Output, asset

from ingestion.nyc311.jobs import fetch_incremental_partition


nyc311_partitions = DailyPartitionsDefinition(start_date="2024-01-01")


@asset(partitions_def=nyc311_partitions, group_name="ingestion")
def nyc311_raw_partition(context: AssetExecutionContext) -> Output[int]:
    """Pull one day of 311 data and write local parquet artifact."""
    partition_date = dt.date.fromisoformat(context.partition_key)
    next_date = partition_date + dt.timedelta(days=1)
    output_file = Path("data/raw/nyc311") / f"created_date={partition_date.isoformat()}" / "data.parquet"
    row_count = fetch_incremental_partition(partition_date, next_date, output_file)
    return Output(row_count, metadata={"rows": row_count, "path": str(output_file)})
