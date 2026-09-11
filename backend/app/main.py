"""
ASILI HAWK — FastAPI application
Cloud-ready, serves both API and static frontend.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.services.hawk import get_hawk_feed, get_stats

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    default_response_class=ORJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "name": settings.app_name,
        "version": settings.version,
    }


@app.get("/api/hawk")
async def hawk(limit: int = Query(default=25, ge=1, le=50)):
    """Primary early-opportunity feed (Pump.fun curve + fresh pairs)."""
    data = await get_hawk_feed(limit=limit)
    return {"count": len(data), "results": data}


@app.get("/api/intel")
async def intel(limit: int = Query(default=25, ge=1, le=50)):
    """Alias kept for compatibility with original frontend."""
    data = await get_hawk_feed(limit=limit)
    return data


@app.get("/api/stats")
async def stats():
    return await get_stats()


# ---------- Static frontend (production) ----------
# Resolve dist from several possible layouts (local monorepo / Docker / Railway)
_candidates = [
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",  # monorepo
    Path(__file__).resolve().parent.parent / "frontend" / "dist",         # docker-ish
    Path("/app/frontend/dist"),
]
FRONTEND_DIST = next((p for p in _candidates if p.exists()), _candidates[0])

if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            return ORJSONResponse({"detail": "Not Found"}, status_code=404)
        index = FRONTEND_DIST / "index.html"
        return FileResponse(index)


@app.get("/")
async def root():
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "name": settings.app_name,
        "version": settings.version,
        "message": "ASILI HAWK API is online. Build the frontend or hit /api/hawk",
        "endpoints": ["/api/health", "/api/hawk", "/api/intel", "/api/stats"],
    }
