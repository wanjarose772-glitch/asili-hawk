"""Adversarial + unit tests for Hawk intelligence."""

from app.intelligence.engine import analyze_token, rank_tokens
from app.intelligence.lifecycle import classify_lifecycle


def _base(**kw):
    d = {
        "ticker": "MOONCAT",
        "name": "Moon Cat",
        "address": "Addr111",
        "stage": "bonding",
        "curve_progress": 40,
        "age_minutes": 20,
        "reply_count": 12,
        "market_cap": 12000,
        "liquidity": 8000,
        "volume": 5000,
        "twitter": "https://x.com/x",
        "description": "A community cat meme on solana",
        "price_change_m5": 8,
        "is_live": False,
        "complete": False,
    }
    d.update(kw)
    return d


def test_silent_fresh_not_prime():
    t = analyze_token(_base(age_minutes=1.0, reply_count=0, twitter="", market_cap=5000, curve_progress=55, price_change_m5=60))
    assert t["signal"] != "prime"
    assert t["rug_risk"] >= 50
    assert t["entry_state"] in ("AVOID", "WAIT", "WATCH")
    assert t["hawk_score"] < 70


def test_ghost_rejected():
    t = analyze_token(_base(age_minutes=0.8, reply_count=0, twitter="", market_cap=1500, curve_progress=10))
    assert t["hawk_score"] == 0 or t["signal"] == "reject"


def test_quality_can_be_prime():
    t = analyze_token(
        _base(
            age_minutes=18,
            reply_count=22,
            curve_progress=48,
            market_cap=18000,
            liquidity=12000,
            volume=20000,
            is_live=True,
            price_change_m5=12,
        )
    )
    # May or may not hit prime depending on velocity history, but should not be reject
    assert t["hawk_score"] > 0
    assert t["rug_risk"] < 70
    assert t["confidence"] >= 40


def test_fake_volume_penalized():
    t = analyze_token(
        _base(
            age_minutes=5,
            reply_count=0,
            volume=500000,
            market_cap=8000,
            liquidity=2000,
            curve_progress=70,
            price_change_m5=80,
        )
    )
    assert t["signal"] != "prime"
    assert t["rug_risk"] >= 45


def test_lifecycle_graduating():
    assert classify_lifecycle(_base(curve_progress=80, stage="bonding")) == "GRADUATING"


def test_lifecycle_new():
    assert classify_lifecycle(_base(age_minutes=3, curve_progress=10)) == "NEW"


def test_rank_orders_by_opportunity():
    a = _base(address="A", ticker="ALPHAONE", reply_count=0, age_minutes=1)
    b = _base(address="B", ticker="BETACAT", reply_count=20, age_minutes=15, is_live=True)
    ranked = rank_tokens([a, b])
    assert ranked
    # B should outrank pure silent fresh if both score > 0
    if len(ranked) == 2:
        assert ranked[0]["ticker"] == "BETACAT"


def test_insufficient_data_fields():
    t = analyze_token(_base())
    assert t["holder_quality"] == "INSUFFICIENT_DATA"
    assert t["smart_money"] == "INSUFFICIENT_DATA"
    assert t["creator_intel"] == "INSUFFICIENT_DATA"


def test_confidence_separated_from_score():
    t = analyze_token(_base(age_minutes=2, reply_count=2, twitter=""))
    # Young weak evidence → confidence should not be sky high
    assert t["confidence"] <= 75


def test_holder_intel_absent_is_insufficient():
    t = analyze_token(
        _base(
            ticker="HOLDLESS",
            address="HoldLess111",
            age_minutes=20,
            reply_count=10,
        )
    )
    # Without Helius enrichment on the token dict, still insufficient
    assert t["holder_quality"] == "INSUFFICIENT_DATA" or (
        isinstance(t.get("holder_quality"), dict) and t["holder_quality"].get("data_quality") != "OK"
    )


def test_holder_concentration_raises_risk():
    token = _base(
        ticker="WHALECOIN",
        address="Whale111",
        age_minutes=20,
        reply_count=12,
        market_cap=15000,
        liquidity=8000,
    )
    token["holder_intel"] = {
        "data_quality": "OK",
        "top1_pct": 55.0,
        "top10_pct": 92.0,
        "holder_quality_score": 20,
        "flags": ["top1_dominant", "top10_highly_concentrated"],
    }
    t = analyze_token(token)
    assert t["rug_risk"] >= 40
    assert t["signal"] != "prime" or t["rug_risk"] < 48  # prime blocked if risk high
