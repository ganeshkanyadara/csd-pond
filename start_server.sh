#!/bin/bash
# Start script to run application and watchdog supervisor in the background
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="/opt/conda/bin/python"

echo "=========================================================="
echo " Starting AI Village Pond Planning API in Background"
echo "=========================================================="

cd "$APP_DIR"

# If uvicorn is not running, start it
if ! pgrep -f "uvicorn main:app" > /dev/null; then
    echo "Starting uvicorn server in background..."
    nohup "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port 3000 >> "$APP_DIR/app.log" 2>&1 </dev/null &
    sleep 2
else
    echo "uvicorn is already running (PID: $(pgrep -f "uvicorn main:app" | head -n1))."
fi

# If supervisor is not running, start supervisor watchdog
SUPERVISOR_PID=""
if [ -f "$APP_DIR/supervisor.pid" ]; then
    SPID=$(cat "$APP_DIR/supervisor.pid" 2>/dev/null)
    if [ -n "$SPID" ] && kill -0 "$SPID" 2>/dev/null; then
        SUPERVISOR_PID="$SPID"
    fi
fi

if [ -z "$SUPERVISOR_PID" ]; then
    echo "Starting watchdog supervisor in background..."
    nohup bash "$APP_DIR/supervisor.sh" >> "$APP_DIR/supervisor.log" 2>&1 </dev/null &
    sleep 1
    SUPERVISOR_PID=$(cat "$APP_DIR/supervisor.pid" 2>/dev/null)
else
    echo "Supervisor is already running (PID: $SUPERVISOR_PID)."
fi

UVICORN_PID=$(pgrep -f "uvicorn main:app" | head -n1)

echo "=========================================================="
echo " Application is running in the background!"
echo " - Uvicorn PID:    $UVICORN_PID"
echo " - Supervisor PID: $SUPERVISOR_PID"
echo " - Local Port:     3000"
echo " - External URL:   http://10.1.75.51:3213"
echo " - Health Check:   http://10.1.75.51:3213/health"
echo " - Swagger Docs:   http://10.1.75.51:3213/docs"
echo " - Logs:           $APP_DIR/app.log"
echo "                   $APP_DIR/supervisor.log"
echo "=========================================================="
