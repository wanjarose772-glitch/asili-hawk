"""HAWK orchestration — discovery → intelligence → feed."""

from __future__ import annotations

import time
from typing import Any

from cachetools import TTLCache

from app.config import get_settings
from app.discovery.aggregator import discover_opportunities
from app.intelligence.engine import rank_tokens, top_opportunities
from app.services.alerts import scan_and_alert

_settings = get_settings()
_cache: TTLCache = TTLCache(maxsize=16, ttl=max(18, _settings.cache_ttl_seconds))


def _public(t: dict) -> dict:
    """API-safe payload for dashboard and clients."""
    return {
        "ticker": t.get("ticker"),
        "name": t.get("name"),
        "address": t.get("address"),
        "source": t.get("source"),
        "stage": t.get("stage"),
        "lifecycle": t.get("lifecycle"),
        "signal": t.get("signal"),
        "hawk_score": t.get("hawk_score"),
        "alpha_score": t.get("hawk_score") or t.get("alpha_score"),
        "opportunity_score": t.get("opportunity_score"),
        "confidence": t.get("confidence"),
        "momentum_score": t.get("momentum_score"),
        "organicity_score": t.get("organicity_score"),
        "liquidity_score": t.get("liquidity_score"),
        "narrative_score": t.get("narrative_score"),
        "earlyness_score": t.get("earlyness_score"),
        "rug_risk": t.get("rug_risk"),
        "rating": t.get("rating"),
        "recommendation": t.get("recommendation"),
        "entry_state": t.get("entry_state"),
        "reasons": t.get("reasons") or [],
        "risk_flags": [f for f in (t.get("risk_flags") or []) if "INSUFFICIENT" not in f][:8],
        "positive_signals": t.get("positive_signals") or [],
        "negative_signals": t.get("negative_signals") or [],
        "thesis": t.get("thesis") or {},
        "velocity": t.get("velocity") or {},
        "market_cap": t.get("market_cap"),
        "liquidity": t.get("liquidity"),
        "volume": t.get("volume"),
        "price_usd": t.get("price_usd"),
        "curve_progress": t.get("curve_progress"),
        "age_minutes": t.get("age_minutes"),
        "reply_count": t.get("reply_count"),
        "image": t.get("image"),
        "twitter": t.get("twitter"),
        "website": t.get("website"),
        "dex_url": t.get("dex_url") or t.get("url"),
        "is_live": t.get("is_live"),
        "price_change_m5": t.get("price_change_m5"),
        "holder_quality": t.get("holder_quality"),
        "holder_top1_pct": (t.get("holder_intel") or {}).get("top1_pct") if isinstance(t.get("holder_intel"), dict) else None,
        "holder_top10_pct": (t.get("holder_intel") or {}).get("top10_pct") if isinstance(t.get("holder_intel"), dict) else None,
        "smart_money": t.get("smart_money"),
        "creator_intel": t.get("creator_intel"),
        "confirmation": t.get("confirmation"),
        "creator_launch_count_seen": t.get("creator_launch_count_seen"),
        "actionable": t.get("entry_state") in ("EARLY_ENTRY", "CONFIRMATION_ENTRY"),
        "wash_score": t.get("wash_score"),
        "breakout_eligible": t.get("breakout_eligible"),
        "breakout_score": t.get("breakout_score"),
        "breakout_label": t.get("breakout_label"),
        "path_to_100k": t.get("path_to_100k"),
        "mcap_gap_to_100k": t.get("mcap_gap_to_100k"),
        "breakout_notes": t.get("breakout_notes") or [],
        "discovery_channel": t.get("discovery_channel"),
        "ladder": t.get("ladder"),
        "ladder_intent": t.get("ladder_intent"),
        "size_hint": t.get("size_hint"),
        "lottery_score": t.get("lottery_score"),
        "lottery_eligible": t.get("lottery_eligible"),
        "lottery_warning": t.get("lottery_warning"),
        "lottery_notes": t.get("lottery_notes") or [],
        "focus_score": t.get("focus_score"),
        "operator_priority": t.get("operator_priority"),
        "pattern_score": t.get("pattern_score"),
        "pattern_net": t.get("pattern_net"),
        "pattern_summary": t.get("pattern_summary"),
        "hidden_signals": t.get("hidden_signals") or [],
        "convergence_score": t.get("convergence_score"),
        "convergence_label": t.get("convergence_label"),
        "convergence_channels": t.get("convergence_channels"),
        "reliability": t.get("reliability"),
        "decay": t.get("decay"),
        "display_score": t.get("display_score"),
        "runner_score": t.get("runner_score"),
        "runner_label": t.get("runner_label"),
        "winner_watch": t.get("winner_watch"),
        "volume_watch": t.get("volume_watch"),
        "attention_watch": t.get("attention_watch"),
        "runner_notes": t.get("runner_notes") or [],
        "developer_intel": t.get("developer_intel"),
        "missing_channels": t.get("missing_channels") or [],


        "wash_flags": (t.get("wash") or {}).get("flags") if isinstance(t.get("wash"), dict) else [],


        "scanned_at": int(time.time()),
    }


