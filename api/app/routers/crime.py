"""Crime analytics endpoints backed by BigQuery gold marts."""

from __future__ import annotations

from datetime import date
from itertools import product
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
    "east-village": "MANHATTAN",
    "greenwich-village": "MANHATTAN",
    "chelsea": "MANHATTAN",
    "midtown": "MANHATTAN",
    "upper-east-side": "MANHATTAN",
    "upper-west-side": "MANHATTAN",
    "harlem": "MANHATTAN",
    "washington-heights": "MANHATTAN",
    "williamsburg": "BROOKLYN",
    "brooklyn": "BROOKLYN",
    "bushwick": "BROOKLYN",
    "bed-stuy": "BROOKLYN",
    "park-slope": "BROOKLYN",
    "sunset-park": "BROOKLYN",
    "coney-island": "BROOKLYN",
    "red-hook": "BROOKLYN",
    "dumbo": "BROOKLYN",
    "queens": "QUEENS",
    "astoria": "QUEENS",
    "long-island-city": "QUEENS",
    "flushing": "QUEENS",
    "jackson-heights": "QUEENS",
    "elmhurst": "QUEENS",
    "ridgewood": "QUEENS",
    "jamaica": "QUEENS",
    "bronx": "BRONX",
    "fordham": "BRONX",
    "mott-haven": "BRONX",
    "highbridge": "BRONX",
    "staten-island": "STATEN ISLAND",
    "tottenville": "STATEN ISLAND",
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
        "dog-walking": 4,
        "commute-rush": 6,
        "date-night-stroll": 3,
    },
    "awareness": {
        "head-on-swivel": -8,
        "casually-alert": 0,
        "vibing-not-observing": 11,
        "main-character-energy": 17,
        "wired-but-tired": 8,
    },
    "appearance": {
        "corporate-clean": 2,
        "low-key-local": -3,
        "standing-out": 6,
        "rob-me-outfit": 14,
        "tourist-lanyard": 12,
    },
    "movement": {
        "subway-platform": 8,
        "side-street": 7,
        "busy-avenue": 2,
        "transit-hub": 9,
        "tourist-zone": 10,
        "waterfront-walk": 7,
        "park-cut-through": 6,
    },
    "environment": {
        "bright-busy": -5,
        "rainy-empty": 8,
        "sketchy-quiet": 12,
        "crowded-chaos": 5,
        "construction-canyon": 10,
    },
    "group_context": {
        "solo-mission": 6,
        "with-a-friend": 0,
        "group-energy": -6,
        "lone-wolf-2am": 17,
        "pair-outing": 1,
        "tour-squad": -7,
    },
    "chaos": {
        "responsible-citizen": -4,
        "little-reckless": 4,
        "bad-decisions-pending": 10,
        "lets-see-what-happens": 16,
    },
}

# RF baseline is incident-only; caps keep "safe" chip combos from always losing to the model.
_BASELINE_CAP = 34
_BASELINE_K = 3.35
_PRESSURE_SLICE_MAX = 7
_PRESSURE_MULT = 0.92
_RECENT_DIV = 720
_RECENT_CAP = 5


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
    """Verdict bands on the 1–99 receipt score (same scale as the UI total)."""
    if score < 40:
        return ("LOW", "You're chilling", "Daytime Bubble")
    if score < 64:
        return ("MEDIUM", "Keep your head up", "Busy but Watchful")
    if score < 86:
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


def _clamped_baseline(predicted_pressure: float) -> int:
    return max(1, min(_BASELINE_CAP, round(predicted_pressure * _BASELINE_K)))


def _pressure_slice(predicted_pressure: float) -> int:
    return min(_PRESSURE_SLICE_MAX, round(predicted_pressure * _PRESSURE_MULT))


