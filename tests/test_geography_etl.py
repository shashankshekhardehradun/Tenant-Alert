import polars as pl
from ingestion.geography.tract_nta import _normalize_tract_nta_frame


def test_normalize_tract_nta_frame_fills_missing_columns() -> None:
    frame = pl.DataFrame(
        [
            {
                "geoid": "36005001901",
                "countyfips": "005",
                "borocode": "2",
                "boroname": "Bronx",
                "ntacode": "BX0101",
                "ntaname": "Mott Haven-Port Morris",
            }
        ],
        strict=False,
    )

    normalized = _normalize_tract_nta_frame(frame)

    assert normalized["geoid"][0] == "36005001901"
    assert normalized["ntacode"][0] == "BX0101"
    assert "cdtaname" in normalized.columns
