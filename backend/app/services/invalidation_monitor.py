"""Pantau posisi terbuka: alert SL/TP cascade + pinned PnL summary.

Cascade exit (sesuai execution plan di signal):
- TP1 hit → alert "book 50%, trail rest", posisi tetap open
- TP2 hit → alert "book 30%, runner aktif", posisi tetap open
- TP3 hit → alert "full exit", posisi closed
- SL hit (kapan saja) → alert "exit semua", posisi closed
- Setelah cascade selesai, refresh PINNED message di channel berisi total PnL.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal

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


def _parse_notes(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _alert_tp_partial(ticker: str, level_name: str, level_price: float, entry: float, pct_book: int) -> bool:
    pnl_pct = (level_price / entry - 1) * 100
    text = (
        f"🎯 *{level_name} HIT* — `{ticker}`\n"
        f"Entry `{entry:,.0f}` → Now `{level_price:,.0f}`  (*+{pnl_pct:.2f}%*)\n"
        f"_Action_ : *book {pct_book}%* posisi, sisanya trail.\n"
        f"_Trail_  : geser SL ke breakeven (entry) setelah {level_name}."
    )
    return notifier.telegram_send(text)


def _alert_full_exit(ticker: str, kind: str, exit_price: float, entry: float, setup: str | None) -> bool:
    pnl_pct = (exit_price / entry - 1) * 100
    emoji = "🟢" if pnl_pct >= 0 else "🔴"
    word = "TP3 / FULL TARGET" if "TP" in kind else "STOP LOSS"
    text = (
        f"{emoji} *{word} HIT — POSITION CLOSED* `{ticker}`\n"
        f"Entry `{entry:,.0f}` → Exit `{exit_price:,.0f}`\n"
        f"PnL : *{pnl_pct:+.2f}%*\n"
        f"_Setup_ : {setup or 'n/a'}\n"
        f"_Posisi ini perlu di-close manual di broker._"
    )
    return notifier.telegram_send(text)


def check_open_positions() -> dict:
    """Cascade SL/TP check on all open trades. Returns summary dict."""
    summary = {"checked": 0, "tp1": 0, "tp2": 0, "closed_tp": 0, "closed_sl": 0}
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
            summary["checked"] += 1

            entry = float(p.entry_price)
            sl = float(p.stop_loss)
            tp3 = float(p.take_profit) if p.take_profit else None
            notes = _parse_notes(p.notes)
            tp1 = notes.get("tp1")
            tp2 = notes.get("tp2")

            # SL hit → close immediately
            if last <= sl:
                _alert_full_exit(p.ticker, "SL", last, entry, p.setup)
                p.exit_date = datetime.utcnow()
                p.exit_price = Decimal(str(last))
                p.pnl_pct = Decimal(str(round((last / entry - 1) * 100, 2)))
                p.invalidated_at = datetime.utcnow()
                summary["closed_sl"] += 1
                continue

            # TP1 partial alert
            if tp1 and last >= tp1 and not notes.get("tp1_hit"):
                _alert_tp_partial(p.ticker, "TP1", tp1, entry, 50)
                notes["tp1_hit"] = True
                p.notes = json.dumps(notes)
                summary["tp1"] += 1

            # TP2 partial alert
            if tp2 and last >= tp2 and not notes.get("tp2_hit"):
                _alert_tp_partial(p.ticker, "TP2", tp2, entry, 30)
                notes["tp2_hit"] = True
                p.notes = json.dumps(notes)
                summary["tp2"] += 1

            # TP3 / full target → close
            if tp3 and last >= tp3:
                _alert_full_exit(p.ticker, "TP3", last, entry, p.setup)
                p.exit_date = datetime.utcnow()
                p.exit_price = Decimal(str(last))
                p.pnl_pct = Decimal(str(round((last / entry - 1) * 100, 2)))
                summary["closed_tp"] += 1

        db.commit()

    try:
        refresh_pinned_pnl_summary()
    except Exception as e:
        log.warning("Pin refresh failed: %s", e)

    log.info("Invalidation monitor: %s", summary)
    return summary


def _build_pnl_summary() -> str:
    with SessionLocal() as db:
        trades = db.execute(select(Trade).order_by(Trade.entry_date.desc())).scalars().all()

        open_t = [t for t in trades if t.exit_date is None]
        closed_t = [t for t in trades if t.exit_date is not None]
        wins = [t for t in closed_t if t.pnl_pct and float(t.pnl_pct) > 0]
        losses = [t for t in closed_t if t.pnl_pct and float(t.pnl_pct) <= 0]

        total_pnl = sum(float(t.pnl_pct or 0) for t in closed_t)
        avg_win = (sum(float(t.pnl_pct) for t in wins) / len(wins)) if wins else 0
        avg_loss = (sum(float(t.pnl_pct) for t in losses) / len(losses)) if losses else 0
        win_rate = (len(wins) / len(closed_t) * 100) if closed_t else 0

        lines = [
            "📌 *SAHAMFLOW LIVE PERFORMANCE*",
            f"_Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
            "",
            f"*Total trades* : {len(trades)} ({len(open_t)} open, {len(closed_t)} closed)",
            f"*Win rate*     : {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)",
            f"*Total PnL*    : *{total_pnl:+.2f}%* (sum % per trade, equal-weight)",
            f"*Avg win*      : +{avg_win:.2f}%   ·   *Avg loss*: {avg_loss:.2f}%",
        ]

        if open_t:
            lines += ["", "*━━ OPEN POSITIONS ━━*"]
            for t in open_t[:10]:
                last = _last_close(db, t.ticker) or float(t.entry_price)
                entry = float(t.entry_price)
                unrealized = (last / entry - 1) * 100
                notes = _parse_notes(t.notes)
                flags = []
                if notes.get("tp1_hit"):
                    flags.append("TP1✓")
                if notes.get("tp2_hit"):
                    flags.append("TP2✓")
                flag_str = f" [{','.join(flags)}]" if flags else ""
                lines.append(
                    f"  `{t.ticker}` @ {entry:,.0f} → {last:,.0f}  *{unrealized:+.2f}%*{flag_str}"
                )

        if closed_t:
            lines += ["", "*━━ RECENT CLOSED (last 5) ━━*"]
            for t in closed_t[:5]:
                emoji = "🟢" if (t.pnl_pct and float(t.pnl_pct) >= 0) else "🔴"
                lines.append(
                    f"  {emoji} `{t.ticker}` {float(t.pnl_pct or 0):+.2f}%  ({t.setup or 'n/a'})"
                )

    lines += ["", "_PnL = % per trade, equal-weight. Bukan return modal aktual._"]
    return "\n".join(lines)


def refresh_pinned_pnl_summary() -> bool:
    text = _build_pnl_summary()
    notifier.telegram_unpin_all()
    msg_id = notifier.telegram_send_with_id(text)
    if not msg_id:
        return False
    return notifier.telegram_pin(msg_id, disable_notification=True)
