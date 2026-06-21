#!/bin/bash
# LaunchDLM - Auto-restart wrapper for Jackrabbit DLM Server
#
# Runs the server in an infinite loop, restarting on crash after 60s.
# Supports Python virtualenv activation.
#
# Usage:
#   ./scripts/launch_dlm.sh
#
# Crontab (uncomment to auto-start on boot):
#   @reboot ( /path/to/launch_dlm.sh & ) > /dev/null 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${JACKRABBIT_BASE:-$(dirname "$SCRIPT_DIR")}"

# Activate virtualenv if present
if [ -f "$BASE_DIR/.venv/bin/activate" ]; then
    source "$BASE_DIR/.venv/bin/activate"
fi

LOGS_DIR="$BASE_DIR/logs"
mkdir -p "$LOGS_DIR"

cd "$BASE_DIR"

echo "Starting Jackrabbit DLM Server (base: $BASE_DIR)"

while true; do
    python3 -m jackrabbitdlm.server.daemon > "$LOGS_DIR/stderr.log" 2>&1
    echo "$(date): Server exited, restarting in 60s..."
    sleep 60
done
