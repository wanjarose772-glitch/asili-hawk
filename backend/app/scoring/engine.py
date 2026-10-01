"""Compatibility wrapper — scoring lives in app.intelligence.engine."""

from app.intelligence.engine import analyze_token, rank_tokens, top_opportunities

# Back-compat alias
score_token = analyze_token

__all__ = ["analyze_token", "score_token", "rank_tokens", "top_opportunities"]
