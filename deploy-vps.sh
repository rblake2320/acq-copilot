#!/bin/bash
# Deploy acq-copilot-v2 to VPS — run from D:\acq-copilot-v2 in git bash
set -e

VPS="root@76.13.118.222"
DEPLOY_DIR="/opt/acq-copilot-v2"
API_PORT=8001
WEB_PORT=3001

echo "==> [1/6] Syncing code to VPS..."
rsync -az --delete \
  --exclude='.git' --exclude='node_modules' --exclude='.next' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  --exclude='test-results' --exclude='*.log' \
  /d/acq-copilot-v2/ $VPS:$DEPLOY_DIR/

echo "==> [2/6] Uploading .env with all API keys..."
# Patch DATABASE_URL and REDIS_URL for VPS, keep all API keys
sed \
  -e 's|DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://acqcopilot:devpassword@localhost:5432/acqcopilot_v2|' \
  -e 's|REDIS_URL=.*|REDIS_URL=redis://localhost:6379/1|' \
  -e 's|ENVIRONMENT=.*|ENVIRONMENT=prod|' \
  -e 's|CORS_ORIGINS=.*|CORS_ORIGINS=["https://76.13.118.222","http://76.13.118.222","http://localhost:3001"]|' \
  /d/acq-copilot-v2/apps/api/.env | ssh $VPS "cat > $DEPLOY_DIR/apps/api/.env"

echo "==> [3/6] Creating DB and setting up Python venv..."
ssh $VPS "
  psql -U postgres -c \"CREATE DATABASE acqcopilot_v2 OWNER acqcopilot;\" 2>/dev/null || echo '  DB already exists'
  cd $DEPLOY_DIR/apps/api
  python3 -m venv .venv 2>/dev/null || true
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  .venv/bin/alembic upgrade head 2>&1 | tail -5
"

echo "==> [4/6] Building Next.js frontend..."
ssh $VPS "
  cd $DEPLOY_DIR/apps/web
  npm ci --silent 2>&1 | tail -3
  npm run build 2>&1 | tail -10
"

echo "==> [5/6] Starting services with pm2..."
ssh $VPS "
  # Stop old web (v1), start new API and web
  pm2 stop acq-web 2>/dev/null || true
  pm2 delete acq-web 2>/dev/null || true
  pm2 delete acq-api-v2 2>/dev/null || true

  # Start API
  pm2 start '$DEPLOY_DIR/apps/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $API_PORT --workers 2' \
    --name acq-api-v2 --cwd $DEPLOY_DIR/apps/api

  # Start web (Next.js production)
  cd $DEPLOY_DIR/apps/web
  PORT=$WEB_PORT pm2 start npm --name acq-web -- start

  pm2 save
"

echo "==> [6/6] Verifying health..."
sleep 4
ssh $VPS "
  curl -s http://localhost:$API_PORT/health | python3 -m json.tool
" && echo "  API: healthy" || echo "  API: check logs"

echo ""
echo "================================================================"
echo " LIVE at: https://76.13.118.222"
echo " Check:   ssh $VPS 'pm2 logs --lines 20'"
echo "================================================================"
