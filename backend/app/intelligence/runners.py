"""
Runner / winner-catch potential from public activity signals.

Vision: surface names that can expand (Jupiter-visible), including
silent graduated volume (WATCH only) — without treating them as PRIME.
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
    runner_score 0-100: expansion / attention worthiness (not a buy call).
    winner_watch: organic path (chat + activity)
    volume_watch: silent graduated + real flow (research / micro only)
    """
    vel = vel or {}
    patterns = patterns or {}
    mcap = _f(token.get("market_cap"))
    age = max(_f(token.get("age_minutes"), 0.1), 0.1)
    replies = int(token.get("reply_count") or 0)
    vol = max(_f(token.get("volume")), _f(token.get("volume_h1")), _f(token.get("volume_h6")))
    vol_h1 = _f(token.get("volume_h1")) or vol
    liq = _f(token.get("liquidity"))
    curve = _f(token.get("curve_progress"))
    chg = _f(token.get("price_change_m5") or token.get("price_change_h1"))
    stage = (token.get("stage") or "").lower()
    channel = token.get("discovery_channel") or ""
    complete = bool(token.get("complete"))
    buys_h1 = int(token.get("buys_h1") or 0)
    sells_h1 = int(token.get("sells_h1") or 0)
    tx_h1 = buys_h1 + sells_h1

    graduated = complete or stage in ("graduated", "post_graduation") or curve >= 99

    score = 18
    notes: list[str] = []

    # --- Chat / organicity ---
    if replies >= 15:
        score += 18
        notes.append("strong_chat")
    elif replies >= 8:
        score += 12
        notes.append("solid_chat")
    elif replies >= 3:
        score += 6
    else:
        # Silent: only hard-tax if NOT a graduated volume candidate
        if not (graduated and (vol_h1 >= 15_000 or tx_h1 >= 80 or vol >= 40_000)):
            score -= 12
            notes.append("silent_tax")
        else:
            notes.append("silent_but_flow")

    # --- Flow ---
    if vol > 0 and mcap > 0:
        turn = vol / max(mcap, 1)
        if turn >= 2.0 and replies >= 5:
            score += 14
            notes.append("high_turnover_with_chat")
        elif turn >= 1.0 and replies >= 3:
            score += 8
        elif turn >= 2.5 and replies < 3 and graduated:
            score += 10  # CLOVER-class: graduated churn
            notes.append("grad_volume_turnover")
        elif turn >= 3.0 and replies < 3 and not graduated:
            score -= 12
            notes.append("bonding_volume_without_chat")

    if vol_h1 >= 50_000:
        score += 12
        notes.append("heavy_h1_volume")
    elif vol_h1 >= 20_000:
        score += 8
        notes.append("solid_h1_volume")
    elif vol_h1 >= 8_000:
        score += 4

    if tx_h1 >= 200:
        score += 10
        notes.append("hyper_active_txns")
    elif tx_h1 >= 80:
        score += 6
        notes.append("active_txns")

    # --- Lifecycle ---
    if stage == "bonding" and 25 <= curve <= 85 and replies >= 5:
        score += 12
        notes.append("mid_curve_with_chat")
    if stage == "bonding" and curve >= 70 and replies >= 8:
        score += 10
        notes.append("graduation_pressure_organic")
    if graduated and age <= 360 and mcap >= 15_000:
        score += 10
        notes.append("fresh_grad_window")
        if vol_h1 >= 15_000 or tx_h1 >= 80 or vol >= 40_000:
            score += 12
            notes.append("fresh_grad_with_flow")
    if channel == "active" and mcap >= 15_000:
        score += 6
        notes.append("active_trade_channel")

    # --- Asymmetric bands ---
    if 8_000 <= mcap <= 45_000:
        score += 8
        notes.append("asymmetric_band")
    elif 45_000 <= mcap <= 180_000:
        score += 8
        notes.append("early_runner_band")
    elif mcap > 800_000:
        score -= 10
        notes.append("already_extended")

    # --- Velocity ---
    if vel.get("mcap_accelerating") and vel.get("reply_accelerating"):
        score += 16
        notes.append("dual_acceleration")
    elif vel.get("mcap_accelerating") and replies >= 6:
        score += 8
    elif vel.get("mcap_accelerating") and replies < 3 and not graduated:
        score -= 8

    if 3 <= chg <= 60 and (replies >= 4 or graduated):
        score += 6
        notes.append("orderly_grind")
    elif chg >= 100 and replies < 3 and not graduated:
        score -= 10
        notes.append("vertical_thin_bonding")

    if liq >= 8_000 and mcap >= 20_000:
        score += 6
    elif mcap >= 40_000 and 0 < liq < 2_500:
        score -= 8
        notes.append("untradable_thin_liq")

    pnet = int(patterns.get("pattern_net") or 0)
    if pnet >= 10:
        score += 6
    elif pnet <= -15:
        score -= 8

    if token.get("twitter") and (replies >= 5 or (graduated and vol_h1 >= 20_000)):
        score += 4
    if token.get("is_live"):
        score += 8
        notes.append("live_stream")

    score = int(max(0, min(100, score)))

    # Paths
    organic = replies >= 5 and score >= 55
    volume_watch = (
        graduated
        and replies < 5
        and 12_000 <= mcap <= 250_000
        and age <= 720
        and (vol_h1 >= 12_000 or tx_h1 >= 60 or vol >= 30_000 or (vel.get("mcap_accelerating") and mcap >= 25_000))
        and score >= 42
    )
    winner_watch = organic or (score >= 70 and replies >= 8)

    if winner_watch and organic:
        label = "RUNNER_CANDIDATE"
    elif volume_watch:
        label = "VOLUME_WATCH"
        score = max(score, 52)  # surface on Focus
    elif score >= 55:
        label = "MOMENTUM_WATCH"
    elif score >= 40:
        label = "WEAK_MOMENTUM"
    else:
        label = "NO_RUNNER_EDGE"

    return {
        "runner_score": int(max(0, min(100, score))),
        "runner_label": label,
        "runner_notes": notes[:10],
        "winner_watch": bool(winner_watch),
        "volume_watch": bool(volume_watch),
        "attention_watch": bool(winner_watch or volume_watch),
    }
