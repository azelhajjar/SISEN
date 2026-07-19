#!/bin/bash
# Physical hardware AP interface preparation. Expected interface: lab-wlan.
# Stop HWSIM separately before using the hardware AP scripts.

set -euo pipefail

RESET=$'\033[0m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'

info() { printf "[${YELLOW}i${RESET}] %s\n" "$*"; }
ok() { printf "[${GREEN}+${RESET}] %s\n" "$*"; }
err() { printf "[${RED}!${RESET}] %s\n" "$*" >&2; }

TARGET_INTERFACE="${TARGET_INTERFACE:-lab-wlan}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hw-ap-common.sh
. "$SCRIPT_DIR/hw-ap-common.sh"

require_root

wireless_interfaces() {
  iw dev | awk '$1 == "Interface" { print $2 }'
}

interface_exists() {
  ip link show dev "$1" >/dev/null 2>&1
}

is_wireless_interface() {
  iw dev "$1" info >/dev/null 2>&1
}

interface_driver() {
  local iface="$1"
  local driver_path="/sys/class/net/$iface/device/driver"
  if [ -e "$driver_path" ]; then
    basename "$(readlink -f "$driver_path")"
  else
    echo "unknown"
  fi
}

is_hwsim_interface() {
  [ "$(interface_driver "$1")" = "mac80211_hwsim" ]
}

validate_source_interface() {
  local iface="$1"
  if ! interface_exists "$iface"; then
    err "Interface '$iface' was not found."
    exit 1
  fi
  if ! is_wireless_interface "$iface"; then
    err "Interface '$iface' is not a wireless interface."
    exit 1
  fi
  if is_hwsim_interface "$iface"; then
    err "Interface '$iface' uses the mac80211_hwsim driver and is not a physical adapter."
    exit 1
  fi
}

physical_wireless_interfaces() {
  local iface
  for iface in $(wireless_interfaces); do
    if ! is_hwsim_interface "$iface"; then
      printf '%s\t%s\n' "$iface" "$(interface_driver "$iface")"
    fi
  done
}

select_source_interface() {
  local explicit_source="${1:-}"
  local count

  if [ -n "$explicit_source" ]; then
    validate_source_interface "$explicit_source"
    printf '%s\n' "$explicit_source"
    return
  fi

  if interface_exists "$TARGET_INTERFACE"; then
    validate_source_interface "$TARGET_INTERFACE"
    info "Interface '$TARGET_INTERFACE' already exists; no rename is required."
    printf '%s\n' "$TARGET_INTERFACE"
    return
  fi

  mapfile -t candidates < <(physical_wireless_interfaces)
  count="${#candidates[@]}"

  if [ "$count" -eq 0 ]; then
    err "No physical wireless interface was found."
    err "Stop HWSIM if it is active, connect the physical adapter, then retry."
    exit 1
  fi

  if [ "$count" -gt 1 ]; then
    err "More than one physical wireless interface was found; not guessing."
    printf '%s\n' "Detected interfaces:" >&2
    printf '  %s\n' "${candidates[@]}" >&2
    err "Specify one explicitly, for example: sudo ./prepare-hw-interface.sh wlan1"
    exit 1
  fi

  printf '%s\n' "${candidates[0]%%$'\t'*}"
}

rename_to_target() {
  local source_iface="$1"

  if [ "$source_iface" = "$TARGET_INTERFACE" ]; then
    ensure_networkmanager_unmanaged "$TARGET_INTERFACE"
    ok "Hardware AP interface is ready: $TARGET_INTERFACE"
    return
  fi

  if interface_exists "$TARGET_INTERFACE"; then
    err "Target interface '$TARGET_INTERFACE' already exists. Refusing to rename '$source_iface'."
    exit 1
  fi

  info "Renaming physical wireless interface '$source_iface' to '$TARGET_INTERFACE'..."
  ip link set "$source_iface" down
  ip link set "$source_iface" name "$TARGET_INTERFACE"
  ip link set "$TARGET_INTERFACE" up

  ensure_networkmanager_unmanaged "$TARGET_INTERFACE"

  if ! interface_exists "$TARGET_INTERFACE"; then
    err "Rename completed command sequence, but '$TARGET_INTERFACE' was not found afterwards."
    exit 1
  fi

  ok "Hardware AP interface is ready: $TARGET_INTERFACE"
}

SOURCE_INTERFACE="$(select_source_interface "${1:-}")"
rename_to_target "$SOURCE_INTERFACE"
