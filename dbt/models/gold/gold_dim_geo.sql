{{ config(materialized='table') }}

select distinct
  borough,
  incident_zip
from {{ ref('silver_complaints') }}
