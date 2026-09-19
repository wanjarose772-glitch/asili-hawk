"""
In-process snapshot memory for velocity / acceleration.

Stores recent observations per mint so Hawk can detect rate-of-change
rather than only absolute levels. Process-local (lost on restart) —
sufficient for live acceleration detection during an uptime window.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any

_MAX_POINTS = 12  # ~5 min of history at 25s poll
_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_POINTS))
_lock = Lock()


def record(token: dict) -> None:
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
    with _lock:
        _store[addr].append(point)


def history(address: str) -> list[dict]:
    with _lock:
        return list(_store.get(address, []))


def velocity_metrics(address: str) -> dict[str, Any]:
    """
    Derive simple velocities and acceleration flags from snapshots.
    Returns INSUFFICIENT_DATA style zeros when history is too short.
    """
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

    # Compare newest vs oldest in window
    a, b = pts[0], pts[-1]
    dt_min = max((b["ts"] - a["ts"]) / 60.0, 0.15)

    def vel(key: str) -> float:
        return (b[key] - a[key]) / dt_min

    mcap_v = vel("mcap")
    curve_v = vel("curve")
    reply_v = vel("replies")
    vol_v = vel("volume")

    # Acceleration: compare first half velocity vs second half when possible
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
