"""
ASILI HAWK composite intelligence engine v1.0

Produces:
- lifecycle
- velocities (from memory when available)
- organicity proxy (from available public signals only)
- liquidity health
- narrative
- risk / rug_risk
- confidence (evidence quality)
- hawk_score (composite)
- opportunity_score
- entry_state
- thesis (evidence-based bullets)
- signal classification (prime only with multi-confirm)

Honest about missing data: holder distribution, true smart-money,
and creator history are INSUFFICIENT_DATA without paid indexers.
"""

from __future__ import annotations

import re
from typing import Any

from app.intelligence.lifecycle import classify_lifecycle
from app.intelligence.memory import track, persist, velocity_metrics, confirmation_metrics, creator_launch_count
from app.intelligence.narrative import analyze_narrative
from app.intelligence.wash import score_wash
from app.intelligence.ladder import assign_ladder
from app.intelligence.patterns import analyze_patterns
from app.intelligence.developer import analyze_developer
from app.intelligence.convergence import score_convergence
from app.intelligence.reliability import score_reliability

EXCLUDED = {
    "SOL", "USDC", "USDT", "WSOL", "BTC", "ETH", "WBTC", "WETH",
    "JUP", "JTO", "BONK", "WIF", "RAY", "ORCA", "PUMP",
}
SUSPICIOUS = (
    "airdrop", "claim", "presale", "test", "scam", "rug", "honeypot",
    "free mint", "whitelist", "1000x", "100x",
)
# Word-boundary matching so e.g. "test" doesn't match inside "CONTEST",
# "PROTEST", "ATTEST", and "claim" doesn't match inside "CLAIMR". \b works
# fine here since all SUSPICIOUS terms are plain alnum/space strings.
_SUSPICIOUS_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in SUSPICIOUS) + r")\b",
    re.IGNORECASE,
)


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _hard_reject(token: dict) -> list[str] | None:
    symbol = (token.get("ticker") or token.get("symbol") or "").upper().strip()
    name = (token.get("name") or "").lower()
    desc = (token.get("description") or "").lower()
    if not symbol or symbol in EXCLUDED or len(symbol) > 24:
        return ["excluded_symbol"]
    if _SUSPICIOUS_RE.search(f"{name} {symbol.lower()} {desc}"):
        return ["suspicious_terms"]
    mcap = _f(token.get("market_cap"))
    replies = int(token.get("reply_count") or 0)
    age = _f(token.get("age_minutes"), 999)
    if 0 < mcap < 1000 and replies == 0:
        return ["dust_inactive"]
    if age < 1.2 and replies == 0 and mcap < 2000 and not token.get("twitter"):
        return ["ghost_launch"]
    return None


def _organicity(token: dict, vel: dict) -> dict:
    """
    Proxy organicity from public signals only.
    True wash-trade / wallet clustering requires holder/tx graphs → INSUFFICIENT beyond proxies.
    """
    replies = int(token.get("reply_count") or 0)
    age = max(_f(token.get("age_minutes"), 0.1), 0.1)
    curve = _f(token.get("curve_progress"))
    vol = _f(token.get("volume"))
    mcap = _f(token.get("market_cap"))
    has_social = bool(token.get("twitter") or token.get("website") or token.get("is_live"))

    score = 35
    notes: list[str] = []
    flags: list[str] = []

    # Chat density vs age
    reply_rate = replies / age
    if reply_rate >= 2:
        score += 18
        notes.append("strong_chat_rate")
    elif reply_rate >= 0.5:
        score += 10
        notes.append("moderate_chat_rate")
    elif replies == 0:
        score -= 20
        flags.append("no_chat")
        notes.append("no_organic_chat_signal")

    if has_social:
        score += 8
        notes.append("external_social_link")
    else:
        score -= 5
        flags.append("no_social")

    # Fast curve without chat is suspicious
    curve_vel = vel.get("curve_velocity_per_min")
    if curve_vel is not None and curve_vel > 15 and replies < 5:
        score -= 22
        flags.append("possible_inorganic_curve_fill")
        notes.append("fast_curve_low_chat")
    if age > 0 and curve / age > 30 and replies < 5:
        score -= 12
        flags.append("high_curve_velocity")

    # Volume vs mcap without chat
    if vol > 0 and mcap > 0 and vol / max(mcap, 1) > 3 and replies < 5:
        score -= 10
        flags.append("volume_mcap_outlier")
        notes.append("volume_high_relative_to_mcap_low_chat")

    if token.get("is_live"):
        score += 12
        notes.append("live_stream_participation")

    if vel.get("reply_accelerating"):
        score += 8
        notes.append("reply_acceleration")
    if vel.get("mcap_accelerating") and replies >= 3:
        score += 6
        notes.append("mcap_acceleration_with_chat")

    score = max(0, min(100, score))
    return {
        "organicity_score": score,
        "notes": notes,
        "flags": flags,
        "data_quality": "PROXY_ONLY",
        "limitation": "Holder/tx graph not available from current public feeds",
    }


