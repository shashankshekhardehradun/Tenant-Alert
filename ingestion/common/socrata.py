"""Shared Socrata client for NYC open data pulls."""

from __future__ import annotations

from collections.abc import Iterator
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
        self._client = httpx.Client(
            base_url=config.base_url,
            headers=headers,
            timeout=config.timeout_seconds,
        )

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
        for page in self.iter_pages(dataset_id, where=where, order=order, page_size=page_size):
            rows.extend(page)
        return rows

    def iter_pages(
        self,
        dataset_id: str,
        *,
        where: str | None = None,
        order: str = "created_date asc",
        page_size: int = 50_000,
        max_pages: int | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """Yield Socrata pages so large backfills do not accumulate in memory."""
        offset = 0
        page_number = 0
        while max_pages is None or page_number < max_pages:
            page = self.fetch_page(
                dataset_id,
                where=where,
                order=order,
                limit=page_size,
                offset=offset,
            )
            if not page:
                break
            yield page
            offset += page_size
            page_number += 1
