"""Overnight gap detector — INFORMASI, bukan blocker.

Dua layer:
1. Gap per saham (open today vs close yesterday)
2. Gap IHSG (^JKSE) untuk konteks macro

Smart money baca KOMBINASI:
- Saham gap down + IHSG gap down  = market-wide, mungkin overdone (opportunity)
- Saham gap down + IHSG flat/up   = isolated event (suspicious, hati-hati)
- Saham gap up + IHSG gap up      = euphoria sektoral/macro
- Saham gap up + IHSG flat/down   = leader breakout (strong relative strength)

Bot tidak BLOCK signal karena gap — hanya tambah konteks di alert message.
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


def compute_ihsg_gap() -> dict | None:
    """Fetch IHSG (^JKSE) latest 2 bars, return same shape as compute_overnight_gap."""
    try:
        from app.data_sources.yahoo_finance import fetch_ohlc_history

        bars = fetch_ohlc_history("^JKSE", period="5d")
    except Exception as e:
        log.debug("IHSG fetch failed: %s", e)
        return None
    if not bars or len(bars) < 2:
        return None
    today, yesterday = bars[-1], bars[-2]
    if not today.get("open") or not yesterday.get("close"):
        return None
    open_ = float(today["open"])
    prev_close = float(yesterday["close"])
    gap_pct = round((open_ / prev_close - 1) * 100, 2)
    abs_g = abs(gap_pct)
    if abs_g < 0.5:
        severity, direction = "normal", "flat"
    elif abs_g < 1.5:
        severity = "moderate"
        direction = "up" if gap_pct > 0 else "down"
    elif abs_g < 3.0:
        severity = "large"
        direction = "up" if gap_pct > 0 else "down"
    else:
        severity = "extreme"
        direction = "up" if gap_pct > 0 else "down"
    return {
        "gap_pct": gap_pct,
        "severity": severity,
        "direction": direction,
        "open": open_,
        "prev_close": prev_close,
        "date": today["date"],
    }


def combined_interpretation(stock_gap: dict | None, ihsg_gap: dict | None) -> str | None:
    """Smart money narrative berdasar kombinasi stock vs market gap."""
    if not stock_gap or stock_gap.get("severity") == "normal":
        return None
    s_dir = stock_gap["direction"]
    s_pct = stock_gap["gap_pct"]
    if not ihsg_gap or ihsg_gap.get("severity") == "normal":
        # IHSG flat → gap isolated
        if s_dir == "down":
            return (
                f"Saham gap down {s_pct:+.2f}% sementara IHSG flat → ISOLATED event. "
                f"Bukan macro, hati-hati ada news/earnings specific. Tunggu reversal candle."
            )
        return (
            f"Saham gap up {s_pct:+.2f}% sementara IHSG flat → LEADER breakout. "
            f"Relative strength kuat, tapi rentan profit-taking. Tunggu retest."
        )
    i_dir = ihsg_gap["direction"]
    i_pct = ihsg_gap["gap_pct"]
    same = (s_dir == i_dir)
    if same and s_dir == "down":
        return (
            f"Saham {s_pct:+.2f}% · IHSG {i_pct:+.2f}% → MARKET-WIDE selling, "
            f"bukan event-specific. Smart money sering akumulasi di gap macro overdone. "
            f"Watch IHSG bounce sebagai trigger."
        )
    if same and s_dir == "up":
        return (
            f"Saham {s_pct:+.2f}% · IHSG {i_pct:+.2f}% → MARKET euphoria. "
            f"Sektor leader OK, tapi extreme entry risk exhaustion. Tunggu pullback ke gap fill."
        )
    # Diverge
    if s_dir == "down" and i_dir == "up":
        return (
            f"Saham {s_pct:+.2f}% sementara IHSG {i_pct:+.2f}% → DIVERGENCE BERBAHAYA. "
            f"Saham dijual saat market naik = red flag specific. Investigasi sebelum entry."
        )
    return (
        f"Saham {s_pct:+.2f}% sementara IHSG {i_pct:+.2f}% → STRONG RELATIVE STRENGTH. "
        f"Saham naik saat market turun = institutional accumulation kemungkinan. Konfirmasi volume."
    )


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
