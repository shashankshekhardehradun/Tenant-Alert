"""Crime analytics endpoints backed by BigQuery gold marts."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery
from pydantic import BaseModel

from api.app.services.bigquery_service import BigQueryService
from tenant_alert.config import settings

router = APIRouter()
service = BigQueryService()


class RiskScoreRequest(BaseModel):
    location: str = "SOHO"
    time_range: str = "late-night-decisions"
    activity: str = "just-walking"
    awareness: str = "casually-alert"
    appearance: str = "low-key-local"
    movement: str = "busy-avenue"
    environment: str = "bright-busy"
    group_context: str = "with-a-friend"
    chaos: str = "responsible-citizen"


LOCATION_TO_BOROUGH = {
    "soho": "MANHATTAN",
    "lower-manhattan": "MANHATTAN",
    "lower-east-side": "MANHATTAN",
    "midtown": "MANHATTAN",
    "williamsburg": "BROOKLYN",
    "brooklyn": "BROOKLYN",
    "bushwick": "BROOKLYN",
    "coney-island": "BROOKLYN",
    "bronx": "BRONX",
    "fordham": "BRONX",
    "mott-haven": "BRONX",
    "queens": "QUEENS",
    "astoria": "QUEENS",
    "flushing": "QUEENS",
    "jamaica": "QUEENS",
    "staten-island": "STATEN ISLAND",
}

TIME_FACTORS = {
    "sun-still-doing-its-job": (0, 14),
    "after-work-wander": (7, 18),
    "late-night-decisions": (18, 23),
    "you-should-probably-be-home": (24, 2),
}

MODEL_WEIGHTS = {
    "activity": {
        "just-walking": 0,
        "walking-texting": 8,
        "headphones-on": 9,
        "post-drinks-confidence": 13,
        "lost-pretending": 10,
        "tourist-mode": 11,
        "rideshare-wait": 7,
        "late-night-food-run": 8,
        "camera-out": 12,
        "shopping-bags": 9,
    },
    "awareness": {
        "head-on-swivel": -8,
        "casually-alert": 0,
        "vibing-not-observing": 11,
        "main-character-energy": 17,
    },
    "appearance": {
        "corporate-clean": 2,
        "low-key-local": -3,
        "standing-out": 6,
        "rob-me-outfit": 14,
    },
    "movement": {
        "subway-platform": 8,
        "side-street": 7,
        "busy-avenue": 2,
        "transit-hub": 9,
        "tourist-zone": 10,
    },
    "environment": {
        "bright-busy": -5,
        "rainy-empty": 8,
        "sketchy-quiet": 12,
        "crowded-chaos": 9,
    },
    "group_context": {
        "solo-mission": 7,
        "with-a-friend": 0,
        "group-energy": -6,
        "lone-wolf-2am": 16,
    },
    "chaos": {
        "responsible-citizen": -4,
        "little-reckless": 4,
        "bad-decisions-pending": 10,
        "lets-see-what-happens": 16,
    },
}


def _crime_table() -> str:
    if not settings.gcp_project_id:
        raise HTTPException(status_code=500, detail="GCP_PROJECT_ID is not configured")
    return f"`{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_fct_crime_events`"


def _demographics_table() -> str:
    if not settings.gcp_project_id:
        raise HTTPException(status_code=500, detail="GCP_PROJECT_ID is not configured")
    return f"`{settings.gcp_project_id}.{settings.bq_dataset_gold}.gold_agg_demographics_by_nta`"


def _risk_features_table() -> str:
    if not settings.gcp_project_id:
        raise HTTPException(status_code=500, detail="GCP_PROJECT_ID is not configured")
    return f"`{settings.gcp_project_id}.{settings.bq_dataset_ml}.features_crime_risk_hourly`"


def _risk_model() -> str:
    if not settings.gcp_project_id:
        raise HTTPException(status_code=500, detail="GCP_PROJECT_ID is not configured")
    return f"`{settings.gcp_project_id}.{settings.bq_dataset_ml}.crime_risk_rf_model`"


def _risk_feature_importance_table() -> str:
    if not settings.gcp_project_id:
        raise HTTPException(status_code=500, detail="GCP_PROJECT_ID is not configured")
    return f"`{settings.gcp_project_id}.{settings.bq_dataset_ml}.crime_risk_feature_importance`"


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


def _risk_bucket(score: int) -> tuple[str, str, str]:
    if score < 35:
        return ("LOW", "You're chilling", "Daytime Bubble")
    if score < 60:
        return ("MEDIUM", "Keep your head up", "Busy but Watchful")
    if score < 80:
        return ("HIGH", "Eyes up. Phone down.", "Classic NYC Chaos")
    return ("VERY HIGH", "Respectfully... go home", "Late Night Gamble Zone")


def _borough_for_location(location: str) -> str:
    normalized = location.lower().strip().replace(" ", "-").replace("_", "-")
    return LOCATION_TO_BOROUGH.get(normalized, "MANHATTAN")


def _hour_for_time_range(time_range: str) -> int:
    return TIME_FACTORS.get(time_range, (18, 23))[1]


def _model_weight(group: str, value: str) -> int:
    return MODEL_WEIGHTS.get(group, {}).get(value, 0)


def _factor(label: str, points: int, detail: str) -> dict[str, object]:
    return {"label": label, "points": points, "detail": detail}


@router.post("/risk-score")
def crime_risk_score(payload: RiskScoreRequest) -> dict[str, object]:
    """BQML Random Forest baseline plus transparent modifiers for contextual risk."""
    borough = _borough_for_location(payload.location)
    hour = _hour_for_time_range(payload.time_range)
    sql = f"""
        with feature_row as (
          select
            feature_date,
            borough,
            hour,
            day_of_week,
            month,
            is_weekend,
            recent_7d_incidents,
            recent_14d_incidents,
            recent_30d_incidents,
            recent_14d_severity_score,
            total_population,
            poverty_rate,
            renter_share,
            bachelors_or_higher_share,
            approx_median_household_income,
            approx_median_gross_rent
          from {_risk_features_table()}
          where borough = @borough
            and hour = @hour
            and feature_date = (
              select max(feature_date)
              from {_risk_features_table()}
              where borough = @borough
            )
        ),
        prediction as (
          select *
          from ml.predict(
            model {_risk_model()},
            (select * from feature_row)
          )
        ),
        top_offenses as (
          select offense_description, count(*) as crime_count
          from {_crime_table()}
          where offense_description is not null
            and borough = @borough
            and complaint_date between (
              select date_sub(max(feature_date), interval 13 day)
              from {_risk_features_table()}
              where borough = @borough
            ) and (
              select max(feature_date)
              from {_risk_features_table()}
              where borough = @borough
            )
          group by offense_description
          order by crime_count desc
          limit 3
        )
        select
          prediction.feature_date as latest_day,
          prediction.predicted_crime_pressure_score,
          prediction.recent_7d_incidents,
          prediction.recent_14d_incidents,
          prediction.recent_30d_incidents,
          prediction.recent_14d_severity_score,
          prediction.total_population,
          prediction.poverty_rate,
          prediction.renter_share,
          prediction.bachelors_or_higher_share,
          prediction.approx_median_household_income,
          prediction.approx_median_gross_rent,
          array_agg(
            struct(top_offenses.offense_description, top_offenses.crime_count)
          ) as top_offenses
        from prediction
        left join top_offenses on true
        group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
    """
    rows = service.query_safe(
        sql,
        params=[
            bigquery.ScalarQueryParameter("borough", "STRING", borough),
            bigquery.ScalarQueryParameter("hour", "INT64", hour),
        ],
    )
    if not rows:
        raise HTTPException(
            status_code=503,
            detail=(
                "BQML risk model is not available yet. Run dbt for "
                "features_crime_risk_hourly, train_crime_risk_rf_model, "
                "and crime_risk_feature_importance."
            ),
        )
    stats = rows[0] if rows else {}
    predicted_pressure = float(stats.get("predicted_crime_pressure_score") or 0)
    recent_14d_incidents = int(stats.get("recent_14d_incidents") or 0)
    model_baseline = max(1, min(70, round(predicted_pressure * 8)))
    night_factor = max(0, _model_weight("activity", payload.activity) // 3)
    if payload.time_range == "late-night-decisions":
        night_factor += 14
    elif payload.time_range == "you-should-probably-be-home":
        night_factor += 20
    elif payload.time_range == "after-work-wander":
        night_factor += 7
    crowd_density = min(18, round(predicted_pressure * 2)) + _model_weight(
        "movement", payload.movement
    )
    recent_factor = min(15, recent_14d_incidents // 450)
    behavior_factor = (
        _model_weight("activity", payload.activity)
        + _model_weight("awareness", payload.awareness)
        + _model_weight("appearance", payload.appearance)
        + _model_weight("environment", payload.environment)
        + _model_weight("group_context", payload.group_context)
        + _model_weight("chaos", payload.chaos)
    )
    raw_score = model_baseline + night_factor + crowd_density + recent_factor + behavior_factor
    score = max(1, min(99, raw_score))
    category, verdict, persona = _risk_bucket(score)
    importance_rows = service.query_safe(
        f"""
            select feature, importance_weight, importance_gain
            from {_risk_feature_importance_table()}
            order by importance_gain desc nulls last, importance_weight desc nulls last
            limit 5
        """
    )
    baseline_detail = (
        f"Random Forest predicted {predicted_pressure:.1f} "
        f"severity-weighted incidents for {borough} around {hour}:00."
    )
    recent_detail = (
        f"{recent_14d_incidents:,} borough incidents in the latest 14-day feature window."
    )
    density_detail = "Predicted area/hour pressure plus movement context."
    behavior_detail = (
        "Activity, awareness, appearance, group, environment, and chaos inputs."
    )
    top_factors = sorted(
        [
            _factor("BQML baseline", model_baseline, baseline_detail),
            _factor("Night factor", night_factor, f"Time range resolved near {hour}:00."),
            _factor("Density context", crowd_density, density_detail),
            _factor("Recent incidents", recent_factor, recent_detail),
            _factor("Behavior/vibe", behavior_factor, behavior_detail),
        ],
        key=lambda item: abs(int(item["points"])),
        reverse=True,
    )
    headline = f"{payload.activity.replace('-', ' ').upper()} MEETS {borough} AFTER DARK"
    if payload.awareness in {"vibing-not-observing", "main-character-energy"}:
        headline = f"CONFIDENCE HIGH, AWARENESS LOW IN {borough}"
    if payload.group_context in {"solo-mission", "lone-wolf-2am"}:
        headline = f"LONE WOLF ENERGY SPIKES RISK IN {borough}"

    return {
        "score": score,
        "category": category,
        "verdict": verdict,
        "persona": persona,
        "headline": headline,
        "borough": borough,
        "location": payload.location,
        "model_version": "bqml-random-forest-v0.1",
        "latest_data_day": stats.get("latest_day"),
        "top_factors": top_factors,
        "receipt_lines": [
            {"label": "BQML BASELINE", "value": model_baseline},
            {"label": "NIGHT FACTOR", "value": night_factor},
            {"label": "DENSITY CONTEXT", "value": crowd_density},
            {"label": "RECENT INCIDENTS", "value": recent_factor},
            {"label": "BEHAVIOR/VIBE", "value": behavior_factor},
        ],
        "top_offenses": stats.get("top_offenses") or [],
        "model_feature_importance": importance_rows,
        "tip": "Eyes up. Move with purpose. Stay boring when the block gets loud.",
    }


@router.get("/overview")
def crime_overview(
    start_date: Annotated[date, Query(..., description="Inclusive start date.")],
    end_date: Annotated[date, Query(..., description="Inclusive end date.")],
    top_n: Annotated[int, Query(ge=1, le=25)] = 10,
    map_limit: Annotated[int, Query(ge=1, le=5000)] = 1500,
    borough: Annotated[
        str | None,
        Query(description="Optional uppercase NYC borough filter."),
    ] = None,
) -> dict[str, object]:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")

    table = _crime_table()
    borough_name = borough.upper().strip() if borough else None
    borough_filter = "and borough = @borough" if borough_name else ""
    date_params = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date.isoformat()),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date.isoformat()),
    ]
    if borough_name:
        date_params.append(bigquery.ScalarQueryParameter("borough", "STRING", borough_name))
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
          and borough not in ('(NULL)', 'NULL', 'N/A', 'UNKNOWN')
          {borough_filter}
        group by borough
        order by crime_count desc
    """
    by_law_sql = f"""
        select law_category, count(*) as crime_count
        from {table}
        where complaint_date between @start_date and @end_date
          and law_category is not null
          {borough_filter}
        group by law_category
        order by crime_count desc
    """
    daily_sql = f"""
        with daily_totals as (
          select complaint_date as day, count(*) as crime_count
          from {table}
          where complaint_date between @start_date and @end_date
            {borough_filter}
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
            {borough_filter}
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
          {borough_filter}
        group by offense_description, law_category
        order by crime_count desc
        limit @top_n
    """
    hourly_density_sql = f"""
        select
          complaint_day_of_week as day_of_week,
          complaint_hour as hour,
          count(*) as crime_count
        from {table}
        where complaint_date between @start_date and @end_date
          and complaint_day_of_week is not null
          and complaint_hour is not null
          {borough_filter}
        group by day_of_week, hour
        order by day_of_week, hour
    """
    demographic_sql = f"""
        with crime as (
          select borough, count(*) as crime_count
          from {table}
          where complaint_date between @start_date and @end_date
            and borough is not null
            and borough not in ('(NULL)', 'NULL', 'N/A', 'UNKNOWN')
            {borough_filter}
          group by borough
        ),
        demographics as (
          select
            upper(borough) as borough,
            sum(total_population) as total_population,
            safe_divide(sum(poverty_count), nullif(sum(total_population), 0)) as poverty_rate,
            safe_divide(
              sum(renter_occupied_units),
              nullif(sum(renter_occupied_units + owner_occupied_units), 0)
            ) as renter_share,
            safe_divide(
              sum(bachelors_or_higher_count),
              nullif(sum(education_pop_25_plus), 0)
            ) as bachelors_or_higher_share,
            safe_divide(
              sum(approx_median_household_income * total_population),
              nullif(sum(total_population), 0)
            ) as approx_median_household_income,
            safe_divide(
              sum(approx_median_gross_rent * renter_occupied_units),
              nullif(sum(renter_occupied_units), 0)
            ) as approx_median_gross_rent
          from {_demographics_table()}
          where borough is not null
          group by upper(borough)
        )
        select
          demographics.borough,
          demographics.total_population,
          demographics.poverty_rate,
          demographics.renter_share,
          demographics.bachelors_or_higher_share,
          demographics.approx_median_household_income,
          demographics.approx_median_gross_rent,
          crime.crime_count,
          safe_divide(crime.crime_count, nullif(demographics.total_population, 0)) * 100000
            as crime_rate_per_100k
        from demographics
        join crime using (borough)
        order by crime_rate_per_100k desc
    """
    total_sql = f"""
        select count(*) as row_count
        from {table}
        where complaint_date between @start_date and @end_date
          {borough_filter}
    """
    map_points_sql = f"""
        select
          complaint_id,
          source_dataset,
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
          {borough_filter}
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
        "hourly_density": service.query(hourly_density_sql, params=date_params),
        "demographics_by_borough": service.query(demographic_sql, params=date_params),
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
