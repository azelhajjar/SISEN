#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_ROOT"

echo "=== SISEN setup ==="

if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    echo "ERROR: do not run setup.sh with sudo."
    echo "Run it as your normal lab user so .venv is not owned by root:"
    echo "  ./setup.sh"
    exit 1
fi

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        echo "WARNING: .env.example was not found; skipping .env creation."
    fi
fi

if [ ! -d ".venv" ]; then
    echo "Creating .venv..."
    python3 -m venv .venv
else
    echo ".venv already exists"
fi

VENV_PYTHON=".venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ERROR: could not find $VENV_PYTHON after virtual environment setup."
    exit 1
fi

echo "Installing Python dependencies..."
"$VENV_PYTHON" -m pip install -r requirements.txt

echo "Verifying Python dependencies..."
"$VENV_PYTHON" -c "import flask, paho.mqtt, yaml; print('Python dependencies OK')"

echo
echo "SISEN setup complete."
echo
echo "Next:"
echo "  python3 launch_sisen.py"
