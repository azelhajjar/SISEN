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
SSID="${SSID:-SISEN-WPA2-AP}"
WPA_PASSPHRASE="${WPA_PASSPHRASE:-password123}"

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
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
wpa_passphrase=$WPA_PASSPHRASE
wmm_enabled=1
ieee80211n=1
ht_capab=[HT20]
ignore_broadcast_ssid=0
ap_isolate=0
disassoc_low_ack=0
skip_inactivity_poll=1
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2
EOF
}

setup_networking() {
  info "Configuring IP forwarding and firewall..."
  echo 1 > /proc/sys/net/ipv4/ip_forward
  iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
  iptables -D FORWARD -i "$INTERFACE" -o eth0 -j ACCEPT 2>/dev/null || true
  iptables -D FORWARD -i eth0 -o "$INTERFACE" -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true
  iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
  iptables -A FORWARD -i "$INTERFACE" -o eth0 -j ACCEPT
  iptables -A FORWARD -i eth0 -o "$INTERFACE" -m state --state ESTABLISHED,RELATED -j ACCEPT
  iptables -I INPUT -i "$INTERFACE" -p udp --dport 67:68 -j ACCEPT
  iptables -I OUTPUT -o "$INTERFACE" -p udp --sport 67:68 -j ACCEPT
}

write_dnsmasq_conf() {
  write_common_dnsmasq_conf "$RUNTIME_DIR/dhcp.leases"
}

start_services() {
  setup_networking
  info "Starting hostapd..."
  /usr/sbin/hostapd -B -P "$RUNTIME_DIR/hostapd.pid" -f "$RUNTIME_DIR/hostapd_wpa2.log" "$RUNTIME_DIR/hostapd.conf"

  info "Starting dnsmasq..."
  pkill dnsmasq 2>/dev/null || true
  sleep 1
  dnsmasq --conf-file="$RUNTIME_DIR/dnsmasq.conf" \
          --pid-file="$RUNTIME_DIR/dnsmasq.pid" \
          --log-facility="$RUNTIME_DIR/dnsmasq_wpa2.log"

  ok "WPA2 AP Enabled: SSID ${CYAN}${SSID}${RESET} on ${CYAN}${INTERFACE}${RESET} (${CYAN}${AP_IP_BASE}${RESET})"
  info "Logs: hostapd=${RUNTIME_DIR}/hostapd_wpa2.log dnsmasq=${RUNTIME_DIR}/dnsmasq_wpa2.log"
  ok "WPA2 Passphrase: ${CYAN}${WPA_PASSPHRASE}${RESET}"
}

tail_clean() {
  info "Showing connections and DHCP leases (Ctrl-C to stop)..."
  stdbuf -oL -eL tail -F "$RUNTIME_DIR/hostapd_wpa2.log" "$RUNTIME_DIR/dnsmasq_wpa2.log" | \
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
  tail_clean
}

main "$@"
