"""ACS 5-year Census API ingestion for NYC tract-level demographics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import polars as pl
from google.cloud import bigquery

from ingestion.common.bigquery import load_parquet_to_table
from ingestion.common.storage import upload_file_to_gcs
from tenant_alert.config import settings

NYC_COUNTIES = {
    "005": "Bronx",
    "047": "Brooklyn",
    "061": "Manhattan",
    "081": "Queens",
    "085": "Staten Island",
}

ACS_VARIABLES = {
    "B01003_001E": "total_population",
    "B19013_001E": "median_household_income",
    "B19013_001M": "median_household_income_moe",
    "B19301_001E": "per_capita_income",
    "B25064_001E": "median_gross_rent",
    "B17001_002E": "poverty_count",
    "B02001_002E": "white_alone",
    "B02001_003E": "black_alone",
    "B02001_005E": "asian_alone",
    "B03003_003E": "hispanic_or_latino",
    "B25003_002E": "owner_occupied_units",
    "B25003_003E": "renter_occupied_units",
    "B15003_001E": "education_pop_25_plus",
    "B15003_022E": "bachelors_degree",
    "B15003_023E": "masters_degree",
    "B15003_024E": "professional_degree",
    "B15003_025E": "doctorate_degree",
}

RAW_CENSUS_ACS_TRACT_TABLE = "raw_census_acs_tract"
ACS_SCHEMA = [
    bigquery.SchemaField("acs_year", "INTEGER"),
    bigquery.SchemaField("state_fips", "STRING"),
    bigquery.SchemaField("county_fips", "STRING"),
    bigquery.SchemaField("county_name", "STRING"),
    bigquery.SchemaField("tract", "STRING"),
    bigquery.SchemaField("geoid", "STRING"),
    bigquery.SchemaField("name", "STRING"),
    *[bigquery.SchemaField(column_name, "FLOAT") for column_name in ACS_VARIABLES.values()],
]


@dataclass(frozen=True)
class CensusAcsResult:
    row_count: int
    local_path: Path
    gcs_uri: str | None = None
    bigquery_table: str | None = None


def _fetch_county_tracts(
    year: int,
    county_fips: str,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    variables = ["NAME", *ACS_VARIABLES.keys()]
    params = {
        "get": ",".join(variables),
        "for": "tract:*",
        "in": f"state:36 county:{county_fips}",
    }
    if api_key:
        params["key"] = api_key

    url = f"https://api.census.gov/data/{year}/acs/acs5"
    response = httpx.get(url, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    header = payload[0]
    rows = payload[1:]

    records: list[dict[str, Any]] = []
    for row in rows:
        raw = dict(zip(header, row, strict=True))
        tract = str(raw["tract"])
        geoid = f"36{county_fips}{tract}"
        record: dict[str, Any] = {
            "acs_year": year,
            "state_fips": "36",
            "county_fips": county_fips,
            "county_name": NYC_COUNTIES[county_fips],
            "tract": tract,
            "geoid": geoid,
            "name": raw["NAME"],
        }
        for variable, column_name in ACS_VARIABLES.items():
            record[column_name] = raw.get(variable)
        records.append(record)
    return records


def _normalize_acs_frame(frame: pl.DataFrame) -> pl.DataFrame:
    numeric_columns = list(ACS_VARIABLES.values())
    return frame.select(
        pl.col("acs_year").cast(pl.Int64),
        pl.col("state_fips").cast(pl.Utf8),
        pl.col("county_fips").cast(pl.Utf8),
        pl.col("county_name").cast(pl.Utf8),
        pl.col("tract").cast(pl.Utf8),
        pl.col("geoid").cast(pl.Utf8),
        pl.col("name").cast(pl.Utf8),
        *[pl.col(column).cast(pl.Float64, strict=False) for column in numeric_columns],
    )


def run_census_acs_tract_etl(
    year: int,
    *,
    api_key: str | None = None,
    local_data_dir: Path | None = None,
    upload_to_gcs: bool = False,
    load_to_bigquery: bool = False,
) -> CensusAcsResult:
    """Pull tract-level ACS 5-year data for NYC, land parquet, and optionally load bronze."""
    local_root = local_data_dir or Path(settings.local_data_dir)
    output_path = (
        local_root
        / "raw"
        / "census_acs"
        / f"year={year}"
        / "geography=tract"
        / "acs_tract.parquet"
    )

    records: list[dict[str, Any]] = []
    for county_fips in NYC_COUNTIES:
        records.extend(_fetch_county_tracts(year, county_fips, api_key=api_key))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = _normalize_acs_frame(pl.DataFrame(records, strict=False))
    frame.write_parquet(output_path)

    gcs_uri: str | None = None
    bigquery_table: str | None = None
    if upload_to_gcs:
        if not settings.raw_bucket_name:
            raise ValueError("upload_to_gcs=True requires GCS_RAW_BUCKET or GCP_PROJECT_ID")
        blob_name = f"census_acs/year={year}/geography=tract/acs_tract.parquet"
        gcs_uri = upload_file_to_gcs(output_path, settings.raw_bucket_name, blob_name)

    if load_to_bigquery:
        if not settings.gcp_project_id:
            raise ValueError("load_to_bigquery=True requires GCP_PROJECT_ID")
        if not gcs_uri:
            raise ValueError("load_to_bigquery=True requires upload_to_gcs=True")
        bigquery_table = load_parquet_to_table(
            gcs_uri,
            project_id=settings.gcp_project_id,
            dataset_id=settings.bq_dataset_bronze,
            table_id=RAW_CENSUS_ACS_TRACT_TABLE,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=ACS_SCHEMA,
            clustering_fields=["county_fips", "geoid"],
        )

    return CensusAcsResult(
        row_count=frame.height,
        local_path=output_path,
        gcs_uri=gcs_uri,
        bigquery_table=bigquery_table,
    )
