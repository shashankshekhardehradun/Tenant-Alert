{{ config(materialized='view') }}

select
  complaint_hour,
  borough,
  law_category,
  count(*) as crime_count
from {{ ref('gold_fct_crime_events') }}
where complaint_hour is not null
group by 1, 2, 3
