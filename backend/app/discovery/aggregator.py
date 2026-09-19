"""
Unified discovery layer.
Pulls early Pump.fun bonding-curve tokens (primary edge)
and optionally enriches / merges with DexScreener.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.discovery.pumpfun import fetch_pumpfun_launches
from app.discovery.dexscreener import enrich_token, discover_new_solana_pairs
from app.providers.helius import enrich_holders


async def discover_opportunities(
    limit: int = 40,
    enrich: bool = True,
) -> list[dict]:
    """
    Main discovery entrypoint.

    Priority:
    1. Pump.fun tokens still on bonding curve (true early edge)
    2. Very recent DexScreener Solana pairs (just listed / graduated)
    """
    pump_task = fetch_pumpfun_launches(limit=limit)
    dex_task = discover_new_solana_pairs(limit=20)

    pump_tokens, dex_tokens = await asyncio.gather(pump_task, dex_task)

    # Pump.fun first â€” that is the pre-terminal edge
    merged: list[dict] = []
    seen: set[str] = set()

    for t in pump_tokens:
        addr = t["address"]
        if addr in seen:
            continue
        seen.add(addr)
        merged.append(t)

    for t in dex_tokens:
        addr = t["address"]
        if addr in seen:
            continue
        seen.add(addr)
        merged.append(t)

    if enrich and merged:
        # Enrich top candidates with live DexScreener stats (price, vol, liq)
        to_enrich = [t for t in merged[:25] if t.get("source") == "pump.fun"]
        if to_enrich:
            enrich_results = await asyncio.gather(
                *[enrich_token(t["address"]) for t in to_enrich],
                return_exceptions=True,
            )
            for token, extra in zip(to_enrich, enrich_results):
                if isinstance(extra, dict) and extra:
                    if extra.get("price_usd"):
                        token["price_usd"] = extra["price_usd"]
                    if extra.get("liquidity") and extra["liquidity"] > 0:
                        token["liquidity"] = extra["liquidity"]
                    if extra.get("volume") and extra["volume"] > 0:
                        token["volume"] = extra["volume"]
                    if extra.get("market_cap") and (
                        not token.get("market_cap") or token["market_cap"] == 0
                    ):
                        token["market_cap"] = extra["market_cap"]
                    token["dex_url"] = extra.get("url")
                    token["price_change_m5"] = extra.get("price_change_m5")
                    token["price_change_h1"] = extra.get("price_change_h1")

    # Optional Helius holder concentration (no-op without API key)
    try:
        await enrich_holders(merged, max_tokens=min(12, len(merged)))
    except Exception:
        pass

    return merged[:limit]

