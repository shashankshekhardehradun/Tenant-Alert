"""Command-line runner for Census ACS tract ingestion."""

from __future__ import annotations

import argparse
from pathlib import Path

from ingestion.census.acs import run_census_acs_tract_etl
from tenant_alert.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Census ACS tract ETL for NYC.")
    parser.add_argument("--year", type=int, required=True, help="ACS 5-year vintage, e.g. 2023.")
    parser.add_argument("--upload-to-gcs", action="store_true")
    parser.add_argument("--load-to-bigquery", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_census_acs_tract_etl(
        args.year,
        api_key=settings.census_api_key or None,
        local_data_dir=Path(settings.local_data_dir),
        upload_to_gcs=args.upload_to_gcs,
        load_to_bigquery=args.load_to_bigquery,
    )
    print(f"rows={result.row_count}")
    print(f"local_path={result.local_path}")
    if result.gcs_uri:
        print(f"gcs_uri={result.gcs_uri}")
    if result.bigquery_table:
        print(f"bigquery_table={result.bigquery_table}")


if __name__ == "__main__":
    main()
