{{ config(materialized='table', cluster_by=["borough", "nta_code"]) }}

with tract_demographics as (
  select
    eq.nta_code,
    eq.nta_name,
    eq.borough,
    acs.acs_year,
    acs.tract_geoid,
    acs.total_population,
    acs.median_household_income,
    acs.per_capita_income,
    acs.median_gross_rent,
    acs.poverty_count,
    acs.white_alone,
    acs.black_alone,
    acs.asian_alone,
    acs.hispanic_or_latino,
    acs.owner_occupied_units,
    acs.renter_occupied_units,
    acs.education_pop_25_plus,
    acs.bachelors_degree,
    acs.masters_degree,
    acs.professional_degree,
    acs.doctorate_degree
  from {{ ref('silver_census_acs_tract') }} as acs
  join {{ ref('silver_tract_nta_equivalency') }} as eq
    on acs.tract_geoid = eq.tract_geoid
),

nta_rollup as (
  select
    nta_code,
    any_value(nta_name) as nta_name,
    any_value(borough) as borough,
    max(acs_year) as acs_year,
    count(distinct tract_geoid) as tract_count,
    sum(total_population) as total_population,
    sum(poverty_count) as poverty_count,
    sum(white_alone) as white_alone,
    sum(black_alone) as black_alone,
    sum(asian_alone) as asian_alone,
    sum(hispanic_or_latino) as hispanic_or_latino,
    sum(owner_occupied_units) as owner_occupied_units,
    sum(renter_occupied_units) as renter_occupied_units,
    sum(education_pop_25_plus) as education_pop_25_plus,
    sum(bachelors_degree + masters_degree + professional_degree + doctorate_degree)
      as bachelors_or_higher_count,
    safe_divide(
      sum(median_household_income * nullif(total_population, 0)),
      sum(nullif(total_population, 0))
    ) as approx_median_household_income,
    safe_divide(
      sum(per_capita_income * nullif(total_population, 0)),
      sum(nullif(total_population, 0))
    ) as approx_per_capita_income,
    safe_divide(
      sum(median_gross_rent * nullif(total_population, 0)),
      sum(nullif(total_population, 0))
    ) as approx_median_gross_rent
  from tract_demographics
  group by nta_code
)

select
  *,
  safe_divide(poverty_count, total_population) as poverty_rate,
  safe_divide(white_alone, total_population) as white_alone_share,
  safe_divide(black_alone, total_population) as black_alone_share,
  safe_divide(asian_alone, total_population) as asian_alone_share,
  safe_divide(hispanic_or_latino, total_population) as hispanic_or_latino_share,
  safe_divide(renter_occupied_units, owner_occupied_units + renter_occupied_units) as renter_share,
  safe_divide(bachelors_or_higher_count, education_pop_25_plus) as bachelors_or_higher_share
from nta_rollup
