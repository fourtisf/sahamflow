"""Overnight gap detector — INFORMASI, bukan blocker.

Gap = open hari ini vs close hari sebelumnya. Untuk smart-money desk, gap adalah
signal kuat tentang sentiment overnight:

- Gap up >+3% : ada minat beli kuat overnight (good news, follow-through),
  TAPI sering exhaustion → bot warning entry mungkin late.
- Gap down >-3%: ada panic overnight, TAPI gap down sering "dibayar ke atas"
  (gap fill = mean reversion). Untuk reversal trader, ini opportunity.

Bot tidak BLOCK signal karena gap — hanya tambah konteks di alert message,
biar trader putuskan sendiri.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OHLCVDaily

log = logging.getLogger("sahamflow.gap")


def compute_overnight_gap(db: Session, ticker: str) -> dict | None:
    """Return latest gap analysis or None if data insufficient.

    {
      'gap_pct': float (-100..+100, sign = direction),
      'severity': 'normal' | 'moderate' | 'large' | 'extreme',
      'direction': 'up' | 'down' | 'flat',
      'interpretation': str (human-readable smart-money note),
      'open': float, 'prev_close': float, 'date': str,
    }
    """
    rows = (
        db.execute(
            select(OHLCVDaily)
            .where(OHLCVDaily.ticker == ticker)
            .order_by(OHLCVDaily.date.desc())
            .limit(2)
        )
        .scalars()
        .all()
    )
    if len(rows) < 2:
        return None

    today, yesterday = rows[0], rows[1]
    if not today.open or not yesterday.close:
        return None

    open_ = float(today.open)
    prev_close = float(yesterday.close)
    gap_pct = round((open_ / prev_close - 1) * 100, 2)

    abs_g = abs(gap_pct)
    if abs_g < 1.0:
        severity, direction = "normal", "flat"
    elif abs_g < 3.0:
        severity = "moderate"
        direction = "up" if gap_pct > 0 else "down"
    elif abs_g < 5.0:
        severity = "large"
        direction = "up" if gap_pct > 0 else "down"
    else:
        severity = "extreme"
        direction = "up" if gap_pct > 0 else "down"

    interpretation = _interpret(gap_pct, severity, direction)

    return {
        "gap_pct": gap_pct,
        "severity": severity,
        "direction": direction,
        "interpretation": interpretation,
        "open": open_,
        "prev_close": prev_close,
        "date": str(today.date),
    }


def _interpret(gap_pct: float, severity: str, direction: str) -> str:
    """Smart-money commentary singkat untuk dipakai di alert message."""
    if severity == "normal":
        return f"Gap {gap_pct:+.2f}% — normal, entry biasa."
    if direction == "up":
        if severity == "moderate":
            return f"Gap up {gap_pct:+.2f}% — momentum kuat, hati-hati entry late, tunggu pullback ke gap fill area."
        if severity == "large":
            return f"Gap up {gap_pct:+.2f}% — exhaustion risk tinggi. Tunggu retest atau close di atas open untuk konfirmasi continuation."
        return f"Gap up {gap_pct:+.2f}% EXTREM — kemungkinan blow-off top. Jangan kejar; tunggu pullback signifikan."
    if direction == "down":
        if severity == "moderate":
            return f"Gap down {gap_pct:+.2f}% — sentimen lemah, tapi potensi gap fill ke atas (mean reversion)."
        if severity == "large":
            return f"Gap down {gap_pct:+.2f}% — panic selling. Smart money sering akumulasi di gap down besar. Watch reversal candle."
        return f"Gap down {gap_pct:+.2f}% EXTREM — event-driven (earnings/news). Tunggu volume capitulation + bullish engulfing sebelum entry."
    return f"Gap {gap_pct:+.2f}%."
