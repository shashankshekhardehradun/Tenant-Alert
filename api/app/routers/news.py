"""News ticker endpoints for NYC public-safety headlines."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from fastapi import APIRouter

router = APIRouter()

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
NY1_RSS_URL = "https://ny1.com/nyc/all-boroughs/rss"
NYC_TERMS = ("nyc", "new york", "manhattan", "brooklyn", "queens", "bronx", "staten island")
SAFETY_TERMS = (
    "crime",
    "nypd",
    "police",
    "arrest",
    "robbery",
    "theft",
    "assault",
    "shooting",
    "subway",
    "public safety",
)
FALLBACK_HEADLINES = [
    {
        "title": "NYPD weekly complaint data refreshed for the latest citywide read",
        "url": "https://www.nyc.gov/site/nypd/stats/crime-statistics/citywide-crime-stats.page",
        "source": "NYPD Stats",
        "published_at": None,
        "borough": "NYC",
    },
    {
        "title": "Street Ledger running on historical NYPD complaints and borough-level context",
        "url": "https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Year-To-Date-/5uac-w243",
        "source": "NYC Open Data",
        "published_at": None,
        "borough": "NYC",
    },
]


@dataclass
class CacheEntry:
    expires_at: float
    payload: dict[str, Any]


_CACHE: CacheEntry | None = None


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in terms)


def _borough_for_text(value: str) -> str:
    lowered = value.lower()
    if "brooklyn" in lowered:
        return "Brooklyn"
    if "queens" in lowered:
        return "Queens"
    if "bronx" in lowered:
        return "Bronx"
    if "staten island" in lowered:
        return "Staten Island"
    if "manhattan" in lowered or "new york city" in lowered or "nyc" in lowered:
        return "Manhattan"
    return "NYC"


def _clean_title(title: str) -> str:
    return " ".join(title.replace("\n", " ").split())


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = item["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _fetch_gdelt(limit: int) -> list[dict[str, Any]]:
    query = (
        '(NYC OR "New York City" OR Manhattan OR Brooklyn OR Queens OR Bronx '
        'OR "Staten Island") (crime OR NYPD OR police OR robbery OR theft OR assault OR subway)'
    )
    with httpx.Client(timeout=12) as client:
        response = client.get(
            GDELT_DOC_API,
            params={
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": limit,
                "sort": "hybridrel",
            },
        )
        response.raise_for_status()
        articles = response.json().get("articles", [])

    items: list[dict[str, Any]] = []
    for article in articles:
        title = _clean_title(str(article.get("title") or ""))
        if (
            not title
            or not _contains_any(title, NYC_TERMS)
            or not _contains_any(title, SAFETY_TERMS)
        ):
            continue
        items.append(
            {
                "title": title,
                "url": article.get("url"),
                "source": article.get("sourcecountry") or article.get("domain") or "GDELT",
                "published_at": article.get("seendate"),
                "borough": _borough_for_text(title),
            }
        )
    return items


def _fetch_rss(limit: int) -> list[dict[str, Any]]:
    with httpx.Client(timeout=12) as client:
        response = client.get(NY1_RSS_URL)
        response.raise_for_status()
        root = ET.fromstring(response.text)

    items: list[dict[str, Any]] = []
    for node in root.findall("./channel/item"):
        title = _clean_title(node.findtext("title") or "")
        description = _clean_title(node.findtext("description") or "")
        haystack = f"{title} {description}"
        if (
            not title
            or not _contains_any(haystack, NYC_TERMS)
            or not _contains_any(haystack, SAFETY_TERMS)
        ):
            continue
        published_at = None
        pub_date = node.findtext("pubDate")
        if pub_date:
            try:
                published_at = parsedate_to_datetime(pub_date).isoformat()
            except (TypeError, ValueError):
                published_at = pub_date
        items.append(
            {
                "title": title,
                "url": node.findtext("link"),
                "source": "NY1 RSS",
                "published_at": published_at,
                "borough": _borough_for_text(haystack),
            }
        )
        if len(items) >= limit:
            break
    return items


@router.get("/ticker")
def news_ticker(limit: int = 12) -> dict[str, object]:
    """Return ticker-safe NYC public-safety headlines from GDELT with RSS/static fallback."""
    global _CACHE
    now = time.time()
    safe_limit = max(3, min(limit, 25))
    if _CACHE and _CACHE.expires_at > now:
        return _CACHE.payload

    source = "fallback"
    try:
        items = _fetch_gdelt(safe_limit * 2)
        source = "gdelt"
    except (httpx.HTTPError, ValueError):
        items = []

    if len(items) < 3:
        try:
            items.extend(_fetch_rss(safe_limit))
            source = "gdelt+rss" if source == "gdelt" else "rss"
        except (httpx.HTTPError, ET.ParseError):
            pass

    items = _dedupe(items)[:safe_limit] or FALLBACK_HEADLINES
    payload = {
        "source": source if items != FALLBACK_HEADLINES else "static-fallback",
        "items": items,
        "ticker_text": " · ".join(f"LATEST: {item['title']}" for item in items),
    }
    _CACHE = CacheEntry(expires_at=now + 600, payload=payload)
    return payload
