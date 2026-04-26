"""Dagster jobs for phase execution."""

from dagster import AssetSelection, define_asset_job

ingestion_job = define_asset_job("ingestion_job", selection=AssetSelection.groups("ingestion"))
transform_job = define_asset_job("transform_job", selection=AssetSelection.groups("dbt"))
