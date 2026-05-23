"""Telegram push notifier — actionable buy-side ticket, BUKAN sinyal random.

Setiap alert adalah TICKET LENGKAP gaya hedge fund desk:
- Setup classifier (BREAKOUT / PULLBACK / ACCUMULATION / REVERSAL / TREND)
- Execution levels (Entry, SL, TP1/TP2/TP3 multi-level dengan distribusi exit)
- R:R, risk % per trade
- Market context (regime, modifier)
- Confluence reasons (fakta angka, bukan jargon)
- Track record setup ini
- Invalidation eksplisit (price + regime)
- Execution plan (scaling, time stop, trail)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import RegimeHistory, SignalCache, Trade
from app.services import signal_intelligence, signal_qualifier

log = logging.getLogger("sahamflow.notifier")


def _tg_api(method: str, payload: dict) -> dict | None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return None
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload,
            timeout=15,
        )
        if r.status_code != 200:
            # "message is not modified" untuk editMessageText artinya konten sama
            # → bukan failure, pinned sudah up-to-date. Treat as success.
            if method == "editMessageText" and "not modified" in r.text:
                return {"ok": True, "result": True, "noop": True}
            log.warning("Telegram %s %s: %s", method, r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception as e:
        log.warning("Telegram %s failed: %s", method, e)
        return None


def telegram_send(text: str) -> bool:
    """Send message, return True/False. (Kept for backward compat.)"""
    return telegram_send_with_id(text) is not None


def telegram_send_with_id(text: str) -> int | None:
    """Send message, return message_id (or None on failure)."""
    chat = settings.TELEGRAM_CHAT_ID
    if not chat:
        log.info("Telegram disabled (no chat). Skipping: %s", text[:80])
        return None
    resp = _tg_api("sendMessage", {
        "chat_id": chat,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    if resp and resp.get("ok"):
        return resp["result"]["message_id"]
    return None


def telegram_pin(message_id: int, disable_notification: bool = True) -> bool:
    resp = _tg_api("pinChatMessage", {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "disable_notification": disable_notification,
    })
    return bool(resp and resp.get("ok"))


def telegram_unpin_all() -> bool:
    resp = _tg_api("unpinAllChatMessages", {
        "chat_id": settings.TELEGRAM_CHAT_ID,
    })
    return bool(resp and resp.get("ok"))


def telegram_edit(message_id: int, text: str) -> bool:
    resp = _tg_api("editMessageText", {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    return bool(resp and resp.get("ok"))


# --- Persistent bot state (pinned message id, dll) ---
_STATE_PATH = Path(__file__).resolve().parents[2] / "bot_state.json"


def _load_state() -> dict:
    try:
        return json.loads(_STATE_PATH.read_text())
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_PATH.write_text(json.dumps(state))
    except Exception as e:
        log.warning("Failed to save bot_state: %s", e)


def get_pinned_msg_id() -> int | None:
    v = _load_state().get("pinned_pnl_msg_id")
    return int(v) if v else None


def set_pinned_msg_id(msg_id: int | None) -> None:
    s = _load_state()
    if msg_id is None:
        s.pop("pinned_pnl_msg_id", None)
    else:
        s["pinned_pnl_msg_id"] = msg_id
    _save_state(s)


def _classify_setup(intel: dict) -> tuple[str, str, str]:
    """Return (code, label, thesis_one_liner)."""
    if intel.get("alternate_setup"):
        return (
            "REVERSAL",
            "REVERSAL ACCUMULATION",
            "Oversold di structural support, regime/signature mendukung smart-money akumulasi.",
        )

    ind = intel.get("indicators") or {}
    bandar = intel.get("bandar") or {}
    score = intel.get("composite_score", 0) or 0
    rsi = ind.get("rsi14") or 50
    vol = ind.get("volume_ratio_20d") or 1
    range_pos = ind.get("range_position_pct") or 50
    macd_bias = ind.get("macd_bias")
    last = intel.get("last_close")
    ma20 = ind.get("ma20")

    if score >= 0.5 and vol >= 1.5 and range_pos >= 65 and macd_bias == "bullish":
        return (
            "BREAKOUT",
            "BREAKOUT MOMENTUM",
            "High-conviction breakout: composite kuat, volume thrust, near range high.",
        )
    if bandar.get("phase") == "Accumulation" and range_pos <= 60:
        return (
            "ACCUM",
            "INSTITUTIONAL ACCUMULATION",
            "Bandar fase akumulasi di range bawah-tengah — pre-markup positioning.",
        )
    if ma20 and last and abs(last - ma20) / ma20 <= 0.03 and 40 <= rsi <= 60 and macd_bias == "bullish":
        return (
            "PULLBACK",
            "PULLBACK CONTINUATION",
            "Pullback sehat ke MA20 dalam tren bullish — re-entry continuation.",
        )
    if bandar.get("phase") == "Markup" and score >= 0.3:
        return (
            "MARKUP",
            "MARKUP TREND FOLLOW",
            "Bandar markup confirmed, ride the trend dengan trailing stop disiplin.",
        )
    return (
        "TREND",
        "TREND FOLLOW",
        "Setup trend-following standard — confluence multi-indikator bullish.",
    )


def _multi_tp(entry: float, sl: float, tp_structural: float) -> dict:
    """TP1 = +1R (50% exit), TP2 = +2R (30% exit), TP3 = structural (20% runner).

    Kalau TP structural < TP2, fallback TP3 = +3R supaya tidak collapse.
    """
    risk = entry - sl
    if risk <= 0 or entry <= 0:
        return {}
    tp1 = entry + risk * 1.0
    tp2 = entry + risk * 2.0
    tp3 = tp_structural if tp_structural and tp_structural > tp2 else entry + risk * 3.0
    return {
        "tp1": round(tp1, 2),
        "tp1_pct": round((tp1 - entry) / entry * 100, 2),
        "tp2": round(tp2, 2),
        "tp2_pct": round((tp2 - entry) / entry * 100, 2),
        "tp3": round(tp3, 2),
        "tp3_pct": round((tp3 - entry) / entry * 100, 2),
        "tp3_capped": tp_structural and tp_structural > tp2,
    }


def _confluence_bullets(intel: dict, qual: dict) -> list[str]:
    """Plain-language fakta numerik, max 6 bullet — bukan jargon."""
    ind = intel.get("indicators") or {}
    bandar = intel.get("bandar") or {}
    track = intel.get("track_record") or {}
    bullets: list[str] = []

    score = intel.get("composite_score", 0)
    bullets.append(f"Composite score *{score}* ({intel.get('signal')})")

    rsi = ind.get("rsi14")
    if rsi is not None:
        zone = "oversold" if rsi < 35 else "overbought" if rsi > 70 else "netral-bullish" if rsi > 50 else "netral-lemah"
        bullets.append(f"RSI(14) *{rsi}* ({zone})")

    if ind.get("macd_bias"):
        bullets.append(f"MACD *{ind['macd_bias']}* (hist {ind.get('macd_hist')})")

    vol = ind.get("volume_ratio_20d")
    if vol:
        tag = "thrust kuat" if vol >= 1.5 else "kering" if vol < 0.7 else "normal"
        bullets.append(f"Volume *{vol}×* MA20 ({tag})")

    if ind.get("ma200_distance_pct") is not None:
        d = ind["ma200_distance_pct"]
        bullets.append(f"vs MA200 *{d}%* ({'di atas tren panjang' if d > 0 else 'di bawah tren panjang'})")

    if bandar.get("phase"):
        bullets.append(f"Bandar fase *{bandar['phase']}* (score {bandar.get('score')}, estimasi)")

    rp = ind.get("range_position_pct")
    if rp is not None:
        bullets.append(f"Posisi *{rp}%* range 60D (low {ind.get('swing_low_60d')} / high {ind.get('swing_high_60d')})")

    adv = ind.get("adv_value_idr_20d")
    if adv:
        bullets.append(f"Likuiditas ADV *Rp {adv/1e9:.1f}B/hari*")

    tr_n = track.get("n", 0)
    if tr_n >= 5:
        bullets.append(
            f"Track record setup: hit *{track.get('hit_rate_pct')}%* · exp *{track.get('expectancy_pct')}%* (n={tr_n})"
        )

    return bullets[:8]


def _build_ticket(intel: dict, qual: dict) -> str:
    t = intel["ticker"]
    last = intel["last_close"]
    regime = intel.get("regime") or {}
    levels = intel.get("levels") or {}
    triggers = intel.get("triggers") or {}
    trig = triggers.get("trigger", {}) if triggers else {}
    inv = triggers.get("invalidation", {}) if triggers else {}

    setup_code, setup_label, thesis = _classify_setup(intel)
    conviction = qual.get("score_setup", 0)

    entry = levels.get("entry") or last
    sl = levels.get("stop_loss")
    tp_struct = levels.get("take_profit")
    tp = _multi_tp(entry, sl, tp_struct) if sl else {}

    lines = [
        f"🟢 *LONG SETUP* — `{t}`",
        f"_{setup_label}_  ·  Conviction *{conviction}%*",
        f"_{thesis}_",
        "",
        "*━━ EXECUTION ━━*",
        f"  Last close : `{last:,.0f}`",
        f"  Entry      : breakout *> {trig.get('entry_breakout_above', last):,.0f}* (vol ≥ {trig.get('require_volume_x', 1.5)}×)",
        f"               atau pullback @ `{trig.get('entry_pullback_at', last):,.0f}`",
        f"  Stop Loss  : `{sl:,.0f}`  (−{levels.get('risk_pct')}%)" if sl else "  Stop Loss  : —",
    ]
    if tp:
        cap_note = " _(capped @ resistance)_" if tp.get("tp3_capped") else ""
        lines += [
            f"  TP1 (50%)  : `{tp['tp1']:,.0f}`  (+{tp['tp1_pct']}%)  → 1R",
            f"  TP2 (30%)  : `{tp['tp2']:,.0f}`  (+{tp['tp2_pct']}%)  → 2R",
            f"  TP3 (20%)  : `{tp['tp3']:,.0f}`  (+{tp['tp3_pct']}%)  runner{cap_note}",
            f"  R:R        : *1 : {levels.get('rr_ratio')}*  ·  Risk *{levels.get('risk_pct')}%/trade*",
        ]

    modifier = regime.get("note") or ""
    lines += [
        "",
        "*━━ MARKET CONTEXT ━━*",
        f"  Regime  : *{regime.get('name')}*" + (f" — {modifier}" if modifier else ""),
        f"  Bias    : {intel.get('action', 'BUY')}  ·  Regime-aligned: {'✅' if regime.get('regime_aligned') else '⚠️ counter-trend'}",
    ]

    # Gap context (informational, not a blocker) — saham + IHSG context
    gap = intel.get("gap")
    ihsg_gap = intel.get("ihsg_gap")
    gap_combined = intel.get("gap_combined")
    show_gap = (gap and gap.get("severity") != "normal") or (ihsg_gap and ihsg_gap.get("severity") != "normal")
    if show_gap:
        lines += ["", "*━━ GAP CHECK ━━*"]
        if gap:
            emoji_s = "📈" if gap["direction"] == "up" else "📉" if gap["direction"] == "down" else "➖"
            lines.append(f"  {emoji_s} Saham  : {gap['gap_pct']:+.2f}%  (open {gap['open']:,.0f} vs prev {gap['prev_close']:,.0f})")
        if ihsg_gap:
            emoji_i = "📈" if ihsg_gap["direction"] == "up" else "📉" if ihsg_gap["direction"] == "down" else "➖"
            lines.append(f"  {emoji_i} IHSG   : {ihsg_gap['gap_pct']:+.2f}%  ({ihsg_gap['severity']})")
        if gap_combined:
            lines.append(f"  _{gap_combined}_")
        elif gap and gap.get("interpretation"):
            lines.append(f"  _{gap['interpretation']}_")

    lines += ["", "*━━ CONFLUENCE ━━*"]
    for b in _confluence_bullets(intel, qual):
        lines.append(f"  ✓ {b}")

    lines += [
        "",
        "*━━ INVALIDATION ━━*",
        f"  ✗ Close di bawah `{inv.get('level', '?'):,.0f}` → exit semua",
        f"  ✗ Regime flip ke Risk-Off / Crash → review semua posisi",
        f"  ⏱ Time stop : {triggers.get('time_stop_bars', 10)} bar tanpa follow-through",
    ]

    lines += [
        "",
        "*━━ EXECUTION PLAN ━━*",
        "  • Scale-in: 1/3 trigger · 1/3 di +1R · 1/3 di +2R",
        "  • Trail stop ke breakeven setelah TP1 hit",
        f"  • Konfirmasi entry: volume ≥ {trig.get('require_volume_x', 1.5)}× MA20",
    ]

    lines += [
        "",
        "_Bukan rekomendasi investasi. Verifikasi setup di chart sebelum eksekusi._",
    ]
    return "\n".join(lines)


def _cooldown_blocker(db, ticker: str) -> str | None:
    """Return blocker message if ticker punya signal/trade dalam COOLDOWN_DAYS."""
    days = settings.COOLDOWN_DAYS
    if days <= 0:
        return None
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = db.execute(
        select(Trade)
        .where(Trade.ticker == ticker)
        .where(Trade.entry_date >= cutoff)
        .order_by(Trade.entry_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if recent:
        return f"Cooldown: signal {ticker} sudah dikirim {recent.entry_date.date()} (<{days} hari)."
    return None


def _record_trade(db, intel: dict, levels: dict, tp_dict: dict, setup_label: str) -> bool:
    """Insert an open Trade row so invalidation_monitor dapat track SL/TP.

    Skip kalau ticker masih punya open position (avoid duplicate). TP1/TP2 disimpan
    di `notes` JSON karena schema Trade hanya punya 1 kolom take_profit.
    """
    ticker = intel["ticker"]
    existing = db.execute(
        select(Trade).where(Trade.ticker == ticker, Trade.exit_date.is_(None))
    ).scalar_one_or_none()
    if existing:
        log.info("Trade %s sudah open, skip insert.", ticker)
        return False
    entry = float(levels.get("entry") or intel["last_close"])
    sl = float(levels["stop_loss"])
    notes = {
        "tp1": tp_dict.get("tp1"),
        "tp2": tp_dict.get("tp2"),
        "tp3": tp_dict.get("tp3"),
        "tp1_hit": False,
        "tp2_hit": False,
        "thesis": setup_label,
        "rr_ratio": levels.get("rr_ratio"),
        "risk_pct": levels.get("risk_pct"),
    }
    trade = Trade(
        ticker=ticker,
        entry_price=Decimal(str(entry)),
        stop_loss=Decimal(str(sl)),
        take_profit=Decimal(str(tp_dict.get("tp3") or levels.get("take_profit"))),
        entry_date=datetime.utcnow(),
        source="sahamflow",
        setup=setup_label[:80],
        notes=json.dumps(notes),
    )
    db.add(trade)
    db.commit()
    log.info("Trade tracked: %s entry=%s sl=%s tp3=%s", ticker, entry, sl, notes.get("tp3"))
    return True


def alert_strong_setups(max_per_run: int = 5, min_score_override: float | None = None) -> dict:
    """Generate qualified tickets and push to Telegram.

    Args:
        max_per_run: maksimum ticket dikirim per run.
        min_score_override: kalau di-set, override threshold composite (default
            dari signal_qualifier.MIN_ABS_SCORE). Pakai untuk testing format.

    Returns {evaluated, qualified, sent, skipped:[{ticker, blockers}]}.
    """
    threshold = min_score_override if min_score_override is not None else signal_qualifier.MIN_ABS_SCORE
    summary = {"evaluated": 0, "qualified": 0, "sent": 0, "skipped": [], "threshold": threshold}
    with SessionLocal() as db:
        regime = db.execute(
            select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
        ).scalar_one_or_none()
        if not regime:
            log.info("No regime row, skip alerts.")
            return summary

        rows = (
            db.execute(
                select(SignalCache)
                .where(SignalCache.date == regime.date)
                .order_by(SignalCache.composite_score.desc())
            )
            .scalars()
            .all()
        )

        # Header pasar
        modifier = (regime.extra or {}).get("modifier")
        header_lines = [
            f"📊 *Sahamflow EOD* `{regime.date}`",
            f"Regime: *{regime.regime}*"
            + (f" → *{modifier}*" if modifier else "")
            + f" (conf {regime.confidence}%, score {regime.raw_score})",
        ]
        path = (regime.extra or {}).get("path_signals") or {}
        if path.get("streak_down"):
            header_lines.append(f"  • Streak turun {path['streak_down']}D · 30D {path.get('return_30d_pct')}%")
        if path.get("reversal_day"):
            header_lines.append(f"  • Reversal day +{path['reversal_day'].get('reversal_pct')}% terdeteksi")
        if min_score_override is not None:
            header_lines.append(f"  ⚠️ _TEST MODE — threshold composite diturunkan ke {threshold}_")
        telegram_send("\n".join(header_lines))

        watchlist = settings.watchlist_set
        candidates = [r for r in rows if (r.composite_score or 0) >= threshold]
        # IHSG gap diambil sekali per run (di-share ke semua ticker)
        ihsg_gap = None
        try:
            from app.services import gap_detector
            ihsg_gap = gap_detector.compute_ihsg_gap()
        except Exception as e:
            log.debug("IHSG gap fetch failed: %s", e)
        # Watchlist filter: kalau di-set, hanya ticker di list yang lolos
        if watchlist:
            before = len(candidates)
            candidates = [r for r in candidates if r.ticker.upper() in watchlist]
            log.info("Watchlist filter: %d → %d (allowed: %s)", before, len(candidates), watchlist)
        for r in candidates:
            summary["evaluated"] += 1
            # Pre-qualifier blockers (cooldown + earnings) — production only
            if min_score_override is None:
                cd = _cooldown_blocker(db, r.ticker)
                if cd:
                    summary["skipped"].append({"ticker": r.ticker, "blockers": [cd]})
                    continue
            intel = signal_intelligence.build_intel(db, r.ticker)
            if not intel:
                continue
            # Inject gap info — informational, tidak block signal
            try:
                from app.services import gap_detector
                intel["gap"] = gap_detector.compute_overnight_gap(db, r.ticker)
                intel["ihsg_gap"] = ihsg_gap
                intel["gap_combined"] = gap_detector.combined_interpretation(
                    intel["gap"], ihsg_gap
                )
            except Exception as e:
                log.debug("Gap calc %s failed: %s", r.ticker, e)
            qual = signal_qualifier.qualify(intel, account_size_idr=settings.ACCOUNT_SIZE_IDR)
            # In test mode, kirim juga yang gagal qualifier supaya bisa lihat format
            passed = qual["qualified"] or min_score_override is not None
            if not passed:
                summary["skipped"].append({"ticker": r.ticker, "blockers": qual["blockers"]})
                continue
            summary["qualified"] += 1
            if summary["sent"] >= max_per_run:
                break
            if telegram_send(_build_ticket(intel, qual)):
                summary["sent"] += 1
                # Production only — jangan polusi Trade table dengan test signals
                if min_score_override is None:
                    levels = intel.get("levels") or {}
                    entry_v = float(levels.get("entry") or intel["last_close"])
                    sl_v = levels.get("stop_loss")
                    if sl_v:
                        tp_dict = _multi_tp(entry_v, float(sl_v), levels.get("take_profit"))
                        setup_code, setup_label, _ = _classify_setup(intel)
                        try:
                            _record_trade(db, intel, levels, tp_dict, setup_label)
                        except Exception as e:
                            log.warning("Failed to record trade %s: %s", intel["ticker"], e)

        if summary["sent"] == 0 and candidates:
            blockers_summary = "; ".join(
                f"{s['ticker']}: {s['blockers'][0]}" for s in summary["skipped"][:5]
            )
            telegram_send(
                "ℹ️ Hari ini tidak ada setup yang lolos filter buy-side.\n"
                f"_{len(candidates)} kandidat dievaluasi, semua diblokir._\n"
                f"`{blockers_summary}`"
            )

    # Refresh pinned PnL kalau ada Trade baru ter-record (production only)
    if summary["sent"] > 0 and min_score_override is None:
        try:
            from app.services import invalidation_monitor
            invalidation_monitor.refresh_pinned_pnl_summary()
        except Exception as e:
            log.warning("Pinned refresh after alerts failed: %s", e)

    log.info("Alerts: %s", summary)
    return summary
