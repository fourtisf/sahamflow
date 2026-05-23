"""Telegram push notifier — actionable buy-side ticket, BUKAN sinyal random.

Setiap alert sebuah TICKET LENGKAP:
- Action (BUY/SELL) + ticker + level entry/SL/TP/RR
- REASON: rantai bukti yang membuatnya layak alert (composite, regime,
  track record, indikator pendukung, likuiditas)
- Position sizing (risk-based, dicap likuiditas)
- Invalidation level eksplisit

Filter ketat di signal_qualifier.qualify(): high-conviction + regime selaras +
track record OK + likuiditas cukup. Sinyal yang tidak qualified TIDAK dikirim
— lebih baik diam daripada kirim noise.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import RegimeHistory, SignalCache
from app.services import signal_intelligence, signal_qualifier

log = logging.getLogger("sahamflow.notifier")


def telegram_send(text: str) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    chat = settings.TELEGRAM_CHAT_ID
    if not token or not chat:
        log.info("Telegram disabled (no token/chat). Skipping: %s", text[:80])
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if r.status_code != 200:
            log.warning("Telegram %s: %s", r.status_code, r.text[:200])
        return r.status_code == 200
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        return False


def _fmt_idr(n: int | float | None) -> str:
    if n is None:
        return "—"
    if n >= 1e9:
        return f"Rp {n/1e9:.2f}B"
    if n >= 1e6:
        return f"Rp {n/1e6:.1f}jt"
    return f"Rp {int(n):,}".replace(",", ".")


def _build_ticket(intel: dict, qual: dict) -> str:
    """Compose a single-ticker Markdown ticket for Telegram."""
    t = intel["ticker"]
    score = intel.get("composite_score", 0)
    label = intel.get("signal", "Hold")
    action = "🟢 *BUY*"  # long-only mode untuk IDX retail
    last = intel["last_close"]
    regime = intel.get("regime") or {}
    levels = intel.get("levels") or {}
    triggers = intel.get("triggers") or {}
    trig = triggers.get("trigger", {}) if triggers else {}
    inv = triggers.get("invalidation", {}) if triggers else {}
    pos = qual.get("position") or {}

    entry_str = f"breakout *> {trig.get('entry_breakout_above', last)}* (vol ≥ 1.5×) atau pullback ke {trig.get('entry_pullback_at')}"

    lines = [
        f"{action} `{t}` — {label}",
        f"_Last_ `{last:,.0f}` · _Conviction_ *{qual.get('score_setup')}%* · _Regime_ {regime.get('name')}"
        + (f" → {intel.get('regime', {}).get('note', '')}" if regime.get("note") else ""),
        "",
        "*ENTRY*",
        f"  {entry_str}",
        "",
        "*EXIT*",
        f"  TP `{levels.get('take_profit', '?'):,.0f}` (+{levels.get('reward_pct')}%)",
        f"  SL `{levels.get('stop_loss', '?'):,.0f}` (−{levels.get('risk_pct')}%)",
        f"  R:R *1 : {levels.get('rr_ratio', 3)}* · Invalidation: close di luar `{inv.get('level', '?'):,.0f}`",
        "",
        "*POSITION SIZING*",
        (
            f"  Risk per trade: *{levels.get('risk_pct', 1)}%* dari modal"
            + (f" · _likuiditas: {pos['capped_by']}_" if pos and pos.get("capped_by") else "")
        ),
        "",
        "*REASON*",
    ]
    for r in qual.get("reasons", [])[:8]:
        lines.append(f"  • {r}")
    lines.append("")
    lines.append("_Bukan rekomendasi investasi. Konfirmasi trigger & invalidation di dashboard._")
    return "\n".join(lines)


def alert_strong_setups(max_per_run: int = 5) -> dict:
    """Generate qualified tickets and push to Telegram.

    Returns {evaluated, qualified, sent, skipped:[{ticker, blockers}]}.
    """
    summary = {"evaluated": 0, "qualified": 0, "sent": 0, "skipped": []}
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
        telegram_send("\n".join(header_lines))

        # Per-ticker tickets — LONG-ONLY: hanya kandidat skor positif (Buy).
        # Score negatif tidak actionable di IDX retail (no short). Reversal candidates
        # ditangani panel terpisah di dashboard, tidak via TG alert default.
        candidates = [r for r in rows if (r.composite_score or 0) >= 0.5]
        for r in candidates:
            summary["evaluated"] += 1
            intel = signal_intelligence.build_intel(db, r.ticker)
            if not intel:
                continue
            qual = signal_qualifier.qualify(intel, account_size_idr=settings.ACCOUNT_SIZE_IDR)
            if not qual["qualified"]:
                summary["skipped"].append({"ticker": r.ticker, "blockers": qual["blockers"]})
                continue
            summary["qualified"] += 1
            if summary["sent"] >= max_per_run:
                break
            if telegram_send(_build_ticket(intel, qual)):
                summary["sent"] += 1

        # Footer if no tickets passed
        if summary["sent"] == 0 and candidates:
            blockers_summary = "; ".join(
                f"{s['ticker']}: {s['blockers'][0]}" for s in summary["skipped"][:5]
            )
            telegram_send(
                "ℹ️ Hari ini tidak ada setup yang lolos filter buy-side.\n"
                f"_{len(candidates)} kandidat dievaluasi, semua diblokir._\n"
                f"`{blockers_summary}`"
            )

    log.info("Alerts: %s", summary)
    return summary
