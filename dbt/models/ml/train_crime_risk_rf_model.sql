{{ config(
    materialized='table',
    pre_hook="
      create or replace model `{{ target.project }}.ml.crime_risk_rf_model`
      options(
        model_type = 'RANDOM_FOREST_REGRESSOR',
        input_label_cols = ['crime_pressure_score'],
        data_split_method = 'CUSTOM',
        data_split_col = 'is_eval',
        num_parallel_tree = 80,
        max_tree_depth = 12
      ) as
      with feature_bounds as (
        select
          min(feature_date) as min_feature_date,
          max(feature_date) as max_feature_date,
          date_diff(max(feature_date), min(feature_date), day) as feature_day_span
        from {{ ref('features_crime_risk_hourly') }}
        where crime_pressure_score is not null
      )
      select
        features.crime_pressure_score,
        features.borough,
        features.hour,
        features.day_of_week,
        features.month,
        features.is_weekend,
        features.recent_7d_incidents,
        features.recent_14d_incidents,
        features.recent_30d_incidents,
        features.recent_14d_severity_score,
        features.total_population,
        features.poverty_rate,
        features.renter_share,
        features.bachelors_or_higher_share,
        features.approx_median_household_income,
        features.approx_median_gross_rent,
        case
          when feature_bounds.feature_day_span >= 60 then
            features.feature_date >= date_sub(feature_bounds.max_feature_date, interval 30 day)
          else
            mod(abs(farm_fingerprint(concat(
              cast(features.feature_date as string),
              '|',
              features.borough,
              '|',
              cast(features.hour as string)
            ))), 5) = 0
        end as is_eval
      from {{ ref('features_crime_risk_hourly') }} as features
      cross join feature_bounds
      where features.crime_pressure_score is not null
    "
) }}

select
  'crime_risk_rf_model' as model_name,
  'RANDOM_FOREST_REGRESSOR' as model_type,
  current_timestamp() as trained_at,
  count(*) as training_rows,
  min(feature_date) as training_start_date,
  max(feature_date) as training_end_date
from {{ ref('features_crime_risk_hourly') }}
