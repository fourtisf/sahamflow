"""Telegram push notifier — agar trader tidak miss setup."""

from __future__ import annotations

import logging
from datetime import date

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import RegimeHistory, SignalCache

log = logging.getLogger("sahamflow.notifier")


def telegram_send(text: str) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    chat = settings.TELEGRAM_CHAT_ID
    if not token or not chat:
        log.info("Telegram disabled (no token/chat). Would have sent: %s", text[:80])
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        return False


def alert_strong_setups() -> int:
    """Push Telegram alerts for today's high-conviction setups."""
    with SessionLocal() as db:
        regime = db.execute(
            select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
        ).scalar_one_or_none()
        if not regime:
            return 0

        rows = db.execute(
            select(SignalCache)
            .where(SignalCache.date == regime.date)
            .order_by(SignalCache.composite_score.desc())
        ).scalars().all()

    if not rows:
        return 0

    strong_long = [r for r in rows if (r.composite_score or 0) >= 0.5]
    strong_short = [r for r in rows if (r.composite_score or 0) <= -0.5]

    if not strong_long and not strong_short:
        return 0

    modifier = (regime.extra or {}).get("modifier")
    header = f"*Sahamflow {regime.date}* — Regime: *{regime.regime}*"
    if modifier:
        header += f" → *{modifier}*"
    header += f" (conf {regime.confidence}%)\n"

    body_lines: list[str] = []
    if strong_long:
        body_lines.append("\n🟢 *Strong Buy setups*")
        for r in strong_long[:8]:
            body_lines.append(f"  • `{r.ticker}` score `{r.composite_score}` · bandar `{r.bandar_phase}`")
    if strong_short:
        body_lines.append("\n🔴 *Strong Sell setups*")
        for r in strong_short[:8]:
            body_lines.append(f"  • `{r.ticker}` score `{r.composite_score}` · bandar `{r.bandar_phase}`")

    body_lines.append("\n_Bukan rekomendasi investasi. Konfirmasi trigger di dashboard sebelum entry._")
    sent = telegram_send(header + "\n".join(body_lines))
    log.info("Telegram alerts sent=%s long=%d short=%d", sent, len(strong_long), len(strong_short))
    return len(strong_long) + len(strong_short)