def _liquidity_health(token: dict) -> dict:
    liq = _f(token.get("liquidity"))
    mcap = _f(token.get("market_cap"))
    vol = _f(token.get("volume"))
    notes: list[str] = []
    score = 40
    ratio = None
    if mcap > 0 and liq > 0:
        ratio = liq / mcap
        if ratio >= 0.25:
            score += 20
            notes.append("healthy_liq_mcap_ratio")
        elif ratio >= 0.1:
            score += 10
            notes.append("moderate_liq_mcap_ratio")
        elif ratio < 0.05:
            score -= 15
            notes.append("thin_liquidity_vs_mcap")
    else:
        notes.append("liquidity_or_mcap_incomplete")
        return {
            "liquidity_score": 30,
            "liq_mcap_ratio": ratio,
            "notes": notes,
            "data_quality": "LIMITED",
        }

    if vol > 0 and liq > 0:
        if vol / liq > 15:
            score -= 12
            notes.append("volume_far_exceeds_liquidity")
        elif vol / liq > 5:
            score -= 5
            notes.append("elevated_volume_vs_liquidity")

    if liq >= 15000:
        score += 10
    elif liq >= 5000:
        score += 5
    elif liq < 1500 and mcap > 10000:
        score -= 10
        notes.append("exit_risk_thin_pool")

    score = max(0, min(100, score))
    return {
        "liquidity_score": score,
        "liq_mcap_ratio": round(ratio, 4) if ratio is not None else None,
        "notes": notes,
        "data_quality": "OK" if liq > 0 else "LIMITED",
    }


def _risk_engine(token: dict, org: dict, liq: dict, vel: dict) -> dict:
    risk = 20
    flags: list[str] = list(org.get("flags") or [])

    age = _f(token.get("age_minutes"), 999)
    replies = int(token.get("reply_count") or 0)
    curve = _f(token.get("curve_progress"))
    chg = _f(token.get("price_change_m5"))
    stage = token.get("stage")

    if replies == 0:
        risk += 18
        if age < 5:
            risk += 14
            flags.append("silent_and_fresh")
        if age < 2:
            risk += 8
            flags.append("brand_new_silent")

    if stage == "bonding" and age > 0:
        velocity = curve / max(age, 0.25)
        if velocity > 40 and replies < 5:
            risk += 18
            flags.append("fast_curve_no_chat")
        elif velocity > 25 and replies < 3:
            risk += 10
            flags.append("fast_fill")

    if chg >= 50 and replies < 5:
        risk += 14
        flags.append("parabolic_thin")
    if chg <= -30:
        risk += 12
        flags.append("already_dumping")

    if (liq.get("liquidity_score") or 50) < 35:
        risk += 10
        flags.append("liquidity_concern")

    if (org.get("organicity_score") or 50) < 30:
        risk += 12
        flags.append("low_organicity")

    if vel.get("data_quality") == "INSUFFICIENT_DATA" and age < 5:
        risk += 5
        flags.append("insufficient_history")

    # Holder concentration when Helius provided it
    hi = token.get("holder_intel") or {}
    if hi.get("data_quality") == "OK":
        top1 = float(hi.get("top1_pct") or 0)
        top10 = float(hi.get("top10_pct") or 0)
        if top1 >= 40:
            risk += 18
            flags.append("holder_top1_dominant")
        elif top1 >= 25:
            risk += 10
            flags.append("holder_top1_elevated")
        if top10 >= 85:
            risk += 14
            flags.append("holder_top10_concentrated")
        elif top10 < 55:
            risk -= 6  # modest relief
            flags.append("holder_top10_dispersed")
        for f in hi.get("flags") or []:
            flags.append(f"holder:{f}")
    else:
        flags.append("holder_distribution:INSUFFICIENT_DATA")

    flags.append("creator_history:INSUFFICIENT_DATA")
    flags.append("smart_money:INSUFFICIENT_DATA")

    risk = max(0, min(100, risk))
    return {"rug_risk": risk, "risk_flags": list(dict.fromkeys(flags))[:14]}


