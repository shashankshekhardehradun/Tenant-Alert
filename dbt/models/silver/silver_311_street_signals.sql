{{ config(
    materialized='table',
    partition_by={"field": "signal_date", "data_type": "date"},
    cluster_by=["borough", "signal_category"]
) }}

with base as (
    select
      cast(unique_key as string) as unique_key,
      cast(created_date as timestamp) as created_ts,
      cast(closed_date as timestamp) as closed_ts,
      upper(trim(coalesce(borough, 'UNKNOWN'))) as borough,
      cast(incident_zip as string) as incident_zip,
      upper(trim(coalesce(complaint_type, 'UNKNOWN'))) as complaint_type,
      upper(trim(coalesce(descriptor, ''))) as descriptor,
      upper(trim(coalesce(status, 'UNKNOWN'))) as status,
      cast(latitude as float64) as latitude,
      cast(longitude as float64) as longitude
    from {{ source('raw', 'raw_311_complaints') }}
    where created_date is not null
),

classified as (
    select
      *,
      case
        when complaint_type like '%NOISE%' then 'noise'
        when complaint_type in ('ILLEGAL PARKING', 'BLOCKED DRIVEWAY', 'DERELICT VEHICLE')
          then 'parking'
        when complaint_type like '%STREET LIGHT%' or complaint_type like '%TRAFFIC SIGNAL%'
          then 'lights_and_signals'
        when complaint_type in ('DIRTY CONDITION', 'UNSANITARY CONDITION', 'RODENT')
          then 'grime'
        when complaint_type like '%STREET CONDITION%' or complaint_type like '%SIDEWALK%'
          then 'street_condition'
        when complaint_type like '%HOMELESS%' then 'public_space'
        else null
      end as signal_category
    from base
)

select
  unique_key,
  date(created_ts) as signal_date,
  created_ts,
  closed_ts,
  borough,
  incident_zip,
  complaint_type,
  descriptor,
  status,
  signal_category,
  case signal_category
    when 'noise' then 1.35
    when 'parking' then 1.1
    when 'lights_and_signals' then 1.25
    when 'grime' then 1.0
    when 'street_condition' then 1.05
    when 'public_space' then 1.2
    else 1.0
  end as signal_weight,
  latitude,
  longitude,
  timestamp_diff(coalesce(closed_ts, current_timestamp()), created_ts, hour) as age_hours,
  status not in ('CLOSED', 'CANCELLED') as is_open
from classified
where signal_category is not null
  and borough not in ('UNKNOWN', 'UNSPECIFIED', 'N/A', '(NULL)', 'NULL')
qualify row_number() over (partition by unique_key order by created_ts desc) = 1
