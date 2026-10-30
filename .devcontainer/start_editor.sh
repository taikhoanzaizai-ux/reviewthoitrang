#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
LOG="/tmp/auto-review-codespaces.log"
PIDFILE="/tmp/auto-review-codespaces.pid"

if [ -f "$PIDFILE" ]; then
  OLD_PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    exit 0
  fi
fi

nohup env PORT="$PORT" python run_codespaces.py >"$LOG" 2>&1 &
echo $! > "$PIDFILE"
echo "Auto Review Video started on port $PORT"
echo "Log: $LOG"
