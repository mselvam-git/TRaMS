#!/bin/bash
# TRaMS One-Click Startup
# Usage: bash start_trams.sh
# Run this from the investment-dashboard directory

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$PROJ_DIR/backend"
FRONTEND="$PROJ_DIR/frontend"

echo "╔═══════════════════════════════════╗"
echo "║   TRaMS v2 — Starting up          ║"
echo "╚═══════════════════════════════════╝"

# Check Python
python3 --version >/dev/null 2>&1 || { echo "❌ Python3 not found"; exit 1; }

# Install deps if needed
echo "► Checking dependencies..."
cd "$BACKEND"
if [ -d "venv" ]; then
    source venv/bin/activate
else
    python3 -m venv venv && source venv/bin/activate
fi
pip install fastapi uvicorn python-dotenv requests python-multipart -q

# Stop existing
pkill -f uvicorn 2>/dev/null; sleep 1

# Start backend
echo "► Starting backend on :8000..."
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 \
    > /tmp/trams_backend.log 2>&1 &
sleep 3

if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "  ✅ Backend live → http://localhost:8000"
    echo "  📖 API docs    → http://localhost:8000/docs"
else
    echo "  ⚠️  Backend starting... (check /tmp/trams_backend.log)"
fi

# Open frontend
echo "► Opening dashboard..."
open "$FRONTEND/index.html" 2>/dev/null || xdg-open "$FRONTEND/index.html" 2>/dev/null
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║ ✅ TRaMS is running!                                  ║"
echo "║                                                       ║"
echo "║ ⚠️  Add your eToro API keys to backend/.env:          ║"
echo "║    ETORO_PUBLIC_KEY=...                               ║"
echo "║    ETORO_USER_KEY=...                                 ║"
echo "║    ETORO_RADHIKA_PUBLIC_KEY=...                       ║"
echo "║    ETORO_RADHIKA_USER_KEY=...                         ║"
echo "║                                                       ║"
echo "║    Then click Refresh in the dashboard                ║"
echo "╚═══════════════════════════════════════════════════════╝"
