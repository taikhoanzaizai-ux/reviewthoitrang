#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
LOG="/tmp/auto-review-codespaces.log"
PIDFILE="/tmp/auto-review-codespaces.pid"

if [ -f "$PIDFILE" ]; then
  OLD_PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
fi

# Also clear any stale process bound to the editor port.
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
  sleep 1
fi

nohup env PORT="$PORT" python run_codespaces.py >"$LOG" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PIDFILE"
sleep 1

if kill -0 "$NEW_PID" 2>/dev/null; then
  echo "Auto Review Video started on port $PORT (PID $NEW_PID)"
  echo "Log: $LOG"
else
  echo "Backend khong khoi dong duoc. Log:"
  cat "$LOG" || true
  exit 1
fi
