# dbt (BigQuery)

## Prereqs

- Google ADC configured (`gcloud auth application-default login`) **or** `GOOGLE_APPLICATION_CREDENTIALS` set
- `GCP_PROJECT_ID` set in the environment
- Datasets `bronze`, `silver`, `gold`, `ml` exist in the project (Terraform creates them)

## Run

From the repo root:

```powershell
cd dbt
dbt deps
dbt build
```

## Dagster integration

Dagster expects a manifest at `dbt/target/manifest.json`. After changing models, regenerate it:

```powershell
cd dbt
dbt parse
```

The manifest is gitignored; generate it locally/CI after model changes.
