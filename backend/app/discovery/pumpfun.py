"""
Early Pump.fun discovery.

Goal: surface tokens that are still on the bonding curve
(complete=False) so HAWK can score them before graduation
and before they flood DexScreener / terminals.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def estimate_curve_progress(coin: dict) -> float:
    """
    Approximate bonding-curve progress (0-100).

    Pump.fun starts with ~793.1M real token reserves available for sale
    out of 1B total supply. Progress ≈ how much of those have been bought.
    """
    real_token = _safe_float(coin.get("real_token_reserves"))
    # Fallback when reserves missing
    if real_token <= 0:
        # Use market-cap heuristic: graduation historically ~$60k-$100k
        mcap = _safe_float(coin.get("usd_market_cap") or coin.get("market_cap"))
        if mcap <= 0:
            return 0.0
        return min(99.0, (mcap / 85_000.0) * 100.0)

    initial_real = 793_100_000_000_000  # typical initial real_token_reserves (lamports style)
    # Some responses use different scale; normalize by total_supply if present
    total = _safe_float(coin.get("total_supply"), 1_000_000_000_000_000)
    if total > 0 and real_token > total:
        # already in different unit
        pass

    # Progress = 100 - (remaining / initial) * 100
    remaining_ratio = real_token / max(initial_real, 1)
    progress = max(0.0, min(99.9, (1.0 - remaining_ratio) * 100.0))
    return round(progress, 2)


def normalize_coin(coin: dict) -> dict | None:
    settings = get_settings()
    symbol = (coin.get("symbol") or "").strip()
    name = (coin.get("name") or "").strip()
    mint = coin.get("mint") or ""

    if not symbol or not mint:
        return None

    complete = bool(coin.get("complete"))
    mcap = _safe_float(coin.get("usd_market_cap") or coin.get("market_cap"))
    created_ts = coin.get("created_timestamp")  # ms

    age_minutes = None
    if created_ts:
        try:
            age_minutes = (time.time() * 1000 - float(created_ts)) / 60_000
        except (TypeError, ValueError):
            age_minutes = None

    curve_progress = 100.0 if complete else estimate_curve_progress(coin)

    # Hard early-edge filters
    if complete:
        # Still useful as "just graduated" but secondary
        stage = "graduated"
    else:
        stage = "bonding"

    if age_minutes is not None and age_minutes > settings.max_age_minutes:
        return None
    if mcap > 0 and (mcap < settings.min_usd_mcap or mcap > settings.max_usd_mcap):
        return None
    if stage == "bonding" and (
        curve_progress < settings.min_curve_progress
        or curve_progress > settings.max_curve_progress
    ):
        return None

    real_sol = _safe_float(coin.get("real_sol_reserves") or coin.get("real_quote_reserves"))
    # Convert lamports-ish to SOL if needed
    if real_sol > 1_000_000:
        real_sol = real_sol / 1e9

    return {
        "source": "pump.fun",
        "stage": stage,
        "ticker": symbol.upper(),
        "symbol": symbol.upper(),
        "name": name,
        "address": mint,
        "creator": coin.get("creator"),
        "price_usd": None,  # filled later if needed
        "market_cap": round(mcap, 2),
        "liquidity": round(real_sol * 150, 2) if real_sol else 0,  # rough SOL*price proxy
        "volume": 0,  # not always present on this endpoint
        "reply_count": int(coin.get("reply_count") or 0),
        "curve_progress": curve_progress,
        "complete": complete,
        "age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
        "created_at": (
            datetime.fromtimestamp(created_ts / 1000, tz=timezone.utc).isoformat()
            if created_ts
            else None
        ),
        "image": coin.get("image_uri"),
        "twitter": coin.get("twitter") or "",
        "website": coin.get("website") or "",
        "telegram": coin.get("telegram") or "",
        "description": (coin.get("description") or "")[:280],
        "is_live": bool(coin.get("is_currently_live")),
        "raw_created_ts": created_ts,
    }


async def fetch_pumpfun_launches(limit: int = 50) -> list[dict]:
    """Fetch newest Pump.fun coins (still mostly on curve)."""
    settings = get_settings()
    url = f"{settings.pumpfun_base}/coins"
    params = {
        "offset": 0,
        "limit": min(limit, 50),
        "sort": "created_timestamp",
        "order": "DESC",
        "includeNsfw": "false",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
        except Exception:
            return []

    results = []
    seen = set()
    for coin in data:
        normalized = normalize_coin(coin)
        if not normalized:
            continue
        addr = normalized["address"]
        if addr in seen:
            continue
        seen.add(addr)
        results.append(normalized)

    # Prefer still-on-curve, then youngest
    results.sort(
        key=lambda t: (
            0 if t["stage"] == "bonding" else 1,
            t.get("age_minutes") or 9999,
        )
    )
    return results


def fetch_pumpfun_launches_sync(limit: int = 50) -> list[dict]:
    """Sync wrapper for scripts / tests."""
    import asyncio

    return asyncio.run(fetch_pumpfun_launches(limit))
