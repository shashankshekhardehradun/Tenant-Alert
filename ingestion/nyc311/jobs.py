"""Ingestion entrypoints for NYC 311 datasets."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from google.cloud import bigquery

from ingestion.common.bigquery import load_parquet_to_table
from ingestion.common.socrata import SocrataClient, SocrataConfig
from ingestion.common.storage import upload_file_to_gcs
from tenant_alert.config import settings

NYC311_DATASET_ID = "erm2-nwe9"
RAW_311_TABLE = "raw_311_complaints"
NYC311_BRONZE_SCHEMA = [
    bigquery.SchemaField("unique_key", "STRING"),
    bigquery.SchemaField("created_date", "TIMESTAMP"),
    bigquery.SchemaField("closed_date", "TIMESTAMP"),
    bigquery.SchemaField("agency", "STRING"),
    bigquery.SchemaField("agency_name", "STRING"),
    bigquery.SchemaField("complaint_type", "STRING"),
    bigquery.SchemaField("descriptor", "STRING"),
    bigquery.SchemaField("location_type", "STRING"),
    bigquery.SchemaField("incident_zip", "STRING"),
    bigquery.SchemaField("incident_address", "STRING"),
    bigquery.SchemaField("street_name", "STRING"),
    bigquery.SchemaField("cross_street_1", "STRING"),
    bigquery.SchemaField("cross_street_2", "STRING"),
    bigquery.SchemaField("address_type", "STRING"),
    bigquery.SchemaField("city", "STRING"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("resolution_description", "STRING"),
    bigquery.SchemaField("resolution_action_updated_date", "TIMESTAMP"),
    bigquery.SchemaField("community_board", "STRING"),
    bigquery.SchemaField("council_district", "INTEGER"),
    bigquery.SchemaField("bbl", "STRING"),
    bigquery.SchemaField("borough", "STRING"),
    bigquery.SchemaField("latitude", "FLOAT"),
    bigquery.SchemaField("longitude", "FLOAT"),
    bigquery.SchemaField("open_data_channel_type", "STRING"),
]
NYC311_COLUMNS = [field.name for field in NYC311_BRONZE_SCHEMA]


@dataclass(frozen=True)
class ExtractLoadResult:
    """Metadata describing one completed 311 extract/load partition."""

    row_count: int
    local_path: Path
    gcs_uri: str | None = None
    bigquery_table: str | None = None


def _date_range_where(start_date: dt.date, end_date: dt.date) -> str:
    start = start_date.isoformat()
    end = end_date.isoformat()
    return f"created_date >= '{start}T00:00:00' AND created_date < '{end}T00:00:00'"


def _normalize_311_frame(frame: pl.DataFrame) -> pl.DataFrame:
    """Keep a stable bronze schema and cast fields BigQuery should partition/filter on."""
    for column in NYC311_COLUMNS:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.Utf8).alias(column))

    return frame.select(
        pl.col("unique_key").cast(pl.Utf8),
        pl.col("created_date").str.strptime(pl.Datetime, strict=False),
        pl.col("closed_date").str.strptime(pl.Datetime, strict=False),
        pl.col("agency").cast(pl.Utf8),
        pl.col("agency_name").cast(pl.Utf8),
        pl.col("complaint_type").cast(pl.Utf8),
        pl.col("descriptor").cast(pl.Utf8),
        pl.col("location_type").cast(pl.Utf8),
        pl.col("incident_zip").cast(pl.Utf8),
        pl.col("incident_address").cast(pl.Utf8),
        pl.col("street_name").cast(pl.Utf8),
        pl.col("cross_street_1").cast(pl.Utf8),
        pl.col("cross_street_2").cast(pl.Utf8),
        pl.col("address_type").cast(pl.Utf8),
        pl.col("city").cast(pl.Utf8),
        pl.col("status").cast(pl.Utf8),
        pl.col("resolution_description").cast(pl.Utf8),
        pl.col("resolution_action_updated_date").str.strptime(pl.Datetime, strict=False),
        pl.col("community_board").cast(pl.Utf8),
        pl.col("council_district").cast(pl.Int64, strict=False),
        pl.col("bbl").cast(pl.Utf8),
        pl.col("borough").cast(pl.Utf8),
        pl.col("latitude").cast(pl.Float64, strict=False),
        pl.col("longitude").cast(pl.Float64, strict=False),
        pl.col("open_data_channel_type").cast(pl.Utf8),
    )


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


def run_311_partition_etl(
    partition_date: dt.date,
    *,
    app_token: str | None = None,
    local_data_dir: Path | None = None,
    upload_to_gcs: bool = False,
    load_to_bigquery: bool = False,
    page_size: int = 50_000,
    max_pages: int | None = None,
) -> ExtractLoadResult:
    """Extract one 311 day from Socrata, land parquet, and optionally load bronze."""
    next_date = partition_date + dt.timedelta(days=1)
    local_root = local_data_dir or Path(settings.local_data_dir)
    output_path = (
        local_root
        / "raw"
        / "nyc311"
        / f"created_date={partition_date.isoformat()}"
        / "raw_311_complaints.parquet"
    )

    client = SocrataClient(SocrataConfig(app_token=app_token))
    where = _date_range_where(partition_date, next_date)
    frames: list[pl.DataFrame] = []
    for page in client.iter_pages(
        NYC311_DATASET_ID,
        where=where,
        order="created_date asc",
        page_size=page_size,
        max_pages=max_pages,
    ):
        frames.append(pl.DataFrame(page))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not frames:
        pl.DataFrame().write_parquet(output_path)
        return ExtractLoadResult(row_count=0, local_path=output_path)

    frame = _normalize_311_frame(pl.concat(frames, how="diagonal_relaxed"))
    frame.write_parquet(output_path)

    gcs_uri: str | None = None
    bigquery_table: str | None = None
    if upload_to_gcs:
        if not settings.raw_bucket_name:
            raise ValueError("upload_to_gcs=True requires GCS_RAW_BUCKET or GCP_PROJECT_ID")
        blob_name = f"nyc311/created_date={partition_date.isoformat()}/raw_311_complaints.parquet"
        gcs_uri = upload_file_to_gcs(output_path, settings.raw_bucket_name, blob_name)

    if load_to_bigquery:
        if not settings.gcp_project_id:
            raise ValueError("load_to_bigquery=True requires GCP_PROJECT_ID")
        if not gcs_uri:
            raise ValueError("load_to_bigquery=True requires upload_to_gcs=True")
        bigquery_table = load_parquet_to_table(
            gcs_uri,
            project_id=settings.gcp_project_id,
            dataset_id=settings.bq_dataset_bronze,
            table_id=RAW_311_TABLE,
            schema=NYC311_BRONZE_SCHEMA,
            partition_field="created_date",
            clustering_fields=["borough", "complaint_type"],
        )

    return ExtractLoadResult(
        row_count=frame.height,
        local_path=output_path,
        gcs_uri=gcs_uri,
        bigquery_table=bigquery_table,
    )
