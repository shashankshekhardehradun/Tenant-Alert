"""NYPD complaint ingestion from NYC Open Data."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery

from ingestion.common.bigquery import delete_rows_for_date_range, load_parquet_to_table
from ingestion.common.socrata import SocrataClient, SocrataConfig
from ingestion.common.storage import upload_file_to_gcs
from tenant_alert.config import settings

NYPD_COMPLAINT_HISTORIC_DATASET_ID = "qgea-i56i"
NYPD_COMPLAINT_YTD_DATASET_ID = "5uac-w243"
RAW_NYPD_COMPLAINTS_TABLE = "raw_nypd_complaints"

NYPD_COMPLAINT_SCHEMA = [
    bigquery.SchemaField("source_dataset", "STRING"),
    bigquery.SchemaField("cmplnt_num", "STRING"),
    bigquery.SchemaField("cmplnt_fr_dt", "TIMESTAMP"),
    bigquery.SchemaField("cmplnt_fr_tm", "STRING"),
    bigquery.SchemaField("cmplnt_to_dt", "TIMESTAMP"),
    bigquery.SchemaField("cmplnt_to_tm", "STRING"),
    bigquery.SchemaField("addr_pct_cd", "INTEGER"),
    bigquery.SchemaField("rpt_dt", "TIMESTAMP"),
    bigquery.SchemaField("ky_cd", "INTEGER"),
    bigquery.SchemaField("ofns_desc", "STRING"),
    bigquery.SchemaField("pd_cd", "INTEGER"),
    bigquery.SchemaField("pd_desc", "STRING"),
    bigquery.SchemaField("crm_atpt_cptd_cd", "STRING"),
    bigquery.SchemaField("law_cat_cd", "STRING"),
    bigquery.SchemaField("boro_nm", "STRING"),
    bigquery.SchemaField("loc_of_occur_desc", "STRING"),
    bigquery.SchemaField("prem_typ_desc", "STRING"),
    bigquery.SchemaField("juris_desc", "STRING"),
    bigquery.SchemaField("parks_nm", "STRING"),
    bigquery.SchemaField("hadevelopt", "STRING"),
    bigquery.SchemaField("housing_psa", "STRING"),
    bigquery.SchemaField("x_coord_cd", "FLOAT"),
    bigquery.SchemaField("y_coord_cd", "FLOAT"),
    bigquery.SchemaField("latitude", "FLOAT"),
    bigquery.SchemaField("longitude", "FLOAT"),
    bigquery.SchemaField("patrol_boro", "STRING"),
    bigquery.SchemaField("station_name", "STRING"),
    bigquery.SchemaField("transit_district", "STRING"),
]
NYPD_COMPLAINT_COLUMNS = [field.name for field in NYPD_COMPLAINT_SCHEMA]


@dataclass(frozen=True)
class NypdComplaintResult:
    row_count: int
    local_path: Path
    gcs_uri: str | None = None
    bigquery_table: str | None = None


def _date_range_where(start_date: dt.date, end_date: dt.date) -> str:
    start = start_date.isoformat()
    end = end_date.isoformat()
    return f"cmplnt_fr_dt >= '{start}T00:00:00' AND cmplnt_fr_dt < '{end}T00:00:00'"


def _dataset_id(source: str) -> str:
    if source == "historic":
        return NYPD_COMPLAINT_HISTORIC_DATASET_ID
    if source == "ytd":
        return NYPD_COMPLAINT_YTD_DATASET_ID
    raise ValueError("source must be 'historic' or 'ytd'")


def _normalize_complaint_frame(frame: pl.DataFrame, source: str) -> pl.DataFrame:
    for column in NYPD_COMPLAINT_COLUMNS:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.Utf8).alias(column))

    return frame.select(
        pl.lit(source).alias("source_dataset"),
        pl.col("cmplnt_num").cast(pl.Utf8),
        pl.col("cmplnt_fr_dt").str.strptime(pl.Datetime, strict=False),
        pl.col("cmplnt_fr_tm").cast(pl.Utf8),
        pl.col("cmplnt_to_dt").str.strptime(pl.Datetime, strict=False),
        pl.col("cmplnt_to_tm").cast(pl.Utf8),
        pl.col("addr_pct_cd").cast(pl.Int64, strict=False),
        pl.col("rpt_dt").str.strptime(pl.Datetime, strict=False),
        pl.col("ky_cd").cast(pl.Int64, strict=False),
        pl.col("ofns_desc").cast(pl.Utf8),
        pl.col("pd_cd").cast(pl.Int64, strict=False),
        pl.col("pd_desc").cast(pl.Utf8),
        pl.col("crm_atpt_cptd_cd").cast(pl.Utf8),
        pl.col("law_cat_cd").cast(pl.Utf8),
        pl.col("boro_nm").cast(pl.Utf8),
        pl.col("loc_of_occur_desc").cast(pl.Utf8),
        pl.col("prem_typ_desc").cast(pl.Utf8),
        pl.col("juris_desc").cast(pl.Utf8),
        pl.col("parks_nm").cast(pl.Utf8),
        pl.col("hadevelopt").cast(pl.Utf8),
        pl.col("housing_psa").cast(pl.Utf8),
        pl.col("x_coord_cd").cast(pl.Float64, strict=False),
        pl.col("y_coord_cd").cast(pl.Float64, strict=False),
        pl.col("latitude").cast(pl.Float64, strict=False),
        pl.col("longitude").cast(pl.Float64, strict=False),
        pl.col("patrol_boro").cast(pl.Utf8),
        pl.col("station_name").cast(pl.Utf8),
        pl.col("transit_district").cast(pl.Utf8),
    )


def run_nypd_complaints_etl(
    start_date: dt.date,
    end_date: dt.date,
    *,
    source: str = "historic",
    app_token: str | None = None,
    local_data_dir: Path | None = None,
    upload_to_gcs: bool = False,
    load_to_bigquery: bool = False,
    page_size: int = 50_000,
    max_pages: int | None = None,
) -> NypdComplaintResult:
    """Extract NYPD complaints for [start_date, end_date), land parquet, optionally load bronze."""
    if start_date >= end_date:
        raise ValueError("start_date must be before end_date")

    local_root = local_data_dir or Path(settings.local_data_dir)
    output_path = (
        local_root
        / "raw"
        / "nypd_complaints"
        / f"source={source}"
        / f"start_date={start_date.isoformat()}"
        / f"end_date={end_date.isoformat()}"
        / "raw_nypd_complaints.parquet"
    )

    client = SocrataClient(SocrataConfig(app_token=app_token))
    where = _date_range_where(start_date, end_date)
    frames: list[pl.DataFrame] = []
    for page in client.iter_pages(
        _dataset_id(source),
        where=where,
        order="cmplnt_fr_dt asc",
        page_size=page_size,
        max_pages=max_pages,
    ):
        frames.append(pl.DataFrame(page, strict=False))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not frames:
        pl.DataFrame(schema={field.name: pl.Utf8 for field in NYPD_COMPLAINT_SCHEMA}).write_parquet(
            output_path
        )
        return NypdComplaintResult(row_count=0, local_path=output_path)

    frame = _normalize_complaint_frame(pl.concat(frames, how="diagonal_relaxed"), source)
    frame.write_parquet(output_path)

    gcs_uri: str | None = None
    bigquery_table: str | None = None
    if upload_to_gcs:
        if not settings.raw_bucket_name:
            raise ValueError("upload_to_gcs=True requires GCS_RAW_BUCKET or GCP_PROJECT_ID")
        blob_name = (
            f"nypd_complaints/source={source}/"
            f"start_date={start_date.isoformat()}/"
            f"end_date={end_date.isoformat()}/raw_nypd_complaints.parquet"
        )
        gcs_uri = upload_file_to_gcs(output_path, settings.raw_bucket_name, blob_name)

    if load_to_bigquery:
        if not settings.gcp_project_id:
            raise ValueError("load_to_bigquery=True requires GCP_PROJECT_ID")
        if not gcs_uri:
            raise ValueError("load_to_bigquery=True requires upload_to_gcs=True")
        try:
            delete_rows_for_date_range(
                project_id=settings.gcp_project_id,
                dataset_id=settings.bq_dataset_bronze,
                table_id=RAW_NYPD_COMPLAINTS_TABLE,
                start_date=start_date,
                end_date=end_date,
                date_field="cmplnt_fr_dt",
            )
        except gcp_exceptions.NotFound:
            pass
        if frame.height > 0:
            bigquery_table = load_parquet_to_table(
                gcs_uri,
                project_id=settings.gcp_project_id,
                dataset_id=settings.bq_dataset_bronze,
                table_id=RAW_NYPD_COMPLAINTS_TABLE,
                schema=NYPD_COMPLAINT_SCHEMA,
                partition_field="cmplnt_fr_dt",
                clustering_fields=["boro_nm", "law_cat_cd", "ofns_desc"],
            )

    return NypdComplaintResult(
        row_count=frame.height,
        local_path=output_path,
        gcs_uri=gcs_uri,
        bigquery_table=bigquery_table,
    )
