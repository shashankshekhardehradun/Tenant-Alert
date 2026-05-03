"""News ticker endpoints for NYC public-safety headlines."""

from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter

router = APIRouter()

# Google News topic RSS — no API key; works well from Cloud Run vs GDELT doc API.
_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    + urlencode(
        {
            "q": "New York City (NYPD OR crime OR police OR subway OR shooting)",
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
    )
)
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
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NYCRouletteTicker/1.0; +https://nycroulette.net) "
        "python-httpx"
    ),
}
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
_CACHE_TTL_SECONDS = 3600


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


def _strip_xmlns_for_parse(xml_text: str) -> str:
    """Default xmlns on <rss> breaks ET.findall('.//item') for some feeds."""
    if 'xmlns="' not in xml_text[:600]:
        return xml_text
    return re.sub(r" xmlns=\"[^\"]+\"", "", xml_text, count=1)


def _xml_item_nodes(xml_text: str, cap: int) -> list[ET.Element]:
    root = ET.fromstring(_strip_xmlns_for_parse(xml_text))
    return root.findall(".//item")[:cap]


def _fetch_google_news_rss(limit: int) -> list[dict[str, Any]]:
    """Headlines from Google News RSS — query is already NYC + public-safety scoped."""
    with httpx.Client(timeout=18.0, headers=_HTTP_HEADERS) as client:
        response = client.get(_GOOGLE_NEWS_RSS)
        response.raise_for_status()
    items: list[dict[str, Any]] = []
    for node in _xml_item_nodes(response.text, limit * 2):
        raw_title = html.unescape(node.findtext("title") or "")
        title = _clean_title(raw_title)
        if len(title) < 12:
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
                "source": "Google News",
                "published_at": published_at,
                "borough": _borough_for_text(title),
            }
        )
        if len(items) >= limit:
            break
    return items


def _fetch_rss(limit: int) -> list[dict[str, Any]]:
    with httpx.Client(timeout=18.0, headers=_HTTP_HEADERS) as client:
        response = client.get(NY1_RSS_URL)
        response.raise_for_status()
    items: list[dict[str, Any]] = []
    for node in _xml_item_nodes(response.text, limit * 2):
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
    """NYC public-safety headlines: Google News RSS, then NY1 RSS, then static fallback."""
    global _CACHE
    now = time.time()
    safe_limit = max(3, min(limit, 25))
    if _CACHE and _CACHE.expires_at > now:
        return _CACHE.payload

    source = "fallback"
    items: list[dict[str, Any]] = []
    try:
        items = _fetch_google_news_rss(safe_limit * 2)
        if items:
            source = "google-news"
    except (httpx.HTTPError, ET.ParseError, ValueError):
        items = []

    if len(items) < 3:
        try:
            extra = _fetch_rss(safe_limit)
            items.extend(extra)
            if extra:
                source = f"{source}+ny1" if source == "google-news" else "ny1"
        except (httpx.HTTPError, ET.ParseError):
            pass

    items = _dedupe(items)[:safe_limit] or FALLBACK_HEADLINES
    payload = {
        "source": source if items != FALLBACK_HEADLINES else "static-fallback",
        "items": items,
        "ticker_text": " · ".join(f"LATEST: {item['title']}" for item in items),
    }
    _CACHE = CacheEntry(expires_at=now + _CACHE_TTL_SECONDS, payload=payload)
    return payload
