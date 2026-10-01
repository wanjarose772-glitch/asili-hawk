"""
Convergence engine — answers:

Which assets show the strongest convergence of early structure,
developer history, narrative, social, liquidity, and holder quality?
"""

from __future__ import annotations

from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def score_convergence(
    token: dict,
    *,
    developer: dict,
    patterns: dict,
    narrative: dict,
    organicity: dict,
    liquidity: dict,
    wash: dict,
    holder_intel: dict | None,
) -> dict:
    replies = int(token.get("reply_count") or 0)
    age = max(_f(token.get("age_minutes"), 0.1), 0.1)
    mcap = _f(token.get("market_cap"))

    # Channel scores 0-100
    # 1) Early wallet / flow proxy
    flow = 50
    wscore = wash.get("wash_score")
    if wscore is not None:
        flow = max(0, 100 - int(wscore))
    if patterns.get("pattern_net"):
        flow = int(max(0, min(100, flow + int(patterns["pattern_net"]) * 0.4)))

    # 2) Developer
    dev = int(developer.get("developer_score") or 50)

    # 3) Narrative
    narr = int(narrative.get("narrative_score") or 40)

    # 4) Social acceleration proxy
    social = 25
    if replies >= 20:
        social = 80
    elif replies >= 10:
        social = 68
    elif replies >= 5:
        social = 55
    elif replies >= 2:
        social = 40
    if token.get("is_live"):
        social = min(100, social + 12)
    if token.get("twitter") and replies >= 3:
        social = min(100, social + 8)
    # acceleration: replies per minute soft
    rpm = replies / age
    if rpm >= 1.0 and age <= 45:
        social = min(100, social + 10)

    # 5) Liquidity
    liq = int(liquidity.get("liquidity_score") or 40)

    # 6) Holders
    holders = 45
    hi = holder_intel if isinstance(holder_intel, dict) else {}
    top1 = hi.get("top1_pct")
    if top1 is None:
        top1 = token.get("holder_top1_pct")
    if hi.get("data_quality") == "OK" or top1 is not None:
        top1 = _f(top1, 50)
        if top1 >= 80:
            holders = 15
        elif top1 >= 60:
            holders = 30
        elif top1 >= 45:
            holders = 45
        elif top1 >= 25:
            holders = 70
        else:
            holders = 75
    else:
        holders = 40  # unknown

    # Structure from patterns
    structure = int(patterns.get("pattern_score") or 50)

    channels = {
        "flow": {"score": flow, "data_quality": wash.get("data_quality") or "LIMITED"},
        "developer": developer,
        "narrative": {"score": narr},
        "social": {"score": social},
        "liquidity": {"score": liq, **liquidity},
        "holders": {
            "score": holders,
            "data_quality": "OK" if top1 is not None or hi.get("data_quality") == "OK" else "INSUFFICIENT_DATA",
        },
        "structure": {"pattern_score": structure, "score": structure},
    }

    # Weighted convergence (independent-ish channels)
    raw = (
        flow * 0.16
        + dev * 0.14
        + narr * 0.10
        + social * 0.18
        + liq * 0.12
        + holders * 0.16
        + structure * 0.14
    )
    convergence = int(max(0, min(100, round(raw))))

    # Agreement: how many channels are constructively above 55
    above = sum(
        1
        for k, w in [
            ("flow", flow),
            ("developer", dev),
            ("social", social),
            ("liquidity", liq),
            ("holders", holders),
            ("structure", structure),
        ]
        if w >= 55
    )
    below = sum(
        1
        for w in (flow, dev, social, liq, holders, structure)
        if w < 35
    )

    if above >= 4 and below == 0:
        label = "STRONG_CONVERGENCE"
    elif above >= 3:
        label = "MODERATE_CONVERGENCE"
    elif above >= 2:
        label = "WEAK_CONVERGENCE"
    else:
        label = "DIVERGENT_OR_THIN"

    return {
        "convergence_score": convergence,
        "convergence_label": label,
        "channels": {
            "flow": flow,
            "developer": dev,
            "narrative": narr,
            "social": social,
            "liquidity": liq,
            "holders": holders,
            "structure": structure,
        },
        "channels_above_55": above,
        "channel_detail": channels,
    }
