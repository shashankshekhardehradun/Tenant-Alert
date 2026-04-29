{{ config(materialized='view') }}

select
  acs_year,
  state_fips,
  county_fips,
  county_name,
  tract,
  geoid,
  name,
  total_population,
  median_household_income,
  median_household_income_moe,
  per_capita_income,
  median_gross_rent,
  poverty_count,
  white_alone,
  black_alone,
  asian_alone,
  hispanic_or_latino,
  owner_occupied_units,
  renter_occupied_units,
  education_pop_25_plus,
  bachelors_degree,
  masters_degree,
  professional_degree,
  doctorate_degree
from {{ source('raw', 'raw_census_acs_tract') }}
