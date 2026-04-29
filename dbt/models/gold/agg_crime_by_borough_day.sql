{{ config(materialized='view') }}

select
  complaint_date,
  borough,
  law_category,
  offense_description,
  count(*) as crime_count
from {{ ref('gold_fct_crime_events') }}
group by 1, 2, 3, 4
