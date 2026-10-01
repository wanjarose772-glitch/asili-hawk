import sqlite3

from app.intelligence import store


def test_load_history_returns_latest_points_in_chronological_order(tmp_path, monkeypatch):
    db = tmp_path / "history.db"
    monkeypatch.setattr(store, "_db_candidates", lambda: [db])

    path = store._db_path()
    assert path == db
    for i in range(30):
        store.record_snapshot({
            "address": "MINT",
            "market_cap": i,
            "curve_progress": i,
            "reply_count": i,
            "volume": i,
            "liquidity": i,
            "hawk_score": i,
            "rug_risk": i,
        })

    history = store.load_history("MINT", limit=5)
    assert [row["mcap"] for row in history] == [25, 26, 27, 28, 29]


def test_legacy_snapshot_schema_is_migrated_in_place(tmp_path, monkeypatch):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE snapshots (
            address TEXT NOT NULL,
            ts REAL NOT NULL,
            mcap REAL,
            curve REAL,
            replies INTEGER,
            volume REAL,
            liquidity REAL
        )
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(store, "_db_candidates", lambda: [db])

    assert store._db_path() == db
    conn = sqlite3.connect(db)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(snapshots)")}
    conn.close()
    assert {"rug_risk", "hawk_score", "payload"}.issubset(columns)

    store.record_snapshot({"address": "LEGACY", "market_cap": 123, "hawk_score": 77, "rug_risk": 12})
    history = store.load_history("LEGACY", limit=1)
    assert history[0]["mcap"] == 123
