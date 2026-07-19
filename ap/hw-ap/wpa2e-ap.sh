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
SSID="${SSID:-SISEN-WPA2E-AP}"
FILES_DIR="${FILES_DIR:-$SCRIPT_DIR/files}"
RADIUS_ADDR="${RADIUS_ADDR:-127.0.0.1}"
RADIUS_PORT="${RADIUS_PORT:-1812}"
RADIUS_SECRET_FILE="${RADIUS_SECRET_FILE:-$FILES_DIR/radius.secret}"

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
country_code=$REGDOM
ieee80211d=1
auth_algs=1
wmm_enabled=1
ieee80211n=1
ieee8021x=1
wpa=2
wpa_key_mgmt=WPA-EAP
rsn_pairwise=CCMP
eapol_version=2
eap_server=0
auth_server_addr=$RADIUS_ADDR
auth_server_port=$RADIUS_PORT
auth_server_shared_secret=$RADIUS_SECRET
nas_identifier=$SSID
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
  /usr/sbin/hostapd -B -P "$RUNTIME_DIR/hostapd.pid" -f "$RUNTIME_DIR/hostapd_wpa2e.log" "$RUNTIME_DIR/hostapd.conf"

  info "Starting dnsmasq..."
  pkill dnsmasq 2>/dev/null || true
  dnsmasq --conf-file="$RUNTIME_DIR/dnsmasq.conf" \
          --pid-file="$RUNTIME_DIR/dnsmasq.pid" \
          --log-facility="$RUNTIME_DIR/dnsmasq_wpa2e.log"

  ok "AP Enabled: SSID ${CYAN}${SSID}${RESET} on ${CYAN}${INTERFACE}${RESET} (${CYAN}${AP_IP_BASE}${RESET})"
  info "RADIUS: $RADIUS_ADDR:$RADIUS_PORT (secret from $RADIUS_SECRET_FILE)"
}

tail_clean() {
  info "Showing EAP + DHCP events..."
  stdbuf -oL -eL tail -F "$RUNTIME_DIR/hostapd_wpa2e.log" "$RUNTIME_DIR/dnsmasq_wpa2e.log" | \
  awk -v GREEN="$GREEN" -v CYAN="$CYAN" -v YELLOW="$YELLOW" -v RESET="$RESET" '
    /CTRL-EVENT-EAP-STARTED/ { ts=strftime("%H:%M:%S"); mac=$NF; printf("[%s] %sEAP-START%s %s\n", ts, YELLOW, RESET, mac); fflush(); }
    /CTRL-EVENT-EAP-SUCCESS/ { ts=strftime("%H:%M:%S"); mac=$NF; printf("[%s] %sEAP-SUCCESS%s %s\n", ts, GREEN, RESET, mac); fflush(); }
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
  [ -f "$RADIUS_SECRET_FILE" ] || { err "Missing $RADIUS_SECRET_FILE"; exit 2; }
  RADIUS_SECRET="$(tr -d '[:space:]' < "$RADIUS_SECRET_FILE")"
  [ -n "$RADIUS_SECRET" ] || { err "Empty RADIUS secret"; exit 2; }
  if ! systemctl is-active --quiet freeradius; then
    info "Starting FreeRADIUS service..."
    systemctl start freeradius || { err "Failed to start FreeRADIUS"; exit 2; }
    sleep 2
  fi
  prepare_ap_interface
  write_hostapd_conf
  write_dnsmasq_conf
  HW_AP_STARTED=1
  start_services
  tail_clean
}

main "$@"
