{{ config(materialized='table', cluster_by=["borough", "hour"]) }}

with latest_feature_day as (
  select max(feature_date) as feature_date
  from {{ ref('features_crime_risk_hourly') }}
),

prediction_input as (
  select
    feature_date,
    borough,
    hour,
    day_of_week,
    month,
    is_weekend,
    recent_7d_incidents,
    recent_14d_incidents,
    recent_30d_incidents,
    recent_14d_severity_score,
    total_population,
    poverty_rate,
    renter_share,
    bachelors_or_higher_share,
    approx_median_household_income,
    approx_median_gross_rent
  from {{ ref('features_crime_risk_hourly') }}
  where feature_date = (select feature_date from latest_feature_day)
)

select
  *
from ml.predict(
  model `{{ target.project }}.ml.crime_risk_rf_model`,
  table prediction_input
)
