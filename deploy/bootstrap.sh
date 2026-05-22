#!/usr/bin/env bash
# One-time VPS provisioning for the Sahamflow backend (Ubuntu/Debian).
# Native install: Postgres + Redis + Nginx + systemd. Run as root:
#   sudo bash deploy/bootstrap.sh
#
# Re-runnable: skips steps that are already done. After it finishes, edit
# /opt/sahamflow/backend/.env (set ANTHROPIC_API_KEY) and restart the services.
set -euo pipefail

# ---- config (override via env) ------------------------------------------------
APP_DIR="${APP_DIR:-/opt/sahamflow}"
REPO_URL="${REPO_URL:-https://github.com/fourtisf/sahamflow.git}"
BRANCH="${BRANCH:-claude/jolly-curie-5LI5X}"
APP_USER="${APP_USER:-sahamflow}"
DB_NAME="${DB_NAME:-sahamflow}"
DB_USER="${DB_USER:-sahamflow}"
DB_PASS="${DB_PASS:-sahamflow}"   # CHANGE THIS for production
PY="${PY:-python3}"

echo ">> Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git curl build-essential \
  "${PY}" "${PY}-venv" "${PY}-dev" \
  postgresql postgresql-contrib \
  redis-server \
  nginx certbot python3-certbot-nginx

systemctl enable --now postgresql redis-server nginx

echo ">> Creating app user '${APP_USER}'..."
if ! id "${APP_USER}" &>/dev/null; then
  useradd --system --create-home --shell /bin/bash "${APP_USER}"
fi

echo ">> Creating Postgres role + database..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
# pgcrypto provides gen_random_uuid() used by the trades table.
sudo -u postgres psql -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

echo ">> Fetching code into ${APP_DIR}..."
if [ ! -d "${APP_DIR}/.git" ]; then
  git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
else
  git -C "${APP_DIR}" fetch origin "${BRANCH}"
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
fi
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo ">> Creating virtualenv + installing deps..."
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_DIR}/backend'
  ${PY} -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
"

echo ">> Writing .env (if missing)..."
ENV_FILE="${APP_DIR}/backend/.env"
if [ ! -f "${ENV_FILE}" ]; then
  cat > "${ENV_FILE}" <<EOF
DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-6
APP_ENV=production
TIMEZONE=Asia/Jakarta
ALLOWED_HOSTS=*
NARRATIVE_TOP_N=50
NARRATIVE_CACHE_TTL=86400
EOF
  chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  echo "   -> EDIT ${ENV_FILE} and set ANTHROPIC_API_KEY + a real DB_PASS."
fi

echo ">> Running migrations + seeding (Tahap 0)..."
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_DIR}/backend'
  .venv/bin/alembic upgrade head
  .venv/bin/python -m scripts.fetch_seed || echo 'WARN: seed failed (check yfinance network access)'
"

echo ">> Installing systemd services..."
cp "${APP_DIR}/deploy/sahamflow-api.service" /etc/systemd/system/
cp "${APP_DIR}/deploy/sahamflow-scheduler.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sahamflow-api sahamflow-scheduler

echo ">> Installing Nginx site..."
cp "${APP_DIR}/deploy/nginx-sahamflow.conf" /etc/nginx/sites-available/sahamflow
ln -sf /etc/nginx/sites-available/sahamflow /etc/nginx/sites-enabled/sahamflow
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo ">> Done. Check:  curl http://localhost/health"
echo ">> Logs:        journalctl -u sahamflow-api -f"
echo ">> TLS later:   sudo certbot --nginx -d api.sahamflow.com"
