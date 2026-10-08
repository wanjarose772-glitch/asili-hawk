"""
Runner / winner-catch potential from public activity signals.

Goal: stand a chance of surfacing names that can expand (Jupiter-visible),
not only reject rugs. Still legal public data only.
"""

from __future__ import annotations

from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def score_runner(token: dict, vel: dict | None = None, patterns: dict | None = None) -> dict:
    """
    runner_score 0-100: chance this name is in a live expansion phase
    worth watching (not a buy recommendation).
    """
    vel = vel or {}
    patterns = patterns or {}
    mcap = _f(token.get("market_cap"))
    age = max(_f(token.get("age_minutes"), 0.1), 0.1)
    replies = int(token.get("reply_count") or 0)
    vol = _f(token.get("volume"))
    liq = _f(token.get("liquidity"))
    curve = _f(token.get("curve_progress"))
    chg = _f(token.get("price_change_m5"))
    stage = (token.get("stage") or "").lower()
    channel = token.get("discovery_channel") or ""
    complete = bool(token.get("complete"))

    score = 20
    notes: list[str] = []

    # --- Activity geometry (winners usually have flow + people) ---
    if replies >= 15:
        score += 18
        notes.append("strong_chat")
    elif replies >= 8:
        score += 12
        notes.append("solid_chat")
    elif replies >= 3:
        score += 6
    else:
        score -= 10
        notes.append("silent_tax")

    if vol > 0 and mcap > 0:
        turn = vol / max(mcap, 1)
        if turn >= 2.0 and replies >= 5:
            score += 14
            notes.append("high_turnover_with_chat")
        elif turn >= 1.0 and replies >= 3:
            score += 8
        elif turn >= 3.0 and replies < 3:
            score -= 12
            notes.append("volume_without_chat")

    # --- Lifecycle windows where winners often appear ---
    if stage == "bonding" and 25 <= curve <= 85 and replies >= 5:
        score += 12
        notes.append("mid_curve_with_chat")
    if stage == "bonding" and curve >= 70 and replies >= 8:
        score += 10
        notes.append("graduation_pressure_organic")
    if (stage == "graduated" or complete) and age <= 180 and replies >= 8 and mcap >= 25_000:
        score += 14
        notes.append("fresh_grad_active")
    if channel == "active" and mcap >= 20_000:
        score += 8
        notes.append("active_trade_channel")

    # --- Asymmetric bands (room to still expand) ---
    if 8_000 <= mcap <= 45_000 and replies >= 5:
        score += 10
        notes.append("asymmetric_band")
    elif 45_000 <= mcap <= 150_000 and replies >= 8:
        score += 8
        notes.append("early_runner_band")
    elif mcap > 500_000:
        score -= 8
        notes.append("already_extended")

    # --- Velocity confirmation ---
    if vel.get("mcap_accelerating") and vel.get("reply_accelerating"):
        score += 16
        notes.append("dual_acceleration")
    elif vel.get("mcap_accelerating") and replies >= 6:
        score += 8
    elif vel.get("mcap_accelerating") and replies < 3:
        score -= 10

    if 3 <= chg <= 45 and replies >= 4:
        score += 6
        notes.append("orderly_grind")
    elif chg >= 80 and replies < 4:
        score -= 12
        notes.append("vertical_thin")

    # --- Liquidity tradability ---
    if liq >= 10_000 and mcap >= 20_000:
        score += 6
    elif mcap >= 40_000 and liq > 0 and liq < 3_000:
        score -= 10
        notes.append("untradable_thin_liq")

    # Pattern net assist
    pnet = int(patterns.get("pattern_net") or 0)
    if pnet >= 10:
        score += 6
    elif pnet <= -15:
        score -= 8

    # Social surface
    if token.get("twitter") and replies >= 5:
        score += 5
    if token.get("is_live"):
        score += 8
        notes.append("live_stream")

    score = int(max(0, min(100, score)))

    if score >= 70 and replies >= 8:
        label = "RUNNER_CANDIDATE"
    elif score >= 55:
        label = "MOMENTUM_WATCH"
    elif score >= 40:
        label = "WEAK_MOMENTUM"
    else:
        label = "NO_RUNNER_EDGE"

    return {
        "runner_score": score,
        "runner_label": label,
        "runner_notes": notes[:8],
        "winner_watch": score >= 55 and replies >= 5,
    }
