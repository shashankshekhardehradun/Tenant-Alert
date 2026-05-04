"""Refresh current NYPD crime data and rebuild downstream dbt/BQML models."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import traceback
from pathlib import Path

# Running as `python scripts/daily_crime_refresh.py` puts `scripts/` on sys.path first, so
# `import ingestion` fails unless the repo root (parent of `scripts/`) is on the path.
# Cloud Run Job uses this entrypoint; without this fix the container exits immediately with code 1.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.crime.nypd_complaints import run_nypd_complaints_etl  # noqa: E402
from ingestion.mta.alerts import run_mta_service_alerts_etl  # noqa: E402
from ingestion.nyc311.jobs import run_311_partition_etl  # noqa: E402

from tenant_alert.config import settings  # noqa: E402


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
    parser.add_argument("--skip-311", action="store_true")
    parser.add_argument("--skip-mta", action="store_true")
    parser.add_argument("--skip-dbt", action="store_true")
    parser.add_argument(
        "--street-signal-days",
        type=int,
        default=7,
        help="Rolling 311 partition days to refresh for late-arriving street-signal records.",
    )
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
            "bronze_raw_311_complaints",
            "bronze_raw_mta_service_alerts",
            "bronze_raw_nypd_complaints",
            "silver_crime_events",
            "gold_fct_crime_events",
            "gold_agg_demographics_by_nta",
            "features_crime_risk_hourly",
            "silver_311_street_signals",
            "silver_mta_service_alerts",
            "gold_avoidability_area_latest",
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
        print(f"running: {' '.join(command)}", flush=True)
        subprocess.run(command, check=True)


def run_311_street_signal_partitions(
    start_date: dt.date,
    end_date: dt.date,
    *,
    page_size: int,
) -> None:
    """Refresh a rolling 311 partition window that powers the daily avoidability page."""
    day = start_date
    total_rows = 0
    while day < end_date:
        result = run_311_partition_etl(
            day,
            app_token=settings.soda_app_token or None,
            local_data_dir=Path(settings.local_data_dir),
            upload_to_gcs=True,
            load_to_bigquery=True,
            page_size=max(page_size, 10_000),
        )
        total_rows += result.row_count
        print(f"311_date={day.isoformat()} rows={result.row_count}", flush=True)
        day += dt.timedelta(days=1)
    print(f"311_total_rows={total_rows}", flush=True)


def main() -> None:
    args = parse_args()
    today = dt.datetime.now(dt.UTC).date()
    start_date = (
        dt.date.fromisoformat(args.start_date)
        if args.start_date
        else today - dt.timedelta(days=1)
    )
    end_date = dt.date.fromisoformat(args.end_date) if args.end_date else today
    street_signal_start = min(start_date, today - dt.timedelta(days=args.street_signal_days))

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

    if not args.skip_311:
        run_311_street_signal_partitions(
            street_signal_start,
            end_date,
            page_size=args.page_size,
        )

    if not args.skip_mta:
        mta_result = run_mta_service_alerts_etl(
            local_data_dir=Path(settings.local_data_dir),
            upload_to_gcs=True,
            load_to_bigquery=True,
        )
        print(f"mta_service_alert_rows={mta_result.row_count}", flush=True)

    if not args.skip_dbt:
        run_dbt_models()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"subprocess failed (exit {exc.returncode}): {exc.cmd}", flush=True)
        traceback.print_exc()
        raise SystemExit(exc.returncode) from exc
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
