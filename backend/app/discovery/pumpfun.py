"""
Pump.fun discovery — hybrid.

CRITICAL LESSON (live ops):
Sorting only by created_timestamp shows the birth channel: sub-$20k, 0 replies.
Tokens that actually clear $100k+ show up on last_trade / graduated activity,
not in the newest-mint list. Jupiter reflects the active-trade universe.

We therefore fetch BOTH:
1) newest mints (early edge)
2) last_trade activity (runners / graduating / post-grad)
"""

from __future__ import annotations

import asyncio
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
    real_token = _safe_float(coin.get("real_token_reserves"))
    if real_token <= 0:
        mcap = _safe_float(coin.get("usd_market_cap") or coin.get("market_cap"))
        if mcap <= 0:
            return 0.0
        return min(99.0, (mcap / 85_000.0) * 100.0)

    initial_real = 793_100_000_000_000
    remaining_ratio = real_token / max(initial_real, 1)
    progress = max(0.0, min(99.9, (1.0 - remaining_ratio) * 100.0))
    return round(progress, 2)


def normalize_coin(coin: dict, *, channel: str = "new") -> dict | None:
    settings = get_settings()
    symbol = (coin.get("symbol") or "").strip()
    name = (coin.get("name") or "").strip()
    mint = coin.get("mint") or ""

    if not symbol or not mint:
        return None

    complete = bool(coin.get("complete"))
    mcap = _safe_float(coin.get("usd_market_cap") or coin.get("market_cap"))
    created_ts = coin.get("created_timestamp")

    age_minutes = None
    if created_ts:
        try:
            age_minutes = (time.time() * 1000 - float(created_ts)) / 60_000
        except (TypeError, ValueError):
            age_minutes = None

    curve_progress = 100.0 if complete else estimate_curve_progress(coin)
    stage = "graduated" if complete else "bonding"

    # Age windows differ by channel
    max_age = settings.max_age_minutes
    if channel == "active":
        max_age = max(settings.max_age_minutes, getattr(settings, "active_max_age_minutes", 1440))

    if age_minutes is not None and age_minutes > max_age:
        return None

    # Mcap bands — active channel allows higher (runners past 100k)
    max_mcap = settings.max_usd_mcap
    if channel == "active":
        max_mcap = max(max_mcap, getattr(settings, "active_max_usd_mcap", 2_000_000))

    if mcap > 0 and (mcap < settings.min_usd_mcap or mcap > max_mcap):
        return None

    if stage == "bonding" and (
        curve_progress < settings.min_curve_progress
        or curve_progress > settings.max_curve_progress
    ):
        return None

    if stage == "graduated" and age_minutes is not None:
        post_max = getattr(settings, "hybrid_postgrad_max", 180)
        if channel == "active":
            post_max = max(post_max, getattr(settings, "active_max_age_minutes", 1440))
        if age_minutes > post_max:
            return None

    real_sol = _safe_float(coin.get("real_sol_reserves") or coin.get("real_quote_reserves"))
    if real_sol > 1_000_000:
        real_sol = real_sol / 1e9

    return {
        "source": "pump.fun",
        "discovery_channel": channel,
        "stage": stage,
        "ticker": symbol.upper(),
        "symbol": symbol.upper(),
        "name": name,
        "address": mint,
        "creator": coin.get("creator"),
        "price_usd": None,
        "market_cap": round(mcap, 2),
        "liquidity": round(real_sol * 150, 2) if real_sol else 0,
        "volume": 0,
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


async def _fetch_pages(
    client: httpx.AsyncClient,
    url: str,
    sort: str,
    pages: int,
    page_size: int = 50,
) -> list[dict]:
    raw: list[dict] = []
    for page in range(pages):
        params = {
            "offset": page * page_size,
            "limit": page_size,
            "sort": sort,
            "order": "DESC",
            "includeNsfw": "false",
        }
        ok = False
        for attempt in range(3):
            try:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not isinstance(data, list):
                    break
                if not data:
                    ok = True
                    break
                raw.extend(data)
                ok = True
                break
            except Exception:
                if attempt == 2:
                    break
                await asyncio.sleep(0.4 * (attempt + 1))
        if not ok:
            break
    return raw


async def fetch_pumpfun_launches(limit: int = 50) -> list[dict]:
    """
    Hybrid discovery:
    - created_timestamp: brand-new launches (early radar)
    - last_trade_timestamp: actively traded / running tokens (what Jupiter-like boards show)
    """
    settings = get_settings()
    url = f"{settings.pumpfun_base}/coins"

    async with httpx.AsyncClient(timeout=22.0) as client:
        new_raw, active_raw = await asyncio.gather(
            _fetch_pages(client, url, "created_timestamp", pages=2),
            _fetch_pages(client, url, "last_trade_timestamp", pages=2),
        )

    results: list[dict] = []
    seen: set[str] = set()

    # Active / running first so survivors past 20–100k are in the pool
    for coin in active_raw:
        normalized = normalize_coin(coin, channel="active")
        if not normalized:
            continue
        addr = normalized["address"]
        if addr in seen:
            continue
        seen.add(addr)
        results.append(normalized)

    for coin in new_raw:
        normalized = normalize_coin(coin, channel="new")
        if not normalized:
            continue
        addr = normalized["address"]
        if addr in seen:
            continue
        seen.add(addr)
        results.append(normalized)

    def _pref(t: dict):
        age = t.get("age_minutes") or 9999
        replies = t.get("reply_count") or 0
        curve = t.get("curve_progress") or 0
        mcap = t.get("market_cap") or 0
        stage = t.get("stage")
        channel = t.get("discovery_channel")
        # Prefer active runners with real mcap, then emerging bonding with chat
        if channel == "active" and mcap >= 20_000:
            band = 0
        elif stage == "bonding" and 6 <= age <= 45 and replies >= 3:
            band = 1
        elif stage == "bonding" and curve >= 70:
            band = 2
        elif stage == "graduated" and mcap >= 50_000:
            band = 1
        elif stage == "bonding" and replies >= 1:
            band = 3
        else:
            band = 4
        return (band, -mcap, -replies, age)

    results.sort(key=_pref)
    return results[: max(limit, 80)]


def fetch_pumpfun_launches_sync(limit: int = 50) -> list[dict]:
    return asyncio.run(fetch_pumpfun_launches(limit))