def _recent_term(recent_14d_incidents: int) -> int:
    return min(_RECENT_CAP, recent_14d_incidents // _RECENT_DIV)


def _temporal_adjustment(time_range: str) -> int:
    """Negative = safer receipt: daylight / normal-hours chips vs late-night buckets."""
    return {
        "sun-still-doing-its-job": -22,
        "after-work-wander": -12,
        "late-night-decisions": 3,
        "you-should-probably-be-home": 9,
    }.get(time_range, 0)


def _witness_crowd_comfort_values(environment: str, movement: str, group_context: str) -> int:
    """Negative = witnesses / cover / eyes on the street; can stack with env weights."""
    n = 0
    if environment == "bright-busy":
        n -= 7
    if movement == "busy-avenue":
        n -= 5
    if movement == "transit-hub":
        n -= 3
    if group_context in {"group-energy", "tour-squad"}:
        n -= 6
    if environment == "crowded-chaos" and group_context in {
        "with-a-friend",
        "pair-outing",
        "group-energy",
        "tour-squad",
    }:
        n -= 9
    if environment == "sketchy-quiet" and group_context in {"solo-mission", "lone-wolf-2am"}:
        n += 5
    return n


def _witness_crowd_comfort(payload: RiskScoreRequest) -> int:
    return _witness_crowd_comfort_values(
        payload.environment,
        payload.movement,
        payload.group_context,
    )


def _behavior_six_sum(payload: RiskScoreRequest) -> int:
    return (
        _model_weight("activity", payload.activity)
        + _model_weight("awareness", payload.awareness)
        + _model_weight("appearance", payload.appearance)
        + _model_weight("environment", payload.environment)
        + _model_weight("group_context", payload.group_context)
        + _model_weight("chaos", payload.chaos)
    )


def _compute_swing_extrema() -> tuple[int, int]:
    """Min/max of (behavior six-pack + temporal + witness) over every chip permutation."""
    groups_six = (
        "activity",
        "awareness",
        "appearance",
        "environment",
        "group_context",
        "chaos",
    )
    key_lists = [tuple(MODEL_WEIGHTS[g]) for g in groups_six]
    movements = tuple(MODEL_WEIGHTS["movement"])
    times = tuple(TIME_FACTORS)
    lo = 10**9
    hi = -10**9
    for bundle in product(*key_lists, movements, times):
        six_vals, movement, time_range = bundle[:-2], bundle[-2], bundle[-1]
        behavior = sum(
            _model_weight(g, v) for g, v in zip(groups_six, six_vals, strict=True)
        )
        env_v = six_vals[3]
        temporal = _temporal_adjustment(time_range)
        witness = _witness_crowd_comfort_values(env_v, movement, six_vals[4])
        total = behavior + temporal + witness
        lo = min(lo, total)
        hi = max(hi, total)
    return lo, hi


_ROUTING_WEIGHT_MIN = min(MODEL_WEIGHTS["movement"].values())
_ROUTING_WEIGHT_MAX = max(MODEL_WEIGHTS["movement"].values())
_CRIME_STACK_MIN = 1 + 0 + 0 + _ROUTING_WEIGHT_MIN
_CRIME_STACK_MAX = _BASELINE_CAP + _PRESSURE_SLICE_MAX + _RECENT_CAP + _ROUTING_WEIGHT_MAX
_SWING_MIN, _SWING_MAX = _compute_swing_extrema()
_RAW_CALIB_MIN = _CRIME_STACK_MIN + _SWING_MIN
_RAW_CALIB_MAX = _CRIME_STACK_MAX + _SWING_MAX


def _calibrated_display_score(raw_points_total: int) -> int:
    span = max(1, _RAW_CALIB_MAX - _RAW_CALIB_MIN)
    t = (raw_points_total - _RAW_CALIB_MIN) / span
    t = max(0.0, min(1.0, t))
    return int(max(1, min(99, round(1 + t * 98))))


@router.post("/risk-score")
def crime_risk_score(payload: RiskScoreRequest) -> dict[str, object]:
    """
    Score contextual risk with a BQML Random Forest baseline plus transparent behavior modifiers.
    """
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
                "features_crime_risk_hourly, train_crime_risk_rf_model, and "
                "crime_risk_feature_importance."
            ),
        )
    stats = rows[0] if rows else {}
    predicted_pressure = float(stats.get("predicted_crime_pressure_score") or 0)
    recent_14d_incidents = int(stats.get("recent_14d_incidents") or 0)
    model_baseline = _clamped_baseline(predicted_pressure)
    pressure_slice = _pressure_slice(predicted_pressure)
    recent_factor = _recent_term(recent_14d_incidents)
    route_context = _model_weight("movement", payload.movement)
    crime_stack = model_baseline + pressure_slice + recent_factor + route_context

    behavior_six = _behavior_six_sum(payload)
    temporal_adj = _temporal_adjustment(payload.time_range)
    witness_adj = _witness_crowd_comfort(payload)
    comfort_stack = temporal_adj + witness_adj
    raw_points_total = crime_stack + behavior_six + comfort_stack
    score = _calibrated_display_score(raw_points_total)
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
    behavior_detail = (
        "Activity, awareness, appearance, group, environment, and chaos chips "
        "(movement stays in the route row)."
    )
    area_detail = (
        "Rolling incident density from the RF slice plus the latest 14-day borough volume "
        f"({recent_14d_incidents:,} incidents in that window)."
    )
    route_detail = "Street geometry / transit exposure separate from the BQML hour slice."
    comfort_detail = (
        "Daylight bucket plus extra witness cover: bright blocks, busy avenues, "
        "transit hubs, and crowds when you are not solo. These can go negative."
    )
    top_factors = sorted(
        [
            _factor("BQML baseline", model_baseline, baseline_detail),
            _factor("Area window", pressure_slice + recent_factor, area_detail),
            _factor("Route context", route_context, route_detail),
            _factor("Daylight & witnesses", comfort_stack, comfort_detail),
            _factor("Behavior/vibe", behavior_six, behavior_detail),
        ],
        key=lambda item: abs(int(item["points"])),
        reverse=True,
    )
    headline = f"{payload.activity.replace('-', ' ').upper()} OUT IN {borough}"
    if payload.time_range in {"late-night-decisions", "you-should-probably-be-home"}:
        headline = f"{payload.activity.replace('-', ' ').upper()} MEETS {borough} AFTER HOURS"
    if payload.awareness in {"vibing-not-observing", "main-character-energy"}:
        headline = f"CONFIDENCE HIGH, AWARENESS LOW IN {borough}"
    if payload.group_context in {"solo-mission", "lone-wolf-2am"}:
        headline = f"LONE WOLF ENERGY SPIKES RISK IN {borough}"

    return {
        "score": score,
        "raw_points_total": raw_points_total,
        "category": category,
        "verdict": verdict,
        "persona": persona,
        "headline": headline,
        "borough": borough,
        "location": payload.location,
        "model_version": "bqml-random-forest-v0.2",
        "latest_data_day": stats.get("latest_day"),
        "top_factors": top_factors,
        "receipt_lines": [
            {"label": "BQML BASELINE", "value": model_baseline},
            {"label": "AREA WINDOW", "value": pressure_slice + recent_factor},
            {"label": "ROUTE CONTEXT", "value": route_context},
            {"label": "DAYLIGHT & WITNESSES", "value": comfort_stack},
            {"label": "BEHAVIOR/VIBE", "value": behavior_six},
        ],
        "top_offenses": stats.get("top_offenses") or [],
        "model_feature_importance": importance_rows,
        "tip": (
            "Receipt rows are raw points that add up to the blend; the TOTAL rescales that "
            "blend to 1–99 using every chip permutation so daylight and crowd-cover can pull "
            "you back from the RF layer (it only reads incident pressure, not your choices)."
        ),
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
