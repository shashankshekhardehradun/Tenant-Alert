{{ config(materialized='view') }}

select
  complaint_created_date,
  borough,
  complaint_type,
  count(*) as complaint_count
from {{ ref('gold_fct_complaints') }}
group by 1, 2, 3
