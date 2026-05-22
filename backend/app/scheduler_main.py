"""Standalone scheduler process.

Run as a single dedicated systemd service so the cron jobs fire exactly once,
independent of how many API (gunicorn) workers are running. The API service
itself runs with ENABLE_SCHEDULER=0.
"""

from __future__ import annotations

import logging
import signal
import threading

from app.core.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sahamflow.scheduler_main")


def main() -> None:
    start_scheduler()
    log.info("Scheduler process up. Waiting for jobs (Ctrl+C / SIGTERM to stop).")
    stop = threading.Event()

    def _handle(signum, _frame):
        log.info("Received signal %s, shutting down scheduler.", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    stop.wait()
    shutdown_scheduler()


if __name__ == "__main__":
    main()
