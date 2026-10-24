"""
Pump.fun discovery — hybrid.

When Pump returns 403 (common from cloud IPs), we soft-fail and let
DexScreener / Gecko fill the feed. Browser-like headers + multi-base retry.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://pump.fun",
    "Referer": "https://pump.fun/",
}

_BASES = (
    "https://frontend-api-v3.pump.fun",
    "https://frontend-api.pump.fun",
)


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

    max_age = settings.max_age_minutes
    if channel == "active":
        max_age = max(settings.max_age_minutes, getattr(settings, "active_max_age_minutes", 1440))
    if age_minutes is not None and age_minutes > max_age:
        return None

    max_mcap = settings.max_usd_mcap
    if channel == "active":
        max_mcap = max(max_mcap, getattr(settings, "active_max_usd_mcap", 2_000_000))
    if mcap > max_mcap:
        return None
    if channel == "new" and mcap > 0 and mcap < 500:
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
    base: str,
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
        for attempt in range(2):
            try:
                resp = await client.get(f"{base}/coins", params=params, headers=_BROWSER_HEADERS)
                if resp.status_code == 403 or resp.status_code == 401:
                    return []  # blocked — abort this base
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
                if attempt == 1:
                    break
                await asyncio.sleep(0.3)
        if not ok:
            break
    return raw


async def fetch_pumpfun_launches(limit: int = 50) -> list[dict]:
    """Hybrid Pump discovery; returns [] if all bases are blocked (403)."""
    settings = get_settings()
    new_raw: list[dict] = []
    active_raw: list[dict] = []

    async with httpx.AsyncClient(timeout=18.0, follow_redirects=True) as client:
        for base in _BASES:
            nr, ar = await asyncio.gather(
                _fetch_pages(client, base, "created_timestamp", pages=2),
                _fetch_pages(client, base, "last_trade_timestamp", pages=3),
            )
            if nr or ar:
                new_raw, active_raw = nr, ar
                break

    results: list[dict] = []
    seen: set[str] = set()

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

    def sort_key(t: dict):
        mcap = t.get("market_cap") or 0
        replies = t.get("reply_count") or 0
        channel = t.get("discovery_channel")
        if channel == "active" and mcap >= 20_000:
            return (0, -mcap, -replies)
        if replies >= 3:
            return (1, -replies, -mcap)
        return (2, -(t.get("age_minutes") or 0), -mcap)

    results.sort(key=sort_key)
    return results[:limit]
