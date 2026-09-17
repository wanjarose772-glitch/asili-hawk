"""
Optional Telegram alerts for high-conviction detections.

Set env vars on Render:
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...

If unset, alerts are no-ops (dashboard still works).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_seen: set[str] = set()
_MAX_SEEN = 500


def _enabled() -> bool:
    return bool(
        os.getenv("TELEGRAM_BOT_TOKEN")
        and os.getenv("TELEGRAM_CHAT_ID")
    )


async def notify_prime(token: dict[str, Any]) -> bool:
    """Send a Telegram message for a PRIME/high-conviction token once per mint."""
    if not _enabled():
        return False

    addr = token.get("address") or ""
    if not addr or addr in _seen:
        return False

    ticker = token.get("ticker") or "?"
    score = token.get("alpha_score")
    stage = token.get("stage")
    curve = token.get("curve_progress")
    mcap = token.get("market_cap")
    age = token.get("age_minutes")
    reasons = token.get("reasons") or []
    rating = token.get("rating") or ""

    lines = [
        f"ASILI HAWK | {rating}",
        "",
        f"${ticker} | Alpha {score}",
        f"Stage: {stage} | Curve: {curve}%",
        f"MCAP: ${mcap} | Age: {age}m",
        "",
    ]

    for reason in reasons[:4]:
        lines.append(f"- {reason}")

    lines.append("")
    lines.append(f"https://pump.fun/{addr}")
    lines.append("https://asili-hawk-1.onrender.com")

    text = "\n".join(lines)

    token_bot = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token_bot}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": False,
                },
            )

        if resp.status_code == 200:
            _seen.add(addr)

            if len(_seen) > _MAX_SEEN:
                _seen.clear()
                _seen.add(addr)

            return True

        return False

    except Exception:
        return False


async def scan_and_alert(feed: list[dict]) -> int:
    """Alert on alpha >= 82 for bonding tokens."""
    if not _enabled():
        return 0

    sent = 0

    for token in feed:
        if (
            (token.get("alpha_score") or 0) >= 82
            and token.get("stage") == "bonding"
        ):
            ok = await notify_prime(token)

            if ok:
                sent += 1

    return sent
