# Sahamflow — Deployment

Target: Hostinger VPS + Nginx + systemd (FastAPI) + PM2 (Next.js frontend, later).

## Local / dev

```bash
# 1. Infra
docker compose up -d postgres redis

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill ANTHROPIC_API_KEY if using AI brief

# 3. Migrate + seed (Tahap 0)
alembic upgrade head
python -m scripts.fetch_seed    # or `--check` to validate yfinance only

# 4. Run API
uvicorn app.main:app --reload --port 8000
# docs at http://localhost:8000/docs
```

## Production (VPS)

- Postgres 16 + Redis as managed services or Docker.
- FastAPI under `uvicorn`/`gunicorn` managed by **systemd**; reverse-proxied by
  **Nginx** on `api.sahamflow.com`.
- Set `APP_ENV=production` and a real `ALLOWED_HOSTS` (e.g.
  `sahamflow.com,api.sahamflow.com`).
- APScheduler runs in-process (timezone Asia/Jakarta); set `ENABLE_SCHEDULER=1`
  on exactly one API worker to avoid duplicate cron firing. With multiple workers,
  run the scheduler as a separate single-process service instead.

## Cron schedule (APScheduler, Asia/Jakarta)

| Time | Job |
|---|---|
| 17:30 | sync EOD OHLCV |
| 18:00 | compute regime |
| 18:30 | generate signals |
| 07:00 | warm regime + signals for the morning brief |

## Open questions for the owner (from the build prompt)

1. Domain `sahamflow.com` purchased? New VPS or existing Hostinger box?
2. Universe: currently 10 seed stocks (MVP). Expand to LQ45 / IDX30 / full 800+?
3. Anthropic API monthly budget? (drives `NARRATIVE_TOP_N`)
4. Any paid data access yet, or full yfinance/scraping to start?
