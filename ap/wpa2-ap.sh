#!/bin/bash
# SISEN - Controlled Realistic Infrastructure Scenario Platform
# File: ap/wpa2-ap.sh
# WPA2-PSK WiFi Access Point
# Extra files: None required
# Tailing: Client association + DHCP lease events (MAC/IP)

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
if [ ! -f "$ENV_FILE" ]; then
  ENV_EXAMPLE="$REPO_ROOT/.env.example"
  [ -f "$ENV_EXAMPLE" ] && . "$ENV_EXAMPLE" && \
    echo "[i] No .env found — using .env.example defaults. Copy .env.example to .env to customise."
fi

INTERFACE="${INTERFACE:-wlan0}"
AP_IP="${AP_IP:-192.168.140.1/24}"
AP_IP_BASE="${AP_IP_BASE:-192.168.140.1}"
REGDOM="${REGDOM:-GB}"
RUNTIME_DIR="${RUNTIME_DIR:-/tmp/SISEN}"
AP_MODE_STATE_FILE="${AP_MODE_STATE_FILE:-/tmp/sisen-ap-mode}"
COURSE_DIR="${COURSE_DIR:-$REPO_ROOT}"
SSID_PREFIX="${SSID_PREFIX:-LAB}"
SSID="${SSID:-${SSID_PREFIX}-WPA2-AP}"
CHANNEL="${CHANNEL:-6}"
WPA_PASSPHRASE="${WPA_PASSPHRASE:-changeme123}"

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    err "Please run as root (sudo $0)"
    exit 1
  fi
}

cleanup_trap() {
  info "CTRL-C received: tearing down AP..."
  "$COURSE_DIR/ap/teardown-ap.sh" || true
  exit 130
}

ensure_dirs() {
  mkdir -p "$RUNTIME_DIR"
}

write_ap_mode_state() {
  printf "ap-wpa2\n" > "$AP_MODE_STATE_FILE"
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

docheckbefore() {
  info "Setting regulatory domain: $REGDOM"
  iw reg set "$REGDOM" || true

  info "Resetting interface state: $INTERFACE"
  ip link set "$INTERFACE" down 2>/dev/null || true

  info "Setting fixed MAC address for consistent BSSID"
  ip link set dev "$INTERFACE" address 02:11:22:33:44:55

  iw dev "$INTERFACE" set type __ap 2>/dev/null || true
  ip addr flush dev "$INTERFACE" 2>/dev/null || true
  ip link set "$INTERFACE" up
  sleep 1

  info "Assigning static IP: $AP_IP"
  ip addr add "$AP_IP" dev "$INTERFACE" 2>/dev/null || true
  setup_networking
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

write_dnsmasq_conf() {
  cat > "$RUNTIME_DIR/dnsmasq.conf" <<EOF
interface=$INTERFACE
bind-interfaces
domain-needed
bogus-priv
dhcp-authoritative
dhcp-range=192.168.140.50,192.168.140.150,255.255.255.0,24h
dhcp-option=3,$AP_IP_BASE
dhcp-option=6,$AP_IP_BASE
dhcp-option=1,255.255.255.0
dhcp-leasefile=$RUNTIME_DIR/dhcp.leases
dhcp-broadcast
log-dhcp
no-resolv
EOF
}

start_services() {
  info "Starting hostapd..."
  /usr/sbin/hostapd -B -P "$RUNTIME_DIR/hostapd.pid" -f "$RUNTIME_DIR/hostapd_wpa2.log" "$RUNTIME_DIR/hostapd.conf"

  info "Starting dnsmasq..."
  pkill dnsmasq 2>/dev/null || true
  sleep 1
  dnsmasq --conf-file="$RUNTIME_DIR/dnsmasq.conf" \
          --pid-file="$RUNTIME_DIR/dnsmasq.pid" \
          --log-facility="$RUNTIME_DIR/dnsmasq_wpa2.log"
  sleep 2

  ok "WPA2 AP Enabled: SSID ${CYAN}${SSID}${RESET} on ${CYAN}${INTERFACE}${RESET} (${CYAN}${AP_IP_BASE}${RESET})"
  ok "Passphrase: ${CYAN}${WPA_PASSPHRASE}${RESET}"
  info "Logs: hostapd=${RUNTIME_DIR}/hostapd_wpa2.log  dnsmasq=${RUNTIME_DIR}/dnsmasq_wpa2.log"
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

tail_clean() {
  info "Showing connections and DHCP leases (Ctrl-C to stop)..."
  stdbuf -oL -eL tail -F "$RUNTIME_DIR/hostapd_wpa2.log" "$RUNTIME_DIR/dnsmasq_wpa2.log" | \
  awk -v GREEN="$GREEN" -v CYAN="$CYAN" -v YELLOW="$YELLOW" -v RESET="$RESET" '
    /AP-STA-CONNECTED/ {
      mac=$NF; ts=strftime("%H:%M:%S");
      printf("[%s] %sCONNECT%s %s\n", ts, GREEN, RESET, mac); fflush();
    }
    /AP-STA-DISCONNECTED/ {
      mac=$NF; ts=strftime("%H:%M:%S");
      printf("[%s] %sDISCONN%s %s\n", ts, YELLOW, RESET, mac); fflush();
    }
    /DHCPACK/ {
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
  write_ap_mode_state
  tail_clean
}

main "$@"
