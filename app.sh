#!/bin/bash
# ── Stock Simulation Web App — Unified Management Script ──────
# Usage: ./app.sh <command> [options]
#
# Commands:
#   install              First-time: system pkgs, MySQL, Python venv, frontend build
#   start [dev|prod]     Start services (default: prod)
#   stop                 Stop all services
#   restart [dev|prod]   Stop then start
#   rebuild              Rebuild frontend dist/ only (prod frontend changes)
#   reload               Gracefully reload backend workers (prod backend changes)
#   status               Show running processes and ports
#   logs [backend|frontend]  Tail service logs
#
# When to redeploy after code changes:
#   ┌──────────┬──────────────────┬─────────────────────────────┐
#   │  Mode    │ Frontend change  │ Backend change              │
#   ├──────────┼──────────────────┼─────────────────────────────┤
#   │  dev     │ Auto HMR, no-op  │ Auto --reload, no-op        │
#   │  prod    │ ./app.sh rebuild │ ./app.sh reload             │
#   └──────────┴──────────────────┴─────────────────────────────┘
#
#   rebuild: npm run build → dist/ updated; Nginx serves static files, no restart needed.
#   reload:  sends SIGHUP to gunicorn master → workers restart gracefully with zero downtime.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${2:-prod}"   # dev or prod, used by start/restart

# ── Color helpers ─────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${RED}[WARN]${NC}  $*"; }
step()  { echo -e "${CYAN}[STEP]${NC} $*"; }

# ── install ───────────────────────────────────────────────────
cmd_install() {
    echo "============================================"
    echo " Stock Simulation Web App - Installation"
    echo "============================================"

    # [1/5] System packages
    echo ""; step "[1/5] Installing system packages..."

    if ! dpkg -l | grep -q mysql-server; then
        sudo apt update
        sudo apt install -y mysql-server
    fi

    if ! command -v node &>/dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
        sudo apt install -y nodejs
    fi

    sudo apt install -y python3.12-venv python3-pip
    info "System packages OK"

    # [2/5] MySQL
    echo ""; step "[2/5] Setting up MySQL database..."
    sudo mysql -e "CREATE DATABASE IF NOT EXISTS stock_web CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null || true
    sudo mysql -e "CREATE USER IF NOT EXISTS 'stock'@'localhost' IDENTIFIED BY 'stock123';" 2>/dev/null || true
    sudo mysql -e "GRANT ALL PRIVILEGES ON stock_web.* TO 'stock'@'localhost'; FLUSH PRIVILEGES;" 2>/dev/null || true
    info "MySQL database ready"

    # [3/5] Backend
    echo ""; step "[3/5] Installing Python backend dependencies..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    alembic upgrade head || (alembic revision --autogenerate -m "init" && alembic upgrade head)
    deactivate
    cd ..
    info "Backend dependencies installed"

    # [4/5] Frontend
    echo ""; step "[4/5] Installing frontend dependencies..."
    cd frontend
    npm install
    npm run build
    cd ..
    info "Frontend built"

    # [5/5] Done
    echo ""; step "[5/5] Installation complete!"
    echo ""
    echo "  Next steps:"
    echo "    ./app.sh start              # production mode"
    echo "    ./app.sh start dev          # development mode"
    echo "    ./app.sh status             # check running services"
    echo ""
}

# ── start ─────────────────────────────────────────────────────
cmd_start() {
    echo "=== Starting Stock Web App ($MODE mode) ==="

    # Backend
    step "[1/2] Starting backend..."
    cd backend
    source venv/bin/activate

    if [ "$MODE" = "dev" ]; then
        nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
            > /tmp/stock-web-backend.log 2>&1 &
        echo "  Backend PID: $!"
        echo "  API: http://localhost:8000/api/docs"
    else
        nohup gunicorn -w 4 -k uvicorn.workers.UvicornWorker \
            -b 127.0.0.1:8000 app.main:app \
            > /tmp/stock-web-backend.log 2>&1 &
        echo "  Backend PID: $!"
        # Save master PID for graceful reload
        echo $! > /tmp/stock-web-gunicorn.pid
    fi

    deactivate
    cd ..

    # Frontend
    step "[2/2] Starting frontend..."
    if [ "$MODE" = "dev" ]; then
        cd frontend
        nohup npm run dev > /tmp/stock-web-frontend.log 2>&1 &
        echo "  Frontend PID: $!"
        echo "  Web: http://localhost:5173"
        cd ..
    else
        if [ ! -d frontend/dist ]; then
            info "Building frontend..."
            cd frontend && npm run build && cd ..
        fi
        sudo systemctl reload nginx 2>/dev/null || sudo nginx -s reload 2>/dev/null || true
        echo "  Web: http://localhost"
    fi

    echo ""
    info "Startup complete"
    echo "  Backend log : /tmp/stock-web-backend.log"
    [ "$MODE" = "dev" ] && echo "  Frontend log: /tmp/stock-web-frontend.log"
    echo ""

    # Background watcher for gunicorn PID (prod only)
    if [ "$MODE" != "dev" ]; then
        save_pid
    fi
}

