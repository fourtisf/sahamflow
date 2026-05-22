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


def _morning_brief():
    # Brief is generated lazily by the /brief/today endpoint; here we just warm
    # the regime + signals so the first morning request is fast.
    data_sync.compute_regime()
    data_sync.generate_signals()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone=settings.TIMEZONE)
    sched.add_job(_sync_eod, "cron", hour=17, minute=30, id="sync_eod")
    sched.add_job(data_sync.compute_regime, "cron", hour=18, minute=0, id="compute_regime")
    sched.add_job(data_sync.generate_signals, "cron", hour=18, minute=30, id="generate_signals")
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
