{{ config(materialized='table', cluster_by=["borough", "avoidability_band"]) }}

with signal_bounds as (
    select max(signal_date) as max_signal_day
    from {{ ref('silver_311_street_signals') }}
),

crime_bounds as (
    select max(complaint_date) as max_crime_day
    from {{ ref('gold_fct_crime_events') }}
),

street_base as (
    select
      s.borough,
      s.signal_category,
      s.complaint_type,
      s.descriptor,
      s.incident_zip,
      s.is_open,
      s.signal_weight,
      s.signal_date,
      b.max_signal_day
    from {{ ref('silver_311_street_signals') }} as s
    cross join signal_bounds as b
    where s.signal_date between date_sub(b.max_signal_day, interval 27 day) and b.max_signal_day
),

street_category as (
    select
      borough,
      signal_category,
      countif(signal_date = max_signal_day) as latest_count,
      countif(signal_date between date_sub(max_signal_day, interval 6 day) and max_signal_day)
        as count_7d,
      count(*) / 28.0 as avg_daily_28d,
      safe_divide(countif(is_open), count(*)) as open_ratio,
      sum(if(signal_date = max_signal_day, signal_weight, 0)) as weighted_latest_count,
      array_agg(
        struct(
          complaint_type as complaint_type,
          descriptor as descriptor,
          incident_zip as incident_zip
        )
        order by signal_date desc
        limit 1
      )[offset(0)] as latest_example
    from street_base
    group by borough, signal_category
),

street_scored as (
    select
      *,
      safe_divide(latest_count, nullif(avg_daily_28d, 0)) as spike_ratio,
      least(
        50,
        round(
          weighted_latest_count * 1.8
          + least(18, coalesce(safe_divide(latest_count, nullif(avg_daily_28d, 0)), 0) * 5)
          + coalesce(open_ratio, 0) * 10
        )
      ) as category_score
    from street_category
),

street_rollup as (
    select
      borough,
      sum(latest_count) as street_signal_count_24h,
      sum(count_7d) as street_signal_count_7d,
      round(avg(spike_ratio), 2) as avg_spike_ratio,
      round(avg(open_ratio), 2) as open_ratio,
      least(45, round(sum(category_score))) as street_signal_score,
      array_agg(
        struct(
          signal_category as category,
          latest_count as latest_count,
          round(spike_ratio, 2) as spike_ratio,
          round(category_score) as score,
          latest_example.complaint_type as complaint_type,
          latest_example.descriptor as descriptor,
          latest_example.incident_zip as incident_zip
        )
        order by category_score desc, latest_count desc
      ) as signal_options
    from street_scored
    group by borough
),

crime_rollup as (
    select
      c.borough,
      count(*) as crime_count_90d,
      countif(c.complaint_hour between 20 and 23 or c.complaint_hour between 0 and 3)
        as late_night_crime_count_90d,
      cb.max_crime_day as latest_crime_day
    from {{ ref('gold_fct_crime_events') }} as c
    cross join crime_bounds as cb
    where c.complaint_date between date_sub(cb.max_crime_day, interval 89 day) and cb.max_crime_day
      and c.borough is not null
      and c.borough not in ('(NULL)', 'NULL', 'N/A', 'UNKNOWN')
    group by c.borough, cb.max_crime_day
),

crime_scored as (
    select
      *,
      round(28 * safe_divide(crime_count_90d, max(crime_count_90d) over ())) as crime_pressure_score,
      round(
        10 * safe_divide(late_night_crime_count_90d, nullif(crime_count_90d, 0))
      ) as late_night_pressure_score
    from crime_rollup
),

mta_bounds as (
    select max(snapshot_date) as max_mta_day
    from {{ ref('silver_mta_service_alerts') }}
),

transit_rollup as (
    select
      alerts.borough_hint as borough,
      max(alerts.snapshot_date) as latest_mta_day,
      count(distinct alerts.alert_id) as transit_alert_count,
      count(distinct case when alerts.mode = 'subway' then alerts.alert_id end) as subway_alert_count,
      count(distinct case when alerts.mode = 'bus' then alerts.alert_id end) as bus_alert_count,
      count(distinct alerts.route_id) as affected_route_count,
      least(20, round(sum(alerts.alert_weight) / 2)) as transit_chaos_score,
      array_agg(
        struct(
          alerts.mode as mode,
          alerts.route_id as route_id,
          alerts.alert_type as alert_type,
          alerts.header_text as header_text,
          alerts.alert_weight as alert_weight
        )
        order by
          case alerts.mode when 'subway' then 0 when 'bus' then 1 else 2 end,
          alerts.alert_weight desc,
          alerts.updated_at_ts desc nulls last
        limit 1
      )[offset(0)] as top_transit_alert
    from {{ ref('silver_mta_service_alerts') }} as alerts
    cross join mta_bounds as bounds
    where alerts.snapshot_date = bounds.max_mta_day
      and alerts.borough_hint != 'NYC'
    group by alerts.borough_hint
),

