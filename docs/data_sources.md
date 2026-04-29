# Data Sources

## NYC 311

- Source: NYC Open Data Socrata dataset `erm2-nwe9`
- Refresh: daily partitioned ingestion
- Grain: service request / complaint

## Census ACS 5-Year

- Source: U.S. Census Data API
- Endpoint shape: `https://api.census.gov/data/{year}/acs/acs5`
- Refresh: annual when the Census Bureau publishes a new ACS 5-year vintage
- Grain: census tract
- Auth: `CENSUS_API_KEY`

Current variables include population, median household income, median gross rent, poverty, race/ethnicity, tenure, and education.

## NYC Tract-to-NTA Equivalency

- Source: NYC Open Data Socrata dataset `hm78-6dwm`
- Refresh: when NYC Planning publishes a new geography vintage
- Grain: census tract to NTA/CDTA mapping
- Auth: existing `SODA_APP_TOKEN`

## Modeling Notes

- Median household income and median rent are medians. The current NTA model uses population-weighted tract values as an approximation for dashboarding.
- For production-grade NTA medians, add Census distribution tables and interpolate medians from binned counts.
- These feature layers are intended to support future map popups and ML features.
