"""
Auto paper-journal — market-ready learning loop (no live trading).

Scan → select → paper micro_entry → mark-to-market (feed + Dex) → resolve TP/SL/time.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from app.intelligence.journal import journal_stats, list_journal, log_event, set_outcome

MIN_RUNNER = 52
MAX_MCAP_ENTER = 180_000.0
MIN_MCAP_ENTER = 6_000.0
MAX_OPEN = 15
TP_2X, TP_5X, SL_FRAC = 2.0, 5.0, 0.50
MAX_HOLD_SEC = 6 * 3600
COOLDOWN_SEC = 90
_last_tick = 0.0


def _eligible(t: dict) -> bool:
    mcap = float(t.get("market_cap") or 0)
    if mcap < MIN_MCAP_ENTER or mcap > MAX_MCAP_ENTER:
        return False
    if (t.get("entry_state") or "") == "AVOID" and not (
        t.get("winner_watch") or t.get("volume_watch") or t.get("attention_watch")
    ):
        if float(t.get("runner_score") or 0) < 70:
            return False
    if t.get("signal") == "reject" or t.get("rating") == "REJECT":
        return False
    if (
        t.get("hawk_score") is not None
        and float(t.get("hawk_score") or 0) == 0
        and t.get("lifecycle") == "REJECT"
    ):
        return False
    if float(t.get("rug_risk") or 0) >= 85:
        return False
    if t.get("winner_watch") or t.get("volume_watch") or t.get("attention_watch"):
        return True
    if float(t.get("runner_score") or 0) >= MIN_RUNNER and int(t.get("reply_count") or 0) >= 3:
        return True
    if float(t.get("runner_score") or 0) >= 75 and mcap >= 15_000:
        return True
    return False


def _open_addresses() -> set[str]:
    open_a: set[str] = set()
    for r in list_journal(200):
        if r.get("action") not in ("micro_entry", "small_entry", "watch"):
            continue
        if r.get("outcome"):
            continue
        notes = r.get("notes") or ""
        if "auto_paper" in notes or r.get("action") == "micro_entry":
            if r.get("address"):
                open_a.add(r["address"])
    return open_a


def _payload(r: dict) -> dict:
    p = r.get("payload")
    if isinstance(p, dict):
        return p
    if isinstance(p, str) and p:
        try:
            return json.loads(p)
        except Exception:
            return {}
    return {}


def open_paper_from_feed(feed: list[dict]) -> list[dict]:
    already = _open_addresses()
    opened: list[dict] = []
    open_count = len(already)
    cands = [t for t in feed if _eligible(t) and (t.get("address") or "") not in already]
    cands.sort(
        key=lambda x: (
            0 if x.get("winner_watch") else 1,
            0 if x.get("volume_watch") else 1,
            -(x.get("runner_score") or 0),
            -(x.get("display_score") or 0),
        )
    )
    for t in cands:
        if open_count >= MAX_OPEN:
            break
        addr = t.get("address") or ""
        if not addr:
            continue
        label = (
            "winner_watch"
            if t.get("winner_watch")
            else "volume_watch"
            if t.get("volume_watch")
            else "runner"
        )
        res = log_event(
            {
                "address": addr,
                "ticker": t.get("ticker"),
                "action": "micro_entry",
                "ladder": t.get("ladder"),
                "entry_state": t.get("entry_state"),
                "display_score": t.get("display_score"),
                "convergence_score": t.get("convergence_score"),
                "reliability": t.get("reliability"),
                "hawk_score": t.get("hawk_score") or t.get("alpha_score"),
                "rug_risk": t.get("rug_risk"),
                "market_cap": t.get("market_cap"),
                "reply_count": t.get("reply_count"),
                "age_minutes": t.get("age_minutes"),
                "breakout_score": t.get("breakout_score"),
                "lottery_score": t.get("lottery_score"),
                "size_hint": "paper_micro",
                "notes": f"auto_paper:{label}",
                "convergence_label": t.get("convergence_label"),
                "pattern_summary": t.get("pattern_summary") or t.get("runner_label"),
            }
        )
        if res.get("ok"):
            opened.append(
                {"id": res.get("id"), "ticker": t.get("ticker"), "address": addr, "label": label}
            )
            open_count += 1
            already.add(addr)
    return opened


def _classify_outcome(entry_mcap: float, peak: float, last: float, age_sec: float):
    if entry_mcap <= 0:
        return "unknown", 1.0
    mult_peak = peak / entry_mcap
    mult_last = last / entry_mcap
    if mult_peak >= TP_5X:
        return "win_5x", round(mult_peak, 3)
    if mult_peak >= TP_2X:
        return "win_2x", round(mult_peak, 3)
    if mult_last <= SL_FRAC:
        return "loss", round(mult_last, 3)
    if age_sec >= MAX_HOLD_SEC:
        if mult_last >= 0.85:
            return "flat", round(mult_last, 3)
        return "loss", round(mult_last, 3)
    return "", 0.0


async def _dex_mcap(address: str) -> float | None:
    try:
        from app.discovery.dexscreener import enrich_token

        extra = await enrich_token(address)
        m = extra.get("market_cap")
        if m and float(m) > 0:
            return float(m)
    except Exception:
        return None
    return None


async def mark_and_resolve(feed: list[dict]) -> dict[str, Any]:
    by_addr = {t.get("address"): t for t in feed if t.get("address")}
    resolved: list[dict] = []
    tracked = 0
    now = time.time()
    open_rows = [
        r
        for r in list_journal(200)
        if not r.get("outcome")
        and r.get("action") in ("micro_entry", "small_entry", "watch")
        and ("auto_paper" in (r.get("notes") or "") or r.get("action") == "micro_entry")
    ]

    # Refresh missing mcaps from Dex (up to 12)
    need_dex = [r for r in open_rows if (r.get("address") or "") not in by_addr][:12]
    if need_dex:
        mcaps = await asyncio.gather(
            *[_dex_mcap(r.get("address") or "") for r in need_dex],
            return_exceptions=True,
        )
        for r, m in zip(need_dex, mcaps):
            if isinstance(m, (int, float)) and m > 0:
                by_addr[r["address"]] = {"address": r["address"], "market_cap": float(m)}

    for r in open_rows:
        addr = r.get("address") or ""
        tok = by_addr.get(addr)
        entry_mcap = float(r.get("market_cap") or 0)
        if entry_mcap <= 0:
            continue
        last = float(tok.get("market_cap") or entry_mcap) if tok else entry_mcap
        peak = max(entry_mcap, last, float(_payload(r).get("peak_mcap") or entry_mcap))
        age_sec = now - float(r.get("ts") or now)
        tracked += 1
        outcome, mult = _classify_outcome(entry_mcap, peak, last, age_sec)
        if not outcome:
            continue
        res = set_outcome(r["id"], outcome, exit_mcap=last, notes=f"auto resolve peak={peak:.0f}")
        if res.get("ok"):
            resolved.append(
                {
                    "id": r["id"],
                    "ticker": r.get("ticker"),
                    "outcome": outcome,
                    "multiple": mult,
                    "entry_mcap": entry_mcap,
                    "exit_mcap": last,
                }
            )
    return {"tracked": tracked, "resolved": resolved}


def learning_summary() -> dict[str, Any]:
    base = journal_stats()
    rows = list_journal(300)
    auto = [r for r in rows if "auto_paper" in (r.get("notes") or "")]
    closed = [r for r in auto if r.get("outcome")]
    wins = [r for r in closed if str(r.get("outcome")).startswith("win")]
    losses = [r for r in closed if r.get("outcome") in ("loss", "rug")]
    flats = [r for r in closed if r.get("outcome") == "flat"]
    mults = [float(r["multiple"]) for r in closed if r.get("multiple") is not None]
    by_label: dict[str, dict] = {}
    for r in closed:
        notes = r.get("notes") or ""
        label = (
            "winner_watch"
            if "winner_watch" in notes
            else "volume_watch"
            if "volume_watch" in notes
            else "runner"
        )
        b = by_label.setdefault(label, {"n": 0, "wins": 0, "losses": 0})
        b["n"] += 1
        if str(r.get("outcome")).startswith("win"):
            b["wins"] += 1
        if r.get("outcome") in ("loss", "rug"):
            b["losses"] += 1
    return {
        "journal": base,
        "auto_opened": len(auto),
        "auto_closed": len(closed),
        "auto_open_now": len(auto) - len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "flats": len(flats),
        "hit_rate": round(len(wins) / len(closed), 3) if closed else None,
        "avg_multiple_closed": round(sum(mults) / len(mults), 3) if mults else None,
        "by_label": by_label,
        "rules": {
            "min_runner": MIN_RUNNER,
            "mcap_band": [MIN_MCAP_ENTER, MAX_MCAP_ENTER],
            "tp": [TP_2X, TP_5X],
            "sl": SL_FRAC,
            "max_hold_h": MAX_HOLD_SEC / 3600,
            "max_open": MAX_OPEN,
        },
        "mode": "paper_only",
        "note": "Not financial advice. Auto-journal does not place live trades.",
    }


def export_bundle(limit: int = 200) -> dict[str, Any]:
    """Full snapshot for GitHub / local backup."""
    return {
        "exported_at": time.time(),
        "version": "2.6.0-market",
        "learning": learning_summary(),
        "entries": list_journal(limit),
    }


async def auto_journal_tick(feed: list[dict], *, force: bool = False) -> dict[str, Any]:
    global _last_tick
    now = time.time()
    if not force and (now - _last_tick) < COOLDOWN_SEC:
        return {"ok": True, "skipped": True, "reason": "throttle"}
    _last_tick = now
    if not feed:
        return {"ok": True, "opened": [], "resolve": {"tracked": 0, "resolved": []}}
    resolve = await mark_and_resolve(feed)
    opened = open_paper_from_feed(feed)
    return {
        "ok": True,
        "opened": opened,
        "opened_n": len(opened),
        "resolve": resolve,
        "learning": learning_summary(),
    }
