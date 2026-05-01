# NYC Roulette

NYC Roulette is a crime intelligence and urban analytics platform built on public NYC data. It combines NYPD complaint records, Census ACS demographics, NYC geography mappings, and the original 311 tenant-alert data backbone into an end-to-end data product with ETL, warehouse modeling, API serving, and a portfolio-focused frontend.

The current product direction is an interactive crime analytics dashboard:

- Graphs page with borough, offense, severity, time-density, and socioeconomic views.
- Map page with Google Maps, deck.gl 3D crime-density columns, heat mode, incident points, Street View links, and NYC Open Data source links.
- BigQuery medallion warehouse with raw, cleaned, and analytics-ready marts.
- FastAPI service exposing crime, demographic, and legacy tenant analytics.
- Next.js frontend designed for a visually strong first impression.

The older "Tenant Alert" 311 pipeline remains in the repo as a supporting data source and extensibility example.

## Feature Highlights

- **Immersive crime map:** Google Maps JavaScript API, optional custom Map ID, deck.gl `HexagonLayer`, `HeatmapLayer`, and severity-colored incident overlays.
- **Crime graphs:** borough totals, daily trend with offense breakdown on hover, severity mix, top offenses, and weekday/hour density grid.
- **Demographic context:** borough-level poverty rate, renter share, education share, income, rent, and crime rate per 100k residents.
- **Rotatable 3D visual:** Plotly WebGL socioeconomic crime-space view.
- **Source traceability:** incident popups link to Google Maps, Street View, and the underlying NYC Open Data complaint record.
- **Data engineering backbone:** Socrata ingestion, local parquet landing, optional GCS upload, BigQuery bronze loads, dbt silver/gold models, and API-backed visualization.

## Architecture

- Ingestion: Python jobs pull NYC Open Data and Census API data into parquet and BigQuery.
- Warehouse: BigQuery datasets (`bronze`, `silver`, `gold`, `ml`) follow a medallion-style layout.
- Modeling: dbt cleans raw records, normalizes time/location fields, filters invalid geocodes, and builds analytics marts.
- API: FastAPI routes query BigQuery and return compact dashboard payloads.
- Web: Next.js App Router, Recharts, Plotly, Google Maps JavaScript API, and deck.gl.
- Orchestration: Dagster scaffolding for scheduled ingestion/dbt workflows.
- ML: BigQuery ML resolution-time model scaffold from the original tenant-alert direction.

## Repository layout

- `infra/` Terraform for GCP foundations.
- `ingestion/` Source extract and normalization code.
- `dagster_project/` Dagster assets, jobs, schedules.
- `dbt/` Warehouse transformations and feature models.
- `api/` FastAPI routes for analytics endpoints.
- `web/` Next.js frontend.
- `ml/` BigQuery ML SQL scripts.
- `docs/` data-source, secrets, table inventory, and methodology notes.

## Current Data Sources

- **NYPD complaints:** historic dataset `qgea-i56i` and year-to-date dataset `5uac-w243`.
- **NYC 311 complaints:** tenant/housing complaint analytics and extensibility backbone.
- **Census ACS 5-year:** tract-level income, rent, poverty, race/ethnicity, tenure, and education features.
- **NYC tract-to-NTA equivalency:** geography bridge from Census tracts to neighborhood tabulation areas.

## Key BigQuery Tables

- `bronze.raw_nypd_complaints`
- `silver.silver_crime_events`
- `gold.gold_fct_crime_events`
- `gold.agg_crime_by_borough_day`
- `gold.agg_crime_by_hour`
- `gold.agg_crime_offense_rankings`
- `gold.gold_agg_demographics_by_nta`
- `bronze.raw_311_complaints`
- `silver.silver_complaints`
- `gold.gold_fct_complaints`

See `docs/bigquery_tables.md` for the broader table inventory and starter EDA queries.

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
5. Install web dependencies:
   - `cd web`
   - `npm install`

## Development checks

- `ruff check src tests ingestion api dagster_project`
- `mypy src`
- `pytest`
- `cd web && npx tsc --noEmit`
- `cd web && npm run build`

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

The frontend calls the FastAPI service through `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). If you see connection errors, confirm the API is listening on the same host/port.

Routes:

- `/graphs` crime charts and socioeconomic visuals.
- `/map` immersive Google/deck.gl crime map.
- `/` redirects to `/graphs`.

For the immersive crime map, enable Google Maps Platform's **Maps JavaScript API**, create a browser-restricted API key, and add it to `.env`:

```env
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your-browser-restricted-google-maps-api-key
NEXT_PUBLIC_GOOGLE_MAP_ID=your-optional-google-vector-map-id
```

Restrict the browser key to your local and deployed web origins. A Google Maps Map ID is optional, but recommended for a custom cinematic/vector map style with tilt and rotation.

The web app runs from `web/`, but `web/next.config.js` loads `NEXT_PUBLIC_` values from the repo-root `.env`, so you do not need to duplicate frontend env vars into `web/.env.local`.

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
dbt build --project-dir D:\Tenant-Alert\dbt --profiles-dir D:\Tenant-Alert\dbt --select silver_crime_events+
```

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
dbt build --project-dir D:\Tenant-Alert\dbt --profiles-dir D:\Tenant-Alert\dbt --select silver_census_acs_tract+ silver_tract_nta_equivalency+
```

The dashboard/API can then read `gold.gold_agg_demographics_by_nta` for socioeconomic crime context.

## Legacy 311 Tenant Pipeline

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

See `dbt/README.md` for details. The FastAPI analytics endpoints can still serve the original 311 complaint marts when available (`ANALYTICS_USE_GOLD=true`).

For Dagster, open the UI and materialize the `nyc311_raw_partition` asset. Local runs use `ETL_UPLOAD_TO_GCS=false` and `ETL_LOAD_TO_BIGQUERY=false` unless you opt into GCP in `.env`.

## Security Notes

- Keep `.env` and Google service-account files out of git.
- Use browser restrictions on `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`.
- Restrict the Google Maps key to the Maps JavaScript API.
- Use `scripts/check_secrets.py` before committing sensitive changes.

## Product Roadmap

- Add borough/NTA boundary polygons and normalized per-capita choropleths.
- Add filterable time windows and offense-family controls.
- Add narrative "borough tour" camera sequences for demos.
- Add ML-assisted historical commonality explorer for offense patterns by context.
- Deploy API and web services to Cloud Run with a public demo URL.
