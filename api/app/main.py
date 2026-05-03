"""FastAPI entrypoint for Tenant Alert."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.routers import analytics, buildings, compare, complaints, crime, neighborhoods, news

_DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
)


def _cors_allow_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return list(_DEFAULT_CORS_ORIGINS)


def _cors_allow_origin_regex() -> str | None:
    raw = os.environ.get("CORS_ALLOW_ORIGIN_REGEX", "").strip()
    return raw or None


def _cors_middleware_kwargs() -> dict[str, object]:
    out: dict[str, object] = {
        "allow_origins": _cors_allow_origins(),
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    rx = _cors_allow_origin_regex()
    if rx:
        out["allow_origin_regex"] = rx
    return out


app = FastAPI(title="Tenant Alert API", version="0.1.0")

app.add_middleware(CORSMiddleware, **_cors_middleware_kwargs())

app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(neighborhoods.router, prefix="/neighborhoods", tags=["neighborhoods"])
app.include_router(buildings.router, prefix="/buildings", tags=["buildings"])
app.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
app.include_router(compare.router, prefix="/compare", tags=["compare"])
app.include_router(crime.router, prefix="/crime", tags=["crime"])
app.include_router(news.router, prefix="/news", tags=["news"])


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "Tenant Alert API",
        "status": "ok",
        "links": {
            "health": "/healthz",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
    }


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
