"""Token lifecycle classification based on age, curve, and activity."""

from __future__ import annotations


def classify_lifecycle(token: dict) -> str:
    age = float(token.get("age_minutes") or 999)
    curve = float(token.get("curve_progress") or 0)
    stage = token.get("stage") or "unknown"
    replies = int(token.get("reply_count") or 0)
    complete = bool(token.get("complete")) or stage == "graduated"

    if complete or curve >= 99.5:
        if age <= 30:
            return "POST_GRADUATION"
        return "POST_GRADUATION"

    if curve >= 75:
        return "GRADUATING"

    if age <= 8:
        return "NEW"
    if age <= 20:
        return "EARLY"
    if age <= 45:
        if replies >= 8 or curve >= 35:
            return "EMERGING"
        return "EARLY"
    if age <= 90:
        if replies >= 15 or curve >= 50:
            return "ACCELERATING"
        return "EMERGING"
    if age <= 180:
        if replies >= 25 and curve >= 40:
            return "HIGH_CONVICTION_CANDIDATE"
        return "AGING"

    return "AGING"
