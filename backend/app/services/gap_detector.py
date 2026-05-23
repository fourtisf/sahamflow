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
      'gap_pct', 'severity', 'direction', 'interpretation',
      'open', 'prev_close', 'close', 'day_change_pct', 'date',
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
    close = float(today.close) if today.close else open_
    gap_pct = round((open_ / prev_close - 1) * 100, 2)
    day_change_pct = round((close / prev_close - 1) * 100, 2)

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
        "close": close,
        "day_change_pct": day_change_pct,
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
    close = float(today.get("close") or open_)
    gap_pct = round((open_ / prev_close - 1) * 100, 2)
    day_change_pct = round((close / prev_close - 1) * 100, 2)
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
        "close": close,
        "day_change_pct": day_change_pct,
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


def classify_gap_pattern(gap_pct: float, day_change_pct: float) -> str | None:
    """Smart-money pattern based on gap + intraday closing behavior.

    Returns one of:
      'GAP_FILL_BULL'  — gap down + closing recover ke atas (REVERSAL)
      'GAP_UP_FAIL'    — gap up + closing turun (EXHAUSTION TRAP)
      'GAP_AND_GO'     — gap up + closing naik (BULLISH CONTINUATION)
      'GAP_DN_CONT'    — gap down + closing turun (BEARISH PERSIST)
      None             — gap tidak notable
    """
    if abs(gap_pct) < 1.0:
        return None
    gap_up = gap_pct > 0
    day_up = day_change_pct > 0
    if gap_up and day_up:
        return "GAP_AND_GO"
    if gap_up and not day_up:
        return "GAP_UP_FAIL"
    if not gap_up and day_up:
        return "GAP_FILL_BULL"
    return "GAP_DN_CONT"


PATTERN_META = {
    "GAP_FILL_BULL": {
        "title": "💎 GAP FILL BULLISH",
        "subtitle": "REVERSAL — gap down dibayar ke atas, smart money akumulasi",
        "sort_key": lambda x: -x["day_change_pct"],
        "row_emoji": "💎",
    },
    "GAP_AND_GO": {
        "title": "🚀 GAP & GO",
        "subtitle": "BULLISH CONTINUATION — gap up dengan follow-through kuat",
        "sort_key": lambda x: -x["day_change_pct"],
        "row_emoji": "🚀",
    },
    "GAP_UP_FAIL": {
        "title": "⚠️ GAP UP FAIL",
        "subtitle": "EXHAUSTION TRAP — gap up tapi closing turun, distribusi",
        "sort_key": lambda x: x["day_change_pct"],
        "row_emoji": "⚠️",
    },
    "GAP_DN_CONT": {
        "title": "💀 GAP DOWN CONTINUATION",
        "subtitle": "BEARISH PERSIST — gap down tanpa recover, hindari",
        "sort_key": lambda x: x["day_change_pct"],
        "row_emoji": "💀",
    },
}


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
            if not s:
                continue
            pattern = classify_gap_pattern(s["gap_pct"], s.get("day_change_pct", 0))
            if not pattern:
                continue
            s["ticker"] = t
            s["pattern"] = pattern
            notable.append(s)
    return ihsg, notable


def build_gap_radar_text() -> str:
    """Bangun pinned message GAP RADAR untuk semua ticker notable."""
    from datetime import datetime

    ihsg, notable = scan_universe_gaps()

    data_date = ihsg["date"] if ihsg else "?"
    lines = ["📊 *GAP RADAR — IDX LQ45*"]
    lines.append(f"_Data EOD: *{data_date}*  ·  Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("_Gap = open hari ini vs close hari sebelumnya. Close = penutupan terakhir._")
    lines.append("")

    if ihsg:
        emoji = "📈" if ihsg["direction"] == "up" else "📉" if ihsg["direction"] == "down" else "➖"
        day_pct = ihsg.get("day_change_pct", 0)
        day_emoji = "🟢" if day_pct > 0 else "🔴" if day_pct < 0 else "⚪"
        lines.append(
            f"{emoji} *IHSG* gap {ihsg['gap_pct']:+.2f}% ({ihsg['severity']})  ·  "
            f"close `{ihsg['close']:,.2f}`  ·  day {day_emoji} {day_pct:+.2f}%"
        )
    else:
        lines.append("➖ *IHSG* : data tidak tersedia")
    lines.append("")

    if not notable:
        lines.append("_Tidak ada saham dengan pola gap notable. Market tenang._")
        return "\n".join(lines)

    def _row(n: dict, emoji: str) -> str:
        day = n.get("day_change_pct", 0)
        day_e = "🟢" if day > 0 else "🔴" if day < 0 else "⚪"
        return (
            f"  {emoji} `{n['ticker']:<5}` gap {n['gap_pct']:+.2f}%  "
            f"close `{n['close']:,.0f}`  day {day_e}{day:+.2f}%"
        )

    # Render dalam urutan smart-money priority: bullish reversal dulu,
    # lalu bullish continuation, lalu exhaustion warnings, lalu bearish persist.
    order = ["GAP_FILL_BULL", "GAP_AND_GO", "GAP_UP_FAIL", "GAP_DN_CONT"]
    for pat in order:
        group = [n for n in notable if n["pattern"] == pat]
        if not group:
            continue
        meta = PATTERN_META[pat]
        group.sort(key=meta["sort_key"])
        lines.append(f"*━━ {meta['title']} ━━*")
        lines.append(f"_{meta['subtitle']}_")
        for n in group[:12]:
            lines.append(_row(n, meta["row_emoji"]))
        lines.append("")

    lines.append("*━━ SMART MONEY NOTES ━━*")
    if ihsg and ihsg.get("severity") != "normal":
        lines.append(
            f"  • IHSG gap {ihsg['gap_pct']:+.2f}% ({ihsg['severity']}) → market-wide sentiment."
        )
    else:
        lines.append("  • IHSG flat → pola gap di bawah ini *ISOLATED* (bukan macro).")

    fill_bull = [n for n in notable if n["pattern"] == "GAP_FILL_BULL"]
    up_fail = [n for n in notable if n["pattern"] == "GAP_UP_FAIL"]
    if fill_bull:
        top = max(fill_bull, key=lambda x: x["day_change_pct"])
        lines.append(
            f"  • 💎 Best reversal: *{top['ticker']}* gap {top['gap_pct']:+.2f}% → "
            f"day {top['day_change_pct']:+.2f}% — akumulasi smart money kuat."
        )
    if up_fail:
        top = min(up_fail, key=lambda x: x["day_change_pct"])
        lines.append(
            f"  • ⚠️ Worst trap: *{top['ticker']}* gap {top['gap_pct']:+.2f}% → "
            f"day {top['day_change_pct']:+.2f}% — distribusi, JANGAN kejar."
        )

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
