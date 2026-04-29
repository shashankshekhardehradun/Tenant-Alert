from pathlib import Path

import polars as pl
from ingestion.census.acs import _normalize_acs_frame


def test_normalize_acs_frame_casts_numeric_columns(tmp_path: Path) -> None:
    frame = pl.DataFrame(
        [
            {
                "acs_year": "2023",
                "state_fips": "36",
                "county_fips": "047",
                "county_name": "Brooklyn",
                "tract": "000100",
                "geoid": "36047000100",
                "name": "Census Tract 1, Kings County, New York",
                "total_population": "1000",
                "median_household_income": "75000",
                "median_household_income_moe": "1000",
                "per_capita_income": "42000",
                "median_gross_rent": "2100",
                "poverty_count": "120",
                "white_alone": "300",
                "black_alone": "250",
                "asian_alone": "200",
                "hispanic_or_latino": "180",
                "owner_occupied_units": "100",
                "renter_occupied_units": "350",
                "education_pop_25_plus": "700",
                "bachelors_degree": "120",
                "masters_degree": "80",
                "professional_degree": "20",
                "doctorate_degree": "10",
            }
        ],
        strict=False,
    )

    normalized = _normalize_acs_frame(frame)
    output_path = tmp_path / "acs.parquet"
    normalized.write_parquet(output_path)

    assert normalized["acs_year"][0] == 2023
    assert normalized["total_population"][0] == 1000.0
    assert output_path.exists()
