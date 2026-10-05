"""
Developer / creator public-history analyzer.

Honest scope:
- We can detect SERIAL DEPLOYERS (many mints) from Hawk-observed history
  and, when Helius is on, optional enrichment later.
- "Serial rugger" is NOT provable from mint count alone. We flag
  high-frequency deployers and, when we have journal outcomes, creators
  whose prior logged tokens died (rug/loss). That is directional risk,
  not a legal accusation.
"""

from __future__ import annotations

from typing import Any

from app.intelligence.store import (
    creator_launch_count_db,
    record_creator_event,
    get_creator_profile,
)


def _journal_creator_death_rate(creator: str) -> dict:
    """From journal: fraction of this creator's logged entries that ended rug/loss."""
    if not creator:
        return {"samples": 0, "death_rate": None}
    try:
        from app.intelligence.store import _db_path
        import sqlite3

        path = _db_path()
        if not path:
            return {"samples": 0, "death_rate": None}
        conn = sqlite3.connect(str(path), timeout=5)
        # journal may not have creator column — match via payload or skip
        # Use creator_mints join addresses that appear in journal with bad outcomes
        cur = conn.execute(
            """
            SELECT j.outcome FROM journal j
            INNER JOIN creator_mints c ON c.mint = j.address
            WHERE c.creator = ?
              AND j.outcome IS NOT NULL AND j.outcome != ''
            """,
            (creator,),
        )
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        if not rows:
            return {"samples": 0, "death_rate": None}
        dead = sum(1 for o in rows if o in ("rug", "loss"))
        return {"samples": len(rows), "death_rate": round(dead / len(rows), 3)}
    except Exception:
        return {"samples": 0, "death_rate": None}


def analyze_developer(token: dict) -> dict[str, Any]:
    creator = (token.get("creator") or "").strip()
    mint = (token.get("address") or "").strip()
    if not creator:
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "developer_score": 50,
            "serial_deployer": False,
            "serial_rug_risk": "UNKNOWN",
            "flags": ["no_creator_field"],
            "notes": ["Creator pubkey not present — cannot assess deployer history"],
        }

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
    deaths = _journal_creator_death_rate(creator)

    score = 55
    flags: list[str] = []
    notes: list[str] = []
    serial = False
    rug_risk_label = "UNKNOWN"

    if distinct >= 8:
        serial = True
        score -= 32
        flags.append("serial_factory_deployer")
        notes.append(
            f"Creator linked to {distinct}+ distinct mints in Hawk store — factory / serial deployer risk"
        )
        rug_risk_label = "ELEVATED_SERIAL_DEPLOYER"
    elif distinct >= 4:
        serial = True
        score -= 20
        flags.append("high_frequency_deployer")
        notes.append(
            f"Creator seen on {distinct} mints — elevated repeat-deploy risk (not proof of rug intent)"
        )
        rug_risk_label = "ELEVATED_SERIAL_DEPLOYER"
    elif distinct >= 2:
        score -= 10
        flags.append("repeat_deployer")
        notes.append(f"Creator seen on {distinct} mints in Hawk memory")
        rug_risk_label = "WATCH_REPEAT"
    elif distinct == 1:
        score += 6
        flags.append("first_or_rare_in_window")
        notes.append("Little serial history in Hawk store yet (not proof of clean actor)")
        rug_risk_label = "INSUFFICIENT_HISTORY"
    else:
        flags.append("history_sparse")
        notes.append("No durable creator history yet — treat as unknown")
        rug_risk_label = "UNKNOWN"

    # Journal-linked outcomes (only when you log results)
    if deaths.get("samples", 0) >= 3 and deaths.get("death_rate") is not None:
        dr = deaths["death_rate"]
        if dr >= 0.7:
            score -= 25
            flags.append("journal_high_death_rate")
            notes.append(
                f"Journal: {int(dr*100)}% of {deaths['samples']} logged tokens for this creator ended rug/loss"
            )
            rug_risk_label = "HIGH_JOURNAL_DEATH_RATE"
        elif dr >= 0.4:
            score -= 12
            flags.append("journal_mixed_death_rate")
            notes.append(
                f"Journal: {int(dr*100)}% death rate on {deaths['samples']} samples"
            )
            if rug_risk_label == "INSUFFICIENT_HISTORY":
                rug_risk_label = "WATCH_JOURNAL"

    score = int(max(0, min(100, score)))
    return {
        "data_quality": "OK" if distinct else "LIMITED",
        "creator": creator,
        "launches_observed": distinct,
        "developer_score": score,
        "serial_deployer": serial,
        "serial_rug_risk": rug_risk_label,
        "journal_death_samples": deaths.get("samples") or 0,
        "journal_death_rate": deaths.get("death_rate"),
        "flags": flags,
        "notes": notes[:8],
    }
