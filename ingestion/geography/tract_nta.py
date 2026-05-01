"""NYC tract-to-NTA/CDTA equivalency ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
from google.cloud import bigquery

from ingestion.common.bigquery import load_parquet_to_table
from ingestion.common.socrata import SocrataClient, SocrataConfig
from ingestion.common.storage import upload_file_to_gcs
from tenant_alert.config import settings

TRACT_NTA_DATASET_ID = "hm78-6dwm"
RAW_TRACT_NTA_TABLE = "raw_tract_nta_equivalency"
TRACT_NTA_SCHEMA = [
    bigquery.SchemaField("geoid", "STRING"),
    bigquery.SchemaField("countyfips", "STRING"),
    bigquery.SchemaField("borocode", "STRING"),
    bigquery.SchemaField("boroname", "STRING"),
    bigquery.SchemaField("boroct2020", "STRING"),
    bigquery.SchemaField("ct2020", "STRING"),
    bigquery.SchemaField("ctlabel", "STRING"),
    bigquery.SchemaField("ntacode", "STRING"),
    bigquery.SchemaField("ntatype", "STRING"),
    bigquery.SchemaField("ntaname", "STRING"),
    bigquery.SchemaField("ntaabbrev", "STRING"),
    bigquery.SchemaField("cdtacode", "STRING"),
    bigquery.SchemaField("cdtatype", "STRING"),
    bigquery.SchemaField("cdtaname", "STRING"),
]


@dataclass(frozen=True)
class TractNtaResult:
    row_count: int
    local_path: Path
    gcs_uri: str | None = None
    bigquery_table: str | None = None


def _normalize_tract_nta_frame(frame: pl.DataFrame) -> pl.DataFrame:
    for field in TRACT_NTA_SCHEMA:
        if field.name not in frame.columns:
            frame = frame.with_columns(pl.lit(None, dtype=pl.Utf8).alias(field.name))
    return frame.select([pl.col(field.name).cast(pl.Utf8) for field in TRACT_NTA_SCHEMA])


def run_tract_nta_etl(
    *,
    app_token: str | None = None,
    local_data_dir: Path | None = None,
    upload_to_gcs: bool = False,
    load_to_bigquery: bool = False,
) -> TractNtaResult:
    """Pull NYC 2020 tract-to-NTA equivalency, land parquet, and optionally load bronze."""
    local_root = local_data_dir or Path(settings.local_data_dir)
    output_path = (
        local_root
        / "raw"
        / "nyc_geography"
        / "vintage=2020"
        / "tract_nta_equivalency.parquet"
    )

    client = SocrataClient(SocrataConfig(app_token=app_token))
    rows = client.fetch_all(TRACT_NTA_DATASET_ID, order="geoid asc")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = _normalize_tract_nta_frame(pl.DataFrame(rows, strict=False))
    frame.write_parquet(output_path)

    gcs_uri: str | None = None
    bigquery_table: str | None = None
    if upload_to_gcs:
        if not settings.raw_bucket_name:
            raise ValueError("upload_to_gcs=True requires GCS_RAW_BUCKET or GCP_PROJECT_ID")
        blob_name = "nyc_geography/vintage=2020/tract_nta_equivalency.parquet"
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
            table_id=RAW_TRACT_NTA_TABLE,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=TRACT_NTA_SCHEMA,
            clustering_fields=["ntacode", "geoid"],
        )

    return TractNtaResult(
        row_count=frame.height,
        local_path=output_path,
        gcs_uri=gcs_uri,
        bigquery_table=bigquery_table,
    )
