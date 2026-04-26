{{ config(materialized='table', partition_by={"field": "complaint_created_date", "data_type": "date"}, cluster_by=["borough", "complaint_type"]) }}

select
  unique_key,
  complaint_created_date,
  created_ts,
  closed_ts,
  agency,
  complaint_type,
  borough,
  latitude,
  longitude,
  incident_zip,
  incident_address,
  resolution_hours
from {{ ref('silver_complaints') }}
