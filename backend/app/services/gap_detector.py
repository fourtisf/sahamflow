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


def scan_universe_gaps() -> tuple[dict, list[dict]]:
    """Scan semua ticker di universe untuk gap notable. Returns (ihsg_gap, notable_list).

    notable_list: [{ticker, gap_pct, severity, direction, ...}, ...] sorted by abs gap desc.
    Hanya yang severity != 'normal' yang masuk.
    """
    from app.core.config import settings
    from app.core.database import SessionLocal

    ihsg = compute_ihsg_gap()
    notable = []
    with SessionLocal() as db:
        for t in settings.universe:
            s = compute_overnight_gap(db, t)
            if not s or s.get("severity") == "normal":
                continue
            s["ticker"] = t
            notable.append(s)
    notable.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    return ihsg, notable


def build_gap_radar_text() -> str:
    """Bangun pinned message GAP RADAR untuk semua ticker notable."""
    from datetime import datetime

    ihsg, notable = scan_universe_gaps()

    lines = ["📊 *GAP RADAR — IDX LQ45*"]
    lines.append(f"_Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    if ihsg:
        emoji = "📈" if ihsg["direction"] == "up" else "📉" if ihsg["direction"] == "down" else "➖"
        lines.append(f"{emoji} *IHSG* : {ihsg['gap_pct']:+.2f}% ({ihsg['severity']})")
    else:
        lines.append("➖ *IHSG* : data tidak tersedia")
    lines.append("")

    if not notable:
        lines.append("_Tidak ada saham dengan gap notable hari ini. Market tenang._")
        return "\n".join(lines)

    # Split by direction
    gap_up = [n for n in notable if n["direction"] == "up"]
    gap_down = [n for n in notable if n["direction"] == "down"]

    if gap_up:
        lines.append("*━━ GAP UP ━━*")
        for n in gap_up[:15]:
            sev_emoji = "🔥" if n["severity"] == "extreme" else "⬆️" if n["severity"] == "large" else "↗️"
            lines.append(f"  {sev_emoji} `{n['ticker']:<6}` {n['gap_pct']:+.2f}%  _({n['severity']})_")
        lines.append("")

    if gap_down:
        lines.append("*━━ GAP DOWN ━━*")
        for n in gap_down[:15]:
            sev_emoji = "💥" if n["severity"] == "extreme" else "⬇️" if n["severity"] == "large" else "↘️"
            lines.append(f"  {sev_emoji} `{n['ticker']:<6}` {n['gap_pct']:+.2f}%  _({n['severity']})_")
        lines.append("")

    # Smart money takeaway
    lines.append("*━━ SMART MONEY NOTES ━━*")
    if ihsg and ihsg["severity"] != "normal":
        lines.append(f"  • IHSG gap {ihsg['direction']} {ihsg['gap_pct']:+.2f}% → market-wide sentiment, gap saham yang sama arah = ikut macro.")
    else:
        lines.append("  • IHSG flat → semua gap di bawah ini *ISOLATED* (bukan macro). Investigasi per ticker.")
    if gap_down:
        biggest = gap_down[0]
        lines.append(f"  • Gap down terbesar: *{biggest['ticker']}* {biggest['gap_pct']:+.2f}% — potensi fill ke atas / akumulasi smart money.")
    if gap_up:
        biggest = gap_up[0]
        lines.append(f"  • Gap up terbesar: *{biggest['ticker']}* {biggest['gap_pct']:+.2f}% — leader hari ini, hati-hati exhaustion.")

    lines.append("")
    lines.append("_Bukan rekomendasi. Cross-check volume + struktur chart sebelum entry._")
    return "\n".join(lines)


def refresh_gap_radar_pinned() -> bool:
    """Edit-in-place pinned gap radar message. State key terpisah dari PnL."""
    from app.services import notifier

    text = build_gap_radar_text()
    state = notifier._load_state()
    msg_id = state.get("pinned_gap_msg_id")

    if msg_id:
        if notifier.telegram_edit(int(msg_id), text):
            return True
        log.info("Gap radar edit failed, repinning fresh.")
        state.pop("pinned_gap_msg_id", None)
        notifier._save_state(state)

    new_id = notifier.telegram_send_with_id(text)
    if not new_id:
        return False
    ok = notifier.telegram_pin(new_id, disable_notification=True)
    if ok:
        state = notifier._load_state()
        state["pinned_gap_msg_id"] = new_id
        notifier._save_state(state)
    return ok


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
