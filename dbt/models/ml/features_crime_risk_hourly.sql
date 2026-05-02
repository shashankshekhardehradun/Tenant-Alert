{{ config(materialized='table', partition_by={"field": "feature_date", "data_type": "date"}, cluster_by=["borough", "hour"]) }}

with bounds as (
  select
    min(complaint_date) as min_day,
    max(complaint_date) as max_day
  from {{ ref('gold_fct_crime_events') }}
),

dates as (
  select feature_date
  from bounds,
  unnest(generate_date_array(min_day, max_day)) as feature_date
),

boroughs as (
  select distinct borough
  from {{ ref('gold_fct_crime_events') }}
  where borough is not null
    and borough not in ('(NULL)', 'NULL', 'N/A', 'UNKNOWN')
),

hours as (
  select hour
  from unnest(generate_array(0, 23)) as hour
),

grid as (
  select
    dates.feature_date,
    boroughs.borough,
    hours.hour
  from dates
  cross join boroughs
  cross join hours
),

crime_hourly as (
  select
    complaint_date as feature_date,
    borough,
    complaint_hour as hour,
    count(*) as incident_count,
    sum(case law_category when 'FELONY' then 3 when 'MISDEMEANOR' then 2 else 1 end)
      as severity_weighted_incident_score,
    countif(law_category = 'FELONY') as felony_count,
    countif(law_category = 'MISDEMEANOR') as misdemeanor_count,
    countif(law_category = 'VIOLATION') as violation_count
  from {{ ref('gold_fct_crime_events') }}
  where complaint_hour is not null
    and borough is not null
    and borough not in ('(NULL)', 'NULL', 'N/A', 'UNKNOWN')
  group by 1, 2, 3
),

daily_borough as (
  select
    complaint_date,
    borough,
    count(*) as daily_incidents,
    sum(case law_category when 'FELONY' then 3 when 'MISDEMEANOR' then 2 else 1 end)
      as daily_severity_score
  from {{ ref('gold_fct_crime_events') }}
  where borough is not null
    and borough not in ('(NULL)', 'NULL', 'N/A', 'UNKNOWN')
  group by 1, 2
),

history as (
  select
    grid.feature_date,
    grid.borough,
    grid.hour,
    coalesce(sum(if(
      daily_borough.complaint_date between date_sub(grid.feature_date, interval 7 day)
        and date_sub(grid.feature_date, interval 1 day),
      daily_borough.daily_incidents,
      0
    )), 0) as recent_7d_incidents,
    coalesce(sum(if(
      daily_borough.complaint_date between date_sub(grid.feature_date, interval 14 day)
        and date_sub(grid.feature_date, interval 1 day),
      daily_borough.daily_incidents,
      0
    )), 0) as recent_14d_incidents,
    coalesce(sum(if(
      daily_borough.complaint_date between date_sub(grid.feature_date, interval 30 day)
        and date_sub(grid.feature_date, interval 1 day),
      daily_borough.daily_incidents,
      0
    )), 0) as recent_30d_incidents,
    coalesce(sum(if(
      daily_borough.complaint_date between date_sub(grid.feature_date, interval 14 day)
        and date_sub(grid.feature_date, interval 1 day),
      daily_borough.daily_severity_score,
      0
    )), 0) as recent_14d_severity_score
  from grid
  left join daily_borough
    on grid.borough = daily_borough.borough
   and daily_borough.complaint_date between date_sub(grid.feature_date, interval 30 day)
     and date_sub(grid.feature_date, interval 1 day)
  group by 1, 2, 3
),

demographics as (
  select
    upper(borough) as borough,
    sum(total_population) as total_population,
    safe_divide(sum(poverty_count), nullif(sum(total_population), 0)) as poverty_rate,
    safe_divide(
      sum(renter_occupied_units),
      nullif(sum(renter_occupied_units + owner_occupied_units), 0)
    ) as renter_share,
    safe_divide(
      sum(bachelors_or_higher_count),
      nullif(sum(education_pop_25_plus), 0)
    ) as bachelors_or_higher_share,
    safe_divide(
      sum(approx_median_household_income * total_population),
      nullif(sum(total_population), 0)
    ) as approx_median_household_income,
    safe_divide(
      sum(approx_median_gross_rent * renter_occupied_units),
      nullif(sum(renter_occupied_units), 0)
    ) as approx_median_gross_rent
  from {{ ref('gold_agg_demographics_by_nta') }}
  group by 1
)

select
  grid.feature_date,
  grid.borough,
  grid.hour,
  extract(dayofweek from grid.feature_date) as day_of_week,
  extract(month from grid.feature_date) as month,
  extract(dayofweek from grid.feature_date) in (1, 7) as is_weekend,
  coalesce(crime_hourly.incident_count, 0) as incident_count,
  coalesce(crime_hourly.severity_weighted_incident_score, 0) as crime_pressure_score,
  coalesce(crime_hourly.felony_count, 0) as felony_count,
  coalesce(crime_hourly.misdemeanor_count, 0) as misdemeanor_count,
  coalesce(crime_hourly.violation_count, 0) as violation_count,
  safe_divide(coalesce(crime_hourly.felony_count, 0), nullif(coalesce(crime_hourly.incident_count, 0), 0))
    as felony_share,
  safe_divide(coalesce(crime_hourly.misdemeanor_count, 0), nullif(coalesce(crime_hourly.incident_count, 0), 0))
    as misdemeanor_share,
  history.recent_7d_incidents,
  history.recent_14d_incidents,
  history.recent_30d_incidents,
  history.recent_14d_severity_score,
  demographics.total_population,
  demographics.poverty_rate,
  demographics.renter_share,
  demographics.bachelors_or_higher_share,
  demographics.approx_median_household_income,
  demographics.approx_median_gross_rent
from grid
left join crime_hourly
  on grid.feature_date = crime_hourly.feature_date
 and grid.borough = crime_hourly.borough
 and grid.hour = crime_hourly.hour
left join history
  on grid.feature_date = history.feature_date
 and grid.borough = history.borough
 and grid.hour = history.hour
left join demographics
  on grid.borough = demographics.borough
where grid.feature_date >= date_add((select min_day from bounds), interval 30 day)
