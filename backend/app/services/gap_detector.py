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

from app.core.database import SessionLocal
from app.models import OHLCVDaily

log = logging.getLogger("sahamflow.gap")


def compute_overnight_gap(db: Session, ticker: str) -> dict | None:
    """Latest gap analysis dengan enrichment lengkap (smart-money grade).

    Returns dict dengan: gap_pct, severity, direction, interpretation, open,
    prev_close, close, day_change_pct, date, high, low,
    volume_ratio_20d, ma200_distance_pct, foreign_net_today, foreign_net_5d.
    """
    rows = (
        db.execute(
            select(OHLCVDaily)
            .where(OHLCVDaily.ticker == ticker)
            .order_by(OHLCVDaily.date.desc())
            .limit(210)
        )
        .scalars()
        .all()
    )
    if len(rows) < 2:
        return None

    rows = list(reversed(rows))  # oldest → newest for indicator math
    today, yesterday = rows[-1], rows[-2]
    if not today.open or not yesterday.close:
        return None

    open_ = float(today.open)
    prev_close = float(yesterday.close)
    close = float(today.close) if today.close else open_
    high = float(today.high) if today.high else close
    low = float(today.low) if today.low else open_
    gap_pct = round((open_ / prev_close - 1) * 100, 2)
    day_change_pct = round((close / prev_close - 1) * 100, 2)

    # Volume ratio vs MA20
    volumes = [int(r.volume or 0) for r in rows[-21:]]
    vol_today = volumes[-1] if volumes else 0
    vol_ma20 = sum(volumes[:-1]) / max(len(volumes) - 1, 1) if len(volumes) > 1 else 0
    volume_ratio_20d = round(vol_today / vol_ma20, 2) if vol_ma20 > 0 else None

    # MA200 distance
    closes_200 = [float(r.close) for r in rows[-200:] if r.close is not None]
    ma200_distance_pct = None
    if len(closes_200) >= 30:  # minimal 30 bar untuk MA bermakna
        ma_val = sum(closes_200) / len(closes_200)
        ma200_distance_pct = round((close / ma_val - 1) * 100, 2)

    # Foreign flow
    foreign_net_today = int(today.foreign_net) if today.foreign_net is not None else None
    foreign_net_5d = sum(int(r.foreign_net or 0) for r in rows[-5:] if r.foreign_net is not None) or None
    foreign_net_5d = int(foreign_net_5d) if foreign_net_5d else None

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
        "high": high,
        "low": low,
        "day_change_pct": day_change_pct,
        "date": str(today.date),
        "volume_ratio_20d": volume_ratio_20d,
        "ma200_distance_pct": ma200_distance_pct,
        "foreign_net_today": foreign_net_today,
        "foreign_net_5d": foreign_net_5d,
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


def _entry_plan(record: dict) -> str | None:
    """Entry/SL plan trend-aware. Smart money rule: jangan kejar breakout di
    downtrend. Volume kering = setup tidak valid. Counter-trend hanya kalau ada
    confluence kuat (volume thrust + foreign net buy)."""
    pat = record.get("pattern")
    high = record.get("high")
    low = record.get("low")
    close = record.get("close")
    open_ = record.get("open")
    mad = record.get("ma200_distance_pct") or 0
    vr = record.get("volume_ratio_20d") or 0
    fn5 = record.get("foreign_net_5d") or 0
    if not (high and low and close):
        return None

    is_downtrend = mad < -5
    is_uptrend = mad > 5
    weak_volume = vr < 1.0
    strong_volume = vr >= 1.5
    foreign_supportive = fn5 > 0

    if pat == "GAP_FILL_BULL":
        if is_downtrend and not (strong_volume and foreign_supportive):
            return (
                f"⚠️ COUNTER-TREND di downtrend (vs MA200 {mad:+.1f}%). "
                f"WATCH only — tunggu reclaim MA200 + volume ≥ 1.5× + foreign net buy. "
                f"Jangan kejar breakout."
            )
        if weak_volume:
            return (
                f"⚠️ Volume {vr:.1f}× kering — gap fill tanpa konfirmasi institusi. "
                f"WATCH, tunggu volume thrust ≥ 1.5×."
            )
        return f"entry > `{high:,.0f}` (high)  ·  SL `{low:,.0f}` (low)"

    if pat == "GAP_AND_GO":
        if is_downtrend:
            return f"⚠️ Counter-trend di downtrend — pop & fade risk tinggi. WATCH only."
        if weak_volume:
            return f"⚠️ Volume {vr:.1f}× lemah — continuation lemah. Tunggu pullback + vol thrust."
        return f"entry pullback ke `{open_:,.0f}` (gap)  ·  SL `{low:,.0f}`"

    if pat == "GAP_UP_FAIL":
        return "AVOID — exhaustion. Tunggu konfirmasi reclaim high atau setup baru."

    if pat == "GAP_DN_CONT":
        return "AVOID — bearish persist. Jangan averaging, tunggu reversal candle + volume."
    return None


