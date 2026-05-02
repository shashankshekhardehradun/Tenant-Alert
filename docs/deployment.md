# Deployment Runbook

This runbook deploys NYC Roulette to Google Cloud Run and schedules daily data refreshes.

## Prerequisites

- `gcloud` authenticated to the target project.
- `terraform` installed.
- `dbt-core` and `dbt-bigquery` installed locally for one-time setup/backfills.
- GCP project with billing enabled.
- Maps JavaScript API enabled for the browser map.

Set these variables in PowerShell:

```powershell
$env:GCP_PROJECT_ID="your-gcp-project-id"
$env:REGION="us-east1"
$env:ENVIRONMENT="dev"
```

Authenticate Docker to Artifact Registry:

```powershell
gcloud auth configure-docker "$env:REGION-docker.pkg.dev"
```

## 1. Apply foundation infrastructure

This creates buckets, BigQuery datasets, service account, Artifact Registry, and required APIs.

```powershell
cd D:\Tenant-Alert\infra

terraform init
terraform apply `
  -var="project_id=$env:GCP_PROJECT_ID" `
  -var="region=$env:REGION" `
  -var="environment=$env:ENVIRONMENT"
```

Get the container repository:

```powershell
$repo = terraform output -raw artifact_registry_repository
```

## 2. Build and push API and worker images

```powershell
cd D:\Tenant-Alert

$apiImage="$repo/api:latest"
$workerImage="$repo/worker:latest"

docker build -f Dockerfile.api -t $apiImage .
docker build -f Dockerfile.worker -t $workerImage .

docker push $apiImage
docker push $workerImage
```

## 3. Deploy API and worker job first

```powershell
cd D:\Tenant-Alert\infra

terraform apply `
  -var="project_id=$env:GCP_PROJECT_ID" `
  -var="region=$env:REGION" `
  -var="environment=$env:ENVIRONMENT" `
  -var="api_image=$apiImage" `
  -var="worker_image=$workerImage" `
  -var="soda_app_token=$env:SODA_APP_TOKEN" `
  -var="census_api_key=$env:CENSUS_API_KEY"
```

Capture the API URL:

```powershell
$apiUrl = terraform output -raw api_url
```

## 4. Build and push web image

Next.js public env vars are baked into the browser bundle at build time.

```powershell
cd D:\Tenant-Alert\web

$webImage="$repo/web:latest"

docker build `
  --build-arg NEXT_PUBLIC_API_URL=$apiUrl `
  --build-arg NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=$env:NEXT_PUBLIC_GOOGLE_MAPS_API_KEY `
  --build-arg NEXT_PUBLIC_GOOGLE_MAP_ID=$env:NEXT_PUBLIC_GOOGLE_MAP_ID `
  --build-arg NEXT_PUBLIC_USE_GOOGLE_MAP_ID=$env:NEXT_PUBLIC_USE_GOOGLE_MAP_ID `
  -t $webImage .

docker push $webImage
```

## 5. Deploy web

```powershell
cd D:\Tenant-Alert\infra

terraform apply `
  -var="project_id=$env:GCP_PROJECT_ID" `
  -var="region=$env:REGION" `
  -var="environment=$env:ENVIRONMENT" `
  -var="api_image=$apiImage" `
  -var="web_image=$webImage" `
  -var="worker_image=$workerImage" `
  -var="soda_app_token=$env:SODA_APP_TOKEN" `
  -var="census_api_key=$env:CENSUS_API_KEY"
```

Get the public web URL:

```powershell
terraform output -raw web_url
```

## 6. One-time historical data/backfill

Run historical backfills locally or as one-off Cloud Run jobs. For local:

```powershell
cd D:\Tenant-Alert

python -m ingestion.crime.cli --source historic --start-date 2024-01-01 --end-date 2025-01-01 --page-size 5000 --upload-to-gcs --load-to-bigquery
python -m ingestion.crime.cli --source historic --start-date 2025-01-01 --end-date 2026-01-01 --page-size 5000 --upload-to-gcs --load-to-bigquery
python -m ingestion.crime.cli --source ytd --start-date 2026-01-01 --end-date 2026-05-02 --page-size 5000 --upload-to-gcs --load-to-bigquery
```

Then build marts and BQML:

```powershell
cd D:\Tenant-Alert\dbt

dbt build --select bronze_raw_nypd_complaints silver_crime_events gold_fct_crime_events gold_agg_demographics_by_nta features_crime_risk_hourly
dbt run --select train_crime_risk_rf_model
dbt run --select crime_risk_feature_importance predictions_crime_risk_latest
```

## 7. Verify services

```powershell
Invoke-RestMethod "$apiUrl/healthz"
Invoke-RestMethod "$apiUrl/news/ticker?limit=5"
Invoke-RestMethod "$apiUrl/crime/data-range"
```

Manually trigger the scheduled refresh job:

```powershell
gcloud run jobs execute "tenant-alert-daily-refresh-$env:ENVIRONMENT" `
  --region "$env:REGION" `
  --wait
```

## 8. Ongoing freshness

Cloud Scheduler runs the Cloud Run job every day at 7:00 AM America/New_York.

The job:

1. Pulls yesterday's NYPD YTD complaints.
2. Uploads raw parquet to GCS.
3. Replaces that date window in BigQuery bronze.
4. Rebuilds silver/gold crime marts.
5. Rebuilds BQML features.
6. Retrains the BQML Random Forest.
7. Refreshes feature importance and latest predictions.

News ticker freshness is request-time through FastAPI with a 10-minute in-memory cache.
