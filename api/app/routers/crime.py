"""Crime analytics endpoints backed by BigQuery gold marts."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


def _crime_table() -> str:
    if not settings.gcp_project_id:
        raise HTTPException(status_code=500, detail="GCP_PROJECT_ID is not configured")
    return f"`{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_fct_crime_events`"


@router.get("/data-range")
def crime_data_range() -> dict[str, object]:
    sql = f"""
        select
          min(complaint_date) as min_day,
          max(complaint_date) as max_day,
          count(*) as row_count
        from {_crime_table()}
    """
    rows = service.query_safe(sql)
    if not rows:
        return {"min_day": None, "max_day": None, "row_count": 0}
    return rows[0]


@router.get("/overview")
def crime_overview(
    start_date: Annotated[date, Query(..., description="Inclusive start date.")],
    end_date: Annotated[date, Query(..., description="Inclusive end date.")],
    top_n: Annotated[int, Query(ge=1, le=25)] = 10,
    map_limit: Annotated[int, Query(ge=1, le=5000)] = 1500,
) -> dict[str, object]:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    table = _crime_table()
    date_params = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date.isoformat()),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date.isoformat()),
    ]
    top_params = [
        *date_params,
        bigquery.ScalarQueryParameter("top_n", "INT64", top_n),
    ]
    map_params = [
        *date_params,
        bigquery.ScalarQueryParameter("map_limit", "INT64", map_limit),
    ]
    by_borough_sql = f"""
        select borough, count(*) as crime_count
        from {table}
        where complaint_date between @start_date and @end_date
          and borough is not null
        group by borough
        order by crime_count desc
    """
    by_law_sql = f"""
        select law_category, count(*) as crime_count
        from {table}
        where complaint_date between @start_date and @end_date
          and law_category is not null
        group by law_category
        order by crime_count desc
    """
    daily_sql = f"""
        with daily_totals as (
          select complaint_date as day, count(*) as crime_count
          from {table}
          where complaint_date between @start_date and @end_date
          group by day
        ),
        daily_offenses as (
          select
            complaint_date as day,
            offense_description,
            count(*) as crime_count,
            row_number() over (
              partition by complaint_date
              order by count(*) desc
            ) as offense_rank
          from {table}
          where complaint_date between @start_date and @end_date
            and offense_description is not null
          group by day, offense_description
        )
        select
          totals.day,
          totals.crime_count,
          array_agg(
            struct(
              offenses.offense_description as offense_description,
              offenses.crime_count as crime_count
            )
            order by offenses.crime_count desc
          ) as top_offenses
        from daily_totals as totals
        left join daily_offenses as offenses
          on totals.day = offenses.day
         and offenses.offense_rank <= 5
        group by totals.day, totals.crime_count
        order by totals.day
    """
    top_offense_sql = f"""
        select offense_description, law_category, count(*) as crime_count
        from {table}
        where complaint_date between @start_date and @end_date
          and offense_description is not null
        group by offense_description, law_category
        order by crime_count desc
        limit @top_n
    """
    total_sql = f"""
        select count(*) as row_count
        from {table}
        where complaint_date between @start_date and @end_date
    """
    map_points_sql = f"""
        select
          complaint_id,
          complaint_date,
          borough,
          law_category,
          offense_description,
          premise_type,
          latitude,
          longitude
        from {table}
        where complaint_date between @start_date and @end_date
          and latitude is not null
          and longitude is not null
        order by abs(farm_fingerprint(complaint_id))
        limit @map_limit
    """

    total = service.query(total_sql, params=date_params)
    return {
        "source": "gold_fct_crime_events",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "row_count": int(total[0]["row_count"]) if total else 0,
        "by_borough": service.query(by_borough_sql, params=date_params),
        "by_law_category": service.query(by_law_sql, params=date_params),
        "daily_trend": service.query(daily_sql, params=date_params),
        "top_offenses": service.query(top_offense_sql, params=top_params),
        "map_points": service.query(map_points_sql, params=map_params),
    }


@router.get("/hourly-profile")
def crime_hourly_profile(
    start_date: Annotated[date, Query(..., description="Inclusive start date.")],
    end_date: Annotated[date, Query(..., description="Inclusive end date.")],
) -> dict[str, object]:
    table = _crime_table()
    sql = f"""
        select complaint_hour, law_category, count(*) as crime_count
        from {table}
        where complaint_date between @start_date and @end_date
          and complaint_hour is not null
        group by complaint_hour, law_category
        order by complaint_hour, law_category
    """
    rows = service.query(
        sql,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date.isoformat()),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date.isoformat()),
        ],
    )
    return {"source": "gold_fct_crime_events", "items": rows}
