#!/usr/bin/env bash
# Start the NeuroSync mock server for frontend development.
# Frontend team: run this instead of the real backend.
#
# Usage: bash scripts/backend/mock.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Starting NeuroSync Mock Server ==="
echo "  REST: http://localhost:8001"
echo "  WS:   ws://localhost:8001/ws/session/demo"
echo ""
echo "Frontend: set NEXT_PUBLIC_BACKEND_URL=http://localhost:8001"
echo ""

cd "$REPO_ROOT"
uv run --project src/backend uvicorn examples.mock_server:app \
  --host 127.0.0.1 \
  --port 8001 \
  --reload \
  --log-level info
