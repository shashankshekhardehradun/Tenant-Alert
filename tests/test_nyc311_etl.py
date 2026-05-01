import datetime as dt
from pathlib import Path
from typing import Any

import pytest
from ingestion.nyc311 import jobs


class FakeSocrataClient:
    def __init__(self, config: object) -> None:
        self.config = config

    def iter_pages(
        self,
        dataset_id: str,
        *,
        where: str | None = None,
        order: str = "created_date asc",
        page_size: int = 50_000,
        max_pages: int | None = None,
    ) -> list[list[dict[str, Any]]]:
        return [
            [
                {
                    "unique_key": "1",
                    "created_date": "2024-01-01T01:00:00.000",
                    "complaint_type": "HEAT/HOT WATER",
                    "borough": "BROOKLYN",
                }
            ]
        ]


def test_date_range_where() -> None:
    where = jobs._date_range_where(dt.date(2024, 1, 1), dt.date(2024, 1, 2))
    assert where == "created_date >= '2024-01-01T00:00:00' AND created_date < '2024-01-02T00:00:00'"


def test_run_311_partition_etl_writes_parquet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(jobs, "SocrataClient", FakeSocrataClient)

    result = jobs.run_311_partition_etl(
        dt.date(2024, 1, 1),
        local_data_dir=tmp_path,
        upload_to_gcs=False,
        load_to_bigquery=False,
    )

    assert result.row_count == 1
    assert result.local_path.exists()
    assert result.local_path.name == "raw_311_complaints.parquet"
