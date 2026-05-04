"""MTA service alert ingestion from public JSON feeds."""

from __future__ import annotations

import datetime as dt
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import polars as pl
from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery

from ingestion.common.bigquery import delete_rows_for_partition_date, load_parquet_to_table
from ingestion.common.storage import upload_file_to_gcs
from tenant_alert.config import settings

MTA_ALERT_FEEDS = {
    "subway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts.json",
    "bus": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fbus-alerts.json",
}
RAW_MTA_SERVICE_ALERTS_TABLE = "raw_mta_service_alerts"
MTA_ALERTS_SCHEMA = [
    bigquery.SchemaField("snapshot_ts", "TIMESTAMP"),
    bigquery.SchemaField("feed_timestamp", "TIMESTAMP"),
    bigquery.SchemaField("mode", "STRING"),
    bigquery.SchemaField("alert_id", "STRING"),
    bigquery.SchemaField("alert_type", "STRING"),
    bigquery.SchemaField("header_text", "STRING"),
    bigquery.SchemaField("route_ids", "STRING"),
    bigquery.SchemaField("agency_ids", "STRING"),
    bigquery.SchemaField("active_start_ts", "TIMESTAMP"),
    bigquery.SchemaField("active_end_ts", "TIMESTAMP"),
    bigquery.SchemaField("created_at_ts", "TIMESTAMP"),
    bigquery.SchemaField("updated_at_ts", "TIMESTAMP"),
    bigquery.SchemaField("informed_entity_count", "INTEGER"),
]


@dataclass(frozen=True)
class MtaAlertsResult:
    row_count: int
    local_path: Path
    gcs_uri: str | None = None
    bigquery_table: str | None = None


def _epoch_to_datetime(value: Any) -> dt.datetime | None:
    if value in (None, ""):
        return None
    try:
        return dt.datetime.fromtimestamp(int(value), tz=dt.UTC).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def _translation_text(block: dict[str, Any] | None) -> str:
    if not block:
        return ""
    translations = block.get("translation") or []
    for item in translations:
        if item.get("language") == "en":
            return html.unescape(str(item.get("text") or "")).strip()
    if translations:
        return html.unescape(str(translations[0].get("text") or "")).strip()
    return ""


def _csv(values: set[str]) -> str:
    return ",".join(sorted(value for value in values if value))


def _flatten_alerts(
    payload: dict[str, Any],
    snapshot_ts: dt.datetime,
    mode: str,
) -> list[dict[str, Any]]:
    feed_timestamp = _epoch_to_datetime((payload.get("header") or {}).get("timestamp"))
    rows: list[dict[str, Any]] = []
    for entity in payload.get("entity") or []:
        alert = entity.get("alert") or {}
        mercury = alert.get("transit_realtime.mercury_alert") or {}
        informed_entities = alert.get("informed_entity") or []
        active_periods = alert.get("active_period") or [{}]
        route_ids = _csv({str(item.get("route_id") or "") for item in informed_entities})
        agency_ids = _csv({str(item.get("agency_id") or "") for item in informed_entities})
        for period in active_periods:
            rows.append(
                {
                    "snapshot_ts": snapshot_ts,
                    "feed_timestamp": feed_timestamp,
                    "mode": mode,
                    "alert_id": str(entity.get("id") or ""),
                    "alert_type": str(mercury.get("alert_type") or "Service Alert"),
                    "header_text": _translation_text(alert.get("header_text")),
                    "route_ids": route_ids,
                    "agency_ids": agency_ids,
                    "active_start_ts": _epoch_to_datetime(period.get("start")),
                    "active_end_ts": _epoch_to_datetime(period.get("end")),
                    "created_at_ts": _epoch_to_datetime(mercury.get("created_at")),
                    "updated_at_ts": _epoch_to_datetime(mercury.get("updated_at")),
                    "informed_entity_count": len(informed_entities),
                }
            )
    return rows


def run_mta_service_alerts_etl(
    *,
    local_data_dir: Path | None = None,
    upload_to_gcs: bool = False,
    load_to_bigquery: bool = False,
) -> MtaAlertsResult:
    """Fetch current public MTA subway/bus alerts, land parquet, and optionally load bronze."""
    snapshot_ts = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    partition_date = snapshot_ts.date()
    local_root = local_data_dir or Path(settings.local_data_dir)
    output_path = (
        local_root
        / "raw"
        / "mta"
        / "service_alerts"
        / f"snapshot_date={partition_date.isoformat()}"
        / "raw_mta_service_alerts.parquet"
    )
    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=30.0) as client:
        for mode, url in MTA_ALERT_FEEDS.items():
            response = client.get(url)
            response.raise_for_status()
            rows.extend(_flatten_alerts(response.json(), snapshot_ts, mode))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(rows, strict=False) if rows else pl.DataFrame(schema={})
    if rows:
        frame = frame.select([field.name for field in MTA_ALERTS_SCHEMA])
    frame.write_parquet(output_path)

    gcs_uri: str | None = None
    bigquery_table: str | None = None
    if upload_to_gcs:
        if not settings.raw_bucket_name:
            raise ValueError("upload_to_gcs=True requires GCS_RAW_BUCKET or GCP_PROJECT_ID")
        blob_name = (
            f"mta/service_alerts/snapshot_date={partition_date.isoformat()}/"
            "raw_mta_service_alerts.parquet"
        )
        gcs_uri = upload_file_to_gcs(output_path, settings.raw_bucket_name, blob_name)

    if load_to_bigquery:
        if not settings.gcp_project_id:
            raise ValueError("load_to_bigquery=True requires GCP_PROJECT_ID")
        if not gcs_uri:
            raise ValueError("load_to_bigquery=True requires upload_to_gcs=True")
        try:
            delete_rows_for_partition_date(
                project_id=settings.gcp_project_id,
                dataset_id=settings.bq_dataset_bronze,
                table_id=RAW_MTA_SERVICE_ALERTS_TABLE,
                partition_date=partition_date,
                partition_field="snapshot_ts",
            )
        except gcp_exceptions.NotFound:
            pass
        if rows:
            bigquery_table = load_parquet_to_table(
                gcs_uri,
                project_id=settings.gcp_project_id,
                dataset_id=settings.bq_dataset_bronze,
                table_id=RAW_MTA_SERVICE_ALERTS_TABLE,
                schema=MTA_ALERTS_SCHEMA,
                partition_field="snapshot_ts",
                clustering_fields=["mode", "alert_type"],
            )

    return MtaAlertsResult(
        row_count=len(rows),
        local_path=output_path,
        gcs_uri=gcs_uri,
        bigquery_table=bigquery_table,
    )
