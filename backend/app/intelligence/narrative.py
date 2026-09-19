"""Lightweight narrative quality from name/ticker/description only."""

from __future__ import annotations

import re

# Weak / generic spam patterns
WEAK = re.compile(
    r"\b(test|airdrop|claim|presale|whitelist|1000?x|moon|elon|trump|pepe2|inu2)\b",
    re.I,
)
# Slightly more distinctive meme/culture signals (not proof of quality)
CULTURE = re.compile(
    r"\b(cat|dog|frog|ai|agent|robot|sol|meme|based|chad|wojak|neiro|popcat)\b",
    re.I,
)


def analyze_narrative(token: dict) -> dict:
    name = (token.get("name") or "").strip()
    ticker = (token.get("ticker") or token.get("symbol") or "").strip()
    desc = (token.get("description") or "").strip()
    text = f"{name} {ticker} {desc}"

    score = 40
    notes: list[str] = []

    if not name or not ticker:
        return {
            "narrative_score": 15,
            "narrative_quality": "WEAK",
            "notes": ["missing_name_or_ticker"],
            "data_quality": "LIMITED",
        }

    if WEAK.search(text):
        score -= 25
        notes.append("generic_or_spam_terms")
    if CULTURE.search(text):
        score += 8
        notes.append("recognizable_meme_lexicon")
    if len(desc) >= 40:
        score += 10
        notes.append("has_description")
    elif len(desc) == 0:
        score -= 8
        notes.append("empty_description")
    if token.get("twitter"):
        score += 6
        notes.append("twitter_linked")
    if token.get("website"):
        score += 4
        notes.append("website_linked")
    if token.get("is_live"):
        score += 8
        notes.append("live_stream")

    # Very short ticker can be fine for memes; long garbage tickers are weak
    if len(ticker) > 12:
        score -= 10
        notes.append("long_ticker")

    score = max(0, min(100, score))
    if score >= 65:
        quality = "DECENT"
    elif score >= 45:
        quality = "MIXED"
    else:
        quality = "WEAK"

    return {
        "narrative_score": score,
        "narrative_quality": quality,
        "notes": notes,
        "data_quality": "OK",
    }
