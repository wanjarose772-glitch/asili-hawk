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
from app.discovery.geckoterminal import fetch_gecko_new_pools
from app.providers.helius import enrich_holders, enrich_tx_intel


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
    gecko_task = fetch_gecko_new_pools(limit=20)

    pump_tokens, dex_tokens, gecko_tokens = await asyncio.gather(
        pump_task, dex_task, gecko_task
    )

    # Pump.fun first — that is the pre-terminal edge
    merged: list[dict] = []
    seen: set[str] = set()

    for t in pump_tokens:
        addr = t["address"]
        if addr in seen:
            continue
        seen.add(addr)
        merged.append(t)

    for t in list(dex_tokens) + list(gecko_tokens or []):
        addr = t["address"]
        if addr in seen:
            continue
        seen.add(addr)
        merged.append(t)

    if enrich and merged:
        # Enrich top candidates with live DexScreener stats (price, vol, liq)
        # Prefer active/graduated names for volume (CLOVER-class)
        ranked = sorted(
            [t for t in merged if t.get("source") in ("pump.fun", "geckoterminal", "dexscreener")],
            key=lambda x: (
                0 if x.get("discovery_channel") == "active" else 1,
                0 if x.get("complete") else 1,
                -(x.get("market_cap") or 0),
            ),
        )
        to_enrich = ranked[:35]
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
                    for k in ("volume_h1", "volume_h6", "buys_h1", "sells_h1", "price_change_h1"):
                        if extra.get(k) is not None:
                            token[k] = extra[k]
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

    try:
        # Tx sample only for top candidates (wash / organicity)
        await enrich_tx_intel(merged, max_tokens=min(8, len(merged)))
    except Exception:
        pass

    return merged[:limit]
