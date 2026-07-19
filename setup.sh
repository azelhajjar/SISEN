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

APT_RUNNER=""
if [ "$(id -u)" -eq 0 ]; then
    APT_RUNNER=""
elif command -v sudo >/dev/null 2>&1; then
    APT_RUNNER="sudo"
else
    echo "ERROR: sudo was not found. Install system packages manually first."
    exit 1
fi

SYSTEM_PACKAGES="
hostapd
dnsmasq
mosquitto
mosquitto-clients
iw
iproute2
net-tools
python3
python3-venv
python3-pip
dos2unix
netcat-openbsd
"

echo "Installing SISEN system dependencies..."
$APT_RUNNER apt-get update
$APT_RUNNER apt-get install -y $SYSTEM_PACKAGES

echo "Making shell scripts executable..."
find . -type f -name "*.sh" -exec chmod +x {} +

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
echo "  source .venv/bin/activate"
echo "  python3 launch_sisen.py"
