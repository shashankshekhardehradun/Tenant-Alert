"""Command-line runner for NYPD crime ingestion."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from ingestion.crime.nypd_complaints import run_nypd_complaints_etl
from tenant_alert.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NYPD complaint ETL.")
    parser.add_argument("--source", choices=["historic", "ytd"], default="historic")
    parser.add_argument("--start-date", required=True, help="Inclusive start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Exclusive end date, YYYY-MM-DD.")
    parser.add_argument("--page-size", type=int, default=10_000)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--upload-to-gcs", action="store_true")
    parser.add_argument("--load-to-bigquery", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_nypd_complaints_etl(
        dt.date.fromisoformat(args.start_date),
        dt.date.fromisoformat(args.end_date),
        source=args.source,
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
