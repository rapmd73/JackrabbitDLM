#!/bin/bash
# install.sh - Jackrabbit DLM Installation Script
#
# Sets up directories, installs dependencies, and prepares the environment.
#
# Usage:
#   ./scripts/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${JACKRABBIT_BASE:-$(dirname "$SCRIPT_DIR")}"

echo "=== Jackrabbit DLM Installer ==="
echo "Base directory: $BASE_DIR"

# Check Python
PYTHON=$(command -v python3 || true)
if [ -z "$PYTHON" ]; then
    echo "ERROR: python3 not found. Please install Python 3.x"
    exit 1
fi

echo "Python: $PYTHON ($($PYTHON --version 2>&1))"

# Create virtualenv if not present
VENV_DIR="$BASE_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtualenv..."
    $PYTHON -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r "$BASE_DIR/requirements.txt"

# Create data directories
echo "Creating directories..."
mkdir -p "$BASE_DIR/data/config"
mkdir -p "$BASE_DIR/data/disk"
mkdir -p "$BASE_DIR/data/logs"
mkdir -p "$BASE_DIR/data/quarantine"

# Export environment
echo ""
echo "=== Installation Complete ==="
echo ""
echo "Add to your shell profile (~/.bashrc, ~/.zshrc):"
echo "  export JACKRABBIT_BASE=\"$BASE_DIR\""
echo ""
echo "Start the server:"
echo "  cd $BASE_DIR && source .venv/bin/activate"
echo "  python3 -m jackrabbitdlm.server.daemon"
echo ""
echo "Or use the launch script:"
echo "  $BASE_DIR/scripts/launch_dlm.sh"
echo ""
