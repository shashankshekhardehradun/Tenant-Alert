# Tenant Alert Methodology

## Data sources

- NYC 311 complaints (`erm2-nwe9`)
- NYC PLUTO building attributes

## Data freshness

- 311 ingestion runs daily on partitioned windows.
- dbt transformations run after ingestion completes.
- ML training runs nightly.

## Resolution-time model card (v1)

- Problem type: regression
- Target: `resolution_hours`
- Model: BigQuery ML boosted tree regressor
- Evaluation: rolling time-based holdout
- Intended use: informational estimate, not legal or safety advice

## Known limitations

- 311 data quality varies by agency and category.
- Address normalization can produce ambiguous building matches.
- Predictions may be less reliable for low-volume complaint categories.
