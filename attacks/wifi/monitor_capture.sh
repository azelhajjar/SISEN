#!/usr/bin/env bash
set -euo pipefail

BASE_IFACE="${BASE_IFACE:-wlan0}"
MON_IFACE="${MON_IFACE:-mon-sisen}"
CHANNEL="${CHANNEL:-6}"

usage() {
  cat <<EOF
Usage:
  sudo ./attacks/wifi/monitor_capture.sh start [base-iface]
  sudo ./attacks/wifi/monitor_capture.sh stop
  ./attacks/wifi/monitor_capture.sh status

Environment overrides:
  BASE_IFACE=wlan0
  MON_IFACE=mon-sisen
  CHANNEL=6

Run this manually from a separate terminal after the SISEN scenario AP exists.
Use tcpdump separately to capture on mon-sisen.
EOF
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run this action with sudo." >&2
    exit 1
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1" >&2
    exit 1
  fi
}

start_capture() {
  require_root
  require_command iw
  require_command ip

  base_iface="${1:-$BASE_IFACE}"
  mon_iface="$MON_IFACE"

  if ! iw dev "$mon_iface" info >/dev/null 2>&1; then
    echo "+ iw dev $base_iface interface add $mon_iface type monitor"
    iw dev "$base_iface" interface add "$mon_iface" type monitor
  fi

  echo "+ ip link set $mon_iface up"
  ip link set "$mon_iface" up

  echo "+ iw dev $mon_iface set channel $CHANNEL"
  iw dev "$mon_iface" set channel "$CHANNEL" || true

  echo
  echo "Monitor interface ready: $mon_iface"
  echo "Capture example:"
  echo "  sudo tcpdump -i $mon_iface -n -vv -s 0 -Z \"\$USER\" -w captures/${mon_iface}.pcap"
  echo "Stop monitor mode with:"
  echo "  sudo ./attacks/wifi/monitor_capture.sh stop"
  echo
}

stop_monitor() {
  require_root
  require_command iw
  require_command ip

  mon_iface="$MON_IFACE"

  if iw dev "$mon_iface" info >/dev/null 2>&1; then
    echo "+ ip link set $mon_iface down"
    ip link set "$mon_iface" down || true
    echo "+ iw dev $mon_iface del"
    iw dev "$mon_iface" del
  else
    echo "$mon_iface is not present."
  fi
}

status_monitor() {
  require_command iw
  iw dev
}

case "${1:-}" in
  start)
    shift
    start_capture "$@"
    ;;
  stop)
    shift
    stop_monitor "$@"
    ;;
  status)
    status_monitor
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
