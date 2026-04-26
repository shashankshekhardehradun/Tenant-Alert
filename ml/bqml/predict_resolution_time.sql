create or replace table `{{PROJECT_ID}}.ml.predictions_resolution_time_scored` as
select
  f.unique_key,
  f.complaint_created_date,
  f.complaint_type,
  f.agency,
  f.borough,
  f.resolution_hours as actual_resolution_hours,
  p.predicted_resolution_hours
from ml.predict(
  model `{{PROJECT_ID}}.ml.resolution_time_model`,
  (
    select
      unique_key,
      complaint_created_date,
      complaint_type,
      agency,
      borough,
      month_of_year,
      day_of_week,
      resolution_hours
    from `{{PROJECT_ID}}.ml.features_resolution_time`
  )
) as p
join `{{PROJECT_ID}}.ml.features_resolution_time` as f
  using (complaint_type, agency, borough, month_of_year, day_of_week, resolution_hours);
