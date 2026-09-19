"""
Helius Solana provider — optional.

When HELIUS_API_KEY is set, Hawk can fetch:
- Top holder accounts (getTokenLargestAccounts) → concentration
- Basic supply context

Without a key, all functions return data_quality=INSUFFICIENT_DATA
and never raise into the request path.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


def _rpc_url() -> str | None:
    key = (get_settings().helius_api_key or "").strip()
    if not key:
        return None
    return f"https://mainnet.helius-rpc.com/?api-key={key}"


async def _rpc(method: str, params: list | dict) -> Any | None:
    url = _rpc_url()
    if not url:
        return None
    payload = {"jsonrpc": "2.0", "id": "hawk", "method": method, "params": params}
    try:
        async with httpx.AsyncClient(timeout=18.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("error"):
                return None
            return data.get("result")
    except Exception:
        return None


async def get_largest_holders(mint: str, limit: int = 20) -> dict[str, Any]:
    """
    Top holder accounts by balance for a mint.
    Returns concentration metrics or INSUFFICIENT_DATA.
    """
    if not mint:
        return {"data_quality": "INSUFFICIENT_DATA", "reason": "no_mint"}

    if not _rpc_url():
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "reason": "HELIUS_API_KEY not configured",
            "holder_count_top": None,
            "top1_pct": None,
            "top10_pct": None,
            "top20_pct": None,
        }

    result = await _rpc("getTokenLargestAccounts", [mint])
    if not result or not isinstance(result, dict):
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "reason": "helius_rpc_failed_or_empty",
            "holder_count_top": None,
            "top1_pct": None,
            "top10_pct": None,
            "top20_pct": None,
        }

    accounts = result.get("value") or []
    if not accounts:
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "reason": "no_holder_accounts",
            "holder_count_top": 0,
            "top1_pct": None,
            "top10_pct": None,
            "top20_pct": None,
        }

    # amounts are UI amounts as strings in some responses; prefer uiAmount
    amounts: list[float] = []
    for a in accounts[:limit]:
        ui = a.get("uiAmount")
        if ui is None:
            # fallback raw amount (not decimals-adjusted) — still ok for ratios
            try:
                amounts.append(float(a.get("amount") or 0))
            except (TypeError, ValueError):
                amounts.append(0.0)
        else:
            try:
                amounts.append(float(ui))
            except (TypeError, ValueError):
                amounts.append(0.0)

    total = sum(amounts) or 1.0
    top1 = amounts[0] / total * 100 if amounts else 0.0
    top10 = sum(amounts[:10]) / total * 100 if amounts else 0.0
    top20 = sum(amounts[:20]) / total * 100 if amounts else 0.0

    # Heuristic quality score 0-100 (lower concentration = healthier for memes)
    # Note: top accounts include bonding curve / pool ATAs — interpret cautiously
    score = 55
    flags: list[str] = []
    if top1 >= 50:
        score -= 30
        flags.append("top1_dominant")
    elif top1 >= 30:
        score -= 18
        flags.append("top1_elevated")
    elif top1 >= 20:
        score -= 8
    else:
        score += 10

    if top10 >= 90:
        score -= 25
        flags.append("top10_highly_concentrated")
    elif top10 >= 75:
        score -= 12
        flags.append("top10_concentrated")
    elif top10 < 50:
        score += 12
        flags.append("top10_relatively_dispersed")

    score = max(0, min(100, score))

    return {
        "data_quality": "OK",
        "source": "helius:getTokenLargestAccounts",
        "holder_count_top": len(amounts),
        "top1_pct": round(top1, 2),
        "top10_pct": round(top10, 2),
        "top20_pct": round(top20, 2),
        "holder_quality_score": score,
        "flags": flags,
        "note": "Top accounts may include bonding-curve/pool ATAs; treat as directional",
    }


async def enrich_holders(tokens: list[dict], max_tokens: int = 12) -> None:
    """Mutates top tokens in-place with holder_intel when Helius is configured."""
    if not _rpc_url():
        for t in tokens:
            t.setdefault(
                "holder_intel",
                {
                    "data_quality": "INSUFFICIENT_DATA",
                    "reason": "HELIUS_API_KEY not configured",
                },
            )
        return

    import asyncio

    subset = tokens[:max_tokens]
    results = await asyncio.gather(
        *[get_largest_holders(t.get("address") or "") for t in subset],
        return_exceptions=True,
    )
    for t, res in zip(subset, results):
        if isinstance(res, dict):
            t["holder_intel"] = res
        else:
            t["holder_intel"] = {
                "data_quality": "INSUFFICIENT_DATA",
                "reason": "holder_fetch_error",
            }
