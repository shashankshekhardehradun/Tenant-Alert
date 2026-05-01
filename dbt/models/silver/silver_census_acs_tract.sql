{{ config(materialized='table', cluster_by=["county_fips", "tract_geoid"]) }}

select
  cast(acs_year as int64) as acs_year,
  cast(state_fips as string) as state_fips,
  lpad(cast(county_fips as string), 3, '0') as county_fips,
  county_name,
  lpad(cast(tract as string), 6, '0') as tract,
  cast(geoid as string) as tract_geoid,
  name,
  cast(total_population as float64) as total_population,
  case
    when cast(median_household_income as float64) < 0 then null
    else cast(median_household_income as float64)
  end as median_household_income,
  case
    when cast(median_household_income_moe as float64) < 0 then null
    else cast(median_household_income_moe as float64)
  end as median_household_income_moe,
  case
    when cast(per_capita_income as float64) < 0 then null
    else cast(per_capita_income as float64)
  end as per_capita_income,
  case
    when cast(median_gross_rent as float64) < 0 then null
    else cast(median_gross_rent as float64)
  end as median_gross_rent,
  cast(poverty_count as float64) as poverty_count,
  cast(white_alone as float64) as white_alone,
  cast(black_alone as float64) as black_alone,
  cast(asian_alone as float64) as asian_alone,
  cast(hispanic_or_latino as float64) as hispanic_or_latino,
  cast(owner_occupied_units as float64) as owner_occupied_units,
  cast(renter_occupied_units as float64) as renter_occupied_units,
  cast(education_pop_25_plus as float64) as education_pop_25_plus,
  cast(bachelors_degree as float64) as bachelors_degree,
  cast(masters_degree as float64) as masters_degree,
  cast(professional_degree as float64) as professional_degree,
  cast(doctorate_degree as float64) as doctorate_degree
from {{ ref('bronze_raw_census_acs_tract') }}
