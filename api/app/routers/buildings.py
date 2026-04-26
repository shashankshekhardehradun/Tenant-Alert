"""Building-level analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from google.cloud import bigquery

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


@router.get("/lookup")
def building_lookup(address: str = Query(..., min_length=3)) -> dict[str, object]:
    sql = f"""
        select incident_address, borough, complaint_type, count(*) as complaint_count
        from `{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_fct_complaints`
        where lower(incident_address) = lower(@address)
        group by incident_address, borough, complaint_type
        order by complaint_count desc
        limit 50
    """
    rows = service.query(sql, params=[bigquery.ScalarQueryParameter("address", "STRING", address)])
    return {"address": address, "items": rows}


@router.get("/predictions")
def building_predictions(address: str = Query(..., min_length=3)) -> dict[str, object]:
    sql = f"""
        select borough, complaint_type, avg(predicted_resolution_hours) as predicted_resolution_hours
        from `{settings.gcp_project_id}.{settings.bq_dataset_ml}.predictions_resolution_time`
        where lower(unique_key) is not null
        group by borough, complaint_type
        order by predicted_resolution_hours asc
        limit 25
    """
    rows = service.query(sql)
    return {"address": address, "predictions": rows}