async def get_hawk_feed(limit: int = 30) -> list[dict]:
    """Private-operator default: rank by focus, surface ladder names first."""
    key = f"hawk:{limit}"
    if key in _cache:
        return _cache[key]

    raw = await discover_opportunities(limit=max(limit + 40, 80), enrich=True)
    ranked = rank_tokens(raw)

    def _op_key(x: dict):
        ladder = x.get("ladder") or "NOISE"
        focus = x.get("focus_score") or 0
        pri = 1 if x.get("operator_priority") else 0
        order = {"BREAKOUT": 0, "LOTTERY": 1, "EARLY": 2, "EXPANSION": 3, "NOISE": 9}
        return (
            0 if pri else 1,
            order.get(ladder, 9),
            -focus,
            x.get("rug_risk") or 100,
        )

    ranked.sort(key=_op_key)
    feed = [_public(t) for t in ranked[:limit]]
    _cache[key] = feed

    try:
        await scan_and_alert(feed)
    except Exception:
        pass
    return feed


async def get_prime(limit: int = 10) -> list[dict]:
    feed = await get_hawk_feed(40)
    primes = [
        t
        for t in feed
        if t.get("signal") == "prime"
        or (
            (t.get("hawk_score") or 0) >= 78
            and (t.get("rug_risk") or 100) < 48
            and (t.get("confidence") or 0) >= 55
            and (t.get("reply_count") or 0) >= 6
        )
    ]
    return primes[:limit]


async def get_top5() -> list[dict]:
    feed = await get_hawk_feed(40)
    # already ranked by opportunity; take diverse top
    return feed[:5]


