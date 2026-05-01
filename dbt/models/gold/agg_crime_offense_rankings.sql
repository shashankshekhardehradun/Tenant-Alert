{{ config(materialized='view') }}

select
  offense_description,
  law_category,
  borough,
  count(*) as crime_count
from {{ ref('gold_fct_crime_events') }}
group by 1, 2, 3