def _confidence(token: dict, vel: dict, org: dict, liq: dict) -> int:
    """Evidence quality — high score with low confidence is not tradeable."""
    c = 35
    replies = int(token.get("reply_count") or 0)
    age = _f(token.get("age_minutes"), 0)

    if replies >= 15:
        c += 18
    elif replies >= 6:
        c += 12
    elif replies >= 2:
        c += 5
    else:
        c -= 10

    if age >= 10:
        c += 10
    elif age >= 5:
        c += 5
    elif age < 2:
        c -= 12

    if vel.get("data_quality") == "OK":
        c += 12
    elif vel.get("data_quality") == "LIMITED":
        c += 5

    if (org.get("organicity_score") or 0) >= 55:
        c += 8
    if (liq.get("data_quality") == "OK"):
        c += 6
    if token.get("twitter"):
        c += 4
    if token.get("price_usd"):
        c += 3  # dex enrichment present

    hi = token.get("holder_intel") or {}
    if hi.get("data_quality") == "OK":
        c += 10
        c = min(c, 88)  # holders improve confidence; creator still unknown
    else:
        c = min(c, 78)  # cannot claim high confidence without holders/creators
    return max(5, min(92, c))


def _entry_state(token: dict, hawk: int, risk: int, conf: int, lifecycle: str, confirmed: bool = False) -> str:
    """
    Action tiers — deliberately conservative.
    EARLY_ENTRY / CONFIRMATION_ENTRY are the only 'consider size' states.
    WATCH means research only — not an entry call.
    """
    replies = int(token.get("reply_count") or 0)
    age = _f(token.get("age_minutes"), 999)

    if risk >= 60 or hawk < 48:
        return "AVOID"
    if risk >= 50 or conf < 45:
        return "WAIT"
    if lifecycle == "NEW" and (replies < 8 or age < 6):
        return "WATCH"  # research only
    # Strongest actionable band
    if hawk >= 78 and conf >= 58 and risk < 42 and replies >= 8 and confirmed:
        if age <= 45 and token.get("stage") == "bonding":
            return "EARLY_ENTRY"
        return "CONFIRMATION_ENTRY"
    if hawk >= 70 and conf >= 52 and risk < 48 and replies >= 6:
        return "CONFIRMATION_ENTRY" if confirmed else "WATCH"
    if hawk >= 58 and risk < 55:
        return "WATCH"  # interesting, not an entry call
    if conf < 40:
        return "WAIT"
    return "WATCH"


