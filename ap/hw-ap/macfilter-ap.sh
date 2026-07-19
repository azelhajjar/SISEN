#!/bin/bash
# Physical hardware AP only. Expected interface: lab-wlan.
# Stop HWSIM separately before using the hardware AP scripts.

set -euo pipefail

RESET=$'\033[0m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
RED=$'\033[0;31m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEARDOWN_SCRIPT="$SCRIPT_DIR/teardown-ap.sh"
# shellcheck source=hw-ap-common.sh
. "$SCRIPT_DIR/hw-ap-common.sh"

INTERFACE="${INTERFACE:-lab-wlan}"
AP_IP="${AP_IP:-192.168.140.1/24}"
AP_IP_BASE="${AP_IP_BASE:-192.168.140.1}"
REGDOM="${REGDOM:-GB}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/hw-ap}"
CHANNEL="${CHANNEL:-6}"
SSID="${SSID:-SISEN-MAC-AP}"
MAC_FILE_DEFAULT="$SCRIPT_DIR/files/allowed_macs.txt"
MAC_FILE="${MAC_FILE:-$MAC_FILE_DEFAULT}"

cleanup_trap() {
  stop_hw_ap_on_signal
}

write_hostapd_conf() {
  cat > "$RUNTIME_DIR/hostapd.conf" <<EOF
interface=$INTERFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$CHANNEL
auth_algs=1
wmm_enabled=0
ignore_broadcast_ssid=0
macaddr_acl=1
accept_mac_file=$MAC_FILE
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2
EOF
}

write_dnsmasq_conf() {
  write_common_dnsmasq_conf
}

start_services() {
  info "Starting hostapd..."
  if ! /usr/sbin/hostapd -B -P "$RUNTIME_DIR/hostapd.pid" -f "$RUNTIME_DIR/hostapd_mac.log" "$RUNTIME_DIR/hostapd.conf"; then
    err "hostapd failed to start for MAC-filter AP."
    if [ -f "$RUNTIME_DIR/hostapd_mac.log" ]; then
      tail -n 20 "$RUNTIME_DIR/hostapd_mac.log" >&2 || true
    fi
    return 1
  fi

  info "Starting dnsmasq..."
  pkill dnsmasq 2>/dev/null || true
  dnsmasq --conf-file="$RUNTIME_DIR/dnsmasq.conf" \
          --pid-file="$RUNTIME_DIR/dnsmasq.pid" \
          --log-facility="$RUNTIME_DIR/dnsmasq_mac.log"

  ok "AP Enabled: SSID ${CYAN}${SSID}${RESET} on ${CYAN}${INTERFACE}${RESET} (${CYAN}${AP_IP_BASE}${RESET})"
  info "MAC allow-list file: $MAC_FILE"
  info "Logs: hostapd=${RUNTIME_DIR}/hostapd_mac.log dnsmasq=${RUNTIME_DIR}/dnsmasq_mac.log"
}

tail_clean() {
  info "Showing connections and DHCP leases (Ctrl-C to stop)..."
  stdbuf -oL -eL tail -F "$RUNTIME_DIR/hostapd_mac.log" "$RUNTIME_DIR/dnsmasq_mac.log" | \
  awk -v GREEN="$GREEN" -v CYAN="$CYAN" -v RESET="$RESET" '
    /AP-STA-CONNECTED/ { mac=$NF; ts=strftime("%H:%M:%S"); printf("[%s] %sCONNECT%s %s\n", ts, GREEN, RESET, mac); fflush(); }
    /DHCPACK/ { ts=strftime("%H:%M:%S"); ip=$5; mac=$6; host=$7; if (host=="") host="-"; printf("[%s] %sDHCP%s %s -> %s %s\n", ts, CYAN, RESET, mac, ip, host); fflush(); }
  '
}

main() {
  require_root
  require_hw_interface
  ensure_networkmanager_unmanaged "$INTERFACE"
  trap cleanup_trap INT TERM
  trap stop_hw_ap_on_exit EXIT
  "$TEARDOWN_SCRIPT" || true
  ensure_runtime_dir
  [ -f "$MAC_FILE" ] || { err "MAC list not found: $MAC_FILE"; exit 2; }
  prepare_ap_interface
  write_hostapd_conf
  write_dnsmasq_conf
  HW_AP_STARTED=1
  start_services
  tail_clean
}

main "$@"
