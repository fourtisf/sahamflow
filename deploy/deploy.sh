#!/usr/bin/env bash
# Update an already-provisioned VPS to the latest code. Run as root:
#   sudo bash deploy/deploy.sh
# Pulls the branch, installs deps, migrates, restarts services.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sahamflow}"
BRANCH="${BRANCH:-claude/jolly-curie-5LI5X}"
APP_USER="${APP_USER:-sahamflow}"

echo ">> Pulling ${BRANCH}..."
git -C "${APP_DIR}" fetch origin "${BRANCH}"
git -C "${APP_DIR}" checkout "${BRANCH}"
git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo ">> Installing deps + migrating..."
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_DIR}/backend'
  .venv/bin/pip install -r requirements.txt
  .venv/bin/alembic upgrade head
"

echo ">> Restarting services..."
systemctl restart sahamflow-api sahamflow-scheduler
cp "${APP_DIR}/deploy/nginx-sahamflow.conf" /etc/nginx/sites-available/sahamflow
nginx -t && systemctl reload nginx

echo ">> Done. curl http://localhost/health"