async def get_radar(kind: str) -> list[dict]:
    feed = await get_hawk_feed(40)
    if kind == "graduation":
        return [t for t in feed if t.get("signal") == "graduating" or t.get("lifecycle") == "GRADUATING"][:15]
    if kind == "momentum":
        return [
            t
            for t in feed
            if (t.get("velocity") or {}).get("mcap_accelerating")
            or (t.get("velocity") or {}).get("reply_accelerating")
            or (t.get("momentum_score") or 0) >= 55
        ][:15]
    if kind == "risk":
        return sorted(feed, key=lambda x: -(x.get("rug_risk") or 0))[:15]
    if kind == "early":
        # Emerging hybrid band — not ultra-new spam
        return [
            t
            for t in feed
            if t.get("stage") == "bonding"
            and 6 <= (t.get("age_minutes") or 0) <= 45
            and (t.get("reply_count") or 0) >= 3
        ][:15]
    if kind == "postgrad":
        return [
            t
            for t in feed
            if t.get("stage") == "graduated" or t.get("lifecycle") == "POST_GRADUATION"
        ][:15]
    if kind == "actionable":
        return [t for t in feed if t.get("entry_state") in ("EARLY_ENTRY", "CONFIRMATION_ENTRY")][:15]
    if kind == "breakout":
        band = [
            t
            for t in feed
            if (t.get("market_cap") or 0) >= 30_000
            and (t.get("market_cap") or 0) <= 250_000
        ]
        band.sort(
            key=lambda x: (
                -(x.get("breakout_score") or 0),
                x.get("rug_risk") or 100,
                -(x.get("opportunity_score") or 0),
            )
        )
        return band[:20]
    if kind == "focus":
        # Operator board: ladder names + explicit runner candidates
        band = [
            t
            for t in feed
            if t.get("operator_priority")
            or t.get("winner_watch")
            or t.get("volume_watch")
            or t.get("attention_watch")
            or t.get("ladder") in ("LOTTERY", "EARLY", "BREAKOUT")
            or (t.get("runner_score") or 0) >= 52
        ]
        band = [t for t in band if t.get("ladder") != "NOISE" or t.get("winner_watch")]
        band.sort(
            key=lambda x: (
                0 if x.get("winner_watch") or x.get("volume_watch") or (x.get("runner_score") or 0) >= 70 else
                1 if x.get("ladder") == "BREAKOUT" and (x.get("breakout_score") or 0) >= 50 else
                2 if (x.get("runner_score") or 0) >= 55 else
                3 if x.get("ladder") == "EARLY" else
                4 if x.get("ladder") == "LOTTERY" else 5,
                -(x.get("runner_score") or 0),
                -(x.get("display_score") or x.get("focus_score") or 0),
                x.get("rug_risk") or 100,
            )
        )
        return band[:25]
    if kind == "lottery":
        band = [t for t in feed if t.get("ladder") == "LOTTERY" or (
            t.get("lottery_eligible") and (t.get("lottery_score") or 0) >= 40
        )]
        band.sort(
            key=lambda x: (
                -(x.get("lottery_score") or 0),
                x.get("rug_risk") or 100,
                x.get("age_minutes") or 999,
            )
        )
        return band[:20]
    if kind == "ladder":
        # Full ladder snapshot excluding pure noise
        band = [t for t in feed if t.get("ladder") in ("LOTTERY", "EARLY", "BREAKOUT", "EXPANSION")]
        order = {"LOTTERY": 0, "EARLY": 1, "BREAKOUT": 2, "EXPANSION": 3}
        band.sort(key=lambda x: (order.get(x.get("ladder") or "", 9), -(x.get("lottery_score") or x.get("breakout_score") or 0)))
        return band[:30]
    return feed[:15]


async def get_stats() -> dict[str, Any]:
    feed = await get_hawk_feed(40)
    return {
        "total": len(feed),
        "on_curve": sum(1 for t in feed if t.get("stage") == "bonding"),
        "prime": sum(1 for t in feed if t.get("signal") == "prime"),
        "high": sum(1 for t in feed if t.get("signal") == "high"),
        "graduating": sum(1 for t in feed if t.get("signal") == "graduating" or t.get("lifecycle") == "GRADUATING"),
        "high_risk": sum(1 for t in feed if (t.get("rug_risk") or 0) >= 55),
        "early_entry": sum(1 for t in feed if t.get("entry_state") == "EARLY_ENTRY"),
        "breakout_30k": sum(1 for t in feed if (t.get("market_cap") or 0) >= 30_000),
        "path_high": sum(1 for t in feed if t.get("breakout_label") == "HIGH_PATH_TO_100K"),
        "lottery_n": sum(1 for t in feed if t.get("ladder") == "LOTTERY"),
        "focus_n": sum(1 for t in feed if t.get("operator_priority")),
        "updated_at": int(time.time()),
        "version": _settings.version,
    }
