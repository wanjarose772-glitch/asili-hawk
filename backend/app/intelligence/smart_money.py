"""
Lightweight smart-money / distribution signal (AIE-inspired, public data only).

Uses Helius holder_intel when present. Does not claim labeled smart-money wallets
without a curated set.
"""

from __future__ import annotations

from typing import Any


def analyze_smart_money(token: dict) -> dict[str, Any]:
    hi = token.get("holder_intel") or {}
    if hi.get("data_quality") != "OK":
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "smart_money_score": 50,
            "label": "UNKNOWN",
            "notes": ["Need Helius holder enrichment"],
        }

    top1 = float(hi.get("top1_pct") or 0)
    top10 = float(hi.get("top10_pct") or 0)
    score = 55
    notes = []
    if top1 >= 40:
        score -= 25
        notes.append("extreme_top1_concentration")
    elif top1 >= 25:
        score -= 12
        notes.append("high_top1")
    elif top1 > 0 and top1 < 12:
        score += 10
        notes.append("distributed_top1")

    if top10 >= 80:
        score -= 15
        notes.append("top10_crowded")
    elif 0 < top10 < 50:
        score += 8
        notes.append("healthier_top10")

    score = int(max(0, min(100, score)))
    if score >= 65:
        label = "DISTRIBUTION_OK"
    elif score <= 40:
        label = "CONCENTRATED_RISK"
    else:
        label = "MIXED"
    return {
        "data_quality": "OK",
        "smart_money_score": score,
        "label": label,
        "top1_pct": top1,
        "top10_pct": top10,
        "notes": notes,
    }
