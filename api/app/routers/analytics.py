"""Aggregate analytics endpoints backed by BigQuery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


def _require_project() -> str:
    if not settings.gcp_project_id:
        raise HTTPException(status_code=500, detail="GCP_PROJECT_ID is not configured")
    return settings.gcp_project_id


@dataclass(frozen=True)
class AnalyticsModel:
    name: str
    table: str
    day_expr: str


def _gold_model() -> AnalyticsModel:
    project = _require_project()
    table = f"`{project}.{settings.bq_dataset_gold}.gold_fct_complaints`"
    return AnalyticsModel(name="gold", table=table, day_expr="complaint_created_date")


def _bronze_model() -> AnalyticsModel:
    project = _require_project()
    table = f"`{project}.{settings.bq_dataset_bronze}.raw_311_complaints`"
    created = "safe_cast(created_date as timestamp)"
    return AnalyticsModel(name="bronze", table=table, day_expr=f"date({created})")


def _pick_models() -> list[AnalyticsModel]:
    if settings.analytics_use_gold:
        if settings.analytics_fallback_bronze:
            return [_gold_model(), _bronze_model()]
        return [_gold_model()]
    return [_bronze_model()]


def _overview_for_model(
    model: AnalyticsModel,
    params: list[bigquery.ScalarQueryParameter],
) -> dict[str, object]:
    day = model.day_expr
    table = model.table

    borough_sql = f"""
        select borough, count(*) as complaint_count
        from {table}
        where {day} between @start_date and @end_date
          and borough is not null
        group by borough
        order by complaint_count desc
    """

    trend_sql = f"""
        select {day} as day, count(*) as complaint_count
        from {table}
        where {day} between @start_date and @end_date
        group by day
        order by day asc
    """

    top_types_sql = f"""
        select complaint_type, count(*) as complaint_count
        from {table}
        where {day} between @start_date and @end_date
          and complaint_type is not null
        group by complaint_type
        order by complaint_count desc
        limit @top_n
    """

    range_sql = f"""
        select count(*) as row_count
        from {table}
        where {day} between @start_date and @end_date
    """

    by_borough = service.query(borough_sql, params=params[:2])
    daily_trend = service.query(trend_sql, params=params[:2])
    top_types = service.query(top_types_sql, params=params)
    range_rows = service.query(range_sql, params=params[:2])
    row_count = int(range_rows[0]["row_count"]) if range_rows else 0

    return {
        "source": model.name,
        "row_count": row_count,
        "by_borough": by_borough,
        "daily_trend": daily_trend,
        "top_complaint_types": top_types,
    }


def _data_range_for_model(model: AnalyticsModel) -> dict[str, object]:
    day = model.day_expr
    table = model.table
    sql = f"""
        select
          min({day}) as min_day,
          max({day}) as max_day,
          count(*) as row_count
        from {table}
    """
    rows = service.query_safe(sql)
    if not rows:
        return {"source": model.name, "min_day": None, "max_day": None, "row_count": 0}
    row = rows[0]
    return {"source": model.name, **row}


@router.get("/data-range")
def analytics_data_range() -> dict[str, object]:
    """Return min/max day for the preferred mart (gold), falling back to bronze if needed."""
    for model in _pick_models():
        payload = _data_range_for_model(model)
        if int(payload.get("row_count") or 0) > 0:
            return payload
    return {"source": "none", "min_day": None, "max_day": None, "row_count": 0}


@router.get("/overview")
def analytics_overview(
    start_date: Annotated[date, Query(..., description="Inclusive start date (UTC day bucket).")],
    end_date: Annotated[date, Query(..., description="Inclusive end date (UTC day bucket).")],
    top_n: Annotated[int, Query(ge=1, le=25)] = 8,
) -> dict[str, object]:
    """City-wide aggregates for dashboard charts (prefer gold marts, fallback to bronze)."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    params = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date.isoformat()),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date.isoformat()),
        bigquery.ScalarQueryParameter("top_n", "INT64", top_n),
    ]

    last_error: str | None = None
    for model in _pick_models():
        try:
            body = _overview_for_model(model, params=params)
            if (
                int(body.get("row_count") or 0) == 0
                and model.name == "gold"
                and settings.analytics_fallback_bronze
            ):
                continue
            return {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                **body,
            }
        except gcp_exceptions.GoogleAPIError as exc:
            last_error = str(exc)
            continue

    raise HTTPException(
        status_code=503,
        detail=f"Could not read analytics from BigQuery. Last error: {last_error}",
    )


@router.get("/demographics/nta")
def nta_demographics(
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
) -> dict[str, object]:
    """Return NTA-level demographic feature rows for charts and future map layers."""
    project = _require_project()
    table = f"`{project}.{settings.bq_dataset_gold}.gold_agg_demographics_by_nta`"
    sql = f"""
        select
          nta_code,
          nta_name,
          borough,
          acs_year,
          tract_count,
          total_population,
          approx_median_household_income,
          approx_per_capita_income,
          approx_median_gross_rent,
          poverty_rate,
          renter_share,
          bachelors_or_higher_share,
          white_alone_share,
          black_alone_share,
          asian_alone_share,
          hispanic_or_latino_share
        from {table}
        order by borough, nta_name
        limit @limit
    """
    rows = service.query(
        sql,
        params=[bigquery.ScalarQueryParameter("limit", "INT64", limit)],
    )
    return {"source": "gold_agg_demographics_by_nta", "items": rows}
