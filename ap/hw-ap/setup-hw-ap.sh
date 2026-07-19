#!/bin/bash
# Install system dependencies for the manual hardware AP tools.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BASE_PACKAGES=(
  hostapd
  dnsmasq
  iw
  iproute2
  iptables
  iptables-persistent
  netfilter-persistent
  tcpdump
  wpasupplicant
  python3
)

ENTERPRISE_PACKAGES=(
  freeradius
  freeradius-utils
)

ROGUE_AP_PACKAGES=(
  dsniff
)

usage() {
  cat <<EOF
Usage:
  sudo ./setup-hw-ap.sh [--skip-radius] [--packages-only]

Installs system packages used by the manual hardware AP scripts.

Options:
  --skip-radius    Install packages but do not configure/start FreeRADIUS.
  --packages-only  Install packages only. Same as --skip-radius.
EOF
}

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "ERROR: run with sudo." >&2
    exit 1
  fi
}

install_packages() {
  export DEBIAN_FRONTEND=noninteractive

  echo "Updating package index..."
  apt-get update

  echo "Installing hardware AP packages..."
  apt-get install -y \
    "${BASE_PACKAGES[@]}" \
    "${ENTERPRISE_PACKAGES[@]}" \
    "${ROGUE_AP_PACKAGES[@]}"
}

make_scripts_executable() {
  echo "Making hardware AP scripts executable..."
  find "$SCRIPT_DIR" -type f -name "*.sh" -exec chmod +x {} +
}

configure_radius() {
  echo "Configuring FreeRADIUS for SISEN WPA2-Enterprise AP..."
  "$SCRIPT_DIR/files/setup-radius-server.sh" --start
}

main() {
  local configure_enterprise=1

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --skip-radius|--packages-only)
        configure_enterprise=0
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "ERROR: unknown option: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done

  require_root
  install_packages
  make_scripts_executable

  if [ "$configure_enterprise" -eq 1 ]; then
    configure_radius
  else
    echo "Skipping FreeRADIUS configuration."
  fi

  cat <<EOF

Hardware AP setup complete.

Next:
  sudo ./prepare-hw-interface.sh <wireless-interface>
  sudo ./open-ap.sh

For WPA2-Enterprise:
  sudo ./wpa2e-ap.sh
EOF
}

main "$@"
