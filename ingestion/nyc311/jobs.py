"""Ingestion entrypoints for NYC 311 datasets."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ingestion.common.socrata import SocrataClient, SocrataConfig

NYC311_DATASET_ID = "erm2-nwe9"


def _date_range_where(start_date: dt.date, end_date: dt.date) -> str:
    start = start_date.isoformat()
    end = end_date.isoformat()
    return f"created_date >= '{start}T00:00:00' AND created_date < '{end}T00:00:00'"


def fetch_incremental_partition(
    start_date: dt.date,
    end_date: dt.date,
    output_path: Path,
    app_token: str | None = None,
) -> int:
    """Fetch one partition window and persist to parquet."""
    client = SocrataClient(SocrataConfig(app_token=app_token))
    where = _date_range_where(start_date, end_date)
    rows = client.fetch_all(NYC311_DATASET_ID, where=where)
    if not rows:
        return 0
    frame = pl.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(output_path)
    return frame.height
