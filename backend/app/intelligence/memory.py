"""
In-process snapshot memory for velocity, confirmation, and creator frequency.

Process-local (lost on Render restart). Still the best free way to require
*persistence* of quality instead of one lucky snapshot.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from app.intelligence.store import record_snapshot, load_history as db_history, creator_launch_count_db

_MAX_POINTS = 16  # ~6–7 min at ~25s poll
_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_POINTS))
_creator_launches: dict[str, deque] = defaultdict(lambda: deque(maxlen=30))
_lock = Lock()


def track(token: dict) -> None:
    """
    In-memory velocity/confirmation tracking only — no db write.
    Call this early in analyze_token, on the raw (unscored) token, so
    velocity_metrics/confirmation_metrics see this poll immediately.
    """
    addr = token.get("address")
    if not addr:
        return
    point = {
        "ts": time.time(),
        "mcap": float(token.get("market_cap") or 0),
        "curve": float(token.get("curve_progress") or 0),
        "replies": int(token.get("reply_count") or 0),
        "volume": float(token.get("volume") or 0),
        "liquidity": float(token.get("liquidity") or 0),
    }
    creator = (token.get("creator") or "").strip()
    with _lock:
        _store[addr].append(point)
        if creator:
            launches = _creator_launches[creator]
            if addr not in launches:
                launches.append(addr)


def persist(scored_token: dict) -> None:
    """
    Durable db write of a *scored* token (must already have rug_risk /
    hawk_score set). Call this at the end of analyze_token, after scoring,
    so snapshots carry real scores instead of NULLs.
    """
    if not scored_token.get("address"):
        return
    try:
        record_snapshot(scored_token)
    except Exception:
        pass


def record(token: dict) -> None:
    """Back-compat shim: tracks in memory and persists whatever fields
    the token dict has right now. Prefer track()+persist() in engine.py
    so scores are captured; kept for any external callers."""
    track(token)
    persist(token)


def history(address: str) -> list[dict]:
    with _lock:
        mem = list(_store.get(address, []))
    # Merge DB history for longer confirmation across requests
    try:
        db = db_history(address, limit=24)
    except Exception:
        db = []
    if not db:
        return mem
    if not mem:
        return db
    # merge by ts unique
    by_ts = {round(p["ts"], 1): p for p in db + mem}
    return [by_ts[k] for k in sorted(by_ts.keys())]


def creator_launch_count(creator: str) -> int:
    if not creator:
        return 0
    with _lock:
        mem_n = len(_creator_launches.get(creator, []))
    try:
        db_n = creator_launch_count_db(creator)
    except Exception:
        db_n = 0
    return max(mem_n, db_n)


def confirmation_metrics(address: str) -> dict[str, Any]:
    """
    Multi-poll confirmation: quality that holds across snapshots
    is far more useful than a single hot print.
    """
    pts = history(address)
    n = len(pts)
    if n < 2:
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "points": n,
            "confirmed_polls": 0,
            "replies_non_decreasing": None,
            "mcap_not_collapsing": None,
            "stable_enough_for_prime": False,
        }

    replies = [p["replies"] for p in pts]
    mcaps = [p["mcap"] for p in pts]
    # non-decreasing replies across window (allow flat)
    replies_ok = all(replies[i] <= replies[i + 1] + 0 for i in range(len(replies) - 1)) or replies[-1] >= max(replies[0], 1)
    # last mcap not dumping >35% from peak in window
    peak = max(mcaps) if mcaps else 0
    last = mcaps[-1] if mcaps else 0
    mcap_ok = peak <= 0 or last >= peak * 0.65

    # "confirmed polls" = how many points had replies >= 3
    confirmed = sum(1 for r in replies if r >= 3)

    stable = n >= 3 and confirmed >= 2 and mcap_ok and replies[-1] >= 6

    return {
        "data_quality": "OK" if n >= 3 else "LIMITED",
        "points": n,
        "confirmed_polls": confirmed,
        "replies_non_decreasing": replies_ok,
        "mcap_not_collapsing": mcap_ok,
        "stable_enough_for_prime": stable,
        "latest_replies": replies[-1],
        "peak_mcap_window": peak,
        "latest_mcap": last,
    }


def velocity_metrics(address: str) -> dict[str, Any]:
    pts = history(address)
    if len(pts) < 2:
        return {
            "data_quality": "INSUFFICIENT_DATA",
            "points": len(pts),
            "mcap_velocity_per_min": None,
            "curve_velocity_per_min": None,
            "reply_velocity_per_min": None,
            "volume_velocity_per_min": None,
            "mcap_accelerating": None,
            "curve_accelerating": None,
            "reply_accelerating": None,
        }

    a, b = pts[0], pts[-1]
    dt_min = max((b["ts"] - a["ts"]) / 60.0, 0.15)

    def vel(key: str) -> float:
        return (b[key] - a[key]) / dt_min

    mcap_v = vel("mcap")
    curve_v = vel("curve")
    reply_v = vel("replies")
    vol_v = vel("volume")

    accel = {"mcap": None, "curve": None, "replies": None}
    if len(pts) >= 4:
        mid = len(pts) // 2
        first, second = pts[0], pts[mid]
        third, last = pts[mid], pts[-1]
        dt1 = max((second["ts"] - first["ts"]) / 60.0, 0.15)
        dt2 = max((last["ts"] - third["ts"]) / 60.0, 0.15)
        for key in ("mcap", "curve", "replies"):
            v1 = (second[key] - first[key]) / dt1
            v2 = (last[key] - third[key]) / dt2
            accel[key] = v2 > v1 * 1.15 and v2 > 0

    return {
        "data_quality": "OK" if len(pts) >= 3 else "LIMITED",
        "points": len(pts),
        "mcap_velocity_per_min": round(mcap_v, 2),
        "curve_velocity_per_min": round(curve_v, 3),
        "reply_velocity_per_min": round(reply_v, 3),
        "volume_velocity_per_min": round(vol_v, 2),
        "mcap_accelerating": accel["mcap"],
        "curve_accelerating": accel["curve"],
        "reply_accelerating": accel["replies"],
        "window_minutes": round(dt_min, 2),
    }
