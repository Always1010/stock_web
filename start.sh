#!/bin/bash
# ── Start Stock Web Application ─────────────────────────────
# Usage: ./start.sh [dev|prod]
#   dev  - Backend on :8000, Frontend dev server on :5173
#   prod - Backend on :8000 via gunicorn, Nginx on :80
# Default: prod

set -e
MODE="${1:-prod}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Stock Web App - Starting ($MODE mode) ==="

# ── Backend ─────────────────────────────────────────────────
echo "[1/2] Starting backend..."
cd backend
source venv/bin/activate

if [ "$MODE" = "dev" ]; then
    # Development: single uvicorn with auto-reload
    nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
        > /tmp/stock-web-backend.log 2>&1 &
    echo "  Backend PID: $!"
    echo "  API: http://localhost:8000/api/docs"
else
    # Production: gunicorn with uvicorn workers
    nohup gunicorn -w 4 -k uvicorn.workers.UvicornWorker \
        -b 127.0.0.1:8000 app.main:app \
        > /tmp/stock-web-backend.log 2>&1 &
    echo "  Backend PID: $!"
fi

deactivate
cd ..

# ── Frontend ────────────────────────────────────────────────
echo "[2/2] Starting frontend..."
if [ "$MODE" = "dev" ]; then
    cd frontend
    nohup npm run dev > /tmp/stock-web-frontend.log 2>&1 &
    echo "  Frontend PID: $!"
    echo "  Web: http://localhost:5173"
    cd ..
else
    # Production: Nginx serves pre-built static files
    if [ ! -d frontend/dist ]; then
        echo "  Building frontend..."
        cd frontend && npm run build && cd ..
    fi
    # Ensure Nginx is running
    sudo systemctl reload nginx 2>/dev/null || sudo nginx -s reload 2>/dev/null || true
    echo "  Web: http://localhost"
fi

echo ""
echo "=== Startup complete ==="
echo "Logs: /tmp/stock-web-backend.log"
echo ""
