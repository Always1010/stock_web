#!/bin/bash
set -e

echo "============================================"
echo " Stock Simulation Web App - Installation"
echo "============================================"

# ── System packages ──────────────────────────────────────────
echo ""
echo "[1/5] Installing system packages..."

# MySQL
if ! dpkg -l | grep -q mysql-server; then
    sudo apt update
    sudo apt install -y mysql-server
fi

# Node.js 22 LTS
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt install -y nodejs
fi

# Python venv support
sudo apt install -y python3.12-venv python3-pip

echo "[1/5] System packages OK"

# ── MySQL setup ──────────────────────────────────────────────
echo ""
echo "[2/5] Setting up MySQL database..."
sudo mysql -e "CREATE DATABASE IF NOT EXISTS stock_web CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null || true
sudo mysql -e "CREATE USER IF NOT EXISTS 'stock'@'localhost' IDENTIFIED BY 'stock123';" 2>/dev/null || true
sudo mysql -e "GRANT ALL PRIVILEGES ON stock_web.* TO 'stock'@'localhost'; FLUSH PRIVILEGES;" 2>/dev/null || true
echo "[2/5] MySQL database ready"

# ── Python backend ───────────────────────────────────────────
echo ""
echo "[3/5] Installing Python backend dependencies..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run Alembic migrations
alembic upgrade head || alembic revision --autogenerate -m "init" && alembic upgrade head
deactivate
cd ..
echo "[3/5] Backend dependencies installed"

# ── Frontend ─────────────────────────────────────────────────
echo ""
echo "[4/5] Installing frontend dependencies..."
cd frontend
npm install
npm run build
cd ..
echo "[4/5] Frontend built"

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "[5/5] Installation complete!"
echo ""
echo "To run in development:"
echo "  Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "To run in production:"
echo "  gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app"
echo ""
