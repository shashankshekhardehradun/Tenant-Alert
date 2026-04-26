"""PLUTO ingestion helpers for building attributes."""

from __future__ import annotations

from pathlib import Path

import polars as pl


def normalize_pluto_csv(csv_path: Path, output_path: Path) -> int:
    """Convert raw PLUTO CSV to normalized parquet."""
    frame = pl.read_csv(csv_path, infer_schema_length=10_000)
    normalized = frame.rename({c: c.lower() for c in frame.columns})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_parquet(output_path)
    return normalized.height
