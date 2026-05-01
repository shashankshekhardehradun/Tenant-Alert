# BigQuery Table Inventory

Project: `tenant-alert-494522`

## Bronze raw tables

- `bronze.raw_311_complaints`
- `bronze.raw_nypd_complaints`
- `bronze.raw_census_acs_tract`
- `bronze.raw_tract_nta_equivalency`

## Bronze dbt views

- `bronze.bronze_raw_311_complaints`
- `bronze.bronze_raw_nypd_complaints`
- `bronze.bronze_raw_census_acs_tract`
- `bronze.bronze_raw_tract_nta_equivalency`

## Silver cleaned tables

- `silver.silver_complaints`
- `silver.silver_crime_events`
- `silver.silver_census_acs_tract`
- `silver.silver_tract_nta_equivalency`

## Gold marts

- `gold.gold_fct_complaints`
- `gold.gold_fct_crime_events`
- `gold.gold_dim_building`
- `gold.gold_dim_geo`
- `gold.gold_dim_complaint_type`
- `gold.gold_agg_demographics_by_nta`
- `gold.agg_complaint_volume_by_borough_day`
- `gold.agg_crime_by_borough_day`
- `gold.agg_crime_by_hour`
- `gold.agg_crime_offense_rankings`

## ML tables/views

- `ml.features_resolution_time`
- `ml.predictions_resolution_time`

## Useful EDA queries

```sql
select min(complaint_date), max(complaint_date), count(*)
from `tenant-alert-494522.gold.gold_fct_crime_events`;

select borough, law_category, count(*) as events
from `tenant-alert-494522.gold.gold_fct_crime_events`
group by 1, 2
order by events desc;

select offense_description, count(*) as events
from `tenant-alert-494522.gold.gold_fct_crime_events`
group by 1
order by events desc
limit 25;

select *
from `tenant-alert-494522.gold.gold_agg_demographics_by_nta`
order by approx_median_household_income desc
limit 25;
```
