"""dbt assets exposed through Dagster."""

from __future__ import annotations

from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

DBT_PROJECT_DIR = Path("dbt")
DBT_PROFILES_DIR = Path("dbt")


@dbt_assets(manifest=DBT_PROJECT_DIR / "target" / "manifest.json")
def tenant_alert_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
