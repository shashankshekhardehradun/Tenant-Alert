{{ config(materialized='view') }}

select
  snapshot_ts,
  feed_timestamp,
  alert_id,
  alert_type,
  header_text,
  route_ids,
  agency_ids,
  active_start_ts,
  active_end_ts,
  created_at_ts,
  updated_at_ts,
  informed_entity_count
from {{ source('raw', 'raw_mta_subway_alerts') }}
