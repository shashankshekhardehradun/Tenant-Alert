"""BigQuery access layer for API endpoints."""

from __future__ import annotations

from typing import Any

from google.api_core import exceptions as gcp_exceptions
from google.cloud import bigquery

from tenant_alert.config import settings


class BigQueryService:
    def __init__(self) -> None:
        self._client = bigquery.Client(project=settings.gcp_project_id or None)

    def query(
        self,
        sql: str,
        params: list[bigquery.ScalarQueryParameter] | None = None,
    ) -> list[dict[str, Any]]:
        config = bigquery.QueryJobConfig(query_parameters=params or [])
        result = self._client.query(sql, job_config=config).result()
        return [dict(row.items()) for row in result]

    def query_safe(
        self,
        sql: str,
        params: list[bigquery.ScalarQueryParameter] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            return self.query(sql, params=params)
        except gcp_exceptions.GoogleAPIError:
            return []
