#!/bin/bash
# LockWars - Parallel stress tester launcher
#
# Spawns multiple LockFighter processes to simulate
# high-contention lock fighting scenarios.
#
# Usage:
#   ./scripts/lock_wars.sh <fighters> <count> [chaos|aggressive|locks]
#
# Examples:
#   ./scripts/lock_wars.sh 10 5000           # 10 fighters, 5000 iterations
#   ./scripts/lock_wars.sh 20 1000 chaos     # 20 fighters in chaos mode

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <num_fighters> <count> [chaos|aggressive|locks]"
    exit 1
fi

FIGHTERS=$1
COUNT=$2
shift 2
EXTRA_ARGS="$@"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BASE_DIR"

echo "Launching $FIGHTERS lock fighters (count=$COUNT args=$EXTRA_ARGS)"

N=0
while [ $N -lt $FIGHTERS ]; do
    N=$((N + 1))
    (python3 -m jackrabbitdlm.benchmarks.lock_fighter $COUNT $EXTRA_ARGS &)
done

echo "All $FIGHTERS fighters launched. Waiting..."
wait
echo "LockWars complete."
