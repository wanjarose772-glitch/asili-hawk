"""
Deep public-data pattern layer — non-obvious structural signals.

Legal: only fields from pump.fun / dex / helius / our snapshots.
No non-public tips. Labels are directional forensic hints, not proof.
"""

from __future__ import annotations

import re
from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


# --- name / meta structure ---
_COPYCAT = re.compile(
    r"(pepe|doge|shib|bonk|wif|trump|elon|ai\s*agent|chatgpt|gpt|grok|jeet|rug|moon|1000?x)",
    re.I,
)
_TICKER_SPAM = re.compile(r"(.)\1{3,}")  # aaaa, 1111
_LEET = re.compile(r"[0-9]{3,}")


def _meta_patterns(token: dict) -> list[dict]:
    out = []
    name = (token.get("name") or "")
    ticker = (token.get("ticker") or token.get("symbol") or "")
    desc = (token.get("description") or "")
    blob = f"{name} {ticker} {desc}"

    if _COPYCAT.search(blob):
        out.append({
            "id": "copycat_narrative",
            "severity": "bearish",
            "weight": -8,
            "note": "Generic copycat narrative (pepe/bonk/ai/etc) — crowded meta, lower edge",
        })
    if _TICKER_SPAM.search(ticker):
        out.append({
            "id": "ticker_char_spam",
            "severity": "bearish",
            "weight": -10,
            "note": "Repeated characters in ticker — common low-effort deploys",
        })
    if len(ticker) <= 2 and _f(token.get("market_cap")) < 50_000:
        out.append({
            "id": "ultra_short_ticker",
            "severity": "neutral",
            "weight": -3,
            "note": "Very short ticker — often squatted / contested names",
        })
    if not desc or len(desc.strip()) < 8:
        out.append({
            "id": "empty_description",
            "severity": "bearish",
            "weight": -5,
            "note": "Empty/minimal description — low effort deploy signal",
        })
    social_n = sum(bool(token.get(k)) for k in ("twitter", "website", "telegram"))
    if social_n == 0 and _f(token.get("age_minutes"), 999) > 8:
        out.append({
            "id": "no_social_after_warmup",
            "severity": "bearish",
            "weight": -7,
            "note": "No socials after warmup window — weak organic footprint",
        })
    if social_n >= 2 and int(token.get("reply_count") or 0) >= 5:
        out.append({
            "id": "multi_social_plus_chat",
            "severity": "bullish",
            "weight": 8,
            "note": "Multiple socials + chat — stronger surface organic footprint",
        })
    if token.get("is_live"):
        out.append({
            "id": "live_stream_active",
            "severity": "bullish",
            "weight": 10,
            "note": "Live stream flag — attention channel (still not proof of quality)",
        })
    return out


