#!/bin/bash
# Status check for background application
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Background Service Status ==="
if pgrep -f "uvicorn main:app" > /dev/null; then
    echo "[ONLINE]  Uvicorn PID: $(pgrep -f "uvicorn main:app" | tr '\n' ' ')"
else
    echo "[OFFLINE] Uvicorn is NOT running"
fi

SUPERVISOR_RUNNING=0
if [ -f "$APP_DIR/supervisor.pid" ]; then
    SPID=$(cat "$APP_DIR/supervisor.pid" 2>/dev/null)
    if [ -n "$SPID" ] && kill -0 "$SPID" 2>/dev/null; then
        echo "[ONLINE]  Supervisor PID: $SPID"
        SUPERVISOR_RUNNING=1
    fi
fi
if [ $SUPERVISOR_RUNNING -eq 0 ]; then
    echo "[OFFLINE] Supervisor is NOT running"
fi

echo ""
echo "=== Port 3000 Listener ==="
ss -tlpn | grep 3000 || echo "Port 3000 is not active"

echo ""
echo "=== Health Check ==="
curl -s -m 3 http://localhost:3000/health || echo "Health check failed"
echo ""
