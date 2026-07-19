#!/bin/bash
# Author: Dr Ayman El hajjar
# File: ap/wep-ap.sh
# WEP WiFi Access Point with shared key authentication
# Extra files: None required
# Tailing: Clients association + DHCP lease events (MAC/IP)
# Note: Change SSID and WEP_KEY variables to customize AP name and password

set -euo pipefail

RESET=$'\033[0m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
RED=$'\033[0;31m'

info()    { printf "[${YELLOW}i${RESET}] %s\n" "$*"; }
ok()      { printf "[${GREEN}✓${RESET}] %s\n" "$*"; }
err()     { printf "[${RED}!${RESET}] %s\n" "$*" 1>&2; }

# Dynamic path detection - find the actual repository root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEARDOWN_SCRIPT="$SCRIPT_DIR/teardown-ap.sh"

ENV_FILE="$REPO_ROOT/.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

INTERFACE="${INTERFACE:-lab-wlan}"
AP_IP="${AP_IP:-192.168.140.1/24}"
AP_IP_BASE="${AP_IP_BASE:-192.168.140.1}"
REGDOM="${REGDOM:-GB}"
RUNTIME_DIR="${RUNTIME_DIR:-/home/kali/tmp_ap}"
COURSE_DIR="${COURSE_DIR:-$REPO_ROOT}"
SSID="${SSID:-SISEN-WEP-AP}"
CHANNEL="${CHANNEL:-6}"
WEP_KEY="${WEP_KEY:-C0FFEE1234}"  # 26-hex (104-bit)

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    err "Please run as root (sudo $0)"
    exit 1
  fi
}

cleanup_trap() {
  info "CTRL-C received: tearing down AP..."
  "$TEARDOWN_SCRIPT" || true
  exit 130
}

ensure_dirs() {
  mkdir -p "$RUNTIME_DIR"
}

setup_networking() {
  info "Configuring IP forwarding and firewall..."

  # Enable IP forwarding
  echo 1 > /proc/sys/net/ipv4/ip_forward

  # Clear existing iptables rules for this interface
  iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
  iptables -D FORWARD -i "$INTERFACE" -o eth0 -j ACCEPT 2>/dev/null || true
  iptables -D FORWARD -i eth0 -o "$INTERFACE" -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true

  # Add NAT rules (adjust eth0 to your internet interface if different)
  iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
  iptables -A FORWARD -i "$INTERFACE" -o eth0 -j ACCEPT
  iptables -A FORWARD -i eth0 -o "$INTERFACE" -m state --state ESTABLISHED,RELATED -j ACCEPT

  # Allow DHCP traffic specifically
  iptables -I INPUT -i "$INTERFACE" -p udp --dport 67:68 -j ACCEPT
  iptables -I OUTPUT -o "$INTERFACE" -p udp --sport 67:68 -j ACCEPT
}

verify_services() {
  info "Verifying services..."

  # Check hostapd is running
  if pgrep -f "hostapd.*$RUNTIME_DIR/hostapd.conf" > /dev/null; then
    ok "hostapd is running"
  else
    err "hostapd is not running!"
    return 1
  fi

  # Check dnsmasq is running and bound to interface
  if pgrep -f "dnsmasq.*$RUNTIME_DIR/dnsmasq.conf" > /dev/null; then
    ok "dnsmasq is running"
  else
    err "dnsmasq is not running!"
    return 1
  fi

  # Test DHCP server is listening
  if ss -ulnp | grep -q ":67.*dnsmasq"; then
    ok "DHCP server listening on port 67"
  else
    err "DHCP server not listening!"
  fi

  # Check interface has IP
  if ip addr show "$INTERFACE" | grep -q "$AP_IP_BASE"; then
    ok "Interface $INTERFACE has IP $AP_IP_BASE"
  else
    err "Interface IP assignment failed!"
  fi

  # Additional network debugging
  info "Network debugging info:"
  info "Interface IP: $(ip addr show "$INTERFACE" | grep 'inet ' | awk '{print $2}')"
  info "DHCP listening: $(ss -ulnp | grep ':67' || echo 'Not found')"
  info "IP forwarding: $(cat /proc/sys/net/ipv4/ip_forward)"
}