# ── stop ──────────────────────────────────────────────────────
cmd_stop() {
    echo "=== Stopping Stock Web App ==="

    pkill -f "uvicorn app.main" 2>/dev/null && echo "  Stopped uvicorn" || true
    pkill -f "gunicorn.*app.main" 2>/dev/null && echo "  Stopped gunicorn" || true
    pkill -f "vite" 2>/dev/null && echo "  Stopped vite" || true
    rm -f /tmp/stock-web-gunicorn.pid

    echo "=== All stopped ==="
}

# ── restart ───────────────────────────────────────────────────
cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

# ── rebuild (frontend only, for production) ───────────────────
cmd_rebuild() {
    step "Rebuilding frontend..."
    cd frontend
    npm run build
    cd ..
    info "Frontend rebuilt → dist/ updated (Nginx will serve new files)"
}

# ── reload (backend only, graceful, for production) ───────────
cmd_reload() {
    if [ -f /tmp/stock-web-gunicorn.pid ]; then
        local pid=$(cat /tmp/stock-web-gunicorn.pid)
        if kill -0 "$pid" 2>/dev/null; then
            step "Sending SIGHUP to gunicorn master (PID $pid)..."
            kill -HUP "$pid"
            info "Backend workers reloaded gracefully"
        else
            warn "gunicorn PID $pid not running. Start it first: ./app.sh start"
        fi
    else
        warn "No gunicorn PID file found. Start it first: ./app.sh start prod"
    fi
}

# ── status ────────────────────────────────────────────────────
cmd_status() {
    echo "=== Stock Web App Status ==="
    echo ""

    echo "Processes:"
    ps aux | grep -E "uvicorn|gunicorn|vite" | grep -v grep | sed 's/^/  /' || echo "  (none running)"
    echo ""

    echo "Ports:"
    sudo ss -tlnp 2>/dev/null | grep -E ':80 |:8000 |:5173 ' | sed 's/^/  /' || echo "  (none listening)"
    echo ""

    if [ -f /tmp/stock-web-gunicorn.pid ]; then
        local pid=$(cat /tmp/stock-web-gunicorn.pid)
        if kill -0 "$pid" 2>/dev/null; then
            echo "Gunicorn master PID: $pid (running)"
        else
            echo "Gunicorn master PID: $pid (stale)"
        fi
    fi

    echo ""
    echo "Dist: $([ -d frontend/dist ] && echo 'frontend/dist/ exists' || echo 'frontend/dist/ MISSING — run ./app.sh rebuild')"
}

# ── logs ──────────────────────────────────────────────────────
cmd_logs() {
    local svc="${2:-backend}"
    case "$svc" in
        backend)
            tail -f /tmp/stock-web-backend.log ;;
        frontend)
            if [ -f /tmp/stock-web-frontend.log ]; then
                tail -f /tmp/stock-web-frontend.log
            else
                warn "No frontend log file (only created in dev mode)"
            fi
            ;;
        *)
            echo "Usage: ./app.sh logs [backend|frontend]" ;;
    esac
}

# ── Helper ────────────────────────────────────────────────────
save_pid() {
    # Periodically refresh the gunicorn PID in case the process restarts
    sleep 2
    local ppid=$(pgrep -f "gunicorn.*app.main" | head -1)
    [ -n "$ppid" ] && echo "$ppid" > /tmp/stock-web-gunicorn.pid
}

# ── Main dispatch ─────────────────────────────────────────────
case "${1:-}" in
    install)   cmd_install ;;
    start)     cmd_start ;;
    stop)      cmd_stop ;;
    restart)   cmd_restart ;;
    rebuild)   cmd_rebuild ;;
    reload)    cmd_reload ;;
    status)    cmd_status ;;
    logs)      cmd_logs "$@" ;;
    *)
        echo "Usage: ./app.sh {install|start [dev|prod]|stop|restart [dev|prod]|rebuild|reload|status|logs [service]}"
        echo ""
        echo "Quick reference:"
        echo "  ./app.sh install          First-time setup"
        echo "  ./app.sh start [dev|prod] Start services (default: prod)"
        echo "  ./app.sh stop             Stop all services"
        echo "  ./app.sh restart          Stop + start"
        echo "  ./app.sh rebuild          Rebuild frontend (after prod frontend changes)"
        echo "  ./app.sh reload           Graceful backend reload (after prod backend changes)"
        echo "  ./app.sh status           Show running processes & ports"
        echo "  ./app.sh logs [service]   Tail logs (backend/frontend)"
        echo ""
        echo "After code changes:"
        echo "  Dev mode  → nothing (auto-reload)"
        echo "  Prod frontend → ./app.sh rebuild"
        echo "  Prod backend  → ./app.sh reload"
        exit 1
        ;;
esac
