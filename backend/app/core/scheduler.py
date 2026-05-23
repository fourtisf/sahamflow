"""APScheduler cron jobs (timezone Asia/Jakarta).

Wired to the FastAPI lifespan. The morning-brief job is registered only when an
Anthropic key is present, so a keyless deployment still runs the data jobs.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.services import data_sync

log = logging.getLogger("sahamflow.scheduler")
_scheduler: BackgroundScheduler | None = None


def _sync_eod():
    data_sync.sync_ohlcv()
    # Best-effort foreign flow scrape right after OHLCV.
    try:
        data_sync.sync_foreign_flow()
    except Exception as e:
        log.warning("Foreign flow sync failed: %s", e)


def _invalidation_check():
    from app.services import invalidation_monitor
    invalidation_monitor.check_open_positions()


def _morning_brief():
    # Brief is generated lazily by the /brief/today endpoint; here we just warm
    # the regime + signals so the first morning request is fast.
    data_sync.compute_regime()
    data_sync.generate_signals()


def _post_eod_alerts():
    """After EOD signals are computed, push high-conviction setups to Telegram."""
    from app.services import notifier

    notifier.alert_strong_setups()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone=settings.TIMEZONE)
    sched.add_job(_sync_eod, "cron", hour=17, minute=30, id="sync_eod")
    sched.add_job(data_sync.compute_regime, "cron", hour=18, minute=0, id="compute_regime")
    sched.add_job(data_sync.generate_signals, "cron", hour=18, minute=30, id="generate_signals")
    sched.add_job(_post_eod_alerts, "cron", hour=18, minute=45, id="post_eod_alerts")
    # Invalidation monitor: jam pasar (intraday hook) + post-EOD untuk catch
    # SL/TP dari close baru + refresh pinned PnL.
    sched.add_job(
        _invalidation_check, "cron",
        hour="9-15", minute=15, day_of_week="mon-fri", id="invalidation_monitor_intraday",
    )
    sched.add_job(_invalidation_check, "cron", hour=18, minute=50, id="invalidation_monitor_eod")
    sched.add_job(_morning_brief, "cron", hour=7, minute=0, id="morning_brief")
    sched.start()
    log.info("Scheduler started (tz=%s)", settings.TIMEZONE)
    _scheduler = sched
    return sched


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
