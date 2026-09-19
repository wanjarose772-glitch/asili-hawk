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

from typing import Any

from app.intelligence.lifecycle import classify_lifecycle
from app.intelligence.memory import record, velocity_metrics
from app.intelligence.narrative import analyze_narrative

EXCLUDED = {
    "SOL", "USDC", "USDT", "WSOL", "BTC", "ETH", "WBTC", "WETH",
    "JUP", "JTO", "BONK", "WIF", "RAY", "ORCA", "PUMP",
}
SUSPICIOUS = (
    "airdrop", "claim", "presale", "test", "scam", "rug", "honeypot",
    "free mint", "whitelist", "1000x", "100x",
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
    if any(s in name or s in symbol.lower() or s in desc for s in SUSPICIOUS):
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


def _entry_state(token: dict, hawk: int, risk: int, conf: int, lifecycle: str) -> str:
    replies = int(token.get("reply_count") or 0)
    age = _f(token.get("age_minutes"), 999)

    if risk >= 65 or hawk < 45:
        return "AVOID"
    if risk >= 50 and conf < 50:
        return "WAIT"
    if lifecycle in ("NEW",) and replies < 6:
        return "WATCH"
    if hawk >= 75 and conf >= 55 and risk < 45 and replies >= 6:
        if age <= 40 and token.get("stage") == "bonding":
            return "EARLY_ENTRY"
        return "CONFIRMATION_ENTRY"
    if hawk >= 60 and risk < 55:
        return "WATCH"
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
    record(token)
    vel = velocity_metrics(token.get("address") or "")
    lifecycle = classify_lifecycle(token)
    narrative = analyze_narrative(token)
    org = _organicity(token, vel)
    liq = _liquidity_health(token)
    risk = _risk_engine(token, org, liq, vel)

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

    conf = _confidence(token, vel, org, liq)

    # Opportunity = hawk adjusted by confidence and entry quality
    opp = hawk * (0.55 + 0.45 * (conf / 100.0))
    if rug >= 60:
        opp *= 0.55
    elif rug >= 45:
        opp *= 0.75
    opp = int(max(0, min(100, round(opp))))

    entry = _entry_state(token, hawk, rug, conf, lifecycle)

    # PRIME requires multiple independent confirmations
    prime_ok = (
        hawk >= 78
        and conf >= 55
        and rug < 48
        and replies >= 6
        and stage == "bonding"
        and org_s >= 45
        and age >= 4
    )

    if prime_ok:
        rating, rec, signal = "ASILI PRIME", "WATCH CLOSELY", "prime"
    elif hawk >= 68 and rug < 55 and conf >= 45:
        rating, rec, signal = "ASILI HIGH", "RESEARCH", "high"
    elif hawk >= 55:
        rating, rec, signal = "ASILI SPEC", "HIGH RISK", "spec"
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

    return {
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
        "creator_intel": "INSUFFICIENT_DATA",
        "holder_intel": token.get("holder_intel"),
        "curve_progress": curve,
    }


def rank_tokens(tokens: list[dict]) -> list[dict]:
    scored = [analyze_token(t) for t in tokens]
    scored = [t for t in scored if (t.get("hawk_score") or 0) > 0]

    def key(x):
        return (
            -(x.get("opportunity_score") or 0),
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
