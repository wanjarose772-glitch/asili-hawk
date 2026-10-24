"""GeckoTerminal Solana new pools — extra discovery channel (from AIE-core)."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from app.config import get_settings

GECKO_URL = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"


def _f(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


async def fetch_gecko_new_pools(limit: int = 25) -> list[dict]:
    """Return normalized tokens from GeckoTerminal new Solana pools."""
    settings = get_settings()
    out: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=18.0) as client:
            resp = await client.get(
                GECKO_URL,
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return []
            payload = resp.json()
    except Exception:
        return []

    pools = payload.get("data") or []
    included = payload.get("included") or []
    token_lookup = {}
    for item in included:
        if item.get("type") == "token":
            token_lookup[item.get("id")] = item.get("attributes") or {}

    now_ms = time.time() * 1000
    for pool in pools[: limit * 2]:
        attrs = pool.get("attributes") or {}
        rel = pool.get("relationships") or {}
        base = (rel.get("base_token") or {}).get("data") or {}
        token = token_lookup.get(base.get("id"), {})
        pool_name = attrs.get("name") or ""
        fallback = pool_name.split("/")[0].strip() if "/" in pool_name else "UNK"
        symbol = (token.get("symbol") or fallback or "UNK")[:16]
        name = (token.get("name") or fallback)[:48]
        address = (token.get("address") or "").strip()
        if not address or len(address) < 32:
            # sometimes base id embeds address
            bid = base.get("id") or ""
            if "solana_" in str(bid):
                address = str(bid).split("solana_")[-1]
        if not address or len(address) < 32:
            continue

        mcap = _f(attrs.get("fdv_usd") or attrs.get("market_cap_usd"))
        liq = _f(attrs.get("reserve_in_usd"))
        vol = _f(attrs.get("volume_usd", {}).get("h24") if isinstance(attrs.get("volume_usd"), dict) else attrs.get("volume_usd"))
        created = attrs.get("pool_created_at")
        age_min = None
        if created:
            try:
                # ISO format
                ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp() * 1000
                age_min = (now_ms - ts) / 60000
            except Exception:
                age_min = None
        if age_min is not None and age_min > getattr(settings, "active_max_age_minutes", 1440):
            continue
        if mcap > getattr(settings, "active_max_usd_mcap", 2_000_000):
            continue

        out.append({
            "source": "geckoterminal",
            "discovery_channel": "active",
            "stage": "graduated",
            "ticker": symbol.upper(),
            "symbol": symbol.upper(),
            "name": name,
            "address": address,
            "creator": None,
            "price_usd": _f(attrs.get("base_token_price_usd")) or None,
            "market_cap": round(mcap, 2),
            "liquidity": round(liq, 2),
            "volume": round(vol, 2),
            "volume_h1": 0,
            "reply_count": 0,
            "curve_progress": 100.0,
            "complete": True,
            "age_minutes": round(age_min, 1) if age_min is not None else None,
            "twitter": "",
            "website": "",
            "telegram": "",
            "description": f"Gecko new pool {pool_name}"[:280],
            "is_live": False,
        })
        if len(out) >= limit:
            break
    return out
