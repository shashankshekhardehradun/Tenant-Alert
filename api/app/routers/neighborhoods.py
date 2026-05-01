"""Neighborhood analytics endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from google.cloud import bigquery

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


@router.get("/")
def list_neighborhoods(limit: Annotated[int, Query(ge=1, le=100)] = 20) -> dict[str, object]:
    sql = f"""
        select borough, count(*) as complaints
        from `{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_fct_complaints`
        group by borough
        order by complaints desc
        limit @limit
    """
    rows = service.query(sql, params=[bigquery.ScalarQueryParameter("limit", "INT64", limit)])
    return {"items": rows}
