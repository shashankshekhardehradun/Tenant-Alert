{{ config(materialized='table') }}

select distinct
  bbl,
  bin
from {{ ref('silver_complaints') }}
where bbl is not null
