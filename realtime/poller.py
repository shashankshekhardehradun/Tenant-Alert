"""Near-real-time micro-batch poller scaffold for v2."""

from __future__ import annotations

import datetime as dt

from ingestion.common.socrata import SocrataClient, SocrataConfig


def fetch_last_5_minutes(app_token: str | None = None) -> list[dict[str, object]]:
    now = dt.datetime.utcnow().replace(microsecond=0)
    start = now - dt.timedelta(minutes=5)
    where = f"created_date >= '{start.isoformat()}Z' AND created_date < '{now.isoformat()}Z'"
    client = SocrataClient(SocrataConfig(app_token=app_token))
    return client.fetch_all("erm2-nwe9", where=where, page_size=50_000)
