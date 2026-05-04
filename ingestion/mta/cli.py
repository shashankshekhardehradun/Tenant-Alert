"""Command-line runner for MTA service alerts ingestion."""

from __future__ import annotations

from pathlib import Path

from ingestion.mta.alerts import run_mta_service_alerts_etl
from tenant_alert.config import settings


def main() -> None:
    result = run_mta_service_alerts_etl(
        local_data_dir=Path(settings.local_data_dir),
        upload_to_gcs=True,
        load_to_bigquery=True,
    )
    print(f"rows={result.row_count}")
    print(f"local_path={result.local_path}")
    if result.gcs_uri:
        print(f"gcs_uri={result.gcs_uri}")
    if result.bigquery_table:
        print(f"bigquery_table={result.bigquery_table}")


if __name__ == "__main__":
    main()
