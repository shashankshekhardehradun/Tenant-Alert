{{ config(materialized='view') }}

select
  geoid,
  countyfips,
  borocode,
  boroname,
  boroct2020,
  ct2020,
  ctlabel,
  ntacode,
  ntatype,
  ntaname,
  ntaabbrev,
  cdtacode,
  cdtatype,
  cdtaname
from {{ source('raw', 'raw_tract_nta_equivalency') }}
