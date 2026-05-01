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

For the immersive crime map, enable Google Maps Platform's Maps JavaScript API, create a browser-restricted API key, and add it to `.env`:

```env
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your-browser-restricted-google-maps-api-key
NEXT_PUBLIC_GOOGLE_MAP_ID=your-optional-google-vector-map-id
```

Restrict the browser key to your local and deployed web origins. A Google Maps Map ID is optional, but recommended for a custom cinematic/vector map style with tilt and rotation.

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

## Ingest demographics and geography features

Add your Census API key to `.env`:

```env
CENSUS_API_KEY=your-census-api-key
```

Ingest ACS tract demographics for an ACS 5-year vintage:

```powershell
python -m ingestion.census.cli --year 2023 --upload-to-gcs --load-to-bigquery
```

Ingest NYC tract-to-NTA equivalency:

```powershell
python -m ingestion.geography.cli --dataset tract-nta --upload-to-gcs --load-to-bigquery
```

Then rebuild dbt:

```powershell
$env:GCP_PROJECT_ID='tenant-alert-494522'
dbt build --project-dir D:\Tenant-Alert\dbt --profiles-dir D:\Tenant-Alert\dbt
```

The dashboard/API can then read `gold.gold_agg_demographics_by_nta` for map-ready NTA demographic features.

## Ingest NYPD crime data

Historic NYPD complaints use NYC Open Data dataset `qgea-i56i`; current YTD uses `5uac-w243`.

Small smoke test without touching GCP:

```powershell
python -m ingestion.crime.cli --source historic --start-date 2024-01-01 --end-date 2024-01-02 --max-pages 1
```

Load a date window to GCS and BigQuery:

```powershell
python -m ingestion.crime.cli --source historic --start-date 2024-01-01 --end-date 2024-02-01 --upload-to-gcs --load-to-bigquery
```

Then rebuild dbt:

```powershell
$env:GCP_PROJECT_ID='tenant-alert-494522'
dbt build --project-dir D:\Tenant-Alert\dbt --profiles-dir D:\Tenant-Alert\dbt
```

See `docs/bigquery_tables.md` for the BigQuery table inventory and starter EDA queries.

For Dagster, open the UI and materialize the `nyc311_raw_partition` asset. Local runs use `ETL_UPLOAD_TO_GCS=false` and `ETL_LOAD_TO_BIGQUERY=false` unless you opt into GCP in `.env`.