def _bulk_sectors() -> dict[str, str]:
    """Sector mapping: try Stock.sector from DB, fallback ke hardcoded LQ45 map."""
    from app.models import Stock
    from app.services.sector_mapping import get_sector

    with SessionLocal() as db:
        rows = db.execute(select(Stock.ticker, Stock.sector)).all()
    out: dict[str, str] = {}
    for t, s in rows:
        out[t] = s or get_sector(t)
    # Ensure semua LQ45 ada mapping (kalau Stock row belum ada di DB)
    from app.core.config import LQ45_TICKERS
    for t in LQ45_TICKERS:
        if t not in out or out[t] == "Unknown":
            out[t] = get_sector(t)
    return out


def scan_universe_gaps() -> tuple[dict, list[dict]]:
    """Scan semua ticker di universe untuk gap notable. Returns (ihsg_gap, notable_list).

    notable_list: [{ticker, gap_pct, severity, direction, ...}, ...] sorted by abs gap desc.
    Hanya yang severity != 'normal' yang masuk.
    """
    from app.core.config import settings
    from app.core.database import SessionLocal

    ihsg = compute_ihsg_gap()
    sectors = _bulk_sectors()
    notable = []
    total_scanned = 0
    with SessionLocal() as db:
        for t in settings.universe:
            s = compute_overnight_gap(db, t)
            if not s:
                continue
            total_scanned += 1
            pattern = classify_gap_pattern(s["gap_pct"], s.get("day_change_pct", 0))
            if not pattern:
                continue
            s["ticker"] = t
            s["pattern"] = pattern
            s["sector"] = sectors.get(t, "Unknown")
            notable.append(s)
    ihsg = ihsg or {}
    ihsg["_total_scanned"] = total_scanned
    return ihsg, notable


