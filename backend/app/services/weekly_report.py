"""Weekly performance report — kirim Sabtu pagi ke channel Telegram.

Ringkasan minggu lalu (Senin-Jumat):
- Total signal kirim, qualified
- Trade closed: win/loss, total PnL, best/worst
- Trade masih open: jumlah, unrealized
- Pattern breakdown (mana setup paling profitable)
- Catatan disiplin (apakah Anda follow signal?)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Trade
from app.services import notifier

log = logging.getLogger("sahamflow.weekly_report")


def build_weekly_report() -> str:
    """Build Markdown weekly summary untuk Telegram."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    with SessionLocal() as db:
        trades = db.execute(
            select(Trade)
            .where(Trade.entry_date >= cutoff)
            .order_by(Trade.entry_date.desc())
        ).scalars().all()

        # Trade closed minggu ini (closed dalam 7 hari, terlepas entry kapan)
        closed_recent = db.execute(
            select(Trade)
            .where(Trade.exit_date >= cutoff)
            .order_by(Trade.exit_date.desc())
        ).scalars().all()

    new_signals = len(trades)
    closed_n = len(closed_recent)
    wins = [t for t in closed_recent if t.pnl_pct and float(t.pnl_pct) > 0]
    losses = [t for t in closed_recent if t.pnl_pct and float(t.pnl_pct) <= 0]
    total_pnl = sum(float(t.pnl_pct or 0) for t in closed_recent)
    win_rate = len(wins) * 100 / closed_n if closed_n else 0
    avg_win = sum(float(t.pnl_pct) for t in wins) / len(wins) if wins else 0
    avg_loss = sum(float(t.pnl_pct) for t in losses) / len(losses) if losses else 0
    best = max(closed_recent, key=lambda t: float(t.pnl_pct or 0), default=None)
    worst = min(closed_recent, key=lambda t: float(t.pnl_pct or 0), default=None)
    profit_factor = (
        abs(sum(float(t.pnl_pct) for t in wins) / sum(float(t.pnl_pct) for t in losses))
        if losses and sum(float(t.pnl_pct) for t in losses) != 0 else None
    )

    # Setup performance
    setup_perf: dict[str, list[float]] = {}
    for t in closed_recent:
        if not t.pnl_pct or not t.setup:
            continue
        setup_perf.setdefault(t.setup, []).append(float(t.pnl_pct))

    lines = [
        "📅 *WEEKLY PERFORMANCE — SAHAMFLOW*",
        f"_Periode: {cutoff.strftime('%Y-%m-%d')} → {datetime.utcnow().strftime('%Y-%m-%d')}_",
        "",
        "*━━ AKTIVITAS ━━*",
        f"  Signal baru   : *{new_signals}*",
        f"  Trade closed  : *{closed_n}*  ({len(wins)}W / {len(losses)}L)",
        f"  Win rate      : *{win_rate:.1f}%*",
        f"  Total PnL     : *{total_pnl:+.2f}%* (equal-weight)",
    ]
    if profit_factor is not None:
        lines.append(f"  Profit factor : *{profit_factor:.2f}*")
    lines += [
        f"  Avg win       : +{avg_win:.2f}%",
        f"  Avg loss      : {avg_loss:.2f}%",
    ]

    if best and float(best.pnl_pct or 0) > 0:
        lines += [
            "",
            f"🏆 *Best trade* : `{best.ticker}` {float(best.pnl_pct):+.2f}% ({best.setup or 'n/a'})",
        ]
    if worst and float(worst.pnl_pct or 0) < 0:
        lines.append(f"💀 *Worst trade*: `{worst.ticker}` {float(worst.pnl_pct):+.2f}% ({worst.setup or 'n/a'})")

    if setup_perf:
        lines += ["", "*━━ SETUP BREAKDOWN ━━*"]
        ranked = sorted(setup_perf.items(), key=lambda x: -sum(x[1]) / len(x[1]))
        for setup, pnls in ranked[:6]:
            avg = sum(pnls) / len(pnls)
            n = len(pnls)
            wins_s = sum(1 for p in pnls if p > 0)
            lines.append(
                f"  `{setup[:24]:<24}` avg {avg:+.2f}%  ({wins_s}/{n}W)"
            )

    # Discipline check
    lines += [
        "",
        "*━━ DISIPLIN ━━*",
    ]
    if total_pnl >= 0 and win_rate >= 50:
        lines.append("  ✅ Profitable & disiplin minggu ini.")
    elif total_pnl >= 0:
        lines.append("  ⚠️ Profitable tapi win rate < 50% — average win > average loss bagus.")
    elif win_rate >= 50:
        lines.append("  ⚠️ Win rate tinggi tapi PnL negatif — average loss > average win, perketat SL atau loosen TP.")
    else:
        lines.append("  🔴 Drawdown minggu ini — review setup yang loss, cek disiplin SL.")
    if closed_n == 0 and new_signals == 0:
        lines.append("  💤 Tidak ada aktivitas — regime mungkin tidak mendukung. Sabar lebih baik dari trade paksa.")

    lines += [
        "",
        "_Detail per trade tersedia via /api/v1/trades/export.csv_",
    ]
    return "\n".join(lines)


def send_weekly_report() -> bool:
    text = build_weekly_report()
    return notifier.telegram_send(text)
