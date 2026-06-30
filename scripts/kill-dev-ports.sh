#!/usr/bin/env bash
# Free PressureLab dev ports (run in your Terminal if API returns 502)
set -euo pipefail

PORTS=(8000 5173 5174 5175)

echo "Stopping PressureLab dev processes..."
pkill -9 -f "uvicorn main:app" 2>/dev/null || true
pkill -9 -f "vite --host" 2>/dev/null || true

for port in "${PORTS[@]}"; do
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "  port $port → kill $pids"
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
done

sleep 2

if lsof -ti tcp:8000 >/dev/null 2>&1; then
  echo ""
  echo "Port 8000 still blocked. Try:"
  echo "  kill -9 \$(lsof -ti tcp:8000)"
  echo "  ps -p \$(lsof -ti tcp:8000) -o pid,ppid,stat,command"
  exit 1
fi

echo "Ports clear. Start with: bash scripts/start-dev.sh"
