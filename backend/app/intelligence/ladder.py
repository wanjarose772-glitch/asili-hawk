"""
ASILI HAWK opportunity ladder — private operator tune.

Legal public data only.
Ladder: LOTTERY → EARLY → BREAKOUT → EXPANSION → NOISE
"""

from __future__ import annotations

from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def assign_ladder(token: dict, analysis: dict) -> dict:
    mcap = _f(token.get("market_cap") or analysis.get("market_cap"))
    age = _f(token.get("age_minutes") or analysis.get("age_minutes"), 999)
    stage = (token.get("stage") or analysis.get("stage") or "").lower()
    replies = int(token.get("reply_count") or analysis.get("reply_count") or 0)
    rug = _f(analysis.get("rug_risk"), 100)
    hawk = _f(analysis.get("hawk_score") or analysis.get("alpha_score"))
    curve = _f(token.get("curve_progress") or analysis.get("curve_progress"))
    entry = analysis.get("entry_state") or ""
    breakout_score = int(analysis.get("breakout_score") or 0)
    has_social = bool(token.get("twitter") or token.get("website") or token.get("is_live"))
    wash = analysis.get("wash_score")
    if wash is None:
        wash = token.get("wash_score")

    # --- LOTTERY score (earliest asymmetric) ---
    # Private tune: still early, but tax pure ghosts harder so the board isn't unusable.
    lottery_ok = (
        stage == "bonding"
        and 800 <= mcap < 28_000
        and age <= 40
        and rug < 78
        and not (age < 1.5 and replies == 0 and not has_social)
    )

    lottery_score = 0
    lottery_notes: list[str] = []
    if lottery_ok:
        lottery_score = 28
        if 4 <= age <= 22:
            lottery_score += 14
            lottery_notes.append("age_window")
        elif 22 < age <= 40:
            lottery_score += 6
        elif age < 4:
            lottery_score += 3
            lottery_notes.append("ultra_fresh_variance")

        if 6_000 <= mcap <= 20_000:
            lottery_score += 14
            lottery_notes.append("asymmetric_mcap")
        elif 3_000 <= mcap < 6_000:
            lottery_score += 8
        else:
            lottery_score += 3

        if replies >= 10:
            lottery_score += 16
            lottery_notes.append("solid_chat")
        elif replies >= 5:
            lottery_score += 11
            lottery_notes.append("some_chat")
        elif replies >= 2:
            lottery_score += 5
        else:
            lottery_score -= 12
            lottery_notes.append("silent_lottery_tax")

        if 20 <= curve <= 75:
            lottery_score += 12
            lottery_notes.append("curve_optionality")
        elif curve >= 75:
            lottery_score += 7
            lottery_notes.append("late_curve")
        elif curve < 10:
            lottery_score -= 4

        if has_social:
            lottery_score += 7
            lottery_notes.append("social_link")
        if token.get("is_live"):
            lottery_score += 8
            lottery_notes.append("live_stream")

        if rug >= 65:
            lottery_score -= 14
        elif rug >= 50:
            lottery_score -= 7
        elif rug < 40:
            lottery_score += 5

        if wash is not None and wash >= 60:
            lottery_score -= 12
            lottery_notes.append("wash_tax")

        if hawk >= 60:
            lottery_score += 8
        elif hawk >= 50:
            lottery_score += 4

        lottery_score = int(max(0, min(100, lottery_score)))

    # Quality bar for showing as real LOTTERY (not every bonding mint)
    lottery_quality = lottery_ok and lottery_score >= 52

    # --- Rung assignment ---
    if mcap >= 100_000:
        rung = "EXPANSION"
        size_hint = "SMALL_OR_SKIP"
        intent = "Past $100k — continuation only, most asymmetry gone"
    elif mcap >= 30_000:
        rung = "BREAKOUT"
        if breakout_score >= 60 and rug < 52:
            size_hint = "SMALL_TO_MODERATE"
            intent = "Stronger path-to-$100k setup in band"
        elif breakout_score >= 48:
            size_hint = "SMALL"
            intent = "In $30k+ band — selective"
        else:
            size_hint = "WATCH_OR_SKIP"
            intent = "Crossed $30k but path quality weak"
    elif lottery_quality and replies >= 6 and rug < 52 and age >= 6:
        rung = "EARLY"
        size_hint = "MICRO_TO_SMALL"
        intent = "Lottery with evidence — still early"
    elif lottery_quality:
        rung = "LOTTERY"
        size_hint = "MICRO_ONLY"
        intent = "Earliest asymmetric band — expect high fail rate"
    elif stage == "bonding" and age <= 90 and mcap < 30_000 and (replies >= 4 or hawk >= 55):
        rung = "EARLY"
        size_hint = "MICRO_TO_SMALL"
        intent = "Emerging — not lottery-grade, not noise"
    else:
        rung = "NOISE"
        size_hint = "SKIP"
        intent = "Ignore for entries"

    # Operator focus score: single number for private default board
    if rung == "LOTTERY":
        focus = lottery_score
    elif rung == "EARLY":
        focus = int(min(100, 40 + hawk * 0.4 + replies))
    elif rung == "BREAKOUT":
        focus = breakout_score
    elif rung == "EXPANSION":
        focus = int(min(70, breakout_score * 0.7)) if breakout_score else 30
    else:
        focus = 0

    return {
        "ladder": rung,
        "ladder_intent": intent,
        "size_hint": size_hint,
        "lottery_eligible": lottery_ok,
        "lottery_score": lottery_score if lottery_ok else 0,
        "lottery_notes": lottery_notes[:6],
        "lottery_warning": (
            "HIGH VARIANCE — most lotteries go to zero; MICRO size only"
            if rung == "LOTTERY"
            else None
        ),
        "focus_score": focus,
        "operator_priority": (
            (rung == "LOTTERY" and focus >= 55 and replies >= 2)
            or (rung == "EARLY" and focus >= 52)
            or (rung == "BREAKOUT" and focus >= 55 and rug < 58)
        ),
    }
