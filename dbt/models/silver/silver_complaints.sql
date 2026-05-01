{{ config(materialized='table', partition_by={"field": "complaint_created_date", "data_type": "date"}, cluster_by=["borough", "complaint_type"]) }}

with base as (
    select
      unique_key,
      cast(created_date as timestamp) as created_ts,
      cast(closed_date as timestamp) as closed_ts,
      upper(trim(agency)) as agency,
      upper(trim(complaint_type)) as complaint_type,
      upper(trim(coalesce(borough, 'UNKNOWN'))) as borough,
      cast(latitude as float64) as latitude,
      cast(longitude as float64) as longitude,
      incident_zip,
      incident_address,
      cast(bbl as string) as bbl,
      cast(bin as string) as bin
    from {{ ref('bronze_raw_311_complaints') }}
)
select
  unique_key,
  date(created_ts) as complaint_created_date,
  created_ts,
  closed_ts,
  agency,
  complaint_type,
  borough,
  bbl,
  bin,
  latitude,
  longitude,
  incident_zip,
  incident_address,
  timestamp_diff(closed_ts, created_ts, hour) as resolution_hours
from base
qualify row_number() over (partition by unique_key order by created_ts desc) = 1