def _structure_patterns(token: dict) -> list[dict]:
    """Non-obvious mcap / curve / age / reply geometry."""
    out = []
    mcap = _f(token.get("market_cap"))
    age = max(_f(token.get("age_minutes"), 0.05), 0.05)
    curve = _f(token.get("curve_progress"))
    replies = int(token.get("reply_count") or 0)
    vol = _f(token.get("volume"))
    liq = _f(token.get("liquidity"))
    chg = _f(token.get("price_change_m5"))
    stage = (token.get("stage") or "").lower()

    # mcap velocity proxy without full history
    mcap_per_min = mcap / age
    if mcap_per_min > 25_000 and replies < 3 and age < 15:
        out.append({
            "id": "fast_mcap_no_chat",
            "severity": "bearish",
            "weight": -16,
            "note": "Mcap grew very fast with almost no chat — classic sniper/bundle shape",
        })
    elif mcap_per_min > 8_000 and replies >= 8 and age < 30:
        out.append({
            "id": "fast_mcap_with_chat",
            "severity": "bullish",
            "weight": 9,
            "note": "Fast mcap with concurrent chat — demand less likely pure silent fill",
        })

    # Curve vs mcap inconsistency
    if stage == "bonding" and curve < 15 and mcap > 40_000:
        out.append({
            "id": "mcap_curve_mismatch",
            "severity": "bearish",
            "weight": -12,
            "note": "High mcap vs low curve progress — data inconsistency or weird reserves",
        })
    if stage == "bonding" and curve >= 85 and mcap < 12_000:
        out.append({
            "id": "high_curve_low_mcap",
            "severity": "neutral",
            "weight": -4,
            "note": "Late curve but still small mcap — weak demand into graduation",
        })

    # Reply density vs mcap (organic pressure proxy)
    if mcap >= 15_000:
        reply_per_10k = replies / max(mcap / 10_000, 0.1)
        if reply_per_10k < 0.3 and replies < 4:
            out.append({
                "id": "thin_chat_per_mcap",
                "severity": "bearish",
                "weight": -11,
                "note": "Very thin chat relative to mcap — price without conversation",
            })
        elif reply_per_10k >= 2.0 and replies >= 8:
            out.append({
                "id": "rich_chat_per_mcap",
                "severity": "bullish",
                "weight": 10,
                "note": "Chat density high vs mcap — stronger organic pressure proxy",
            })

    # Liquidity geometry
    if mcap > 0 and liq > 0:
        liq_ratio = liq / mcap
        if mcap >= 30_000 and liq_ratio < 0.08:
            out.append({
                "id": "fragile_liq_vs_mcap",
                "severity": "bearish",
                "weight": -14,
                "note": "Liquidity tiny vs mcap — exit is the trade for someone else",
            })
        elif 0.15 <= liq_ratio <= 0.55 and mcap >= 20_000:
            out.append({
                "id": "balanced_liq_ratio",
                "severity": "bullish",
                "weight": 6,
                "note": "Liquidity ratio in a more tradable band",
            })

    # Volume without structure
    if vol > mcap * 3 and mcap >= 10_000 and replies < 5:
        out.append({
            "id": "volume_overdrive_thin_chat",
            "severity": "bearish",
            "weight": -13,
            "note": "Volume >> mcap with thin chat — possible churn / wash-like activity",
        })

    # Dump into "success" band
    if mcap >= 30_000 and chg <= -30:
        out.append({
            "id": "dumping_in_breakout_band",
            "severity": "bearish",
            "weight": -15,
            "note": "Already dumping hard inside $30k+ band — weak path continuation",
        })
    if 8_000 <= mcap <= 25_000 and 5 <= chg <= 35 and replies >= 5:
        out.append({
            "id": "orderly_grind_early",
            "severity": "bullish",
            "weight": 8,
            "note": "Orderly grind (not vertical) with chat in asymmetric band",
        })

    # Graduation pressure with silence
    if stage == "bonding" and curve >= 78 and replies == 0:
        out.append({
            "id": "silent_graduation_push",
            "severity": "bearish",
            "weight": -12,
            "note": "Near graduation with zero replies — often mechanical/snipe fill",
        })
    if stage == "graduated" and age <= 45 and replies >= 10 and mcap >= 40_000:
        out.append({
            "id": "fresh_grad_with_chat",
            "severity": "bullish",
            "weight": 9,
            "note": "Fresh graduate still carrying chat — better than silent post-grad pumps",
        })

    return out


def _holder_patterns(token: dict) -> list[dict]:
    out = []
    top1 = token.get("holder_top1_pct")
    top10 = token.get("holder_top10_pct")
    hi = token.get("holder_intel") if isinstance(token.get("holder_intel"), dict) else {}
    if top1 is None and hi.get("data_quality") == "OK":
        top1 = hi.get("top1_pct")
        top10 = hi.get("top10_pct")
    top1 = _f(top1, -1)
    top10 = _f(top10, -1)
    if top1 < 0:
        return out

    # Non-obvious: extreme concentration is bearish, but also
    # "perfectly flat" tiny top1 on a brand-new micro can mean data is pool-dominated or sparse
    if top1 >= 85:
        out.append({
            "id": "single_wallet_dominance",
            "severity": "bearish",
            "weight": -20,
            "note": "Top holder ≥85% — effective single-wallet control",
        })
    elif top1 >= 60:
        out.append({
            "id": "high_concentration",
            "severity": "bearish",
            "weight": -12,
            "note": "Top holder ≥60% — elevated dump leverage",
        })
    elif 20 <= top1 <= 40 and top10 > 0 and top10 < 75:
        out.append({
            "id": "moderate_distribution",
            "severity": "bullish",
            "weight": 7,
            "note": "Moderate top1 with non-extreme top10 — healthier distribution band",
        })

    if top10 >= 95 and top1 >= 40:
        out.append({
            "id": "top10_closed_set",
            "severity": "bearish",
            "weight": -14,
            "note": "Top10 holds almost everything — closed holder set",
        })
    return out


