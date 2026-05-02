"""FastAPI entrypoint for Tenant Alert."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.routers import analytics, buildings, compare, complaints, crime, neighborhoods

app = FastAPI(title="Tenant Alert API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(neighborhoods.router, prefix="/neighborhoods", tags=["neighborhoods"])
app.include_router(buildings.router, prefix="/buildings", tags=["buildings"])
app.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
app.include_router(compare.router, prefix="/compare", tags=["compare"])
app.include_router(crime.router, prefix="/crime", tags=["crime"])


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
