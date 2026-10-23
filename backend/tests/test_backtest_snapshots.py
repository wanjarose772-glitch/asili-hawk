import sqlite3

import pytest

from scripts.backtest_snapshots import build_report


def _make_snapshots_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE snapshots ("
            "address TEXT, ts REAL, mcap REAL, hawk_score REAL, payload TEXT)"
        )
        rows = [
            ("A" * 32, 0, 100, 15, "{}"),
            ("A" * 32, 43_200, 200, 15, "{}"),
            ("A" * 32, 86_400, 100, 15, "{}"),
            ("B" * 32, 0, 100, 25, "{}"),
            ("B" * 32, 43_200, 110, 25, "{}"),
            ("B" * 32, 86_400, 300, 25, "{}"),
            # Mature by calendar time but no subsequent market observation.
            ("C" * 32, 0, 100, 45, "{}"),
        ]
        conn.executemany("INSERT INTO snapshots VALUES (?, ?, ?, ?, ?)", rows)


def test_report_exposes_score_bands_uncertainty_and_followup_coverage(tmp_path):
    db_path = tmp_path / "snapshots.db"
    _make_snapshots_db(db_path)

    report = build_report(db_path, horizon_hours=24)

    assert report["mature_first_observations"] == 3
    assert report["mature_first_observations_with_followup"] == 2
    assert report["mature_first_observations_without_followup"] == 1
    assert report["mature_followup_coverage"] == pytest.approx(2 / 3, abs=0.0001)
    assert report["mature_scored_first_observations_with_followup"] == 2
    assert report["cohorts"]["all"]["n"] == 2
    assert report["cohorts"]["all"]["observed_peak_2x_count"] == 2
    assert report["cohorts"]["all"]["observed_peak_2x_rate_ci95"] is not None
    # The median of last multiples 1 and 3 is 2 (not the upper-middle value 3).
    assert report["cohorts"]["all"]["median_last_multiple"] == 2
    assert report["hawk_score_bands"]["10-19"]["n"] == 1
    assert report["hawk_score_bands"]["20-29"]["n"] == 1
    assert report["hawk_score_bands"]["40-49"]["n"] == 0
    assert report["cohorts"]["all"]["median_observed_horizon_fraction"] == 1
    assert report["cohorts"]["all"]["near_full_horizon_count_95pct"] == 2
    assert report["cohorts"]["all"]["median_followup_minutes"] == 1440


def test_report_marks_sparse_followup_as_partial_horizon_coverage(tmp_path):
    db_path = tmp_path / "partial.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE snapshots ("
            "address TEXT, ts REAL, mcap REAL, hawk_score REAL, payload TEXT)"
        )
        conn.executemany(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?)",
            [
                ("A" * 32, 0, 100, 25, "{}"),
                ("A" * 32, 21_600, 130, 25, "{}"),
                # Sets the dataset clock 24 hours later without being mature itself.
                ("B" * 32, 86_400, 100, None, "{}"),
            ],
        )

    report = build_report(db_path, horizon_hours=24)

    assert report["mature_first_observations_with_followup"] == 1
    assert report["cohorts"]["all"]["median_observed_horizon_fraction"] == 0.25
    assert report["cohorts"]["all"]["min_observed_horizon_fraction"] == 0.25
    assert report["cohorts"]["all"]["median_followup_minutes"] == 360
    assert report["cohorts"]["all"]["near_full_horizon_count_95pct"] == 0


def test_corrupt_database_fails_with_read_only_recovery_guidance(tmp_path):
    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(b"not a sqlite database")

    with pytest.raises(RuntimeError, match="opened read-only and was not changed"):
        build_report(db_path)