def build_gap_radar_text() -> str:
    """Pinned GAP RADAR — smart money grade dengan volume, trend, foreign,
    sector, breadth, win rate, dan entry plan per pola."""
    from datetime import datetime
    from app.services import pattern_stats as _ps

    ihsg, notable = scan_universe_gaps()
    stats = _ps.get_cached()

    data_date = ihsg.get("date", "?") if ihsg else "?"
    total_scanned = (ihsg or {}).get("_total_scanned", 0)
    lines = ["📊 *GAP RADAR — IDX LQ45*"]
    lines.append(f"_Data EOD: *{data_date}*  ·  Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    if ihsg and ihsg.get("date"):
        emoji = "📈" if ihsg["direction"] == "up" else "📉" if ihsg["direction"] == "down" else "➖"
        day_pct = ihsg.get("day_change_pct", 0)
        day_emoji = "🟢" if day_pct > 0 else "🔴" if day_pct < 0 else "⚪"
        lines.append(
            f"{emoji} *IHSG* gap {ihsg['gap_pct']:+.2f}% ({ihsg['severity']})  ·  "
            f"close `{ihsg['close']:,.2f}`  ·  day {day_emoji} {day_pct:+.2f}%"
        )
    else:
        lines.append("➖ *IHSG* : data tidak tersedia")

    # === MARKET BREADTH ===
    counts = {p: sum(1 for n in notable if n["pattern"] == p) for p in PATTERN_META}
    bullish = counts["GAP_FILL_BULL"] + counts["GAP_AND_GO"]
    bearish = counts["GAP_UP_FAIL"] + counts["GAP_DN_CONT"]
    bull_pct = bullish * 100 / total_scanned if total_scanned else 0
    bear_pct = bearish * 100 / total_scanned if total_scanned else 0
    breadth_label = "BULLISH SKEW" if bull_pct > bear_pct * 1.5 else "BEARISH SKEW" if bear_pct > bull_pct * 1.5 else "MIXED"
    lines.append(
        f"📐 *Breadth* : {bullish}🟢 / {bearish}🔴 dari {total_scanned} ({bull_pct:.0f}% bull / {bear_pct:.0f}% bear) → *{breadth_label}*"
    )
    lines.append("")

    if not notable:
        lines.append("_Tidak ada saham dengan pola gap notable. Market tenang._")
        return "\n".join(lines)

    def _row(n: dict, emoji: str) -> list[str]:
        day = n.get("day_change_pct", 0)
        day_e = "🟢" if day > 0 else "🔴" if day < 0 else "⚪"
        # Volume confirmation
        vr = n.get("volume_ratio_20d")
        if vr is None:
            vol_str = "vol —"
        elif vr >= 2.0:
            vol_str = f"vol *{vr:.1f}×*🔥"
        elif vr >= 1.5:
            vol_str = f"vol *{vr:.1f}×*"
        elif vr < 0.7:
            vol_str = f"vol {vr:.1f}×⚠️ kering"
        else:
            vol_str = f"vol {vr:.1f}×"
        # Trend context (MA200)
        mad = n.get("ma200_distance_pct")
        if mad is None:
            trend = ""
        elif mad > 5:
            trend = " · UPTREND ✅"
        elif mad < -5:
            trend = " · DOWNTREND ⚠️"
        else:
            trend = " · sideways"
        sector = n.get("sector", "")
        sector_str = f" [{sector[:10]}]" if sector and sector != "Unknown" else ""

        out = [
            f"  {emoji} `{n['ticker']:<5}` gap {n['gap_pct']:+.2f}%  day {day_e}{day:+.2f}%  close `{n['close']:,.0f}`",
            f"     {vol_str}{trend}{sector_str}",
        ]
        plan = _entry_plan(n)
        if plan:
            out.append(f"     ↳ {plan}")
        return out

    order = ["GAP_FILL_BULL", "GAP_AND_GO", "GAP_UP_FAIL", "GAP_DN_CONT"]
    for pat in order:
        group = [n for n in notable if n["pattern"] == pat]
        if not group:
            continue
        meta = PATTERN_META[pat]
        group.sort(key=meta["sort_key"])
        # Header dengan win rate historis
        wr = stats.get(pat, {})
        wr_str = ""
        if wr.get("n"):
            wr_str = f"  ·  hist win {wr['win_rate_pct']}% (avg {wr['avg_return_pct']:+.2f}%, n={wr['n']})"
        lines.append(f"*━━ {meta['title']} ━━*{wr_str}")
        lines.append(f"_{meta['subtitle']}_")
        # Sector clustering note
        sector_groups: dict[str, int] = {}
        for n in group:
            sec = n.get("sector", "Unknown")
            sector_groups[sec] = sector_groups.get(sec, 0) + 1
        top_sec = sorted(sector_groups.items(), key=lambda x: -x[1])
        cluster = ", ".join(f"{s}×{c}" for s, c in top_sec[:3] if c >= 2)
        if cluster:
            lines.append(f"_Sector cluster: {cluster} → ada rotation_")
        for n in group[:10]:
            lines.extend(_row(n, meta["row_emoji"]))
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
    lines.append("_⚡ Cross-check sebelum entry: (1) volume real-time, (2) foreign flow di RTI/Stockbit, (3) struktur chart._")
    lines.append("_Bukan rekomendasi investasi._")
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
