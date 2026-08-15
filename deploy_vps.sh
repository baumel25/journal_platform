#!/usr/bin/env bash
# ============================================================================
# Deploy Journal Platform (Django) on Ubuntu 24.04 VPS
# Run as root on the VPS:  bash deploy_vps.sh
# ============================================================================
set -euo pipefail

# ---- Configuration (edit if needed) ----------------------------------------
DOMAIN1="i-jcsa.com"            # primary domain
DOMAIN2="jcsajournal.com"       # secondary domain
APP_DIR="/opt/journal_platform"
DB_NAME="journal"
DB_USER="journal"
EMAIL_USER="${EMAIL_HOST_USER:-christianyonta73@gmail.com}"
EMAIL_PASS="${EMAIL_HOST_PASSWORD:-}"   # set your Gmail app password here if you have one
SERVER_IP="$(curl -4 -s ifconfig.me || echo '2.24.1.242')"

export DEBIAN_FRONTEND=noninteractive

echo "==> [1/9] Updating system packages..."
apt-get update -y && apt-get upgrade -y

echo "==> [2/9] Installing required packages (PostgreSQL, Python, nginx, git, certbot)..."
apt-get install -y python3 python3-venv python3-pip python3-dev nginx \
  postgresql postgresql-contrib git certbot python3-certbot-nginx \
  libpq-dev build-essential curl

echo "==> [3/9] Creating PostgreSQL database + user..."
systemctl enable --now postgresql
DB_PASS="$(openssl rand -hex 16)"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}'"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
  || sudo -u postgres createdb -O ${DB_USER} ${DB_NAME}

echo "==> [4/9] Cloning application from GitHub..."
if [ ! -d "$APP_DIR" ]; then
  git clone https://github.com/baumel25/journal_platform.git "$APP_DIR"
else
  git -C "$APP_DIR" pull origin main || true
fi
cd "$APP_DIR"

echo "==> [5/9] Creating Python virtual environment + installing dependencies..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "==> [6/9] Writing .env configuration..."
DJANGO_KEY="$(openssl rand -hex 40)"
cat > .env <<EOF
DJANGO_SECRET_KEY=${DJANGO_KEY}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${DOMAIN1},www.${DOMAIN1},${DOMAIN2},www.${DOMAIN2},${SERVER_IP}
BASE_URL=https://www.${DOMAIN1}
DATABASE_URL=postgres://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
EMAIL_HOST_USER=${EMAIL_USER}
EMAIL_HOST_PASSWORD=${EMAIL_PASS}
EOF
chmod 600 .env

echo "==> [7/9] Running migrations + collecting static files..."
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py collectstatic --noinput --clear

echo "==> [8/9] Setting up gunicorn systemd service..."
cat > /etc/systemd/system/journal.service <<EOF
[Unit]
Description=Journal Platform (gunicorn)
After=network.target postgresql.service

[Service]
User=root
Group=root
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn journal_project.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now journal

echo "==> [9/9] Configuring nginx for both domains..."
cat > /etc/nginx/sites-available/journal <<EOF
server {
    listen 80;
    server_name ${DOMAIN1} www.${DOMAIN1} ${DOMAIN2} www.${DOMAIN2};

    client_max_body_size 20M;

    location /static/ {
        alias ${APP_DIR}/staticfiles/;
    }
    location /media/ {
        alias ${APP_DIR}/media/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/journal /etc/nginx/sites-enabled/journal
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable --now nginx && systemctl reload nginx

echo ""
echo "=========================================================="
echo " Deploy complete! App is running via gunicorn + nginx."
echo " Primary:  http://${DOMAIN1}   (SSL not yet enabled)"
echo " Server:   http://${SERVER_IP}"
echo ""
echo " IMPORTANT: save the PostgreSQL password below (it's in ${APP_DIR}/.env):"
echo "   DB_USER=${DB_USER}  DB_PASS=${DB_PASS}"
echo ""
echo " Next: once DNS points here, run:  certbot --nginx -d ${DOMAIN1} -d www.${DOMAIN1} -d ${DOMAIN2} -d www.${DOMAIN2}"
echo "=========================================================="
