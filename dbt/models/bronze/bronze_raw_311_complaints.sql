{{ config(materialized='table') }}

select
  cast(unique_key as string) as unique_key,
  created_date,
  closed_date,
  agency,
  agency_name,
  complaint_type,
  descriptor,
  incident_zip,
  incident_address,
  borough,
  latitude,
  longitude
from {{ source('raw', 'raw_311_complaints') }}
