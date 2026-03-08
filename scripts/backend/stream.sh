#!/usr/bin/env bash
# Start muselsl Muse headband LSL stream.
# Must be running BEFORE starting the FastAPI backend.
#
# Usage: bash scripts/backend/stream.sh [--address XX:XX:XX:XX:XX:XX]
#
# If --address is not provided, muselsl will scan for available Muse devices.
# First-time setup: run 'muselsl list' to find your headband's MAC address.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/src/backend"

ADDRESS=""
if [[ "$1" == "--address" && -n "$2" ]]; then
  ADDRESS="--address $2"
fi

echo "=== Starting Muse LSL Stream ==="
echo ""
echo "Prerequisites:"
echo "  - Muse headband is powered on and in pairing mode"
echo "  - Bluetooth is enabled on this machine"
echo "  - BLE power saving is disabled (Device Manager > Bluetooth > Power Mgmt)"
echo ""

if [ -z "$ADDRESS" ]; then
  echo "No address specified — scanning for Muse devices..."
  echo "Run 'bash scripts/backend/stream.sh --address XX:XX' to specify device"
  echo ""
fi

cd "$BACKEND_DIR"
uv run muselsl stream $ADDRESS

# If stream exits unexpectedly:
echo ""
echo "⚠ muselsl stream exited. Reconnect the headband and re-run this script."
