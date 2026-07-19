#!/bin/bash
# Physical hardware AP helpers. Expected interface: lab-wlan.
# Stop HWSIM separately before using the hardware AP scripts.

info() { printf "[${YELLOW}i${RESET}] %s\n" "$*"; }
ok() { printf "[${GREEN}+${RESET}] %s\n" "$*"; }
err() { printf "[${RED}!${RESET}] %s\n" "$*" >&2; }

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    err "Please run as root (sudo $0)"
    exit 1
  fi
}

require_hw_interface() {
  if ! ip link show dev "$INTERFACE" >/dev/null 2>&1; then
    err "Physical wireless interface '$INTERFACE' was not found."
    err "Stop HWSIM if it is active, connect the physical adapter, then run:"
    err "sudo ./prepare-hw-interface.sh"
    exit 1
  fi

  if ! iw dev "$INTERFACE" info >/dev/null 2>&1; then
    err "Interface '$INTERFACE' exists but is not reported as a wireless interface by iw."
    err "Check the physical adapter, then run: sudo ./prepare-hw-interface.sh"
    exit 1
  fi
}

ensure_runtime_dir() {
  mkdir -p "$RUNTIME_DIR"
}

ensure_networkmanager_unmanaged() {
  local iface="$1"
  local config_file="/etc/NetworkManager/conf.d/99-unmanaged-devices.conf"
  local config_dir
  config_dir="$(dirname "$config_file")"
  local changed=0
  local tmp_file

  mkdir -p "$config_dir"

  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<EOF
[keyfile]
unmanaged-devices=interface-name:$iface
EOF
    changed=1
  elif grep -Eq "(^|[;,[:space:]])interface-name:$iface([;,[:space:]]|$)" "$config_file"; then
    info "NetworkManager already configured to ignore $iface"
  elif grep -q '^unmanaged-devices=' "$config_file"; then
    tmp_file="$(mktemp)"
    awk -v entry="interface-name:$iface" '
      BEGIN { done=0 }
      /^unmanaged-devices=/ && done == 0 {
        print $0 ";" entry
        done=1
        next
      }
      { print }
    ' "$config_file" > "$tmp_file"
    cat "$tmp_file" > "$config_file"
    rm -f "$tmp_file"
    changed=1
  elif grep -q '^\[keyfile\]' "$config_file"; then
    printf '\nunmanaged-devices=interface-name:%s\n' "$iface" >> "$config_file"
    changed=1
  else
    cat >> "$config_file" <<EOF

[keyfile]
unmanaged-devices=interface-name:$iface
EOF
    changed=1
  fi

  if [ "$changed" -eq 1 ]; then
    info "Configuring NetworkManager to ignore $iface..."
    systemctl restart NetworkManager
    sleep 2
    if ! ip link show dev "$iface" >/dev/null 2>&1; then
      err "NetworkManager was restarted, but '$iface' is no longer present."
      exit 1
    fi
    ok "NetworkManager configured to ignore $iface"
  fi
}

prepare_ap_interface() {
  info "Setting regulatory domain: $REGDOM"
  iw reg set "$REGDOM" || true

  info "Resetting interface state: $INTERFACE"
  ip link set "$INTERFACE" down 2>/dev/null || true
  ip link set dev "$INTERFACE" address 02:11:22:33:44:55
  iw dev "$INTERFACE" set type __ap 2>/dev/null || true
  ip addr flush dev "$INTERFACE" 2>/dev/null || true
  ip link set "$INTERFACE" up
  sleep 1

  info "Assigning static IP: $AP_IP"
  ip addr add "$AP_IP" dev "$INTERFACE" 2>/dev/null || true
}

write_common_dnsmasq_conf() {
  local lease_file="${1:-}"
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
  if [ -n "$lease_file" ]; then
    printf 'dhcp-leasefile=%s\n' "$lease_file" >> "$RUNTIME_DIR/dnsmasq.conf"
  fi
}

stop_hw_ap_on_signal() {
  info "CTRL-C received: tearing down AP..."
  exit 130
}

stop_hw_ap_on_exit() {
  local status="$?"
  trap - EXIT INT TERM
  if [ "${HW_AP_STARTED:-0}" -eq 1 ]; then
    "$TEARDOWN_SCRIPT" || true
  fi
  exit "$status"
}
