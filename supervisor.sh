#!/bin/bash
# High-availability background watchdog supervisor for AI-based Village Pond Planning API
APP_DIR="/home/student/csd-pond"
PYTHON_BIN="/opt/conda/bin/python"

# Ensure single instance of supervisor
PIDFILE="$APP_DIR/supervisor.pid"
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor is already running (PID: $OLD_PID)." >> "$APP_DIR/supervisor.log"
        exit 0
    fi
fi
echo $$ > "$PIDFILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor started with PID $$." >> "$APP_DIR/supervisor.log"

cleanup() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor exiting..." >> "$APP_DIR/supervisor.log"
    rm -f "$PIDFILE"
    exit 0
}
trap cleanup SIGINT SIGTERM

while true; do
    if ! pgrep -f "uvicorn main:app" > /dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor: uvicorn main:app not running. Restarting..." >> "$APP_DIR/supervisor.log"
        (cd "$APP_DIR" && exec "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port 3000 >> "$APP_DIR/app.log" 2>&1 </dev/null) &
        sleep 2
    fi
    sleep 5
done
