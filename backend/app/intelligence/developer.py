"""Developer / creator public-history analyzer (Hawk-observed + durable store)."""

from __future__ import annotations

from typing import Any

from app.intelligence.store import (
    creator_launch_count_db,
    record_creator_event,
    get_creator_profile,
)


def analyze_developer(token: dict) -> dict[str, Any]:
    creator = (token.get("creator") or "").strip()
    mint = (token.get("address") or "").strip()
    if not creator:
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "developer_score": 50,
            "flags": ["no_creator_field"],
            "notes": ["Creator pubkey not present on token payload"],
        }

    # Persist observation
    try:
        record_creator_event(
            creator,
            mint,
            {
                "ticker": token.get("ticker"),
                "mcap": token.get("market_cap"),
                "age": token.get("age_minutes"),
            },
        )
    except Exception:
        pass

    profile = {}
    try:
        profile = get_creator_profile(creator) or {}
    except Exception:
        profile = {}

    launches = int(profile.get("launches") or creator_launch_count_db(creator) or 0)
    distinct = int(profile.get("distinct_mints") or launches)
    score = 55
    flags: list[str] = []
    notes: list[str] = []

    if distinct >= 8:
        score -= 30
        flags.append("serial_factory_deployer")
        notes.append(f"Creator linked to {distinct}+ mints in Hawk store — factory risk")
    elif distinct >= 4:
        score -= 18
        flags.append("high_frequency_deployer")
        notes.append(f"Creator seen on {distinct} mints — elevated repeat-deploy risk")
    elif distinct >= 2:
        score -= 8
        flags.append("repeat_deployer")
        notes.append(f"Creator seen on {distinct} mints")
    elif distinct == 1:
        score += 6
        flags.append("first_or_rare_in_window")
        notes.append("Little serial history in Hawk store (not proof of clean actor)")
    else:
        flags.append("history_sparse")
        notes.append("No durable creator history yet")

    score = int(max(0, min(100, score)))
    return {
        "data_quality": "OK" if distinct else "LIMITED",
        "creator": creator,
        "launches_observed": distinct,
        "developer_score": score,
        "flags": flags,
        "notes": notes[:6],
    }
