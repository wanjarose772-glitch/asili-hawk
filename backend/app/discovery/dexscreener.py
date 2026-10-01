"""
DexScreener enrichment + early pair discovery.
Used as secondary signal once tokens appear on terminals,
and to enrich Pump.fun tokens with price/volume/liquidity.
"""

from __future__ import annotations

import time
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


async def enrich_token(address: str) -> dict:
    """Pull latest DexScreener data for a mint."""
    settings = get_settings()
    url = f"{settings.dexscreener_base}/tokens/v1/solana/{address}"

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {}
            pairs = resp.json()
            if not isinstance(pairs, list) or not pairs:
                return {}
        except Exception:
            return {}

    # Prefer highest-liquidity pair
    pairs = sorted(
        pairs,
        key=lambda p: _safe_float(p.get("liquidity", {}).get("usd")),
        reverse=True,
    )
    best = pairs[0]

    liq = _safe_float(best.get("liquidity", {}).get("usd"))
    vol = _safe_float(best.get("volume", {}).get("h24") or best.get("volume", {}).get("h6"))
    price = _safe_float(best.get("priceUsd"))
    mcap = _safe_float(best.get("marketCap") or best.get("fdv"))
    created = best.get("pairCreatedAt")
    age_min = None
    if created:
        age_min = round((time.time() * 1000 - created) / 60_000, 1)

    return {
        "price_usd": price,
        "liquidity": liq,
        "volume": vol,
        "market_cap": mcap or None,
        "dex": best.get("dexId"),
        "pair_address": best.get("pairAddress"),
        "age_minutes_dex": age_min,
        "price_change_m5": _safe_float(best.get("priceChange", {}).get("m5")),
        "price_change_h1": _safe_float(best.get("priceChange", {}).get("h1")),
        "txns_m5": (best.get("txns", {}).get("m5") or {}),
        "url": best.get("url"),
    }


async def discover_new_solana_pairs(limit: int = 30) -> list[dict]:
    """
    Lightweight new-pair scan via DexScreener search.
    Not as early as Pump.fun bonding curve, but useful for
    just-graduated or other launchpad tokens.
    """
    settings = get_settings()
    # Broad search that surfaces recent Solana activity
    url = f"{settings.dexscreener_base}/latest/dex/search"
    params = {"q": "SOL"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            pairs = data.get("pairs") or []
        except Exception:
            return []

    now_ms = time.time() * 1000
    results = []
    seen = set()

    for pair in pairs:
        if pair.get("chainId") != "solana":
            continue
        base = pair.get("baseToken") or {}
        symbol = (base.get("symbol") or "").upper()
        address = base.get("address") or ""
        if not symbol or not address or address in seen:
            continue
        if symbol in {"SOL", "USDC", "USDT", "WSOL", "BONK", "JUP", "WIF"}:
            continue

        created = pair.get("pairCreatedAt")
        if not created:
            continue
        age_min = (now_ms - created) / 60_000
        if age_min > settings.max_age_minutes:
            continue

        liq = _safe_float(pair.get("liquidity", {}).get("usd"))
        vol = _safe_float(pair.get("volume", {}).get("h24"))
        mcap = _safe_float(pair.get("marketCap") or pair.get("fdv"))

        if liq < 3_000 or liq > 400_000:
            continue
        if mcap > 0 and mcap > settings.max_usd_mcap * 1.5:
            continue

        seen.add(address)
        results.append(
            {
                "source": "dexscreener",
                "stage": "listed",
                "ticker": symbol,
                "symbol": symbol,
                "name": base.get("name") or symbol,
                "address": address,
                "price_usd": _safe_float(pair.get("priceUsd")),
                "market_cap": round(mcap, 2),
                "liquidity": round(liq, 2),
                "volume": round(vol, 2),
                "age_minutes": round(age_min, 1),
                "dex": pair.get("dexId"),
                "curve_progress": 100.0,
                "complete": True,
                "reply_count": 0,
                "image": None,
                "twitter": "",
                "website": "",
                "description": "",
                "url": pair.get("url"),
            }
        )

    results.sort(key=lambda t: t.get("age_minutes") or 9999)
    return results[:limit]
