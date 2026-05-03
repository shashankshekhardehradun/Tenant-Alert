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

**PowerShell gotcha:** `$env:tenant-alert-494522` is **not** the project id. It is parsed as `$env:tenant` minus `alert-494522`, which corrupts `-var` values (you may see `project_id=-alert-494522`, `region=-east1`, empty `environment`, and `account_id` errors). Always use **underscore** names like `GCP_PROJECT_ID` above, or literals: `-var="project_id=tenant-alert-494522"`. For a hyphenated env var name you must use braces: `${env:MY-PROJECT-ID}`.

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

Terraform grants **public** `roles/run.invoker` to `allUsers` on the API and web services when `api_allow_unauthenticated` / `web_allow_unauthenticated` are true (defaults), so you do not need manual `gcloud run services add-iam-policy-binding` for a public portfolio deployment. Set them to `false` if your org blocks `allUsers` on Cloud Run.

The API reads CORS from container env: **`CORS_ALLOW_ORIGINS`** (comma-separated exact origins) and optional **`CORS_ALLOW_ORIGIN_REGEX`** (defaults to matching `https://*.a.run.app` so the deployed Next.js URL can call the API without a second apply). Add your custom domain origins to `cors_allow_origins` after domain mapping (see §9).

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

Optional Terraform flags (defaults are usually enough):

- `-var='cors_allow_origins=["http://localhost:3000","https://app.example.com"]'` — exact browser origins allowed to call the API.
- `-var='cors_allow_origin_regex='` — empty string disables the default `*.a.run.app` regex (stricter CORS).
- `-var="api_allow_unauthenticated=false"` — keep the API private (then use authenticated clients or a load balancer / IAP).

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

Pass the same optional CORS / auth flags as in §3 whenever you need to change them.

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

Set `apiUrl` from Terraform (from `infra/`, after the API exists). **Trim** avoids a stray newline breaking the host. The value must be **`https://…a.run.app`** (Cloud Run). If you accidentally use the **Artifact Registry** host (`…docker.pkg.dev`), `Invoke-RestMethod` will hit Google’s infrastructure and return an HTML **404** for `/healthz` — that is not your API.

```powershell
cd D:\Tenant-Alert\infra
$apiUrl = (terraform output -raw api_url).Trim()
Write-Host "API base URL: $apiUrl"
if ($apiUrl -notmatch '^https://.+\.a\.run\.app/?$') {
  Write-Warning "Expected Cloud Run default URL shape; if you use a custom domain, this regex is only a sanity check."
}

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

If the job fails immediately with **exit code 1**, open **Cloud Run → job execution → Logs**. A common failure was the worker importing `ingestion` while `sys.path` only contained `scripts/`; that is fixed in `scripts/daily_crime_refresh.py` and `Dockerfile.worker` (`PYTHONPATH=/app`). **Rebuild and push the worker image**, then `terraform apply` with the new `worker_image` tag.

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

## 9. Custom domain (GCP)

1. **Verify** domain ownership (Google Search Console or the flow linked from Cloud Run).
2. In **Cloud Run** → service **`tenant-alert-web-<environment>`** → **Custom domains** → add e.g. `app.yourdomain.com` → create the **DNS records** the wizard shows (often **CNAME** to a Google target).
3. Repeat for **`tenant-alert-api-<environment>`** with e.g. `api.yourdomain.com` if you want a dedicated API hostname.
4. Run **`terraform apply`** and pass **`cors_allow_origins`** including **`https://app.yourdomain.com`** so the API allows your real web origin (the default `*.a.run.app` regex does not match a custom hostname).
5. **Rebuild the web image** with `--build-arg NEXT_PUBLIC_API_URL=https://api.yourdomain.com` (or your chosen API URL), **push**, and **`terraform apply`** again with the new `web_image` (and rebuilt `api_image` if you changed only Terraform env for CORS—API image unchanged unless you changed Python).
6. In **APIs & Services** → **Credentials**, restrict the Maps browser key **HTTP referrers** to `https://app.yourdomain.com/*` (and localhost for dev if desired).

If you prefer a single hostname and path-based routing, use an **External HTTP(S) load balancer** with serverless NEGs to both services; that is more setup than subdomain → Cloud Run.
