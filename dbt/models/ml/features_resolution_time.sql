{{ config(materialized='table') }}

with base as (
  select
    unique_key,
    complaint_created_date,
    extract(month from complaint_created_date) as month_of_year,
    extract(dayofweek from complaint_created_date) as day_of_week,
    borough,
    complaint_type,
    agency,
    resolution_hours
  from {{ ref('gold_fct_complaints') }}
  where resolution_hours is not null
    and resolution_hours >= 0
    and resolution_hours < 24 * 90
)
select * from base
