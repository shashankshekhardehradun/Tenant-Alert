"""Comparison endpoints for borough/building views."""

from __future__ import annotations

from fastapi import APIRouter, Query
from google.cloud import bigquery

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


@router.get("/boroughs")
def compare_boroughs(left: str = Query(...), right: str = Query(...)) -> dict[str, object]:
    sql = f"""
        select borough, count(*) as complaints, avg(resolution_hours) as avg_resolution_hours
        from `{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_fct_complaints`
        where borough in (@left, @right)
        group by borough
    """
    rows = service.query(
        sql,
        params=[
            bigquery.ScalarQueryParameter("left", "STRING", left.upper()),
            bigquery.ScalarQueryParameter("right", "STRING", right.upper()),
        ],
    )
    return {"items": rows}
