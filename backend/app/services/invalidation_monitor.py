"""Cek posisi terbuka vs harga terakhir — alert kalau SL/TP tertembus.

Smart-money desk tidak ditinggalkan posisi tanpa pengawasan. Kalau setup gugur
(close menembus SL), kamu harus tahu sekarang — bukan besok pagi.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import OHLCVDaily, Trade
from app.services import notifier

log = logging.getLogger("sahamflow.invalidation")


def _last_close(db, ticker: str) -> float | None:
    row = (
        db.execute(
            select(OHLCVDaily.close)
            .where(OHLCVDaily.ticker == ticker)
            .order_by(OHLCVDaily.date.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    return float(row) if row is not None else None


def check_open_positions() -> int:
    """Iterate open positions, alert if SL/TP hit, mark invalidated_at."""
    sent = 0
    with SessionLocal() as db:
        positions = (
            db.execute(select(Trade).where(Trade.exit_date.is_(None))).scalars().all()
        )
        for p in positions:
            if not p.ticker or not p.stop_loss or not p.entry_price:
                continue
            last = _last_close(db, p.ticker)
            if last is None:
                continue
            entry = float(p.entry_price)
            sl = float(p.stop_loss)
            tp = float(p.take_profit) if p.take_profit else None
            is_long = entry < (tp or entry * 1.18)  # heuristic if tp missing

            hit_sl = (last <= sl) if is_long else (last >= sl)
            hit_tp = tp is not None and ((last >= tp) if is_long else (last <= tp))

            if hit_sl or hit_tp:
                if p.invalidated_at:
                    continue  # already alerted
                kind = "🔴 *SL HIT — EXIT*" if hit_sl else "🟢 *TP HIT — TAKE PROFIT*"
                text = (
                    f"{kind} `{p.ticker}`\n"
                    f"Entry `{entry:,.0f}` · Now `{last:,.0f}` · "
                    f"{'SL ' + f'{sl:,.0f}' if hit_sl else 'TP ' + f'{tp:,.0f}'}\n"
                    f"P&L ≈ *{(last / entry - 1) * 100 * (1 if is_long else -1):+.2f}%*\n"
                    f"_Setup: {p.setup or 'n/a'}. Posisi ini perlu di-close manual di broker._"
                )
                if notifier.telegram_send(text):
                    sent += 1
                p.invalidated_at = datetime.utcnow()
        db.commit()
    log.info("Invalidation monitor: sent=%d", sent)
    return sent
