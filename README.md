# Tenant Alert

Tenant Alert is a data platform and web product for NYC renters. It ingests NYC 311 complaints, transforms them into analytics-ready marts, and exposes neighborhood/building insights through an API and frontend.

## Architecture

- Ingestion: Python jobs pull from NYC Socrata API into parquet.
- Orchestration: Dagster assets/jobs/schedules run ingestion and dbt.
- Warehouse: BigQuery datasets (`bronze`, `silver`, `gold`, `ml`).
- App: FastAPI backend and Next.js frontend.
- ML: BigQuery ML resolution-time model scaffold.

## Repository layout

- `infra/` Terraform for GCP foundations.
- `ingestion/` Source extract and normalization code.
- `dagster_project/` Dagster assets, jobs, schedules.
- `dbt/` Warehouse transformations and feature models.
- `api/` FastAPI routes for analytics endpoints.
- `web/` Next.js frontend.
- `ml/` BigQuery ML SQL scripts.
- `docs/` Observability and methodology notes.

## Local setup

1. Create a virtual environment:
   - Windows PowerShell: `python -m venv .venv`
2. Activate:
   - `.venv\\Scripts\\Activate.ps1`
3. Install dependencies:
   - `python -m pip install --upgrade pip`
   - `pip install -r requirements/dev.txt`
   - `pip install -e .`
4. Copy environment template:
   - `copy .env.example .env`

## Development checks

- `ruff check src tests ingestion api dagster_project`
- `mypy src`
- `pytest`

## Run local services

- `docker compose up`

## Run API locally

- `uvicorn api.app.main:app --reload --port 8000`

## Run web locally

Start the API first (see above), then:

```powershell
cd web
npm install
npm run dev
```

The home page calls `GET /analytics/overview` on the API (see `NEXT_PUBLIC_API_URL`). If you see connection errors, confirm the API is listening on the same host/port (default `http://localhost:8000`).

## Run one ETL partition locally

This writes parquet under `data/raw/nyc311/...` and does not touch GCP:

- `python -m ingestion.nyc311.cli --date 2024-01-01 --max-pages 1`

After GCP resources exist and auth is configured, upload and load bronze:

- `python -m ingestion.nyc311.cli --date 2024-01-01 --upload-to-gcs --load-to-bigquery`

Backfill a date range (loads one day at a time; consider `--sleep-seconds` for throttling):

- `python -m ingestion.nyc311.cli --start-date 2024-01-01 --end-date 2024-01-31 --upload-to-gcs --load-to-bigquery`

Re-running a day replaces that day in BigQuery bronze via a `DELETE` for that `created_date` day before append-loading the new parquet.

## Run dbt (silver/gold marts)

After bronze has data:

```powershell
cd dbt
dbt build
```

See `dbt/README.md` for details. The FastAPI analytics endpoints prefer `gold_fct_complaints` when available (`ANALYTICS_USE_GOLD=true`).

For Dagster, open the UI and materialize the `nyc311_raw_partition` asset. Local runs use `ETL_UPLOAD_TO_GCS=false` and `ETL_LOAD_TO_BIGQUERY=false` unless you opt into GCP in `.env`.
