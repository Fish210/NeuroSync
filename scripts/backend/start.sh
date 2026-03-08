#!/usr/bin/env bash
# Start the NeuroSync FastAPI backend.
# Run AFTER: bash scripts/backend/stream.sh (Muse stream must be active)
#
# Usage: bash scripts/backend/start.sh [--reload]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/src/backend"

HOST="${NEUROSYNC_HOST:-127.0.0.1}"
PORT="${NEUROSYNC_PORT:-8000}"
RELOAD_FLAG=""
if [[ "$1" == "--reload" ]]; then
  RELOAD_FLAG="--reload"
fi

echo "=== Starting NeuroSync Backend ==="
echo "  URL:  http://$HOST:$PORT"
echo "  WS:   ws://$HOST:$PORT/ws/session/{session_id}"
echo "  Docs: http://$HOST:$PORT/docs"
echo ""

cd "$BACKEND_DIR"

# Add backend to PYTHONPATH so imports work (eeg.*, session.*, api.*)
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"

uv run uvicorn api.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --log-level info \
  $RELOAD_FLAG
