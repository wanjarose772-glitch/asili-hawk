"""
DexScreener enrichment + primary fallback discovery when Pump is blocked.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.config import get_settings

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AsiliHawk/2.4; +https://asili-hawk)",
    "Accept": "application/json",
}


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


async def enrich_token(address: str) -> dict:
    settings = get_settings()
    url = f"{settings.dexscreener_base}/tokens/v1/solana/{address}"
    async with httpx.AsyncClient(timeout=12.0, headers=_HEADERS) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {}
            pairs = resp.json()
            if not isinstance(pairs, list) or not pairs:
                return {}
        except Exception:
            return {}

    pairs = sorted(
        pairs,
        key=lambda p: _safe_float(p.get("liquidity", {}).get("usd")),
        reverse=True,
    )
    best = pairs[0]
    liq = _safe_float(best.get("liquidity", {}).get("usd"))
    vol_h1 = _safe_float((best.get("volume") or {}).get("h1"))
    vol_h6 = _safe_float((best.get("volume") or {}).get("h6"))
    vol_h24 = _safe_float((best.get("volume") or {}).get("h24"))
    vol = vol_h1 or vol_h6 or vol_h24
    tx_h1 = best.get("txns", {}).get("h1") or {}
    buys_h1 = int(tx_h1.get("buys") or 0)
    sells_h1 = int(tx_h1.get("sells") or 0)
    chg_h1 = _safe_float((best.get("priceChange") or {}).get("h1"))
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
        "volume_h1": vol_h1,
        "volume_h6": vol_h6,
        "buys_h1": buys_h1,
        "sells_h1": sells_h1,
        "price_change_h1": chg_h1,
        "market_cap": mcap or None,
        "dex": best.get("dexId"),
        "pair_address": best.get("pairAddress"),
        "age_minutes_dex": age_min,
        "price_change_m5": _safe_float(best.get("priceChange", {}).get("m5")),
        "url": best.get("url"),
    }


def _pair_to_token(pair: dict, *, channel: str = "active") -> dict | None:
    settings = get_settings()
    if pair.get("chainId") and pair.get("chainId") != "solana":
        return None
    base = pair.get("baseToken") or {}
    symbol = (base.get("symbol") or "").upper().strip()
    address = (base.get("address") or "").strip()
    if not symbol or not address or len(address) < 32:
        return None
    if symbol in {"SOL", "USDC", "USDT", "WSOL", "BONK", "JUP", "WIF", "RAY", "MSOL"}:
        return None

    created = pair.get("pairCreatedAt")
    age_min = None
    if created:
        age_min = (time.time() * 1000 - created) / 60_000
    max_age = max(settings.max_age_minutes, getattr(settings, "active_max_age_minutes", 1440))
    if age_min is not None and age_min > max_age:
        return None

    liq = _safe_float((pair.get("liquidity") or {}).get("usd"))
    vol_h1 = _safe_float((pair.get("volume") or {}).get("h1"))
    vol = vol_h1 or _safe_float((pair.get("volume") or {}).get("h24"))
    mcap = _safe_float(pair.get("marketCap") or pair.get("fdv"))
    max_mcap = getattr(settings, "active_max_usd_mcap", 3_000_000)
    if mcap > max_mcap:
        return None
    if liq and liq < 1_000:
        return None

    tx_h1 = (pair.get("txns") or {}).get("h1") or {}
    return {
        "source": "dexscreener",
        "discovery_channel": channel,
        "stage": "graduated",
        "ticker": symbol,
        "symbol": symbol,
        "name": base.get("name") or symbol,
        "address": address,
        "price_usd": _safe_float(pair.get("priceUsd")),
        "market_cap": round(mcap, 2),
        "liquidity": round(liq, 2),
        "volume": round(vol, 2),
        "volume_h1": vol_h1,
        "buys_h1": int(tx_h1.get("buys") or 0),
        "sells_h1": int(tx_h1.get("sells") or 0),
        "age_minutes": round(age_min, 1) if age_min is not None else None,
        "dex": pair.get("dexId"),
        "curve_progress": 100.0,
        "complete": True,
        "reply_count": 0,
        "image": None,
        "twitter": "",
        "website": "",
        "description": "",
        "url": pair.get("url"),
        "price_change_h1": _safe_float((pair.get("priceChange") or {}).get("h1")),
        "price_change_m5": _safe_float((pair.get("priceChange") or {}).get("m5")),
    }


async def _search_pairs(client: httpx.AsyncClient, q: str) -> list[dict]:
    settings = get_settings()
    url = f"{settings.dexscreener_base}/latest/dex/search"
    try:
        resp = await client.get(url, params={"q": q})
        if resp.status_code != 200:
            return []
        return resp.json().get("pairs") or []
    except Exception:
        return []


async def _boosted_and_profiles(client: httpx.AsyncClient) -> list[dict]:
    """token-boosts + latest profiles → resolve via /tokens/v1/solana/{mint}."""
    mints: list[str] = []
    for path in (
        "https://api.dexscreener.com/token-boosts/top/v1",
        "https://api.dexscreener.com/token-profiles/latest/v1",
    ):
        try:
            resp = await client.get(path)
            if resp.status_code != 200:
                continue
            data = resp.json()
            items = data if isinstance(data, list) else []
            for it in items:
                if (it.get("chainId") or "").lower() != "solana":
                    continue
                addr = it.get("tokenAddress") or ""
                if addr and len(addr) >= 32:
                    mints.append(addr)
        except Exception:
            continue

    # unique preserve order
    seen = set()
    uniq = []
    for m in mints:
        if m not in seen:
            seen.add(m)
            uniq.append(m)

    tokens: list[dict] = []
    for mint in uniq[:30]:
        extra = await enrich_token(mint)
        if not extra or not extra.get("market_cap"):
            # still try minimal from enrich
            pass
        # re-fetch pair list for symbol
        url = f"{get_settings().dexscreener_base}/tokens/v1/solana/{mint}"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                continue
            pairs = resp.json()
            if not isinstance(pairs, list) or not pairs:
                continue
            pairs = sorted(pairs, key=lambda p: _safe_float((p.get("liquidity") or {}).get("usd")), reverse=True)
            tok = _pair_to_token(pairs[0], channel="active")
            if tok:
                # merge enrich volume
                for k in ("volume", "volume_h1", "buys_h1", "sells_h1", "price_change_h1"):
                    if extra.get(k):
                        tok[k] = extra[k]
                tokens.append(tok)
        except Exception:
            continue
    return tokens


async def discover_new_solana_pairs(limit: int = 40) -> list[dict]:
    """Multi-query search + boosts/profiles — works when Pump is 403."""
    settings = get_settings()
    queries = ["SOL", "pump", "meme", "ai", "cat", "dog"]
    results: list[dict] = []
    seen: set[str] = set()

    async with httpx.AsyncClient(timeout=18.0, headers=_HEADERS) as client:
        search_lists = await asyncio.gather(*[_search_pairs(client, q) for q in queries])
        pairs: list[dict] = []
        for lst in search_lists:
            pairs.extend(lst)

        for pair in pairs:
            tok = _pair_to_token(pair, channel="active")
            if not tok:
                continue
            addr = tok["address"]
            if addr in seen:
                continue
            seen.add(addr)
            results.append(tok)

        # boosts / profiles fill runners
        try:
            boosted = await _boosted_and_profiles(client)
            for tok in boosted:
                addr = tok["address"]
                if addr in seen:
                    continue
                seen.add(addr)
                results.append(tok)
        except Exception:
            pass

    results.sort(
        key=lambda t: (
            0 if (t.get("volume_h1") or 0) >= 10_000 else 1,
            -(t.get("volume_h1") or t.get("volume") or 0),
            -(t.get("market_cap") or 0),
        )
    )
    return results[:limit]
