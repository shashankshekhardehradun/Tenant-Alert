{{ config(materialized='table') }}

select distinct
  complaint_type
from {{ ref('silver_complaints') }}
where complaint_type is not null
