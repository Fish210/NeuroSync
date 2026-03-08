#!/usr/bin/env bash
# NeuroSync Backend Bootstrap
# Sets up the Python environment using uv.
# Run once after cloning the repo.
#
# Usage: bash scripts/backend/bootstrap.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/src/backend"
CONFIG_DIR="$REPO_ROOT/config/backend"

echo "=== NeuroSync Backend Bootstrap ==="
echo "Backend: $BACKEND_DIR"

# 1. Verify uv is installed
if ! command -v uv &> /dev/null; then
  echo "ERROR: 'uv' is not installed."
  echo "Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
echo "✓ uv found: $(uv --version)"

# 2. Create virtual environment and install dependencies
echo ""
echo "Installing Python dependencies..."
cd "$BACKEND_DIR"
uv sync
echo "✓ Dependencies installed"

# 3. Set up config
if [ ! -f "$CONFIG_DIR/.env" ]; then
  cp "$CONFIG_DIR/.env.example" "$CONFIG_DIR/.env"
  echo ""
  echo "✓ Created config/backend/.env from .env.example"
  echo "  → Edit config/backend/.env and add your API keys before starting"
else
  echo "✓ config/backend/.env already exists"
fi

# 4. Verify muselsl is available
echo ""
echo "Checking muselsl..."
if uv run python -c "import muselsl; print('muselsl OK')" 2>/dev/null; then
  echo "✓ muselsl available"
else
  echo "⚠ muselsl not importable — may need OS-level Bluetooth deps"
  echo "  macOS: brew install --HEAD libusb"
  echo "  Windows: ensure Bluetooth drivers are installed"
fi

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit config/backend/.env — add FEATHERLESS_API_KEY and ELEVENLABS_API_KEY"
echo "  2. Run: bash scripts/backend/stream.sh    (start Muse LSL stream)"
echo "  3. Run: bash scripts/backend/start.sh     (start FastAPI backend)"
echo "  4. Open: examples/ws-monitor.html         (browser smoke check)"
