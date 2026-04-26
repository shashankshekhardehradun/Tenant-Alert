"""Shared Socrata client for NYC open data pulls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class SocrataConfig:
    base_url: str = "https://data.cityofnewyork.us/resource"
    app_token: str | None = None
    timeout_seconds: int = 60


class SocrataClient:
    """Simple paginated Socrata API client."""

    def __init__(self, config: SocrataConfig) -> None:
        self._config = config
        headers = {"X-App-Token": config.app_token} if config.app_token else None
        self._client = httpx.Client(base_url=config.base_url, headers=headers, timeout=config.timeout_seconds)

    def fetch_page(
        self,
        dataset_id: str,
        *,
        select: str | None = None,
        where: str | None = None,
        order: str | None = None,
        limit: int = 50_000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"$limit": limit, "$offset": offset}
        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        if order:
            params["$order"] = order

        response = self._client.get(f"/{dataset_id}.json", params=params)
        response.raise_for_status()
        return list(response.json())

    def fetch_all(
        self,
        dataset_id: str,
        *,
        where: str | None = None,
        order: str = "created_date asc",
        page_size: int = 50_000,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self.fetch_page(dataset_id, where=where, order=order, limit=page_size, offset=offset)
            if not page:
                break
            rows.extend(page)
            offset += page_size
        return rows
