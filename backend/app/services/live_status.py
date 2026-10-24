"""
Live discovery status + dossier projection for operator UI.

Honest status only — no fake CONNECTED / fake win rates.
"""

from __future__ import annotations

import time
from typing import Any

_status: dict[str, Any] = {
    "pump": {"ok": None, "code": None, "detail": "unknown", "ts": None},
    "dex": {"ok": None, "code": None, "detail": "unknown", "ts": None},
    "gecko": {"ok": None, "code": None, "detail": "unknown", "ts": None},
    "last_discover_n": 0,
    "last_discover_ts": None,
}


def record_source(name: str, *, ok: bool, code: int | None = None, detail: str = "") -> None:
    _status[name] = {
        "ok": ok,
        "code": code,
        "detail": detail[:200],
        "ts": time.time(),
    }


def record_discover_count(n: int) -> None:
    _status["last_discover_n"] = n
    _status["last_discover_ts"] = time.time()


def get_live_status() -> dict[str, Any]:
    return {
        "pump": _status.get("pump"),
        "dex": _status.get("dex"),
        "gecko": _status.get("gecko"),
        "last_discover_n": _status.get("last_discover_n"),
        "last_discover_ts": _status.get("last_discover_ts"),
        "note": "ok=null means not probed this process lifetime",
    }


def token_to_dossier(t: dict) -> dict[str, Any]:
    """Project hawk token dict into UI dossier shape (honest fields only)."""
    holder = t.get("holder_intel") if isinstance(t.get("holder_intel"), dict) else {}
    top10 = holder.get("top10_pct")
    if top10 is None:
        top10 = t.get("holder_top10_pct")

    posture = (t.get("entry_state") or "AVOID").upper()
    if t.get("volume_watch") or t.get("winner_watch"):
        if posture == "AVOID" and float(t.get("runner_score") or 0) >= 70:
            posture = "WATCH"
    if posture in ("EARLY_ENTRY", "CONFIRMATION_ENTRY"):
        posture = "MICRO"
    elif posture in ("WAIT",):
        posture = "WATCH"

    reasons = list(t.get("reasons") or t.get("positive_signals") or [])[:5]
    risk_flags = list(t.get("risk_flags") or t.get("negative_signals") or [])[:5]
    if t.get("volume_watch"):
        reasons = (["VOLUME_WATCH: elevated short-horizon flow"] + reasons)[:5]
    if t.get("winner_watch"):
        reasons = (["WINNER_WATCH: runner + activity"] + reasons)[:5]

    # Scores only from real fields — unknown stays None, not fake 90
    deployer_score = None
    ci = t.get("creator_intel") or t.get("developer_intel")
    if isinstance(ci, dict) and ci.get("journal_death_rate") is not None:
        death = float(ci.get("journal_death_rate") or 0)
        deployer_score = max(0, min(100, int(100 - death * 100)))

    return {
        "mint": t.get("address") or t.get("mint"),
        "symbol": t.get("ticker") or t.get("symbol") or "?",
        "name": t.get("name") or t.get("ticker") or "Unknown",
        "source": t.get("source") or "unknown",
        "mcap": t.get("market_cap"),
        "liquidity": t.get("liquidity"),
        "age_minutes": t.get("age_minutes"),
        "curve_progress": t.get("curve_progress"),
        "top10_concentration": top10,
        "deployer_score": deployer_score,
        "social_velocity": None,  # not implemented — do not fabricate
        "narrative_match": None,
        "focus_score": round(
            float(
                t.get("display_score")
                or t.get("runner_score")
                or t.get("hawk_score")
                or 0
            ),
            1,
        ),
        "runner_score": t.get("runner_score"),
        "runner_label": t.get("runner_label"),
        "volume_watch": bool(t.get("volume_watch")),
        "winner_watch": bool(t.get("winner_watch")),
        "ladder": t.get("ladder"),
        "posture": posture,
        "risk_flags": risk_flags,
        "reasons": reasons,
        "confidence": "LOW"
        if top10 is None and deployer_score is None
        else "MEDIUM",
        "timestamp": time.time(),
    }
