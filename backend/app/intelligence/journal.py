"""
Operator outcome journal — Phase 0 measurement loop.

Records skips/entries and later outcomes so Asili can be tuned
against a real track record (not vibes).
"""

from __future__ import annotations

import json
import time
import uuid
from threading import Lock
from typing import Any

from app.intelligence.store import _db_path

_lock = Lock()


def _conn():
    path = _db_path()
    if not path:
        return None
    import sqlite3

    conn = sqlite3.connect(str(path), timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS journal (
            id TEXT PRIMARY KEY,
            ts REAL NOT NULL,
            address TEXT NOT NULL,
            ticker TEXT,
            action TEXT NOT NULL,
            ladder TEXT,
            entry_state TEXT,
            display_score REAL,
            convergence_score REAL,
            reliability REAL,
            hawk_score REAL,
            rug_risk REAL,
            market_cap REAL,
            reply_count INTEGER,
            age_minutes REAL,
            breakout_score REAL,
            lottery_score REAL,
            size_hint TEXT,
            notes TEXT,
            outcome TEXT,
            outcome_ts REAL,
            exit_mcap REAL,
            multiple REAL,
            payload TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_journal_ts ON journal(ts DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_journal_addr ON journal(address)"
    )
    conn.commit()
    return conn


def log_event(body: dict[str, Any]) -> dict[str, Any]:
    """
    action: skip | watch | micro_entry | small_entry | exit
    outcome (optional): rug | flat | loss | win_2x | win_5x | win_10x | unknown
    """
    action = (body.get("action") or "").strip().lower()
    address = (body.get("address") or "").strip()
    if not action or not address:
        return {"ok": False, "error": "action and address required"}

    allowed = {"skip", "watch", "micro_entry", "small_entry", "exit"}
    if action not in allowed:
        return {"ok": False, "error": f"action must be one of {sorted(allowed)}"}

    eid = body.get("id") or str(uuid.uuid4())
    now = time.time()
    row = (
        eid,
        now,
        address,
        (body.get("ticker") or "")[:32],
        action,
        body.get("ladder"),
        body.get("entry_state"),
        body.get("display_score"),
        body.get("convergence_score"),
        body.get("reliability"),
        body.get("hawk_score") or body.get("alpha_score"),
        body.get("rug_risk"),
        body.get("market_cap"),
        body.get("reply_count"),
        body.get("age_minutes"),
        body.get("breakout_score"),
        body.get("lottery_score"),
        body.get("size_hint"),
        (body.get("notes") or "")[:500],
        body.get("outcome"),
        body.get("outcome_ts"),
        body.get("exit_mcap"),
        body.get("multiple"),
        json.dumps({k: body.get(k) for k in ("convergence_label", "pattern_summary") if body.get(k)})[:1000],
    )

    conn = _conn()
    if not conn:
        return {"ok": False, "error": "journal_db_unavailable"}

    try:
        with _lock:
            conn.execute(
                """
                INSERT INTO journal (
                    id, ts, address, ticker, action, ladder, entry_state,
                    display_score, convergence_score, reliability, hawk_score,
                    rug_risk, market_cap, reply_count, age_minutes,
                    breakout_score, lottery_score, size_hint, notes,
                    outcome, outcome_ts, exit_mcap, multiple, payload
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                row,
            )
            conn.commit()
            conn.close()
        return {"ok": True, "id": eid, "ts": now, "action": action, "address": address}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def set_outcome(entry_id: str, outcome: str, exit_mcap: float | None = None, notes: str = "") -> dict:
    outcome = (outcome or "").strip().lower()
    allowed = {"rug", "flat", "loss", "win_2x", "win_5x", "win_10x", "unknown"}
    if outcome not in allowed:
        return {"ok": False, "error": f"outcome must be one of {sorted(allowed)}"}

    conn = _conn()
    if not conn:
        return {"ok": False, "error": "journal_db_unavailable"}

    multiple = None
    try:
        with _lock:
            cur = conn.execute(
                "SELECT market_cap FROM journal WHERE id = ?", (entry_id,)
            )
            row = cur.fetchone()
            entry_mcap = float(row[0]) if row and row[0] else None
            if entry_mcap and exit_mcap and entry_mcap > 0:
                multiple = round(float(exit_mcap) / entry_mcap, 3)
            conn.execute(
                """
                UPDATE journal
                SET outcome = ?, outcome_ts = ?, exit_mcap = ?, multiple = ?,
                    notes = COALESCE(notes, '') || ?
                WHERE id = ?
                """,
                (
                    outcome,
                    time.time(),
                    exit_mcap,
                    multiple,
                    f" | outcome_notes:{notes[:200]}" if notes else "",
                    entry_id,
                ),
            )
            conn.commit()
            conn.close()
        return {"ok": True, "id": entry_id, "outcome": outcome, "multiple": multiple}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_journal(limit: int = 50) -> list[dict]:
    conn = _conn()
    if not conn:
        return []
    try:
        with _lock:
            cur = conn.execute(
                """
                SELECT id, ts, address, ticker, action, ladder, entry_state,
                       display_score, convergence_score, reliability, hawk_score,
                       rug_risk, market_cap, reply_count, outcome, multiple, notes
                FROM journal ORDER BY ts DESC LIMIT ?
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.close()
        return rows
    except Exception:
        return []


def journal_stats() -> dict:
    conn = _conn()
    if not conn:
        return {"entries": 0, "data_quality": "UNAVAILABLE"}
    try:
        with _lock:
            cur = conn.execute("SELECT COUNT(*) FROM journal")
            n = int(cur.fetchone()[0])
            cur = conn.execute(
                "SELECT action, COUNT(*) FROM journal GROUP BY action"
            )
            by_action = {r[0]: r[1] for r in cur.fetchall()}
            cur = conn.execute(
                """
                SELECT outcome, COUNT(*) FROM journal
                WHERE outcome IS NOT NULL AND outcome != ''
                GROUP BY outcome
                """
            )
            by_outcome = {r[0]: r[1] for r in cur.fetchall()}
            cur = conn.execute(
                """
                SELECT AVG(multiple) FROM journal
                WHERE multiple IS NOT NULL AND action IN ('micro_entry', 'small_entry')
                """
            )
            avg_mult = cur.fetchone()[0]
            conn.close()
        return {
            "entries": n,
            "by_action": by_action,
            "by_outcome": by_outcome,
            "avg_multiple_entries": round(float(avg_mult), 3) if avg_mult is not None else None,
            "data_quality": "OK" if n else "EMPTY",
            "calibration_ready": n >= 50,
        }
    except Exception:
        return {"entries": 0, "data_quality": "ERROR"}
