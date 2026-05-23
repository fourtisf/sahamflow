"""Telegram bot command handler — polling via getUpdates.

Single-user commands untuk manage watchlist & status:
  /watch BBRI           - tambah ke watchlist
  /unwatch BBRI         - hapus dari watchlist
  /watchlist            - list isi watchlist
  /status               - status sistem (trade open, regime, dll)
  /gap                  - kirim ulang pinned gap radar
  /pnl                  - kirim ulang pinned PnL summary
  /report               - generate weekly report
  /help                 - daftar command

Poll setiap 60 detik via scheduler. State (offset + watchlist) di bot_state.json.
"""

from __future__ import annotations

import logging
from typing import Callable

import httpx

from app.core.config import settings
from app.services import notifier

log = logging.getLogger("sahamflow.tg_commands")


def _get_watchlist() -> list[str]:
    state = notifier._load_state()
    return state.get("telegram_watchlist", [])


def _set_watchlist(tickers: list[str]) -> None:
    state = notifier._load_state()
    state["telegram_watchlist"] = sorted({t.upper() for t in tickers if t.strip()})
    notifier._save_state(state)


def get_active_watchlist() -> set[str]:
    """Public: returns set of active watchlist tickers (Telegram-managed first,
    fall back to env WATCHLIST_TICKERS)."""
    tg = _get_watchlist()
    if tg:
        return set(tg)
    return settings.watchlist_set


# === Command handlers ===
def _cmd_help(args: list[str]) -> str:
    return (
        "*Sahamflow Bot Commands*\n"
        "`/watch BBRI`        — tambah ticker ke watchlist\n"
        "`/unwatch BBRI`      — hapus ticker dari watchlist\n"
        "`/watchlist`         — tampilkan watchlist aktif\n"
        "`/status`            — status sistem (regime, open trades)\n"
        "`/gap`               — refresh GAP RADAR pinned\n"
        "`/pnl`               — refresh PnL pinned\n"
        "`/report`            — kirim weekly performance report\n"
        "`/help`              — pesan ini"
    )


def _cmd_watch(args: list[str]) -> str:
    if not args:
        return "Pakai: `/watch TICKER` (contoh: `/watch BBRI`)"
    wl = _get_watchlist()
    added = []
    for t in args:
        t = t.upper().strip()
        if t and t not in wl:
            wl.append(t)
            added.append(t)
    _set_watchlist(wl)
    if added:
        return f"✅ Ditambahkan ke watchlist: *{', '.join(added)}*\nWatchlist sekarang: `{', '.join(sorted(wl)) or '(kosong)'}`"
    return "_Tidak ada ticker baru ditambahkan (sudah ada)._"


def _cmd_unwatch(args: list[str]) -> str:
    if not args:
        return "Pakai: `/unwatch TICKER` (contoh: `/unwatch BBRI`)"
    wl = _get_watchlist()
    removed = []
    for t in args:
        t = t.upper().strip()
        if t in wl:
            wl.remove(t)
            removed.append(t)
    _set_watchlist(wl)
    if removed:
        return f"🗑 Dihapus dari watchlist: *{', '.join(removed)}*\nWatchlist sekarang: `{', '.join(sorted(wl)) or '(kosong)'}`"
    return "_Tidak ada ticker dihapus (tidak ada di list)._"


def _cmd_watchlist(args: list[str]) -> str:
    wl = _get_watchlist()
    env_wl = settings.watchlist_set
    if not wl and not env_wl:
        return "_Watchlist kosong — semua ticker qualified akan dialert._"
    src = "Telegram (override env)" if wl else "ENV (.env file)"
    items = sorted(wl) if wl else sorted(env_wl)
    return f"*Watchlist aktif* ({src}):\n`{', '.join(items)}`\n_Total: {len(items)} ticker_"


