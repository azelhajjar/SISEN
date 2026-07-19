#!/bin/bash
# Author: Dr Ayman El hajjar
# File: ap/teardown-ap.sh
# Stop hostapd/dnsmasq started by lab scripts, clear IPs.
# Reset wlan0 to managed, and clean runtime files.
# Extra files: None required
# Tailing: Clients association + DHCP lease events (MAC/IP)

set -euo pipefail

# Load .env if present
ENV_FILE="$(dirname "$0")/.env"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

INTERFACE="${INTERFACE:-wlan0}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/cybok-ap}"
AP_MODE_STATE_FILE="${AP_MODE_STATE_FILE:-/tmp/sisen-ap-mode}"

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "[!] Please run as root (use: sudo $0)"
    exit 1
  fi
}
force_kill_hostapd() {
  echo "[i] Force killing all hostapd processes..."
  pkill -9 hostapd 2>/dev/null || true
  sleep 2
  # Also kill any processes using the interface
  lsof "/dev/wlan0" 2>/dev/null | awk 'NR>1 {print $2}' | xargs -r kill -9 2>/dev/null || true
}
stop_daemon_by_pid() {
  local name="$1"
  local pidfile="$2"
  if [ -f "$pidfile" ]; then
    local pid
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      echo "[i] Stopping $name (pid $pid)..."
      kill "$pid" || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        echo "[i] Sending SIGKILL to $name (pid $pid)..."
        kill -9 "$pid" || true
      fi
    fi
    rm -f "$pidfile"
  fi
}

stop_daemons() {
  echo "[i] Stopping daemons if running..."
  stop_daemon_by_pid "hostapd"   "$RUNTIME_DIR/hostapd.pid"
  stop_daemon_by_pid "dnsmasq"   "$RUNTIME_DIR/dnsmasq.pid"

  # Fallback: kill any instance bound to our runtime config directory
  pgrep -a hostapd 2>/dev/null | grep -q "$RUNTIME_DIR" && pkill -f "$RUNTIME_DIR" || true
  pgrep -a dnsmasq 2>/dev/null | grep -q "$RUNTIME_DIR" && pkill -f "$RUNTIME_DIR" || true
}

reset_interface() {
  echo "[i] Resetting interface $INTERFACE..."
  ip link set "$INTERFACE" down 2>/dev/null || true
  # Return to managed type in case it was set to __ap or monitor
  iw dev "$INTERFACE" set type managed 2>/dev/null || true
  # Flush any IPs and routes
  ip addr flush dev "$INTERFACE" 2>/dev/null || true
  ip link set "$INTERFACE" up 2>/dev/null || true
}

clean_runtime() {
  echo "[i] Cleaning runtime files in $RUNTIME_DIR..."
  rm -f "$RUNTIME_DIR/hostapd.conf" \
        "$RUNTIME_DIR/dnsmasq.conf" \
        "$RUNTIME_DIR/hostapd.pid" \
        "$RUNTIME_DIR/dnsmasq.pid" \
        "$RUNTIME_DIR/hostapd_cli.sock" \
        "$RUNTIME_DIR"/hostapd_*.log \
        "$RUNTIME_DIR"/dnsmasq_*.log \
        "$RUNTIME_DIR"/.state_* \
        "$AP_MODE_STATE_FILE" 2>/dev/null || true
}

main() {
  require_root
  echo "[*] Teardown starting..."
  stop_daemons
  force_kill_hostapd
  reset_interface
  clean_runtime
  echo "[✓] Teardown complete. $INTERFACE is up in managed mode with no IP."
}

main "$@"
