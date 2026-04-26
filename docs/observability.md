# Observability Guide

## Objectives

- Detect failed ingestion, transformation, and ML jobs quickly.
- Measure API availability and latency.
- Track frontend runtime failures.

## Metrics and alerts

- Dagster asset freshness for `nyc311_raw_partition` and dbt assets.
- Cloud Run p95 latency and error-rate SLOs for API and web.
- BigQuery bytes processed daily budget threshold alerts.
- Cloud SQL CPU and connection thresholds.

## Tooling

- Cloud Monitoring dashboards and alerting policies.
- Sentry for API and web exceptions.
- Structured JSON logs emitted from ingestion/API services.

## Incident response

1. Confirm failing component from alert.
2. Check last successful Dagster materialization.
3. Inspect Cloud Logging for stack traces.
4. Re-run failed partition or dbt job.
5. Backfill missing partitions if needed.
