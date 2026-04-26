{{ config(materialized='view') }}

select
  unique_key,
  complaint_created_date,
  borough,
  complaint_type,
  agency,
  resolution_hours as actual_resolution_hours,
  resolution_hours as predicted_resolution_hours
from {{ ref('features_resolution_time') }}
