"""Avoidability endpoints for the daily street-vibe watchlist."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from google.cloud import bigquery

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


def _avoidability_table() -> str:
    return f"`{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_avoidability_area_latest`"


@router.get("/rankings")
def avoidability_rankings(
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
    borough: Annotated[
        str | None,
        Query(description="Optional uppercase borough filter."),
    ] = None,
) -> dict[str, object]:
    """Return latest deterministic 'I Would Avoid' rankings."""
    borough_name = borough.upper().strip() if borough else None
    borough_filter = "where borough = @borough" if borough_name else ""
    sql = f"""
        select
          borough,
          latest_signal_day,
          latest_crime_day,
          latest_mta_day,
          street_signal_count_24h,
          street_signal_count_7d,
          avg_spike_ratio,
          open_ratio,
          street_signal_score,
          crime_count_90d,
          late_night_crime_count_90d,
          crime_pressure_score,
          late_night_pressure_score,
          transit_chaos_score,
          transit_alert_count,
          subway_alert_count,
          bus_alert_count,
          affected_route_count,
          avoidability_score,
          avoidability_band,
          top_signal_category,
          top_signal_count,
          top_signal_spike_ratio,
          top_complaint_type,
          top_descriptor,
          top_incident_zip,
          top_transit_mode,
          top_transit_route,
          top_transit_alert_type,
          top_transit_header,
          avoid_if,
          stamp_label,
          advice_copy,
          built_at
        from {_avoidability_table()}
        {borough_filter}
        order by avoidability_score desc, street_signal_count_24h desc
        limit @limit
    """
    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if borough_name:
        params.append(bigquery.ScalarQueryParameter("borough", "STRING", borough_name))
    rows = service.query_safe(sql, params=params)
    return {
        "source": "gold_avoidability_area_latest",
        "items": rows,
        "count": len(rows),
    }