def _thesis(token: dict, parts: dict) -> dict:
    """Evidence-linked thesis — only statements grounded in observed fields."""
    interesting: list[str] = []
    confirming: list[str] = []
    explode: list[str] = []
    fail: list[str] = []
    invalidate: list[str] = []
    why_now: list[str] = []

    age = token.get("age_minutes")
    curve = token.get("curve_progress")
    replies = token.get("reply_count")
    stage = token.get("stage")
    vel = parts["velocity"]
    org = parts["organicity"]
    risk = parts["risk"]["rug_risk"]

    if stage == "bonding":
        interesting.append(f"Still on bonding curve at ~{curve}% progress")
    if age is not None and age <= 45:
        interesting.append(f"Age {age}m — still in early window")
    if replies and replies >= 6:
        confirming.append(f"Chat activity present ({replies} replies)")
    if token.get("is_live"):
        confirming.append("Live stream active")
    if vel.get("mcap_accelerating"):
        confirming.append("Market-cap velocity accelerating in recent snapshots")
    if vel.get("reply_accelerating"):
        confirming.append("Reply rate accelerating")
    if (org.get("organicity_score") or 0) >= 55:
        confirming.append(f"Organicity proxy {org['organicity_score']} (chat/social/velocity mix)")

    if curve and curve >= 70 and stage == "bonding":
        explode.append("Approaching graduation zone if participation holds")
    if replies and replies >= 15:
        explode.append("Elevated organic chat may attract secondary attention")
    if token.get("twitter"):
        explode.append("External Twitter link may aid narrative spread")

    if risk >= 50:
        fail.append(f"Elevated rug risk score ({risk})")
    if replies == 0:
        fail.append("No chat — demand may be inorganic or nonexistent")
    if "possible_inorganic_curve_fill" in (org.get("flags") or []):
        fail.append("Curve filled quickly with low chat — possible coordination")
    fail.append("Holder concentration unknown (INSUFFICIENT_DATA)")
    fail.append("Creator track record unknown (INSUFFICIENT_DATA)")

    invalidate.append("Sharp dump in price with rising rug flags")
    invalidate.append("Chat stalls while curve/mcap stalls")
    invalidate.append("Liquidity deteriorates vs market cap")

    if stage == "bonding" and age is not None and age <= 60:
        why_now.append("Pre-terminal window — still before full terminal discovery in many cases")
    if vel.get("mcap_accelerating") or vel.get("reply_accelerating"):
        why_now.append("Observed acceleration in recent polling window")

    return {
        "why_interesting": interesting[:4],
        "what_confirms": confirming[:4],
        "what_could_work": explode[:3],
        "what_could_fail": fail[:5],
        "what_invalidates": invalidate[:3],
        "why_now": why_now[:3],
    }


def _breakout_potential(token: dict, hawk: int, rug: int, conf: int, wash_score) -> dict:
    """
    For tokens already >= ~$30k mcap: likelihood of extending toward $100k+.
    This is relative ranking in the breakout band — not a guarantee.
    """
    mcap = _f(token.get("market_cap"))
    if mcap < 30_000:
        return {
            "breakout_eligible": False,
            "breakout_score": 0,
            "breakout_label": "BELOW_30K",
            "path_to_100k": None,
        }

    score = 35
    notes: list[str] = []
    age = _f(token.get("age_minutes"), 999)
    replies = int(token.get("reply_count") or 0)
    stage = token.get("stage") or ""
    curve = _f(token.get("curve_progress"))
    chg = _f(token.get("price_change_m5"))
    liq = _f(token.get("liquidity"))
    top1 = None
    hi = token.get("holder_intel") if isinstance(token.get("holder_intel"), dict) else None
    if hi and hi.get("data_quality") == "OK":
        top1 = _f(hi.get("top1_pct"))
    elif token.get("holder_top1_pct") is not None:
        top1 = _f(token.get("holder_top1_pct"))

    # Room to 100k
    if mcap < 50_000:
        score += 12
        notes.append("early_breakout_band_30_50k")
    elif mcap < 80_000:
        score += 8
        notes.append("mid_breakout_band_50_80k")
    elif mcap < 100_000:
        score += 4
        notes.append("approaching_100k")
    elif mcap < 150_000:
        score += 2
        notes.append("just_over_100k_continuation")
    else:
        score -= 8
        notes.append("already_extended_past_primary_target")

    if stage == "bonding" and curve >= 70:
        score += 10
        notes.append("near_graduation_pressure")
    elif stage == "graduated" and age <= 180:
        score += 8
        notes.append("fresh_graduate_window")
    elif stage == "bonding":
        score += 4

    if replies >= 15:
        score += 10
    elif replies >= 6:
        score += 6
    elif replies == 0:
        score -= 10
        notes.append("no_chat_weak_organic")

    if 3 <= chg <= 40:
        score += 6
    elif chg <= -25:
        score -= 12
        notes.append("dumping_into_breakout_band")
    elif chg >= 60 and replies < 5:
        score -= 8
        notes.append("thin_parabolic_in_band")

    if top1 is not None:
        if top1 >= 70:
            score -= 18
            notes.append("extreme_holder_concentration")
        elif top1 >= 50:
            score -= 10
            notes.append("high_holder_concentration")
        elif top1 < 35:
            score += 6

    if wash_score is not None and wash_score >= 60:
        score -= 14
        notes.append("wash_risk_elevated")

    if liq >= 15_000:
        score += 5
    elif liq > 0 and liq < 3_000 and mcap >= 40_000:
        score -= 8
        notes.append("thin_liq_vs_mcap")

    # Composite quality
    score += int((hawk - 50) * 0.15)
    score -= int(max(0, rug - 40) * 0.2)
    score += int(max(0, conf - 40) * 0.1)

    score = int(max(0, min(100, round(score))))
    if score >= 70 and rug < 50:
        label = "HIGH_PATH_TO_100K"
    elif score >= 55:
        label = "MODERATE_PATH"
    elif score >= 40:
        label = "WEAK_PATH"
    else:
        label = "UNLIKELY_PATH"

    return {
        "breakout_eligible": True,
        "breakout_score": score,
        "breakout_label": label,
        "path_to_100k": label,
        "breakout_notes": notes[:6],
        "mcap_gap_to_100k": max(0, round(100_000 - mcap, 2)) if mcap < 100_000 else 0,
    }


