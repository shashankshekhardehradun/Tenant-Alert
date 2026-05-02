{{ config(materialized='table') }}

select
  feature,
  importance_weight,
  importance_gain,
  importance_cover
from ml.feature_importance(model `{{ target.project }}.ml.crime_risk_rf_model`)
