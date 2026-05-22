"""Gunicorn config for the Sahamflow API (uvicorn workers).

Keep workers modest for a single-owner MVP VPS. The scheduler runs in a separate
systemd service, so the API workers must NOT start it (ENABLE_SCHEDULER=0 in the
unit file).
"""

import multiprocessing

bind = "127.0.0.1:8000"
workers = min(4, multiprocessing.cpu_count() * 2 + 1)
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
