#!/bin/bash
# Physical hardware AP teardown only. Expected interface: lab-wlan.
# Stop HWSIM separately before using the hardware AP scripts.

set -euo pipefail

INTERFACE="${INTERFACE:-lab-wlan}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/hw-ap}"

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "[!] Please run as root (use: sudo $0)" >&2
    exit 1
  fi
}

stop_daemon_by_pid() {
  local name="$1"
  local pidfile="$2"
  local pid

  if [ ! -f "$pidfile" ]; then
    return
  fi

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
}

stop_daemons() {
  echo "[i] Stopping hardware AP daemons if running..."
  stop_daemon_by_pid "hostapd" "$RUNTIME_DIR/hostapd.pid"
  stop_daemon_by_pid "dnsmasq" "$RUNTIME_DIR/dnsmasq.pid"

  pgrep -a hostapd 2>/dev/null | grep -F "$RUNTIME_DIR" | awk '{print $1}' | xargs -r kill 2>/dev/null || true
  pgrep -a dnsmasq 2>/dev/null | grep -F "$RUNTIME_DIR" | awk '{print $1}' | xargs -r kill 2>/dev/null || true
  sleep 1
  pgrep -a hostapd 2>/dev/null | grep -F "$RUNTIME_DIR" | awk '{print $1}' | xargs -r kill -9 2>/dev/null || true
  pgrep -a dnsmasq 2>/dev/null | grep -F "$RUNTIME_DIR" | awk '{print $1}' | xargs -r kill -9 2>/dev/null || true
}

reset_interface() {
  if ! ip link show dev "$INTERFACE" >/dev/null 2>&1; then
    echo "[i] Interface $INTERFACE not present; skipping interface reset."
    return
  fi

  echo "[i] Resetting interface $INTERFACE..."
  ip link set "$INTERFACE" down 2>/dev/null || true
  iw dev "$INTERFACE" set type managed 2>/dev/null || true
  ip addr flush dev "$INTERFACE" 2>/dev/null || true
  ip link set "$INTERFACE" up 2>/dev/null || true
}

clean_runtime() {
  echo "[i] Cleaning hardware AP runtime files in $RUNTIME_DIR..."
  rm -f "$RUNTIME_DIR/hostapd.conf" \
        "$RUNTIME_DIR/dnsmasq.conf" \
        "$RUNTIME_DIR/hostapd.pid" \
        "$RUNTIME_DIR/dnsmasq.pid" \
        "$RUNTIME_DIR/hostapd_cli.sock" \
        "$RUNTIME_DIR"/hostapd_*.log \
        "$RUNTIME_DIR"/dnsmasq_*.log \
        "$RUNTIME_DIR"/dhcp.leases \
        "$RUNTIME_DIR"/dnsmasq.leases \
        "$RUNTIME_DIR"/.state_* 2>/dev/null || true
}

main() {
  require_root
  echo "[*] Hardware AP teardown starting..."
  stop_daemons
  reset_interface
  clean_runtime
  echo "[+] Teardown complete. $INTERFACE is still named $INTERFACE and is up in managed mode with no IP."
}

main "$@"
