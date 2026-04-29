"""Command-line runner for NYC geography reference datasets."""

from __future__ import annotations

import argparse
from pathlib import Path

from ingestion.geography.tract_nta import run_tract_nta_etl
from tenant_alert.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NYC geography reference ETL.")
    parser.add_argument("--dataset", choices=["tract-nta"], required=True)
    parser.add_argument("--upload-to-gcs", action="store_true")
    parser.add_argument("--load-to-bigquery", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dataset == "tract-nta":
        result = run_tract_nta_etl(
            app_token=settings.soda_app_token or None,
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
