#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SISEN — Controlled Realistic Infrastructure Scenario Platform
# File: configs/setup-base.sh
#
# Baseline setup for wireless lab environments.
# Supports Debian-based systems including Ubuntu and Kali Linux.
#
# - Installs required packages for AP scripts and wireless tools
# - Leaves hostapd/dnsmasq disabled so they don't conflict with AP scripts
# - Copies .env.example to .env if no .env exists
#
# Usage:
#   sudo bash setup-base.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "[!] Please run as root (use: sudo $0)"
    exit 1
  fi
}

detect_os() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "$ID"
  else
    echo "unknown"
  fi
}

detect_real_user() {
  # Returns the non-root user who invoked sudo, or current user
  echo "${SUDO_USER:-$USER}"
}

detect_home() {
  local real_user
  real_user=$(detect_real_user)
  eval echo "~$real_user"
}

print_section() {
  echo ""
  echo "────────────────────────────────────────"
  echo "  $1"
  echo "────────────────────────────────────────"
}

# ─────────────────────────────────────────
# OS Detection
# ─────────────────────────────────────────

check_os() {
  print_section "Detecting Operating System"
  OS=$(detect_os)
  echo "[i] Detected OS: $OS"

  case "$OS" in
    kali|ubuntu|parrot|debian|linuxmint)
      echo "[✓] Supported Debian-based system detected."
      ;;
    *)
      echo "[!] Unrecognised OS: $OS"
      echo "    This script is designed for Debian-based systems."
      echo "    Proceeding anyway — some packages may not be available."
      ;;
  esac
}

# ─────────────────────────────────────────
# Package Installation
# ─────────────────────────────────────────

apt_install_base() {
  print_section "Installing Base Packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends \
    hostapd \
    dnsmasq \
    mosquitto \
    mosquitto-clients \
    iproute2 \
    iptables \
    iw \
    rfkill \
    net-tools \
    tcpdump \
    wireshark \
    python3 \
    python3-venv \
    python3-pip \
    dos2unix \
    netcat-openbsd \
    ca-certificates \
    curl \
    git
  echo "[✓] Base packages installed."
}

apt_install_wireless_tools() {
  print_section "Installing Wireless Tools"
  export DEBIAN_FRONTEND=noninteractive

  # Core tools available on all supported distros
  PACKAGES="aircrack-ng hcxtools freeradius lighttpd"

  # Tools that may only be available on Kali/Parrot
  OPTIONAL="reaver bettercap hcxdumptool mdk4 wifite"

  apt-get install -y --no-install-recommends $PACKAGES || true

  for pkg in $OPTIONAL; do
    if apt-cache show "$pkg" &>/dev/null; then
      apt-get install -y --no-install-recommends "$pkg" || true
      echo "[✓] Optional package installed: $pkg"
    else
      echo "[i] Optional package not available on this distro, skipping: $pkg"
    fi
  done

  echo "[✓] Wireless tools installed."
}

apt_install_python_tools() {
  print_section "Installing Python Tools"
  apt-get install -y \
    python3-scapy \
    python3-pycryptodome \
    python3-venv \
    virtualenv || true
  echo "[✓] Python tools installed."
}

# ─────────────────────────────────────────
# Service Configuration
# ─────────────────────────────────────────

service_sanity() {
  print_section "Disabling Auto-Start Services"
  # hostapd and dnsmasq are managed by AP scripts, not systemd
  systemctl disable hostapd 2>/dev/null || true
  systemctl disable dnsmasq 2>/dev/null || true
  systemctl stop hostapd 2>/dev/null || true
  systemctl stop dnsmasq 2>/dev/null || true
  echo "[✓] hostapd and dnsmasq disabled from auto-start."
}

# ─────────────────────────────────────────
# Environment Setup
# ─────────────────────────────────────────

setup_env() {
  print_section "Setting Up Configuration"
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  ENV_FILE="$REPO_ROOT/.env"

  if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$REPO_ROOT/.env.example" ]; then
      echo "[i] No .env found. Copying from .env.example..."
      cp "$REPO_ROOT/.env.example" "$ENV_FILE"
      echo "[✓] .env created at $ENV_FILE"
      echo "[i] Edit .env to set your interface name, SSID prefix, and passwords."
    else
      echo "[i] No .env.example found. Skipping .env creation."
    fi
  else
    echo "[i] .env already exists at $ENV_FILE — not overwriting."
  fi
}

make_scripts_executable() {
  print_section "Making Shell Scripts Executable"
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  find "$REPO_ROOT" -type f -name "*.sh" -exec chmod +x {} +
  echo "[✓] Shell scripts are executable."
}

# ─────────────────────────────────────────
# Wireless Interface Info
# ─────────────────────────────────────────

show_interface_info() {
  print_section "Wireless Interface"
  if iw dev 2>/dev/null | grep -q Interface; then
    IFACE=$(iw dev | awk '/Interface/{print $2}' | head -n1)
    echo "[✓] Wireless interface detected: $IFACE"
    echo "[i] Set INTERFACE=$IFACE in your .env file."
  else
    echo "[!] No wireless interface detected."
    echo "    Connect a wireless adaptor and recheck with: iw dev"
  fi
}

# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

main() {
  require_root
  check_os

  apt_install_base
  apt_install_wireless_tools
  apt_install_python_tools
  service_sanity
  setup_env
  make_scripts_executable
  show_interface_info

  print_section "Setup Complete"
  echo ""
  echo "  Next:"
  echo "    ./setup.sh"
}

main "$@"
