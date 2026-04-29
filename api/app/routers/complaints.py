"""Complaint trend endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from google.cloud import bigquery

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


@router.get("/trend")
def complaint_trend(
    borough: Annotated[str, Query(...)],
    start_date: Annotated[date, Query(...)],
    end_date: Annotated[date, Query(...)],
) -> dict[str, object]:
    sql = f"""
        select complaint_created_date, complaint_type, count(*) as complaint_count
        from `{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_fct_complaints`
        where borough = @borough
          and complaint_created_date between @start_date and @end_date
        group by complaint_created_date, complaint_type
        order by complaint_created_date asc
    """
    rows = service.query(
        sql,
        params=[
            bigquery.ScalarQueryParameter("borough", "STRING", borough.upper()),
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date.isoformat()),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date.isoformat()),
        ],
    )
    return {"borough": borough, "items": rows}
