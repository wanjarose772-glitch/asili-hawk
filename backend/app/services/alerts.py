"""Telegram alerts — private operator: only rare, useful pings."""

from __future__ import annotations

import os
from typing import Any

import httpx

_seen: set[str] = set()
_MAX_SEEN = 400


def _enabled() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


async def notify(token: dict[str, Any], title: str) -> bool:
    if not _enabled():
        return False
    addr = token.get("address") or ""
    key = f"{title}:{addr}"
    if not addr or key in _seen:
        return False
    _seen.add(key)
    if len(_seen) > _MAX_SEEN:
        for _ in range(80):
            _seen.pop()

    lines = [
        f"ASILI HAWK · {title}",
        f"${token.get('ticker')} · Ladder {token.get('ladder')} · Size {token.get('size_hint')}",
        f"Hawk {token.get('hawk_score') or token.get('alpha_score')} · Focus {token.get('focus_score')} · Risk {token.get('rug_risk')}",
        f"MCAP ${token.get('market_cap')} · Age {token.get('age_minutes')}m · Replies {token.get('reply_count')}",
        f"Entry {token.get('entry_state')} · Curve {token.get('curve_progress')}%",
        "",
    ]
    if token.get("lottery_score"):
        lines.append(f"Lottery score {token.get('lottery_score')}")
    if token.get("breakout_score"):
        lines.append(f"Breakout score {token.get('breakout_score')} · {token.get('breakout_label')}")
    for r in (token.get("reasons") or [])[:3]:
        lines.append(f"• {r}")
    lines.append(f"https://pump.fun/{addr}")
    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(
                url,
                json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text},
            )
            return r.status_code == 200
    except Exception:
        return False


async def scan_and_alert(feed: list[dict]) -> int:
    """Only alert what a private operator would want interrupted for."""
    if not _enabled():
        return 0
    sent = 0
    for t in feed:
        ladder = t.get("ladder")
        rug = t.get("rug_risk") or 100
        focus = t.get("focus_score") or 0
        # High-quality lottery
        if (
            ladder == "LOTTERY"
            and (t.get("lottery_score") or 0) >= 62
            and rug < 55
            and (t.get("reply_count") or 0) >= 3
        ):
            if await notify(t, "LOTTERY"):
                sent += 1
        # Strong breakout path
        elif (
            ladder == "BREAKOUT"
            and (t.get("breakout_score") or 0) >= 65
            and rug < 52
        ):
            if await notify(t, "BREAKOUT"):
                sent += 1
        # True actionable / prime
        elif t.get("signal") == "prime" and t.get("entry_state") in (
            "EARLY_ENTRY",
            "CONFIRMATION_ENTRY",
        ):
            if await notify(t, "PRIME"):
                sent += 1
        elif (
            t.get("entry_state") in ("EARLY_ENTRY", "CONFIRMATION_ENTRY")
            and focus >= 60
            and rug < 50
        ):
            if await notify(t, "ACTIONABLE"):
                sent += 1
    return sent
