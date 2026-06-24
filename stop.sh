#!/bin/bash
# ── Stop Stock Web Application ──────────────────────────────

echo "=== Stopping Stock Web App ==="

# Kill backend processes
pkill -f "uvicorn app.main" 2>/dev/null && echo "  Stopped uvicorn" || true
pkill -f "gunicorn.*app.main" 2>/dev/null && echo "  Stopped gunicorn" || true

# Kill frontend dev server
pkill -f "vite" 2>/dev/null && echo "  Stopped vite" || true

echo "=== All stopped ==="
