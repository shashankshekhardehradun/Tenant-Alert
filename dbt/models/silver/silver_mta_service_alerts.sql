{{ config(
    materialized='table',
    partition_by={"field": "snapshot_date", "data_type": "date"},
    cluster_by=["borough_hint", "mode", "alert_type"]
) }}

with base as (
    select
      snapshot_ts,
      date(snapshot_ts) as snapshot_date,
      feed_timestamp,
      mode,
      alert_id,
      coalesce(nullif(trim(alert_type), ''), 'Service Alert') as alert_type,
      header_text,
      route_ids,
      active_start_ts,
      active_end_ts,
      created_at_ts,
      updated_at_ts,
      informed_entity_count
    from {{ ref('bronze_raw_mta_service_alerts') }}
    where alert_id is not null
),

expanded as (
    select
      *,
      trim(raw_route_id) as route_id
    from base,
    unnest(split(coalesce(route_ids, ''), ',')) as raw_route_id
),

route_borough_map as (
    select 'A' as route_id, 'MANHATTAN' as borough_hint union all
    select 'A', 'BROOKLYN' union all select 'A', 'QUEENS' union all
    select 'C', 'MANHATTAN' union all select 'C', 'BROOKLYN' union all
    select 'E', 'MANHATTAN' union all select 'E', 'QUEENS' union all
    select 'B', 'MANHATTAN' union all select 'B', 'BROOKLYN' union all select 'B', 'BRONX' union all
    select 'D', 'MANHATTAN' union all select 'D', 'BROOKLYN' union all select 'D', 'BRONX' union all
    select 'F', 'MANHATTAN' union all select 'F', 'BROOKLYN' union all select 'F', 'QUEENS' union all
    select 'M', 'MANHATTAN' union all select 'M', 'BROOKLYN' union all select 'M', 'QUEENS' union all
    select 'G', 'BROOKLYN' union all select 'G', 'QUEENS' union all
    select 'J', 'BROOKLYN' union all select 'J', 'QUEENS' union all
    select 'Z', 'BROOKLYN' union all select 'Z', 'QUEENS' union all
    select 'L', 'MANHATTAN' union all select 'L', 'BROOKLYN' union all
    select 'N', 'MANHATTAN' union all select 'N', 'BROOKLYN' union all select 'N', 'QUEENS' union all
    select 'Q', 'MANHATTAN' union all select 'Q', 'BROOKLYN' union all
    select 'R', 'MANHATTAN' union all select 'R', 'BROOKLYN' union all select 'R', 'QUEENS' union all
    select 'W', 'MANHATTAN' union all select 'W', 'QUEENS' union all
    select '1', 'MANHATTAN' union all
    select '2', 'MANHATTAN' union all select '2', 'BROOKLYN' union all select '2', 'BRONX' union all
    select '3', 'MANHATTAN' union all select '3', 'BROOKLYN' union all
    select '4', 'MANHATTAN' union all select '4', 'BROOKLYN' union all select '4', 'BRONX' union all
    select '5', 'MANHATTAN' union all select '5', 'BROOKLYN' union all select '5', 'BRONX' union all
    select '6', 'MANHATTAN' union all select '6', 'BRONX' union all
    select '7', 'MANHATTAN' union all select '7', 'QUEENS' union all
    select 'S', 'MANHATTAN' union all select 'FS', 'BROOKLYN' union all
    select 'GS', 'MANHATTAN' union all select 'SIR', 'STATEN ISLAND'
),

bus_borough_map as (
    select 'B' as route_prefix, 'BROOKLYN' as borough_hint union all
    select 'BM', 'MANHATTAN' union all
    select 'BX', 'BRONX' union all
    select 'M', 'MANHATTAN' union all
    select 'Q', 'QUEENS' union all
    select 'QM', 'MANHATTAN' union all
    select 'S', 'STATEN ISLAND' union all
    select 'SIM', 'MANHATTAN'
),

classified as (
    select
      expanded.*,
      regexp_extract(upper(expanded.route_id), r'^[A-Z]+') as route_prefix
    from expanded
)

select
  snapshot_ts,
  snapshot_date,
  feed_timestamp,
  mode,
  alert_id,
  alert_type,
  header_text,
  route_ids,
  classified.route_id,
  case
    when mode = 'subway' then coalesce(route_borough_map.borough_hint, 'NYC')
    when mode = 'bus' then coalesce(bus_borough_map.borough_hint, 'NYC')
    else 'NYC'
  end as borough_hint,
  case
    when lower(alert_type) like '%delay%' then 8
    when lower(alert_type) like '%planned%' then 3
    when lower(alert_type) like '%service change%' then 6
    when lower(header_text) like '%suspended%' then 10
    when lower(header_text) like '%no train%' or lower(header_text) like '%no bus%' then 10
    else 5
  end as alert_weight,
  active_start_ts,
  active_end_ts,
  created_at_ts,
  updated_at_ts,
  informed_entity_count
from classified
left join route_borough_map
  on classified.mode = 'subway'
 and classified.route_id = route_borough_map.route_id
left join bus_borough_map
  on classified.mode = 'bus'
 and classified.route_prefix = bus_borough_map.route_prefix
where classified.route_id != ''
qualify row_number() over (
  partition by snapshot_date, mode, alert_id, route_id, borough_hint
  order by updated_at_ts desc nulls last, snapshot_ts desc
) = 1
