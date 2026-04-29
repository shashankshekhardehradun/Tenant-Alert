{{ config(materialized='table', partition_by={"field": "complaint_date", "data_type": "date"}, cluster_by=["borough", "law_category", "offense_description"]) }}

with typed as (
  select
    cast(cmplnt_num as string) as complaint_id,
    cast(source_dataset as string) as source_dataset,
    cast(cmplnt_fr_dt as timestamp) as complaint_start_ts,
    cast(cmplnt_to_dt as timestamp) as complaint_end_ts,
    cast(rpt_dt as timestamp) as reported_ts,
    safe_cast(addr_pct_cd as int64) as precinct,
    safe_cast(ky_cd as int64) as offense_code,
    nullif(upper(trim(ofns_desc)), '') as offense_description,
    safe_cast(pd_cd as int64) as internal_classification_code,
    nullif(upper(trim(pd_desc)), '') as internal_classification_description,
    nullif(upper(trim(crm_atpt_cptd_cd)), '') as attempt_completed,
    nullif(upper(trim(law_cat_cd)), '') as law_category,
    nullif(upper(trim(boro_nm)), '') as borough,
    nullif(upper(trim(loc_of_occur_desc)), '') as occurrence_location,
    nullif(upper(trim(prem_typ_desc)), '') as premise_type,
    nullif(upper(trim(juris_desc)), '') as jurisdiction,
    nullif(upper(trim(parks_nm)), '') as park_name,
    nullif(upper(trim(hadevelopt)), '') as housing_development,
    nullif(upper(trim(housing_psa)), '') as housing_psa,
    safe_cast(x_coord_cd as float64) as x_coord,
    safe_cast(y_coord_cd as float64) as y_coord,
    safe_cast(latitude as float64) as latitude,
    safe_cast(longitude as float64) as longitude,
    nullif(upper(trim(patrol_boro)), '') as patrol_borough,
    nullif(upper(trim(station_name)), '') as station_name,
    nullif(upper(trim(transit_district)), '') as transit_district
  from {{ ref('bronze_raw_nypd_complaints') }}
),

located as (
  select
    *,
    date(complaint_start_ts) as complaint_date,
    extract(year from complaint_start_ts) as complaint_year,
    extract(month from complaint_start_ts) as complaint_month,
    extract(dayofweek from complaint_start_ts) as complaint_day_of_week,
    extract(hour from complaint_start_ts) as complaint_hour,
    case
      when latitude between 40.45 and 40.95
       and longitude between -74.30 and -73.65
        then true
      else false
    end as has_valid_nyc_coordinates
  from typed
)

select *
from located
where complaint_start_ts is not null
  and borough is not null
  and has_valid_nyc_coordinates
qualify row_number() over (
  partition by complaint_id
  order by reported_ts desc, complaint_start_ts desc
) = 1
