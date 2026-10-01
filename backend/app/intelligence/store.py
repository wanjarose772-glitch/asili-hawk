"""
Lightweight persistent snapshot store (SQLite).

Survives within an instance lifetime better than pure RAM and
survives deploys if Render disk is retained. On free ephemeral
filesystem it still helps across requests until the instance dies.

Falls back silently if DB cannot be opened.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any

_lock = Lock()


def _db_candidates() -> list[Path]:
    """
    Configured path first (Settings.db_path, overridable via DB_PATH env),
    then /tmp as a last-resort fallback for read-only deploy filesystems.
    No environment-specific paths hardcoded here — those belong in config
    or the environment, not in code.

    Config import is deferred and defensive: this module's whole job is to
    degrade gracefully (see module docstring), so a config-loading problem
    should fall back to a sane default path, not take the app down at
    import time.
    """
    configured = Path("data/hawk_snapshots.db")
    try:
        from app.config import get_settings

        configured = Path(get_settings().db_path)
    except Exception:
        pass
    candidates = [configured]
    fallback = Path("/tmp/asili_hawk_snapshots.db")
    if fallback not in candidates:
        candidates.append(fallback)
    return candidates


def _db_path() -> Path | None:
    for p in _db_candidates():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            # touch test
            conn = sqlite3.connect(str(p), timeout=5)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    address TEXT NOT NULL,
                    ts REAL NOT NULL,
                    mcap REAL,
                    curve REAL,
                    replies INTEGER,
                    volume REAL,
                    liquidity REAL,
                    rug_risk REAL,
                    hawk_score REAL,
                    payload TEXT
                )
                """
            )
            # Existing deployments may already have the snapshots table from
            # an older ASILI release. CREATE TABLE IF NOT EXISTS does not add
            # columns, so migrate missing v2 columns in place.
            existing = {row[1] for row in conn.execute("PRAGMA table_info(snapshots)").fetchall()}
            for column, sql_type in (
                ("rug_risk", "REAL"),
                ("hawk_score", "REAL"),
                ("payload", "TEXT"),
            ):
                if column not in existing:
                    conn.execute(f"ALTER TABLE snapshots ADD COLUMN {column} {sql_type}")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_snap_addr_ts ON snapshots(address, ts)"
            )
            # creator_stats is a mirror of the distinct-mint count kept in
            # creator_mints (see record_creator_event). It is written only
            # from there now — record_snapshot used to also increment it
            # once per poll, which double-counted against the same creator.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS creator_stats (
                    creator TEXT PRIMARY KEY,
                    launches INTEGER DEFAULT 0,
                    last_seen REAL,
                    notes TEXT
                )
                """
            )
            conn.commit()
            conn.close()
            return p
        except Exception:
            continue
    return None


def record_snapshot(token: dict) -> None:
    path = _db_path()
    if not path:
        return
    addr = token.get("address")
    if not addr:
        return
    row = (
        addr,
        time.time(),
        float(token.get("market_cap") or 0),
        float(token.get("curve_progress") or 0),
        int(token.get("reply_count") or 0),
        float(token.get("volume") or 0),
        float(token.get("liquidity") or 0),
        float(token.get("rug_risk") or 0) if token.get("rug_risk") is not None else None,
        float(token.get("hawk_score") or token.get("alpha_score") or 0)
        if (token.get("hawk_score") or token.get("alpha_score")) is not None
        else None,
        json.dumps(
            {
                "ticker": token.get("ticker"),
                "stage": token.get("stage"),
                "lifecycle": token.get("lifecycle"),
            }
        )[:500],
    )
    try:
        with _lock:
            conn = sqlite3.connect(str(path), timeout=5)
            conn.execute(
                "INSERT INTO snapshots(address, ts, mcap, curve, replies, volume, liquidity, rug_risk, hawk_score, payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
                row,
            )
            # prune old rows for this address (keep last 40)
            # SQLite needs nested subquery for LIMIT in some versions
            conn.execute(
                """
                DELETE FROM snapshots WHERE address = ? AND rowid IN (
                    SELECT rowid FROM (
                        SELECT rowid FROM snapshots WHERE address = ? ORDER BY ts DESC LIMIT -1 OFFSET 40
                    )
                )
                """,
                (addr, addr),
            )
            # Creator frequency is tracked exclusively via creator_mints
            # (distinct-mint counting; see record_creator_event) — the old
            # per-snapshot creator_stats counter double-counted polls as
            # launches and has been removed.
            conn.commit()
            conn.close()
    except Exception:
        pass


def load_history(address: str, limit: int = 20) -> list[dict]:
    path = _db_path()
    if not path or not address:
        return []
    try:
        with _lock:
            conn = sqlite3.connect(str(path), timeout=5)
            cur = conn.execute(
                "SELECT ts, mcap, curve, replies, volume, liquidity FROM snapshots WHERE address = ? ORDER BY ts DESC LIMIT ?",
                (address, max(1, int(limit))),
            )
            rows = cur.fetchall()
            conn.close()
        rows.reverse()
        return [
            {
                "ts": r[0],
                "mcap": r[1] or 0,
                "curve": r[2] or 0,
                "replies": int(r[3] or 0),
                "volume": r[4] or 0,
                "liquidity": r[5] or 0,
            }
            for r in rows
        ]
    except Exception:
        return []


def creator_launch_count_db(creator: str) -> int:
    path = _db_path()
    if not path or not creator:
        return 0
    try:
        with _lock:
            conn = sqlite3.connect(str(path), timeout=5)
            cur = conn.execute(
                "SELECT launches FROM creator_stats WHERE creator = ?", (creator,)
            )
            row = cur.fetchone()
            conn.close()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def record_creator_event(creator: str, mint: str, meta: dict | None = None) -> None:
    path = _db_path()
    if not path or not creator:
        return
    import json, time
    meta = meta or {}
    try:
        with _lock:
            conn = sqlite3.connect(str(path), timeout=5)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS creator_mints (
                    creator TEXT NOT NULL,
                    mint TEXT NOT NULL,
                    ts REAL NOT NULL,
                    ticker TEXT,
                    mcap REAL,
                    PRIMARY KEY (creator, mint)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO creator_mints(creator, mint, ts, ticker, mcap)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(creator, mint) DO UPDATE SET
                    ts = excluded.ts,
                    mcap = COALESCE(excluded.mcap, creator_mints.mcap)
                """,
                (
                    creator,
                    mint or "",
                    time.time(),
                    (meta.get("ticker") or "")[:24],
                    float(meta.get("mcap") or 0) or None,
                ),
            )
            cur = conn.execute(
                "SELECT COUNT(*) FROM creator_mints WHERE creator = ?", (creator,)
            )
            n = int(cur.fetchone()[0])
            conn.execute(
                """
                INSERT INTO creator_stats(creator, launches, last_seen, notes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(creator) DO UPDATE SET
                    launches = excluded.launches,
                    last_seen = excluded.last_seen
                """,
                (creator, n, time.time(), f"distinct_mints={n}"),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass


def get_creator_profile(creator: str) -> dict:
    path = _db_path()
    if not path or not creator:
        return {}
    try:
        with _lock:
            conn = sqlite3.connect(str(path), timeout=5)
            cur = conn.execute(
                "SELECT launches, last_seen, notes FROM creator_stats WHERE creator = ?",
                (creator,),
            )
            row = cur.fetchone()
            try:
                cur2 = conn.execute(
                    "SELECT COUNT(*) FROM creator_mints WHERE creator = ?", (creator,)
                )
                distinct = int(cur2.fetchone()[0])
            except Exception:
                distinct = int(row[0]) if row else 0
            conn.close()
        if not row:
            return {"launches": distinct, "distinct_mints": distinct}
        return {
            "launches": int(row[0] or distinct),
            "last_seen": row[1],
            "notes": row[2],
            "distinct_mints": distinct,
        }
    except Exception:
        return {}
