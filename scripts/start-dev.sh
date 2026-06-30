#!/usr/bin/env bash
# Start PressureLab dev servers (kills stale processes first)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "  freeing port $port (PIDs: $pids)"
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
}

find_free_port() {
  local start=$1
  local port
  for port in $(seq "$start" $((start + 20))); do
    if ! lsof -ti tcp:"$port" >/dev/null 2>&1; then
      echo "$port"
      return 0
    fi
  done
  return 1
}

echo "Stopping stale processes..."
pkill -9 -f "uvicorn main:app" 2>/dev/null || true
pkill -9 -f "vite --host" 2>/dev/null || true
for port in 8000 5173 5174 5175; do
  kill_port "$port"
done
sleep 2

BACKEND_PORT=$(find_free_port 8000) || { echo "No free backend port found"; exit 1; }
FRONTEND_PORT=$(find_free_port 5173) || { echo "No free frontend port found"; exit 1; }

if [ "$BACKEND_PORT" != "8000" ]; then
  echo "Note: port 8000 blocked — using backend port $BACKEND_PORT"
fi
if [ "$FRONTEND_PORT" != "5173" ]; then
  echo "Note: port 5173 in use — using frontend port $FRONTEND_PORT"
fi

echo "VITE_BACKEND_PORT=$BACKEND_PORT" > "$FRONTEND/.env.local"

echo "Starting backend on http://127.0.0.1:$BACKEND_PORT ..."
cd "$BACKEND"
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!

echo "Starting frontend on http://127.0.0.1:$FRONTEND_PORT ..."
cd "$FRONTEND"
npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort &
FRONTEND_PID=$!

echo "Waiting for backend..."
for i in $(seq 1 30); do
  if curl -sf --max-time 2 "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    echo "Backend OK (attempt $i)"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "Backend failed to start — check logs or run: bash $ROOT/scripts/kill-dev-ports.sh"
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    exit 1
  fi
  sleep 1
done

if curl -sf --max-time 3 "http://127.0.0.1:$FRONTEND_PORT/api/health" >/dev/null 2>&1; then
  echo "Frontend proxy OK"
else
  echo "Frontend proxy not ready yet — wait a few seconds"
fi

echo ""
echo "PressureLab AI running:"
echo "  App:     http://127.0.0.1:$FRONTEND_PORT"
echo "  API:     http://127.0.0.1:$BACKEND_PORT"
echo "  PIDs:    backend=$BACKEND_PID frontend=$FRONTEND_PID"
echo "  Stop:    kill $BACKEND_PID $FRONTEND_PID"
echo "  502 fix: bash $ROOT/scripts/kill-dev-ports.sh && bash $0"

wait