docheckbefore() {
  info "Setting regulatory domain: $REGDOM"
  iw reg set "$REGDOM" || true

  info "Resetting interface state: $INTERFACE"
  ip link set "$INTERFACE" down 2>/dev/null || true
  iw dev "$INTERFACE" set type managed 2>/dev/null || true
  ip addr flush dev "$INTERFACE" 2>/dev/null || true

  # Set a fixed MAC address BEFORE setting AP mode
  info "Setting fixed MAC address for consistent BSSID"
  ip link set dev "$INTERFACE" address 02:11:22:33:44:55

  ip link set "$INTERFACE" up
  sleep 1

  # Force interface to 2.4GHz band and correct channel
  iw dev "$INTERFACE" set freq 2437 2>/dev/null || true  # Channel 6
  sleep 1

  # Set to AP mode AFTER setting fixed MAC
  ip link set "$INTERFACE" down 2>/dev/null || true
  iw dev "$INTERFACE" set type __ap 2>/dev/null || true

  # Set MAC again after AP mode change to ensure it sticks
  ip link set dev "$INTERFACE" address 02:11:22:33:44:55

  ip link set "$INTERFACE" up
  sleep 1

  info "Assigning static IP: $AP_IP"
  ip addr add "$AP_IP" dev "$INTERFACE" 2>/dev/null || true

  # Setup networking after interface is configured
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
wep_default_key=0
wep_key0=$WEP_KEY
ieee8021x=0
wpa=0
wmm_enabled=0
ignore_broadcast_ssid=0
# Disable MAC randomisation for consistent BSSID
macaddr_acl=0
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
  /usr/sbin/hostapd -B -P "$RUNTIME_DIR/hostapd.pid" -f "$RUNTIME_DIR/hostapd_wep.log" "$RUNTIME_DIR/hostapd.conf"

  info "Starting dnsmasq..."
  pkill dnsmasq 2>/dev/null || true
  sleep 1  # Give time for cleanup

  dnsmasq --conf-file="$RUNTIME_DIR/dnsmasq.conf" \
          --pid-file="$RUNTIME_DIR/dnsmasq.pid" \
          --log-facility="$RUNTIME_DIR/dnsmasq_wep.log"

  sleep 2  # Give services time to start
  verify_services

  ok "AP Enabled: SSID ${CYAN}${SSID}${RESET} on ${CYAN}${INTERFACE}${RESET} (${CYAN}${AP_IP_BASE}${RESET})"
  info "Logs: hostapd=${RUNTIME_DIR}/hostapd_wep.log  dnsmasq=${RUNTIME_DIR}/dnsmasq_wep.log"
  info "DHCP leases: ${RUNTIME_DIR}/dhcp.leases"
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
  info "Troubleshooting tip: If Windows/Linux client connects but no DHCP (Modern operating systems sometimes struggle with WEP.):"
  info "Note: WEP support on modern operating systems is limited and may be unstable. If you dont obtain an IP address, try the following:"
  info "  Windows: ipconfig /release && ipconfig /renew"
  info "  Linux: sudo dhcpcd -r $INTERFACE && sudo dhclient $INTERFACE"

  stdbuf -oL -eL tail -F "$RUNTIME_DIR/hostapd_wep.log" "$RUNTIME_DIR/dnsmasq_wep.log" | \
  awk -v GREEN="$GREEN" -v CYAN="$CYAN" -v YELLOW="$YELLOW" -v RESET="$RESET" '
    /AP-STA-CONNECTED/ {
      mac=$NF; ts=strftime("%H:%M:%S");
      printf("[%s] %sCONNECT%s %s\n", ts, GREEN, RESET, mac); fflush();
    }
    /AP-STA-DISCONNECTED/ {
      mac=$NF; ts=strftime("%H:%M:%S");
      printf("[%s] %sDISCONN%s %s\n", ts, YELLOW, RESET, mac); fflush();
    }
    /DHCPDISCOVER/ {
      ts=strftime("%H:%M:%S");
      mac=$(NF-1);
      printf("[%s] %sDHCP-DISCOVER%s %s\n", ts, CYAN, RESET, mac); fflush();
    }
    /DHCPOFFER/ {
      ts=strftime("%H:%M:%S");
      ip=$5; mac=$6;
      printf("[%s] %sDHCP-OFFER%s %s -> %s\n", ts, CYAN, RESET, mac, ip); fflush();
    }
    /DHCPREQUEST/ {
      ts=strftime("%H:%M:%S");
      mac=$(NF-1);
      printf("[%s] %sDHCP-REQUEST%s %s\n", ts, CYAN, RESET, mac); fflush();
    }
    /DHCPACK/ {
      ts=strftime("%H:%M:%S");
      ip=$5; mac=$6; host=$7; if (host=="") host="-";
      printf("[%s] %sDHCP-ACK%s %s -> %s %s\n", ts, CYAN, RESET, mac, ip, host); fflush();
    }
  '
}

main() {
  require_root
  setup_unmanaged_interface
  trap cleanup_trap INT TERM
  "$TEARDOWN_SCRIPT" || true
  ensure_dirs
  docheckbefore
  write_hostapd_conf
  write_dnsmasq_conf
  start_services
  tail_clean
}

main "$@"