def analyze_token(token: dict) -> dict:
    reject = _hard_reject(token)
    if reject:
        return {
            **token,
            "hawk_score": 0,
            "alpha_score": 0,
            "confidence": 0,
            "opportunity_score": 0,
            "rug_risk": 100,
            "rating": "REJECT",
            "recommendation": "PASS",
            "entry_state": "AVOID",
            "signal": "reject",
            "lifecycle": "REJECT",
            "reasons": reject,
            "risk_flags": reject,
            "positive_signals": [],
            "negative_signals": reject,
            "thesis": {},
            "holder_quality": "INSUFFICIENT_DATA",
            "smart_money": "INSUFFICIENT_DATA",
            "creator_intel": "INSUFFICIENT_DATA",
        }

    # Record snapshot for future velocity
    track(token)
    vel = velocity_metrics(token.get("address") or "")
    wash = score_wash(token.get("tx_intel"))
    # Attach creator frequency before pattern layer so serial-deployer signals fire
    _creator = (token.get("creator") or "").strip()
    token = {**token, "creator_launch_count_seen": creator_launch_count(_creator)}
    patterns = analyze_patterns(token, vel)
    lifecycle = classify_lifecycle(token)
    narrative = analyze_narrative(token)
    org = _organicity(token, vel)
    liq = _liquidity_health(token)
    risk = _risk_engine(token, org, liq, vel)
    dev_intel = analyze_developer(token)

    age = _f(token.get("age_minutes"), 999)
    curve = _f(token.get("curve_progress"))
    replies = int(token.get("reply_count") or 0)
    mcap = _f(token.get("market_cap"))
    stage = token.get("stage") or "unknown"

    # Component scores 0-100
    # Earlyness: earlier is better but not if zero evidence
    if age <= 15 and replies >= 3:
        earlyness = 85
    elif age <= 30 and replies >= 2:
        earlyness = 75
    elif age <= 60:
        earlyness = 60
    elif age <= 120:
        earlyness = 45
    else:
        earlyness = 25

    # Momentum from velocity + price change + replies
    momentum = 30
    if vel.get("mcap_velocity_per_min") and vel["mcap_velocity_per_min"] > 200:
        momentum += 15
    if vel.get("mcap_accelerating"):
        momentum += 12
    if vel.get("reply_accelerating"):
        momentum += 10
    chg = _f(token.get("price_change_m5"))
    if 5 <= chg <= 40:
        momentum += 10
    elif chg > 60 and replies < 5:
        momentum -= 15
    if replies >= 10:
        momentum += 10
    momentum = max(0, min(100, momentum))

    # Alpha-like demand signal
    alpha = 25
    if stage == "bonding":
        alpha += 15
        if 20 <= curve <= 75:
            alpha += 10
        elif curve >= 75:
            alpha += 6
    if 2000 <= mcap <= 50000:
        alpha += 12
    if replies >= 10:
        alpha += 12
    elif replies >= 5:
        alpha += 6
    alpha = max(0, min(100, alpha))

    org_s = org["organicity_score"]
    liq_s = liq["liquidity_score"]
    narr_s = narrative["narrative_score"]
    rug = risk["rug_risk"]
    wscore = wash.get("wash_score")
    if wscore is not None:
        if wscore >= 70:
            rug = min(100, rug + 18)
            risk["risk_flags"] = list(dict.fromkeys((risk.get("risk_flags") or []) + ["likely_inorganic_flow"]))
        elif wscore >= 55:
            rug = min(100, rug + 10)
            risk["risk_flags"] = list(dict.fromkeys((risk.get("risk_flags") or []) + ["suspicious_tx_pattern"]))
        risk["rug_risk"] = rug

    # Deep pattern layer → risk / hawk adjustments
    pnet = int(patterns.get("pattern_net") or 0)
    if pnet <= -15:
        rug = min(100, rug + 12)
        risk["risk_flags"] = list(dict.fromkeys((risk.get("risk_flags") or []) + ["structural_risk_patterns"]))
    elif pnet <= -8:
        rug = min(100, rug + 6)
    elif pnet >= 15:
        rug = max(0, rug - 5)
    risk["rug_risk"] = rug

    # Composite Hawk Score — risk can dominate
    hawk = (
        alpha * 0.18
        + momentum * 0.16
        + earlyness * 0.12
        + org_s * 0.18
        + liq_s * 0.10
        + narr_s * 0.08
        + (100 - rug) * 0.18
    )
    hawk = int(max(0, min(100, round(hawk))))

    # --- Hybrid window adjustment ---
    # Prefer emerging / graduating / young post-grad with evidence over ultra-new noise.
    # Ultra-new without confirmation stays penalized.
    if lifecycle == "NEW" and replies < 8:
        hawk = max(0, hawk - 8)
    elif lifecycle in ("EARLY", "EMERGING") and replies >= 6:
        hawk = min(100, hawk + 5)
    elif lifecycle == "GRADUATING" and replies >= 5 and rug < 55:
        hawk = min(100, hawk + 6)
    elif lifecycle == "POST_GRADUATION" and age <= 180:
        if replies >= 8 and rug < 50:
            hawk = min(100, hawk + 4)
        elif replies < 3:
            hawk = max(0, hawk - 6)

    # Pattern layer influence on hawk (capped)
    pnet = int(patterns.get("pattern_net") or 0)
    if pnet >= 12:
        hawk = min(100, hawk + min(8, pnet // 4))
    elif pnet <= -12:
        hawk = max(0, hawk + max(-10, pnet // 3))

    conf = _confidence(token, vel, org, liq)

    conv = score_convergence(
        token,
        developer=dev_intel,
        patterns=patterns,
        narrative=narrative,
        organicity=org,
        liquidity=liq,
        wash=wash,
        holder_intel=token.get("holder_intel"),
    )
    rel = score_reliability(
        token,
        {
            "holders": {"data_quality": (token.get("holder_intel") or {}).get("data_quality")},
            "developer": dev_intel,
            "liquidity": liq,
            "social": {"score": 1 if int(token.get("reply_count") or 0) else 0},
            "structure": patterns,
            "flow": wash,
        },
    )
    # Display score: convergence × reliability × decay (CTO north-star metric)
    display = conv["convergence_score"] * (rel["reliability"] / 100.0) * rel["decay"]
    display = int(max(0, min(100, round(display))))
    # Blend hawk slightly toward convergence when reliable
    if rel["reliability"] >= 50:
        hawk = int(max(0, min(100, round(hawk * 0.7 + conv["convergence_score"] * 0.3))))

    # Opportunity = hawk adjusted by confidence and entry quality
    opp = hawk * (0.55 + 0.45 * (conf / 100.0))
    opp = int(max(0, min(100, round(opp * 0.6 + display * 0.4))))
    if rug >= 60:
        opp *= 0.55
    elif rug >= 45:
        opp *= 0.75
    opp = int(max(0, min(100, round(opp))))

    # Multi-poll confirmation + creator frequency (process-local)
    confirm = confirmation_metrics(token.get("address") or "")
    creator = (token.get("creator") or "").strip()
    c_launches = creator_launch_count(creator)
    # Single source of truth for the *direct* rug penalty: dev_intel's
    # flags, which come from the durable db-backed distinct-mint count
    # (survives restarts, dedupes polls). Previously this fact also drove
    # a second direct rug bump off the process-local, poll-derived
    # c_launches counter, so the same underlying signal was stacked twice
    # on top of what patterns.py already adds via pattern_net. c_launches
    # is kept only as an informational field and as (softer, capped) input
    # to the pattern layer.
    dev_flags = dev_intel.get("flags") or []
    if "serial_factory_deployer" in dev_flags:
        rug = min(100, rug + 16)
        risk["rug_risk"] = rug
        risk["risk_flags"] = list(dict.fromkeys((risk.get("risk_flags") or []) + ["serial_factory_deployer"]))
    elif "high_frequency_deployer" in dev_flags:
        rug = min(100, rug + 8)
        risk["rug_risk"] = rug
        risk["risk_flags"] = list(dict.fromkeys((risk.get("risk_flags") or []) + ["creator_high_launch_frequency"]))
    elif "repeat_deployer" in dev_flags:
        risk["risk_flags"] = list(dict.fromkeys((risk.get("risk_flags") or []) + ["creator_repeat_launcher"]))

    confirmed = bool(confirm.get("stable_enough_for_prime"))
    entry = _entry_state(token, hawk, rug, conf, lifecycle, confirmed=confirmed)

    # PRIME = rare. Multiple independent confirmations required.
    # Goal: maximize precision, not number of PRIMEs.
    wash_ok = wscore is None or wscore < 55
    prime_ok = (
        hawk >= 80
        and conf >= 58
        and rug < 42
        and replies >= 8
        and stage == "bonding"
        and org_s >= 50
        and age >= 6
        and age <= 90
        and confirmed
        and wash_ok
    )
    # Cold start exception: if no history yet, never PRIME (wait for confirmation)
    if confirm.get("data_quality") == "INSUFFICIENT_DATA":
        prime_ok = False

    if prime_ok:
        rating, rec, signal = "ASILI PRIME", "HIGHEST CONVICTION — STILL NOT CERTAIN", "prime"
    elif hawk >= 70 and rug < 50 and conf >= 50 and replies >= 6:
        rating, rec, signal = "ASILI HIGH", "RESEARCH — NOT AN AUTO ENTRY", "high"
    elif hawk >= 55:
        rating, rec, signal = "ASILI SPEC", "HIGH RISK — WATCH ONLY", "spec"
    else:
        rating, rec, signal = "LOW / AVOID", "PASS", "low"

    if lifecycle == "GRADUATING" and hawk >= 55:
        signal = "graduating"

    positive = []
    negative = []
    if stage == "bonding":
        positive.append("on_bonding_curve")
    if replies >= 6:
        positive.append(f"chat_{replies}")
    if vel.get("mcap_accelerating"):
        positive.append("mcap_accelerating")
    if vel.get("reply_accelerating"):
        positive.append("reply_accelerating")
    if token.get("is_live"):
        positive.append("live_stream")
    if org_s >= 55:
        positive.append("organicity_proxy_ok")
    for f in risk["risk_flags"]:
        if "INSUFFICIENT" not in f:
            negative.append(f)
    if replies == 0:
        negative.append("no_chat")

    reasons = []
    if stage == "bonding":
        reasons.append(f"Lifecycle {lifecycle}, curve ~{curve:.0f}%")
    if replies:
        reasons.append(f"Replies {replies}")
    if vel.get("mcap_accelerating"):
        reasons.append("Mcap accelerating")
    if rug >= 50:
        reasons.append(f"Rug risk {rug}")
    if conf < 50:
        reasons.append(f"Confidence only {conf}")
    reasons.append(f"Entry: {entry}")

    parts = {"velocity": vel, "organicity": org, "risk": risk}
    thesis = _thesis(token, parts)
    brk = _breakout_potential(token, hawk, rug, conf, wscore)
    ladder = assign_ladder(token, {
        "market_cap": token.get("market_cap"),
        "age_minutes": age,
        "stage": stage,
        "reply_count": replies,
        "rug_risk": rug,
        "hawk_score": hawk,
        "curve_progress": curve,
        "entry_state": entry,
        "breakout_score": brk.get("breakout_score"),
        "breakout_label": brk.get("breakout_label"),
    })

    result = {
        **token,
        "lifecycle": lifecycle,
        "hawk_score": hawk,
        "alpha_score": hawk,  # API compat: dashboard used alpha_score
        "alpha_component": int(alpha),
        "momentum_score": int(momentum),
        "earlyness_score": int(earlyness),
        "organicity_score": org_s,
        "liquidity_score": liq_s,
        "narrative_score": narr_s,
        "opportunity_score": opp,
        "confidence": conf,
        "rug_risk": rug,
        "rating": rating,
        "recommendation": rec,
        "entry_state": entry,
        "signal": signal,
        "reasons": reasons[:8],
        "risk_flags": risk["risk_flags"],
        "positive_signals": positive,
        "negative_signals": negative[:8],
        "velocity": vel,
        "organicity": org,
        "liquidity_health": liq,
        "narrative": narrative,
        "thesis": thesis,
        "holder_quality": (
            token.get("holder_intel")
            if (token.get("holder_intel") or {}).get("data_quality") == "OK"
            else "INSUFFICIENT_DATA"
        ),
        "smart_money": "INSUFFICIENT_DATA",
        "holder_intel": token.get("holder_intel"),
        "confirmation": confirm,
        "wash": wash,
        "wash_score": wscore,
        "creator_launch_count_seen": c_launches,
        "curve_progress": curve,
        **brk,
        **ladder,
        "pattern_score": patterns.get("pattern_score"),
        "pattern_net": patterns.get("pattern_net"),
        "pattern_summary": patterns.get("pattern_summary"),
        "hidden_signals": patterns.get("hidden_signals") or [],
        "pattern_signals": patterns.get("pattern_signals") or [],
        "developer_intel": dev_intel,
        "convergence_score": conv.get("convergence_score"),
        "convergence_label": conv.get("convergence_label"),
        "convergence_channels": conv.get("channels"),
        "reliability": rel.get("reliability"),
        "decay": rel.get("decay"),
        "display_score": display,
        "missing_channels": rel.get("missing_channels") or [],
        "creator_intel": dev_intel,
    }

    # Persist the *scored* snapshot (rug_risk/hawk_score now present) so
    # history rows carry real values instead of NULLs. track() above only
    # updates in-memory velocity state; this is the durable db write.
    persist(result)

    return result


def rank_tokens(tokens: list[dict]) -> list[dict]:
    scored = [analyze_token(t) for t in tokens]
    scored = [t for t in scored if (t.get("hawk_score") or 0) > 0]

    def window_rank(x):
        """Ladder-aware rank: actionable, high lottery, breakout, then rest."""
        entry = x.get("entry_state") or ""
        ladder = x.get("ladder") or "NOISE"
        lot = x.get("lottery_score") or 0
        br = x.get("breakout_score") or 0
        if entry in ("EARLY_ENTRY", "CONFIRMATION_ENTRY"):
            return 0
        if ladder == "BREAKOUT" and br >= 55:
            return 0
        if ladder == "LOTTERY" and lot >= 55:
            return 1  # high-quality lottery near top for earliest vision
        if ladder == "EARLY":
            return 2
        if ladder == "BREAKOUT":
            return 2
        if ladder == "LOTTERY":
            return 3
        if ladder == "EXPANSION":
            return 4
        return 5

    def key(x):
        return (
            window_rank(x),
            -(x.get("lottery_score") or 0) if (x.get("ladder") == "LOTTERY") else 0,
            -(x.get("breakout_score") or 0),
            -(x.get("display_score") or x.get("opportunity_score") or 0),
            -(x.get("hawk_score") or 0),
            x.get("rug_risk") or 100,
            x.get("age_minutes") or 999,
        )

    scored.sort(key=key)
    return scored


def top_opportunities(tokens: list[dict], n: int = 5) -> list[dict]:
    ranked = rank_tokens(tokens)
    # Prefer diversity of lifecycle when scores close
    picked: list[dict] = []
    seen_life: set[str] = set()
    for t in ranked:
        if len(picked) >= n:
            break
        life = t.get("lifecycle") or ""
        if life in seen_life and len(picked) < n - 1:
            # allow later if needed
            continue
        picked.append(t)
        seen_life.add(life)
    if len(picked) < n:
        for t in ranked:
            if t not in picked:
                picked.append(t)
            if len(picked) >= n:
                break
    return picked[:n]
