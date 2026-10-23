"""Naive, read-only replay of retained market-cap snapshots (not a trading backtest).

Run from backend with: python scripts/backtest_snapshots.py --horizon-hours 24
The report deliberately excludes tokens without a complete observation window.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

SOLANA_MINT = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def build_report(db_path: Path, horizon_hours: float = 24.0) -> dict:
    horizon = max(1.0, float(horizon_hours)) * 3600
    uri = db_path.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            rows = conn.execute(
                "SELECT address, ts, mcap, hawk_score, payload FROM snapshots "
                "WHERE mcap > 0 ORDER BY address, ts"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(
            f"Cannot evaluate snapshot evidence: {db_path} is unreadable or corrupt. "
            "The database was opened read-only and was not changed. Preserve a copy, "
            "check for a verified backup, then rerun the report against that copy."
        ) from exc

    histories: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        if SOLANA_MINT.fullmatch(row[0] or ""):
            histories[row[0]].append(row)

    latest_ts = max((row[1] for hist in histories.values() for row in hist), default=0)
    earliest_ts = min((row[1] for hist in histories.values() for row in hist), default=0)
    mature_entries = sum(1 for hist in histories.values() if hist[0][1] + horizon <= latest_ts)
    mature_scored_entries = sum(
        1 for hist in histories.values()
        if hist[0][1] + horizon <= latest_ts and hist[0][3] is not None
    )
    mature_scores = [
        float(hist[0][3]) for hist in histories.values()
        if hist[0][1] + horizon <= latest_ts and hist[0][3] is not None
    ]
    mature_display_scores = []
    for hist in histories.values():
        if hist[0][1] + horizon > latest_ts:
            continue
        try:
            payload = json.loads(hist[0][4] or "{}")
            if payload.get("display_score") is not None:
                mature_display_scores.append(float(payload["display_score"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    cohorts: dict[str, list[dict]] = {
        "all": [], "score_50_plus": [], "score_70_plus": [], "score_80_plus": [],
        "display_50_plus": [], "display_70_plus": [], "display_80_plus": [],
    }
    score_bands: dict[str, list[dict]] = {
        f"{lower}-{lower + 9 if lower < 90 else 100}": [] for lower in range(0, 100, 10)
    }
    mature_with_followup = 0
    mature_scored_with_followup = 0
    for hist in histories.values():
        entry = hist[0]
        if latest_ts - entry[1] < horizon:
            continue  # right-censored: not enough time has elapsed to observe the full horizon
        future = [row for row in hist[1:] if 0 < row[1] - entry[1] <= horizon]
        if not future:
            continue
        entry_mcap = float(entry[2])
        if entry_mcap <= 0:
            continue
        sample = {
            "peak_multiple": max(float(r[2]) for r in future) / entry_mcap,
            "trough_multiple": min(float(r[2]) for r in future) / entry_mcap,
            "last_multiple": float(future[-1][2]) / entry_mcap,
            "observed_horizon_fraction": min(1.0, max(0.0, (future[-1][1] - entry[1]) / horizon)),
        }
        mature_with_followup += 1
        cohorts["all"].append(sample)
        score = entry[3]
        if score is not None:
            mature_scored_with_followup += 1
            score_value = float(score)
            lower = min(90, max(0, int(score_value // 10) * 10))
            score_bands[f"{lower}-{lower + 9 if lower < 90 else 100}"].append(sample)
            for threshold in (50, 70, 80):
                if score_value >= threshold:
                    cohorts[f"score_{threshold}_plus"].append(sample)
        try:
            display_score = json.loads(entry[4] or "{}").get("display_score")
        except (TypeError, ValueError, json.JSONDecodeError):
            display_score = None
        if display_score is not None:
            for threshold in (50, 70, 80):
                if float(display_score) >= threshold:
                    cohorts[f"display_{threshold}_plus"].append(sample)

    def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
        if not n:
            return None
        rate = successes / n
        denominator = 1 + z * z / n
        center = (rate + z * z / (2 * n)) / denominator
        half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denominator
        return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]

    def summarize(samples: list[dict]) -> dict:
        n = len(samples)
        peak_2x = sum(s["peak_multiple"] >= 2 for s in samples)
        peak_5x = sum(s["peak_multiple"] >= 5 for s in samples)
        below_half = sum(s["trough_multiple"] <= 0.5 for s in samples)
        horizon_fractions = [s["observed_horizon_fraction"] for s in samples]
        near_full_horizon = sum(fraction >= 0.95 for fraction in horizon_fractions)
        return {
            "n": n,
            "observed_peak_2x_count": peak_2x,
            "observed_peak_2x_rate": round(peak_2x / n, 4) if n else None,
            "observed_peak_2x_rate_ci95": wilson_interval(peak_2x, n),
            "observed_peak_5x_count": peak_5x,
            "observed_peak_5x_rate": round(peak_5x / n, 4) if n else None,
            "observed_peak_5x_rate_ci95": wilson_interval(peak_5x, n),
            "observed_below_half_count": below_half,
            "observed_below_half_rate": round(below_half / n, 4) if n else None,
            "observed_below_half_rate_ci95": wilson_interval(below_half, n),
            "median_last_multiple": round(statistics.median(s["last_multiple"] for s in samples), 4) if n else None,
            "median_observed_horizon_fraction": round(
                statistics.median(horizon_fractions), 4
            ) if n else None,
            "min_observed_horizon_fraction": round(
                min(horizon_fractions), 4
            ) if n else None,
            "max_observed_horizon_fraction": round(max(horizon_fractions), 4) if n else None,
            "median_followup_minutes": round(statistics.median(horizon_fractions) * horizon / 60, 2) if n else None,
            "near_full_horizon_count_95pct": near_full_horizon,
            "near_full_horizon_rate_95pct": round(near_full_horizon / n, 4) if n else None,
        }

    return {
        "report": "retained_snapshot_replay",
        "generated_at": time.time(),
        "horizon_hours": horizon / 3600,
        "source_rows": len(rows),
        "solana_mints": len(histories),
        "valid_mint_data_span_hours": round((latest_ts - earliest_ts) / 3600, 2) if latest_ts and earliest_ts else 0,
        "mature_first_observations": mature_entries,
        "mature_first_observations_with_followup": mature_with_followup,
        "mature_first_observations_without_followup": mature_entries - mature_with_followup,
        "mature_followup_coverage": round(mature_with_followup / mature_entries, 4) if mature_entries else None,
        "mature_scored_first_observations": mature_scored_entries,
        "mature_scored_first_observations_with_followup": mature_scored_with_followup,
        "mature_score_coverage": round(mature_scored_entries / mature_entries, 4) if mature_entries else None,
        "mature_score_min": min(mature_scores) if mature_scores else None,
        "mature_score_median": statistics.median(mature_scores) if mature_scores else None,
        "mature_score_max": max(mature_scores) if mature_scores else None,
        "mature_score_50_plus": sum(score >= 50 for score in mature_scores),
        "mature_display_score_coverage": round(len(mature_display_scores) / mature_entries, 4) if mature_entries else None,
        "mature_display_score_min": min(mature_display_scores) if mature_display_scores else None,
        "mature_display_score_median": statistics.median(mature_display_scores) if mature_display_scores else None,
        "mature_display_score_max": max(mature_display_scores) if mature_display_scores else None,
        "valid_data_latest_utc": datetime.fromtimestamp(latest_ts, timezone.utc).isoformat() if latest_ts else None,
        "cohorts": {name: summarize(samples) for name, samples in cohorts.items()},
        "hawk_score_bands": {name: summarize(samples) for name, samples in score_bands.items()},
        "limitations": [
            "Uses the first retained snapshot, not a verified original alert or executable entry.",
            "Snapshots may be sparse; a token disappearing from discovery is not proof of a zero value.",
            "A follow-up snapshot may cover only part of the requested horizon; cohort metrics report observed horizon fractions.",
            "Observed peaks ignore fees, slippage, liquidity constraints, and order execution.",
            "Wilson intervals treat token outcomes as independent and do not adjust for shared market-period effects.",
            "This is descriptive retrospective evidence, not a validated predictive or trading backtest.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path("data/hawk_snapshots.db"))
    parser.add_argument("--horizon-hours", type=float, default=24)
    args = parser.parse_args()
    print(json.dumps(build_report(args.db_path, args.horizon_hours), indent=2))


if __name__ == "__main__":
    main()
