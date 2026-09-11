"""
HAWK service — orchestration + light caching.
"""

from __future__ import annotations

import time
from typing import Any

from cachetools import TTLCache

from app.config import get_settings
from app.discovery.aggregator import discover_opportunities
from app.scoring.engine import rank_tokens

_settings = get_settings()
_cache: TTLCache = TTLCache(maxsize=8, ttl=_settings.cache_ttl_seconds)


async def get_hawk_feed(limit: int = 30) -> list[dict]:
    cache_key = f"hawk:{limit}"
    if cache_key in _cache:
        return _cache[cache_key]

    raw = await discover_opportunities(limit=limit + 15, enrich=True)
    ranked = rank_tokens(raw)[:limit]

    # Clean payload for frontend
    feed = []
    for t in ranked:
        feed.append(
            {
                "ticker": t.get("ticker"),
                "name": t.get("name"),
                "address": t.get("address"),
                "source": t.get("source"),
                "stage": t.get("stage"),
                "alpha_score": t.get("alpha_score"),
                "confidence": t.get("confidence"),
                "rating": t.get("rating"),
                "recommendation": t.get("recommendation"),
                "reasons": t.get("reasons") or [],
                "risk_flags": t.get("risk_flags") or [],
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
                "scanned_at": int(time.time()),
            }
        )

    _cache[cache_key] = feed
    return feed


async def get_stats() -> dict[str, Any]:
    feed = await get_hawk_feed(40)
    bonding = sum(1 for t in feed if t.get("stage") == "bonding")
    prime = sum(1 for t in feed if (t.get("alpha_score") or 0) >= 82)
    high = sum(1 for t in feed if 70 <= (t.get("alpha_score") or 0) < 82)
    return {
        "total": len(feed),
        "on_curve": bonding,
        "prime": prime,
        "high": high,
        "updated_at": int(time.time()),
    }
