"""FastAPI entrypoint for Tenant Alert."""

from fastapi import FastAPI

from api.app.routers import buildings, compare, complaints, neighborhoods

app = FastAPI(title="Tenant Alert API", version="0.1.0")

app.include_router(neighborhoods.router, prefix="/neighborhoods", tags=["neighborhoods"])
app.include_router(buildings.router, prefix="/buildings", tags=["buildings"])
app.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
app.include_router(compare.router, prefix="/compare", tags=["compare"])


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
