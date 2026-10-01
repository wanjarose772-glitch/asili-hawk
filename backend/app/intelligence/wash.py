"""
Wash / inorganic activity scoring from Helius tx samples.

This is directional, not proof. Language in flags: likely / suspicious.
"""

from __future__ import annotations

from typing import Any


def score_wash(tx_intel: dict[str, Any] | None) -> dict[str, Any]:
    if not tx_intel or tx_intel.get("data_quality") != "OK":
        return {
            "wash_score": None,
            "data_quality": "INSUFFICIENT_DATA",
            "flags": ["tx_sample:INSUFFICIENT_DATA"],
            "notes": ["No transaction sample available"],
        }

    n_tx = int(tx_intel.get("tx_count") or 0)
    unique = int(tx_intel.get("unique_fee_payers") or 0)
    top_share = float(tx_intel.get("top_payer_share") or 0)
    repeat_heavy = bool(tx_intel.get("repeat_payer_heavy"))

    score = 25  # baseline suspicion when we only have a small sample
    flags: list[str] = []
    notes: list[str] = []

    if n_tx < 3:
        return {
            "wash_score": 40,
            "data_quality": "LIMITED",
            "flags": ["too_few_txs"],
            "notes": ["Fewer than 3 recent txs in sample"],
            "tx_count": n_tx,
            "unique_fee_payers": unique,
        }

    # Diversity ratio
    ratio = unique / max(n_tx, 1)
    if ratio < 0.25 and n_tx >= 8:
        score += 35
        flags.append("likely_low_unique_signers")
        notes.append(f"Unique fee payers {unique} vs {n_tx} txs — possible recycling")
    elif ratio < 0.4 and n_tx >= 6:
        score += 22
        flags.append("suspicious_signer_concentration")
        notes.append(f"Low signer diversity ({unique}/{n_tx})")
    elif ratio >= 0.7:
        score -= 12
        notes.append("Healthier unique-signer ratio in sample")

    if top_share >= 0.45:
        score += 20
        flags.append("top_payer_dominates_sample")
        notes.append(f"Top fee payer ≈ {top_share*100:.0f}% of sampled txs")
    elif top_share >= 0.3:
        score += 10
        flags.append("top_payer_elevated")

    if repeat_heavy:
        score += 15
        flags.append("repeat_payers_heavy")

    score = max(0, min(100, int(round(score))))

    return {
        "wash_score": score,
        "data_quality": "OK",
        "flags": flags,
        "notes": notes,
        "tx_count": n_tx,
        "unique_fee_payers": unique,
        "top_payer_share": round(top_share, 3),
        "unique_ratio": round(ratio, 3),
    }