def _deployer_patterns(token: dict) -> list[dict]:
    out = []
    c_launches = int(token.get("creator_launch_count_seen") or 0)
    # From memory/store — process + sqlite lifetime
    if c_launches >= 5:
        out.append({
            "id": "serial_deployer_hot",
            "severity": "bearish",
            "weight": -18,
            "note": f"Creator seen with {c_launches}+ launches in Hawk memory — serial deployer risk",
        })
    elif c_launches >= 3:
        out.append({
            "id": "repeat_deployer",
            "severity": "bearish",
            "weight": -10,
            "note": f"Creator seen {c_launches} times — elevated factory-deploy risk",
        })
    elif c_launches == 1:
        out.append({
            "id": "first_seen_creator",
            "severity": "neutral",
            "weight": 2,
            "note": "Creator first-seen in this Hawk window — no serial history yet",
        })
    return out


def _velocity_patterns(token: dict, vel: dict | None) -> list[dict]:
    out = []
    vel = vel or {}
    if not vel.get("has_history"):
        out.append({
            "id": "no_multi_poll_history",
            "severity": "neutral",
            "weight": -3,
            "note": "Single snapshot — acceleration unconfirmed",
        })
        return out

    if vel.get("mcap_accelerating") and vel.get("reply_accelerating"):
        out.append({
            "id": "dual_acceleration",
            "severity": "bullish",
            "weight": 14,
            "note": "Both mcap and replies accelerating across polls — rare constructive combo",
        })
    elif vel.get("mcap_accelerating") and not vel.get("reply_accelerating") and int(token.get("reply_count") or 0) < 4:
        out.append({
            "id": "mcap_accel_reply_flat",
            "severity": "bearish",
            "weight": -11,
            "note": "Mcap accelerating while replies flat/low — demand may be non-organic",
        })
    if vel.get("curve_accelerating") and int(token.get("reply_count") or 0) >= 6:
        out.append({
            "id": "curve_accel_with_chat",
            "severity": "bullish",
            "weight": 8,
            "note": "Curve filling faster with chat present",
        })
    return out


def _channel_patterns(token: dict) -> list[dict]:
    out = []
    ch = token.get("discovery_channel")
    mcap = _f(token.get("market_cap"))
    if ch == "active" and mcap >= 30_000:
        out.append({
            "id": "active_trade_channel",
            "severity": "neutral",
            "weight": 3,
            "note": "Found via last_trade channel — already in motion (less early, more real)",
        })
    if ch == "new" and mcap >= 30_000 and _f(token.get("age_minutes"), 999) < 10:
        out.append({
            "id": "new_channel_already_30k",
            "severity": "bearish",
            "weight": -9,
            "note": "Brand-new list but already $30k+ — often bundled open",
        })
    return out


def analyze_patterns(token: dict, vel: dict | None = None) -> dict:
    signals: list[dict] = []
    signals.extend(_meta_patterns(token))
    signals.extend(_structure_patterns(token))
    signals.extend(_holder_patterns(token))
    signals.extend(_deployer_patterns(token))
    signals.extend(_velocity_patterns(token, vel))
    signals.extend(_channel_patterns(token))

    bull = sum(s["weight"] for s in signals if s["weight"] > 0)
    bear = sum(s["weight"] for s in signals if s["weight"] < 0)
    net = int(max(-40, min(40, bull + bear)))

    # Pattern score 0-100 (50 = neutral)
    pattern_score = int(max(0, min(100, 50 + net)))

    hidden = [s for s in signals if s["id"] in {
        "fast_mcap_no_chat", "mcap_accel_reply_flat", "thin_chat_per_mcap",
        "volume_overdrive_thin_chat", "silent_graduation_push", "mcap_curve_mismatch",
        "dual_acceleration", "orderly_grind_early", "rich_chat_per_mcap",
        "serial_deployer_hot", "fragile_liq_vs_mcap", "dumping_in_breakout_band",
        "new_channel_already_30k", "top10_closed_set",
    }]

    return {
        "pattern_score": pattern_score,
        "pattern_net": net,
        "pattern_signals": signals[:16],
        "hidden_signals": hidden[:10],
        "pattern_bull": int(bull),
        "pattern_bear": int(bear),
        "pattern_summary": _summary(signals, net),
    }


def _summary(signals: list[dict], net: int) -> str:
    if not signals:
        return "No structural pattern flags from available public fields"
    top_bears = [s["note"] for s in signals if s["weight"] < 0][:2]
    top_bulls = [s["note"] for s in signals if s["weight"] > 0][:2]
    if net <= -12:
        return "Structure leans risk: " + "; ".join(top_bears)
    if net >= 12:
        return "Structure leans constructive: " + "; ".join(top_bulls)
    return "Mixed structure: " + "; ".join((top_bulls + top_bears)[:2])
