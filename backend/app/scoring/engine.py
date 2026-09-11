"""
ASILI HAWK Scoring Engine v0.3

Designed specifically for early memecoin detection:
- Heavy weight on still-on-curve + early momentum
- Penalizes obvious rugs / zero activity
- Produces alpha_score, rating, recommendation, reasons
"""

from __future__ import annotations

from typing import Any


EXCLUDED = {
    "SOL", "USDC", "USDT", "WSOL", "BTC", "ETH", "WBTC", "WETH",
    "JUP", "JTO", "BONK", "WIF", "RAY", "ORCA",
}

SUSPICIOUS = ("airdrop", "claim", "presale", "test", "scam", "rug", "honeypot")


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def safety_check(token: dict) -> tuple[bool, list[str]]:
    """Return (passed, flags)."""
    flags: list[str] = []
    symbol = (token.get("ticker") or token.get("symbol") or "").upper()
    name = (token.get("name") or "").lower()
    desc = (token.get("description") or "").lower()

    if not symbol or symbol in EXCLUDED:
        return False, ["excluded_symbol"]
    if any(s in name or s in symbol.lower() or s in desc for s in SUSPICIOUS):
        flags.append("suspicious_terms")
        return False, flags

    mcap = _f(token.get("market_cap"))
    if mcap > 0 and mcap < 500:
        flags.append("dust_mcap")
        return False, flags

    return True, flags


def score_token(token: dict) -> dict:
    """
    Core scoring. Higher = more interesting early opportunity.
    """
    passed, flags = safety_check(token)
    if not passed:
        return {
            "alpha_score": 0,
            "confidence": 0,
            "rating": "🚫 REJECT",
            "recommendation": "PASS",
            "reasons": flags,
            "risk_flags": flags,
            "stage": token.get("stage"),
        }

    score = 28.0  # base
    reasons: list[str] = []
    risk_flags: list[str] = list(flags)

    stage = token.get("stage") or "unknown"
    curve = _f(token.get("curve_progress"))
    age = _f(token.get("age_minutes"), 999)
    mcap = _f(token.get("market_cap"))
    liq = _f(token.get("liquidity"))
    vol = _f(token.get("volume"))
    replies = int(token.get("reply_count") or 0)
    has_twitter = bool(token.get("twitter"))
    has_website = bool(token.get("website"))
    is_live = bool(token.get("is_live"))
    chg_m5 = _f(token.get("price_change_m5"))

    # ---------- Stage / Curve (biggest early edge) ----------
    if stage == "bonding":
        score += 22
        reasons.append("Still on Pump.fun bonding curve")
        if 15 <= curve <= 70:
            score += 12
            reasons.append(f"Sweet-spot curve progress ({curve:.0f}%)")
        elif 70 < curve <= 92:
            score += 8
            reasons.append(f"Approaching graduation ({curve:.0f}%)")
        elif curve < 15:
            score += 4
            reasons.append("Very early on curve")
    elif stage == "graduated":
        score += 6
        reasons.append("Just graduated")
    else:
        score += 3

    # ---------- Age (fresher is better for pre-terminal) ----------
    if age <= 15:
        score += 14
        reasons.append(f"Brand new ({age:.0f}m)")
    elif age <= 45:
        score += 10
        reasons.append(f"Very fresh ({age:.0f}m)")
    elif age <= 90:
        score += 6
        reasons.append(f"Recent ({age:.0f}m)")
    elif age <= 180:
        score += 2
    else:
        score -= 8
        risk_flags.append("aging")

    # ---------- Market cap (prefer early but not dust) ----------
    if 1_500 <= mcap <= 25_000:
        score += 12
        reasons.append(f"Early mcap zone (${mcap:,.0f})")
    elif 25_000 < mcap <= 60_000:
        score += 9
        reasons.append(f"Mid-curve mcap (${mcap:,.0f})")
    elif 60_000 < mcap <= 100_000:
        score += 5
        reasons.append("Near graduation mcap")
    elif mcap > 150_000:
        score -= 6
        risk_flags.append("extended_mcap")

    # ---------- Activity ----------
    if replies >= 30:
        score += 8
        reasons.append(f"Strong replies ({replies})")
    elif replies >= 10:
        score += 5
        reasons.append(f"Active chat ({replies})")
    elif replies >= 3:
        score += 2

    if vol >= 50_000:
        score += 8
        reasons.append("High volume")
    elif vol >= 10_000:
        score += 5
        reasons.append("Solid volume")
    elif vol >= 2_000:
        score += 2

    if liq >= 15_000:
        score += 5
    elif liq >= 5_000:
        score += 3

    # ---------- Social / narrative hints ----------
    if has_twitter:
        score += 3
        reasons.append("Has Twitter")
    if has_website:
        score += 2
    if is_live:
        score += 4
        reasons.append("Live stream active")

    # ---------- Short-term momentum (if Dex data present) ----------
    if chg_m5 >= 15:
        score += 6
        reasons.append(f"+{chg_m5:.0f}% (5m)")
    elif chg_m5 >= 5:
        score += 3
    elif chg_m5 <= -20:
        score -= 5
        risk_flags.append("sharp_dump")

    # ---------- Final clamp ----------
    score = max(0, min(100, round(score)))

    # Rating bands
    if score >= 82:
        rating = "👑 ASILI PRIME"
        rec = "STRONG WATCH"
    elif score >= 70:
        rating = "🔷 ASILI HIGH"
        rec = "WATCH"
    elif score >= 58:
        rating = "⚡ ASILI SPEC"
        rec = "MONITOR"
    else:
        rating = "🔸 LOW"
        rec = "PASS"

    confidence = min(96, score + 4)

    return {
        "alpha_score": score,
        "confidence": confidence,
        "rating": rating,
        "recommendation": rec,
        "reasons": reasons[:8],
        "risk_flags": risk_flags,
        "stage": stage,
        "curve_progress": curve,
    }


def rank_tokens(tokens: list[dict]) -> list[dict]:
    """Score + sort descending by alpha_score."""
    scored = []
    for t in tokens:
        analysis = score_token(t)
        if analysis["alpha_score"] <= 0:
            continue
        row = {**t, **analysis}
        scored.append(row)

    scored.sort(key=lambda x: (-x["alpha_score"], x.get("age_minutes") or 999))
    return scored
