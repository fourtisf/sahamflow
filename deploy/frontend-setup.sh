#!/usr/bin/env bash
# Build + run the Sahamflow Next.js frontend under PM2, behind the existing Nginx.
# Run as root on the VPS AFTER bootstrap.sh (backend) has succeeded:
#   sudo bash deploy/frontend-setup.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sahamflow}"
APP_USER="${APP_USER:-sahamflow}"
NODE_MAJOR="${NODE_MAJOR:-20}"

echo ">> Installing Node.js ${NODE_MAJOR}.x + PM2 (if missing)..."
if ! command -v node >/dev/null || [ "$(node -v | cut -dv -f2 | cut -d. -f1)" -lt "${NODE_MAJOR}" ]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi
command -v pm2 >/dev/null || npm install -g pm2

# git pull as root leaves files root-owned; restore so the app user can build.
echo ">> Fixing ownership..."
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo ">> Building frontend..."
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_DIR}/frontend'
  npm install
  npm run build
"

echo ">> Starting frontend under PM2..."
sudo -u "${APP_USER}" bash -lc "
  cd '${APP_DIR}/frontend'
  pm2 delete sahamflow-web 2>/dev/null || true
  pm2 start npm --name sahamflow-web -- start
  pm2 save
"
# Make PM2 resurrect on reboot for the app user.
env PATH="$PATH:/usr/bin" pm2 startup systemd -u "${APP_USER}" --hp "/home/${APP_USER}" | tail -1 | bash || true

echo ">> Refreshing Nginx (frontend + /api proxy)..."
# Don't clobber certbot's 443 block. Once /etc/letsencrypt/live/<domain> exists,
# leave the live config alone and just reload.
if [ -d /etc/letsencrypt/live/sahamflow.com ]; then
  echo "   certbot TLS config detected, preserving it (skipping cp)."
else
  cp "${APP_DIR}/deploy/nginx-sahamflow.conf" /etc/nginx/sites-available/sahamflow
  ln -sf /etc/nginx/sites-available/sahamflow /etc/nginx/sites-enabled/sahamflow
fi
nginx -t && systemctl reload nginx

echo ""
echo ">> Done. Buka di browser:  http://<IP-VPS>/"
echo ">> Frontend logs:          sudo -u ${APP_USER} pm2 logs sahamflow-web"
