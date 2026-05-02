"""Refresh current NYPD crime data and rebuild downstream dbt/BQML models."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path

from ingestion.crime.nypd_complaints import run_nypd_complaints_etl
from tenant_alert.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh NYPD YTD data and dbt crime marts.")
    parser.add_argument(
        "--start-date",
        default=None,
        help="Inclusive start date. Defaults to yesterday UTC.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Exclusive end date. Defaults to today UTC.",
    )
    parser.add_argument("--page-size", type=int, default=5_000)
    parser.add_argument("--skip-ingestion", action="store_true")
    parser.add_argument("--skip-dbt", action="store_true")
    return parser.parse_args()


def run_dbt_models() -> None:
    commands = [
        [
            "dbt",
            "build",
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--select",
            "bronze_raw_nypd_complaints",
            "silver_crime_events",
            "gold_fct_crime_events",
            "gold_agg_demographics_by_nta",
            "features_crime_risk_hourly",
        ],
        [
            "dbt",
            "run",
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--select",
            "train_crime_risk_rf_model",
        ],
        [
            "dbt",
            "run",
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--select",
            "crime_risk_feature_importance",
            "predictions_crime_risk_latest",
        ],
    ]
    for command in commands:
        subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    today = dt.datetime.now(dt.UTC).date()
    start_date = dt.date.fromisoformat(args.start_date) if args.start_date else today - dt.timedelta(days=1)
    end_date = dt.date.fromisoformat(args.end_date) if args.end_date else today

    if not args.skip_ingestion:
        result = run_nypd_complaints_etl(
            start_date=start_date,
            end_date=end_date,
            source="ytd",
            app_token=settings.soda_app_token or None,
            local_data_dir=Path(settings.local_data_dir),
            upload_to_gcs=True,
            load_to_bigquery=True,
            page_size=args.page_size,
        )
        print(f"ingested_rows={result.row_count}")
        print(f"gcs_uri={result.gcs_uri or ''}")
        print(f"bigquery_table={result.bigquery_table or ''}")

    if not args.skip_dbt:
        run_dbt_models()


if __name__ == "__main__":
    main()
