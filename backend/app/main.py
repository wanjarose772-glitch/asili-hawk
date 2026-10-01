"""ASILI HAWK — FastAPI application (production-compatible)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.services.hawk import get_hawk_feed, get_prime, get_radar, get_stats, get_top5

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    default_response_class=ORJSONResponse,
)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_cors_wildcard = _cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # allow_credentials=True with allow_origins=["*"] is invalid per the
    # CORS spec (browsers reject it) and is a wide-open default besides.
    # Only allow credentials once real origins are configured via
    # CORS_ORIGINS in the environment.
    allow_credentials=not _cors_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health():
    return {
        "status": "online",
        "name": settings.app_name,
        "version": settings.version,
    }


@app.get("/api/hawk")
async def hawk(limit: int = Query(default=25, ge=1, le=50)):
    data = await get_hawk_feed(limit=limit)
    return {"count": len(data), "results": data}


@app.get("/api/intel")
async def intel(limit: int = Query(default=25, ge=1, le=50)):
    data = await get_hawk_feed(limit=limit)
    return data


@app.get("/api/stats")
async def stats():
    return await get_stats()


@app.get("/api/prime")
async def prime(limit: int = Query(default=10, ge=1, le=25)):
    data = await get_prime(limit=limit)
    return {"count": len(data), "results": data}


@app.get("/api/focus")
async def focus(limit: int = Query(default=25, ge=1, le=40)):
    """Private operator board: LOTTERY + EARLY + BREAKOUT only."""
    data = await get_radar("focus")
    return {
        "count": len(data[:limit]),
        "results": data[:limit],
        "mode": "private_operator_focus",
        "note": "Noise excluded. LOTTERY = micro only. Not financial advice.",
    }


@app.get("/api/lottery")
async def lottery(limit: int = Query(default=20, ge=1, le=40)):
    """Earliest asymmetric band — micro size only, high fail rate expected."""
    data = await get_radar("lottery")
    return {
        "count": len(data[:limit]),
        "results": data[:limit],
        "band": "LOTTERY",
        "warning": "HIGH VARIANCE — most go to zero; micro size only. Not financial advice.",
    }


@app.get("/api/breakout")
async def breakout(limit: int = Query(default=20, ge=1, le=40)):
    """Tokens >= $30k mcap ranked by path-to-$100k potential."""
    data = await get_radar("breakout")
    return {"count": len(data[:limit]), "results": data[:limit], "band": "30k_to_100k_path"}


@app.get("/api/top5")
async def top5():
    data = await get_top5()
    return {"count": len(data), "results": data}


@app.get("/api/radar/{kind}")
async def radar(kind: str):
    if kind not in ("graduation", "momentum", "risk", "early", "postgrad", "actionable", "breakout", "lottery", "ladder", "focus"):
        return ORJSONResponse({"detail": "kind must be graduation|momentum|risk|early|postgrad|actionable|breakout|lottery|ladder|focus"}, status_code=400)
    data = await get_radar(kind)
    return {"kind": kind, "count": len(data), "results": data}


_candidates = [
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    Path(__file__).resolve().parent.parent / "frontend" / "dist",
    Path("/app/frontend/dist"),
]
FRONTEND_DIST = next((p for p in _candidates if p.exists()), _candidates[0])


def _serve_index():
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return ORJSONResponse(
        {
            "name": settings.app_name,
            "version": settings.version,
            "message": "ASILI HAWK API online. Frontend not built in this image.",
            "endpoints": [
                "/api/health",
                "/api/hawk",
                "/api/prime",
                "/api/top5",
                "/api/radar/{graduation|momentum|risk|early}",
                "/api/stats",
            ],
        }
    )


if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            return ORJSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return _serve_index()


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return _serve_index()
