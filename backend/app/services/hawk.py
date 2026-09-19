"""HAWK orchestration — discovery → intelligence → feed."""

from __future__ import annotations

import time
from typing import Any

from cachetools import TTLCache

from app.config import get_settings
from app.discovery.aggregator import discover_opportunities
from app.intelligence.engine import rank_tokens, top_opportunities
from app.services.alerts import scan_and_alert

_settings = get_settings()
_cache: TTLCache = TTLCache(maxsize=16, ttl=max(18, _settings.cache_ttl_seconds))


def _public(t: dict) -> dict:
    """API-safe payload for dashboard and clients."""
    return {
        "ticker": t.get("ticker"),
        "name": t.get("name"),
        "address": t.get("address"),
        "source": t.get("source"),
        "stage": t.get("stage"),
        "lifecycle": t.get("lifecycle"),
        "signal": t.get("signal"),
        "hawk_score": t.get("hawk_score"),
        "alpha_score": t.get("hawk_score") or t.get("alpha_score"),
        "opportunity_score": t.get("opportunity_score"),
        "confidence": t.get("confidence"),
        "momentum_score": t.get("momentum_score"),
        "organicity_score": t.get("organicity_score"),
        "liquidity_score": t.get("liquidity_score"),
        "narrative_score": t.get("narrative_score"),
        "earlyness_score": t.get("earlyness_score"),
        "rug_risk": t.get("rug_risk"),
        "rating": t.get("rating"),
        "recommendation": t.get("recommendation"),
        "entry_state": t.get("entry_state"),
        "reasons": t.get("reasons") or [],
        "risk_flags": [f for f in (t.get("risk_flags") or []) if "INSUFFICIENT" not in f][:8],
        "positive_signals": t.get("positive_signals") or [],
        "negative_signals": t.get("negative_signals") or [],
        "thesis": t.get("thesis") or {},
        "velocity": t.get("velocity") or {},
        "market_cap": t.get("market_cap"),
        "liquidity": t.get("liquidity"),
        "volume": t.get("volume"),
        "price_usd": t.get("price_usd"),
        "curve_progress": t.get("curve_progress"),
        "age_minutes": t.get("age_minutes"),
        "reply_count": t.get("reply_count"),
        "image": t.get("image"),
        "twitter": t.get("twitter"),
        "website": t.get("website"),
        "dex_url": t.get("dex_url") or t.get("url"),
        "is_live": t.get("is_live"),
        "price_change_m5": t.get("price_change_m5"),
        "holder_quality": t.get("holder_quality"),
        "holder_top1_pct": (t.get("holder_intel") or {}).get("top1_pct") if isinstance(t.get("holder_intel"), dict) else None,
        "holder_top10_pct": (t.get("holder_intel") or {}).get("top10_pct") if isinstance(t.get("holder_intel"), dict) else None,
        "smart_money": t.get("smart_money"),
        "creator_intel": t.get("creator_intel"),
        "scanned_at": int(time.time()),
    }


async def get_hawk_feed(limit: int = 30) -> list[dict]:
    key = f"hawk:{limit}"
    if key in _cache:
        return _cache[key]

    raw = await discover_opportunities(limit=limit + 30, enrich=True)
    ranked = rank_tokens(raw)[:limit]
    feed = [_public(t) for t in ranked]
    _cache[key] = feed

    try:
        await scan_and_alert(feed)
    except Exception:
        pass
    return feed


async def get_prime(limit: int = 10) -> list[dict]:
    feed = await get_hawk_feed(40)
    primes = [
        t
        for t in feed
        if t.get("signal") == "prime"
        or (
            (t.get("hawk_score") or 0) >= 78
            and (t.get("rug_risk") or 100) < 48
            and (t.get("confidence") or 0) >= 55
            and (t.get("reply_count") or 0) >= 6
        )
    ]
    return primes[:limit]


async def get_top5() -> list[dict]:
    feed = await get_hawk_feed(40)
    # already ranked by opportunity; take diverse top
    return feed[:5]


async def get_radar(kind: str) -> list[dict]:
    feed = await get_hawk_feed(40)
    if kind == "graduation":
        return [t for t in feed if t.get("signal") == "graduating" or (t.get("lifecycle") == "GRADUATING")][:15]
    if kind == "momentum":
        return [
            t
            for t in feed
            if (t.get("velocity") or {}).get("mcap_accelerating")
            or (t.get("velocity") or {}).get("reply_accelerating")
            or (t.get("momentum_score") or 0) >= 55
        ][:15]
    if kind == "risk":
        return sorted(feed, key=lambda x: -(x.get("rug_risk") or 0))[:15]
    if kind == "early":
        return [t for t in feed if (t.get("age_minutes") or 999) <= 30 and t.get("stage") == "bonding"][:15]
    return feed[:15]


async def get_stats() -> dict[str, Any]:
    feed = await get_hawk_feed(40)
    return {
        "total": len(feed),
        "on_curve": sum(1 for t in feed if t.get("stage") == "bonding"),
        "prime": sum(1 for t in feed if t.get("signal") == "prime"),
        "high": sum(1 for t in feed if t.get("signal") == "high"),
        "graduating": sum(1 for t in feed if t.get("signal") == "graduating" or t.get("lifecycle") == "GRADUATING"),
        "high_risk": sum(1 for t in feed if (t.get("rug_risk") or 0) >= 55),
        "early_entry": sum(1 for t in feed if t.get("entry_state") == "EARLY_ENTRY"),
        "updated_at": int(time.time()),
        "version": _settings.version,
    }