combined as (
    select
      coalesce(street.borough, crime.borough, transit.borough) as borough,
      coalesce(street.street_signal_count_24h, 0) as street_signal_count_24h,
      coalesce(street.street_signal_count_7d, 0) as street_signal_count_7d,
      coalesce(street.avg_spike_ratio, 0) as avg_spike_ratio,
      coalesce(street.open_ratio, 0) as open_ratio,
      coalesce(street.street_signal_score, 0) as street_signal_score,
      coalesce(crime.crime_count_90d, 0) as crime_count_90d,
      coalesce(crime.late_night_crime_count_90d, 0) as late_night_crime_count_90d,
      coalesce(crime.crime_pressure_score, 0) as crime_pressure_score,
      coalesce(crime.late_night_pressure_score, 0) as late_night_pressure_score,
      coalesce(transit.transit_chaos_score, 0) as transit_chaos_score,
      coalesce(transit.transit_alert_count, 0) as transit_alert_count,
      coalesce(transit.subway_alert_count, 0) as subway_alert_count,
      coalesce(transit.bus_alert_count, 0) as bus_alert_count,
      coalesce(transit.affected_route_count, 0) as affected_route_count,
      street.signal_options[
        safe_offset(
          mod(
            case coalesce(street.borough, crime.borough, transit.borough)
              when 'BROOKLYN' then 0
              when 'MANHATTAN' then 1
              when 'QUEENS' then 2
              when 'BRONX' then 3
              when 'STATEN ISLAND' then 4
              else 0
            end,
            coalesce(array_length(street.signal_options), 1)
          )
        )
      ] as top_signal,
      transit.top_transit_alert,
      (select max_signal_day from signal_bounds) as latest_signal_day,
      crime.latest_crime_day,
      transit.latest_mta_day
    from street_rollup as street
    full outer join crime_scored as crime using (borough)
    full outer join transit_rollup as transit
      on transit.borough = coalesce(street.borough, crime.borough)
),

with_raw as (
  select
    *,
    crime_pressure_score + late_night_pressure_score + street_signal_score + transit_chaos_score
      as raw_avoidability
  from combined
),

with_window as (
  select
    *,
    min(raw_avoidability) over () as min_raw,
    max(raw_avoidability) over () as max_raw
  from with_raw
),

scored as (
  select
    *,
    case
      when max_raw > min_raw then greatest(
        38,
        least(
          96,
          cast(round(38 + 58 * safe_divide(raw_avoidability - min_raw, max_raw - min_raw)) as int64)
        )
      )
      else greatest(52, least(72, 62 + mod(abs(farm_fingerprint(borough)), 9) - 4))
    end as avoidability_score
  from with_window
)

select
  borough,
  latest_signal_day,
  latest_crime_day,
  latest_mta_day,
  street_signal_count_24h,
  street_signal_count_7d,
  avg_spike_ratio,
  open_ratio,
  street_signal_score,
  crime_count_90d,
  late_night_crime_count_90d,
  crime_pressure_score,
  late_night_pressure_score,
  transit_chaos_score,
  transit_alert_count,
  subway_alert_count,
  bus_alert_count,
  affected_route_count,
  avoidability_score,
  case
    when avoidability_score >= 82 then 'I would avoid'
    when avoidability_score >= 62 then 'Questionable vibes'
    when avoidability_score >= 38 then 'Keep it moving'
    else 'Probably fine'
  end as avoidability_band,
  top_signal.category as top_signal_category,
  top_signal.latest_count as top_signal_count,
  top_signal.spike_ratio as top_signal_spike_ratio,
  top_signal.complaint_type as top_complaint_type,
  top_signal.descriptor as top_descriptor,
  top_signal.incident_zip as top_incident_zip,
  top_transit_alert.mode as top_transit_mode,
  top_transit_alert.route_id as top_transit_route,
  top_transit_alert.alert_type as top_transit_alert_type,
  top_transit_alert.header_text as top_transit_header,
  case top_signal.category
    when 'noise' then 'Avoid if you need peace and quiet'
    when 'parking' then 'Avoid if you brought a car'
    when 'lights_and_signals' then 'Avoid if you prefer well-lit exits'
    when 'grime' then 'Avoid if mystery sidewalk juice ruins your night'
    when 'street_condition' then 'Avoid if your shoes have survival instincts'
    when 'public_space' then 'Avoid if you are already overstimulated'
    else 'Avoid if you are already making questionable decisions'
  end as avoid_if,
  case mod(
    abs(farm_fingerprint(concat(borough, coalesce(cast(latest_signal_day as string), 'none')))),
    5
  )
    when 0 then 'CITY SIDE-EYE'
    when 1 then 'BLOCK ADVISORY'
    when 2 then 'BAD IDEA DESK'
    when 3 then 'KEEP MOVING'
    else 'FRIEND TEXT'
  end as stamp_label,
  case mod(
    abs(
      farm_fingerprint(concat('advice-', borough, coalesce(cast(latest_signal_day as string), 'none')))
    ),
    5
  )
    when 0 then concat(
      'The block is talking: ', coalesce(top_signal.category, 'street signals'),
      ' is the loudest receipt, backed by historical incident pressure.'
    )
    when 1 then concat(
      'Not a ban, just a raised eyebrow: ', cast(street_signal_count_24h as string),
      ' fresh street-signal calls and a ', cast(crime_pressure_score as string),
      '-point history tax.'
    )
    when 2 then concat(
      'If your plan requires calm exits, reconsider. Top signal: ',
      coalesce(top_transit_alert.alert_type, top_signal.complaint_type, 'city noise'), '.'
    )
    when 3 then concat(
      'The city is doing city things here: ', cast(street_signal_count_7d as string),
      ' signal calls in seven days and ', cast(transit_alert_count as string),
      ' transit alerts in the mix.'
    )
    else concat(
      'Proceed like you have a charged phone, a backup route, and no need to prove a point. ',
      coalesce(top_signal.category, 'vibes'), ' is carrying the warning.'
    )
  end as advice_copy,
  current_timestamp() as built_at
from scored
where borough is not null
