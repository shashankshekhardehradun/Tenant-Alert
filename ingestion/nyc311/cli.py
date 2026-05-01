"""Command-line runner for NYC 311 ETL partitions."""

from __future__ import annotations

import argparse
import datetime as dt
import time
from pathlib import Path

from ingestion.nyc311.jobs import run_311_partition_etl
from tenant_alert.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NYC 311 ETL for one or many partition dates.")
    parser.add_argument("--date", help="Single partition date in YYYY-MM-DD format.")
    parser.add_argument("--start-date", help="Backfill start date (inclusive), YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Backfill end date (inclusive), YYYY-MM-DD.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Delay between days for throttling.",
    )
    parser.add_argument("--page-size", type=int, default=50_000)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--upload-to-gcs", action="store_true")
    parser.add_argument("--load-to-bigquery", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.start_date and args.end_date:
        start = dt.date.fromisoformat(args.start_date)
        end = dt.date.fromisoformat(args.end_date)
        if start > end:
            raise SystemExit("start-date must be on or before end-date")
        day = start
        total_rows = 0
        while day <= end:
            result = run_311_partition_etl(
                day,
                app_token=settings.soda_app_token or None,
                local_data_dir=Path(settings.local_data_dir),
                upload_to_gcs=args.upload_to_gcs,
                load_to_bigquery=args.load_to_bigquery,
                page_size=args.page_size,
                max_pages=args.max_pages,
            )
            print(f"{day.isoformat()} rows={result.row_count} path={result.local_path}")
            total_rows += result.row_count
            day += dt.timedelta(days=1)
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)
        print(f"total_rows={total_rows}")
        return

    if not args.date:
        raise SystemExit("Provide --date, or --start-date and --end-date for backfill.")
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
