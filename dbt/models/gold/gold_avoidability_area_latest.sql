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
      least(55, round(sum(category_score))) as street_signal_score,
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
      )[offset(0)] as top_signal
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
      round(35 * safe_divide(crime_count_90d, max(crime_count_90d) over ())) as crime_pressure_score,
      round(
        10 * safe_divide(late_night_crime_count_90d, nullif(crime_count_90d, 0))
      ) as late_night_pressure_score
    from crime_rollup
),

combined as (
    select
      coalesce(street.borough, crime.borough) as borough,
      coalesce(street.street_signal_count_24h, 0) as street_signal_count_24h,
      coalesce(street.street_signal_count_7d, 0) as street_signal_count_7d,
      coalesce(street.avg_spike_ratio, 0) as avg_spike_ratio,
      coalesce(street.open_ratio, 0) as open_ratio,
      coalesce(street.street_signal_score, 0) as street_signal_score,
      coalesce(crime.crime_count_90d, 0) as crime_count_90d,
      coalesce(crime.late_night_crime_count_90d, 0) as late_night_crime_count_90d,
      coalesce(crime.crime_pressure_score, 0) as crime_pressure_score,
      coalesce(crime.late_night_pressure_score, 0) as late_night_pressure_score,
      0 as transit_chaos_score,
      street.top_signal,
      (select max_signal_day from signal_bounds) as latest_signal_day,
      crime.latest_crime_day
    from street_rollup as street
    full outer join crime_scored as crime using (borough)
)

select
  borough,
  latest_signal_day,
  latest_crime_day,
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
  least(
    99,
    cast(
      round(
        crime_pressure_score
        + late_night_pressure_score
        + street_signal_score
        + transit_chaos_score
      ) as int64
    )
  ) as avoidability_score,
  case
    when least(99, crime_pressure_score + late_night_pressure_score + street_signal_score) >= 82
      then 'I would avoid'
    when least(99, crime_pressure_score + late_night_pressure_score + street_signal_score) >= 62
      then 'Questionable vibes'
    when least(99, crime_pressure_score + late_night_pressure_score + street_signal_score) >= 38
      then 'Keep it moving'
    else 'Probably fine'
  end as avoidability_band,
  top_signal.category as top_signal_category,
  top_signal.latest_count as top_signal_count,
  top_signal.spike_ratio as top_signal_spike_ratio,
  top_signal.complaint_type as top_complaint_type,
  top_signal.descriptor as top_descriptor,
  top_signal.incident_zip as top_incident_zip,
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
      coalesce(top_signal.complaint_type, 'city noise'), '.'
    )
    when 3 then concat(
      'The city is doing city things here: ', cast(street_signal_count_7d as string),
      ' signal calls in seven days, plus late-night pressure.'
    )
    else concat(
      'Proceed like you have a charged phone and no need to prove a point. ',
      coalesce(top_signal.category, 'vibes'), ' is carrying the warning.'
    )
  end as advice_copy,
  current_timestamp() as built_at
from combined
where borough is not null
