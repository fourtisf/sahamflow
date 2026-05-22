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

## Production (VPS) — native systemd + Nginx

All artifacts live in `deploy/`. One command provisions a fresh Ubuntu/Debian VPS:

```bash
# On the VPS, as root. Override defaults via env vars (DB_PASS, REPO_URL, BRANCH).
sudo DB_PASS='<strong-password>' bash deploy/bootstrap.sh
```

`bootstrap.sh` installs Postgres 16 + Redis + Nginx, creates the `sahamflow`
system user, DB role/database (+ `pgcrypto` for `gen_random_uuid()`), clones the
repo to `/opt/sahamflow`, builds the venv, writes `.env`, runs `alembic upgrade
head`, seeds the 10 stocks, then installs and starts both systemd services and the
Nginx site.

After it finishes: **edit `/opt/sahamflow/backend/.env`** to set `ANTHROPIC_API_KEY`
(and a real DB password if you didn't pass `DB_PASS`), then
`sudo systemctl restart sahamflow-api`.

### Services

| Unit | Role | Scheduler |
|---|---|---|
| `sahamflow-api.service` | gunicorn + uvicorn workers on `127.0.0.1:8000` | OFF (`ENABLE_SCHEDULER=0`) |
| `sahamflow-scheduler.service` | single process running APScheduler cron | ON |

The scheduler is split into its own one-process service so cron fires **exactly
once** regardless of API worker count.

```bash
journalctl -u sahamflow-api -f          # API logs
journalctl -u sahamflow-scheduler -f    # cron logs
curl http://localhost/health            # smoke test
```

### Nginx / TLS

MVP listens on **port 80 by IP** (`deploy/nginx-sahamflow.conf`, `server_name _`).
When `api.sahamflow.com` is pointed at the VPS, set `server_name` and run:

```bash
sudo certbot --nginx -d api.sahamflow.com   # adds 443 + TLS automatically
```

Set `APP_ENV=production` and a real `ALLOWED_HOSTS` (e.g.
`sahamflow.com,api.sahamflow.com`) in `.env` once the domain is live.

### Updating a deployed VPS

```bash
sudo bash deploy/deploy.sh   # pull branch, install deps, migrate, restart
```

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
