"""Command-line runner for NYC 311 ETL partitions."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from ingestion.nyc311.jobs import run_311_partition_etl
from tenant_alert.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NYC 311 ETL for one partition date.")
    parser.add_argument("--date", required=True, help="Partition date in YYYY-MM-DD format.")
    parser.add_argument("--page-size", type=int, default=50_000)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--upload-to-gcs", action="store_true")
    parser.add_argument("--load-to-bigquery", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    partition_date = dt.date.fromisoformat(args.date)
    result = run_311_partition_etl(
        partition_date,
        app_token=settings.soda_app_token or None,
        local_data_dir=Path(settings.local_data_dir),
        upload_to_gcs=args.upload_to_gcs,
        load_to_bigquery=args.load_to_bigquery,
        page_size=args.page_size,
        max_pages=args.max_pages,
    )
    print(f"rows={result.row_count}")
    print(f"local_path={result.local_path}")
    if result.gcs_uri:
        print(f"gcs_uri={result.gcs_uri}")
    if result.bigquery_table:
        print(f"bigquery_table={result.bigquery_table}")


if __name__ == "__main__":
    main()
