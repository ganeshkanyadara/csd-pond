#!/bin/bash
# Stop script for background application and supervisor
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping watchdog supervisor..."
pkill -f "supervisor.sh" 2>/dev/null
if [ -f "$APP_DIR/supervisor.pid" ]; then
    kill $(cat "$APP_DIR/supervisor.pid") 2>/dev/null
    rm -f "$APP_DIR/supervisor.pid"
fi

echo "Stopping uvicorn server..."
pkill -9 -f "uvicorn main:app" 2>/dev/null
pkill -9 -f "python.*main:app" 2>/dev/null
sleep 1

echo "Application stopped successfully."
