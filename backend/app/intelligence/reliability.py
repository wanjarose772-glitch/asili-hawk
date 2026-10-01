"""Evidence reliability + time decay for public signals."""

from __future__ import annotations

from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def score_reliability(token: dict, channels: dict[str, dict]) -> dict:
    """
    reliability 0-100: how much of the convergence stack is actually evidenced.
    decay 0-1: soft penalty as setup ages without confirmation.
    """
    covered = 0
    total = 0
    missing: list[str] = []

    checks = [
        ("holders", lambda c: c.get("data_quality") == "OK"),
        ("developer", lambda c: c.get("data_quality") in ("OK", "LIMITED")),
        ("liquidity", lambda c: _f(token.get("liquidity")) > 0 or _f(c.get("score")) > 0),
        ("social", lambda c: int(token.get("reply_count") or 0) > 0 or bool(token.get("twitter"))),
        ("structure", lambda c: c.get("pattern_score") is not None),
        ("flow", lambda c: c.get("data_quality") in ("OK", "LIMITED") or c.get("wash_score") is not None),
    ]

    for name, fn in checks:
        total += 1
        ch = channels.get(name) or {}
        try:
            ok = bool(fn(ch))
        except Exception:
            ok = False
        if ok:
            covered += 1
        else:
            missing.append(name)

    reliability = int(round(100 * covered / max(total, 1)))

    age = _f(token.get("age_minutes"), 0)
    # Decay: very fresh unconfirmed decays less for lottery; old weak setups decay more
    if age <= 20:
        decay = 1.0
    elif age <= 60:
        decay = 0.92
    elif age <= 180:
        decay = 0.8
    else:
        decay = 0.65

    replies = int(token.get("reply_count") or 0)
    if replies == 0 and age > 15:
        decay *= 0.85
    if reliability < 40:
        decay *= 0.9

    return {
        "reliability": reliability,
        "decay": round(decay, 3),
        "channels_covered": covered,
        "channels_total": total,
        "missing_channels": missing,
    }