def _cmd_status(args: list[str]) -> str:
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models import RegimeHistory, Trade

    with SessionLocal() as db:
        regime = db.execute(
            select(RegimeHistory).order_by(RegimeHistory.date.desc()).limit(1)
        ).scalar_one_or_none()
        open_trades = db.execute(
            select(Trade).where(Trade.exit_date.is_(None))
        ).scalars().all()

    lines = ["*Sahamflow Status*"]
    if regime:
        mod = (regime.extra or {}).get("modifier")
        lines.append(
            f"Regime  : *{regime.regime}*"
            + (f" → {mod}" if mod else "")
            + f" (conf {regime.confidence}%)"
        )
        lines.append(f"Date    : {regime.date}")
    else:
        lines.append("Regime  : _data belum tersedia_")
    lines.append(f"Open positions : *{len(open_trades)}*")
    if open_trades:
        for t in open_trades[:10]:
            lines.append(f"  • `{t.ticker}` @ {float(t.entry_price):,.0f}  setup: {t.setup or 'n/a'}")
    return "\n".join(lines)


def _cmd_gap(args: list[str]) -> str:
    from app.services import gap_detector

    ok = gap_detector.refresh_gap_radar_pinned()
    return "✅ Gap radar refreshed." if ok else "❌ Refresh gagal — cek logs."


def _cmd_pnl(args: list[str]) -> str:
    from app.services import invalidation_monitor

    ok = invalidation_monitor.refresh_pinned_pnl_summary()
    return "✅ PnL pinned refreshed." if ok else "❌ Refresh gagal — cek logs."


def _cmd_report(args: list[str]) -> str:
    from app.services import weekly_report

    text = weekly_report.build_weekly_report()
    if notifier.telegram_send(text):
        return "✅ Weekly report dikirim."
    return "❌ Gagal kirim report."


COMMANDS: dict[str, Callable[[list[str]], str]] = {
    "/help": _cmd_help,
    "/start": _cmd_help,
    "/watch": _cmd_watch,
    "/unwatch": _cmd_unwatch,
    "/watchlist": _cmd_watchlist,
    "/list": _cmd_watchlist,
    "/status": _cmd_status,
    "/gap": _cmd_gap,
    "/pnl": _cmd_pnl,
    "/report": _cmd_report,
}


def _handle_message(text: str) -> str | None:
    """Parse + dispatch command. Returns reply text or None if not a command."""
    text = text.strip()
    if not text.startswith("/"):
        return None
    parts = text.split()
    cmd = parts[0].split("@")[0].lower()  # strip @botname
    args = parts[1:]
    handler = COMMANDS.get(cmd)
    if not handler:
        return f"Unknown command: `{cmd}`\n{_cmd_help([])}"
    try:
        return handler(args)
    except Exception as e:
        log.exception("Command %s failed", cmd)
        return f"❌ Error: {e}"


def poll_updates() -> int:
    """Poll Telegram getUpdates, handle commands. Idempotent (uses offset)."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return 0
    state = notifier._load_state()
    offset = state.get("tg_update_offset", 0)
    try:
        r = httpx.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 0, "limit": 50},
            timeout=10,
        )
        if r.status_code != 200:
            log.warning("getUpdates %s: %s", r.status_code, r.text[:200])
            return 0
        data = r.json()
    except Exception as e:
        log.warning("getUpdates failed: %s", e)
        return 0

    if not data.get("ok"):
        return 0

    updates = data.get("result", [])
    if not updates:
        return 0

    handled = 0
    chat_target = str(settings.TELEGRAM_CHAT_ID)
    for upd in updates:
        offset = max(offset, upd["update_id"] + 1)
        msg = upd.get("message") or upd.get("channel_post")
        if not msg:
            continue
        text = msg.get("text", "")
        if not text:
            continue
        # Authorize: only respond ke chat yang dikonfigurasi (channel @sahamflow)
        chat_id = str(msg.get("chat", {}).get("id", ""))
        chat_username = "@" + (msg.get("chat", {}).get("username", "") or "")
        if chat_id != chat_target.lstrip("@") and chat_username != chat_target and not chat_target.lstrip("@") == chat_username.lstrip("@"):
            log.debug("Ignored msg from chat %s (target %s)", chat_id, chat_target)
            continue
        reply = _handle_message(text)
        if reply:
            notifier.telegram_send(reply)
            handled += 1

    # Persist offset
    state = notifier._load_state()
    state["tg_update_offset"] = offset
    notifier._save_state(state)
    return handled
