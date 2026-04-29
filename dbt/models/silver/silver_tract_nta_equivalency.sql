{{ config(materialized='table', cluster_by=["nta_code", "tract_geoid"]) }}

select
  cast(geoid as string) as tract_geoid,
  lpad(cast(countyfips as string), 3, '0') as county_fips,
  cast(borocode as string) as borough_code,
  cast(boroname as string) as borough,
  cast(boroct2020 as string) as boroct2020,
  lpad(cast(ct2020 as string), 6, '0') as tract_2020,
  cast(ctlabel as string) as tract_label,
  cast(ntacode as string) as nta_code,
  cast(ntatype as string) as nta_type,
  cast(ntaname as string) as nta_name,
  cast(ntaabbrev as string) as nta_abbrev,
  cast(cdtacode as string) as cdta_code,
  cast(cdtatype as string) as cdta_type,
  cast(cdtaname as string) as cdta_name
from {{ ref('bronze_raw_tract_nta_equivalency') }}
