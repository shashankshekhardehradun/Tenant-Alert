create or replace model `{{PROJECT_ID}}.ml.resolution_time_model`
options(
  model_type = 'BOOSTED_TREE_REGRESSOR',
  input_label_cols = ['resolution_hours'],
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval'
) as
select
  complaint_type,
  agency,
  borough,
  month_of_year,
  day_of_week,
  resolution_hours,
  case
    when complaint_created_date >= date_sub(current_date(), interval 60 day) then true
    else false
  end as is_eval
from `{{PROJECT_ID}}.ml.features_resolution_time`;
