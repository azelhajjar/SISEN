#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# SISEN — Controlled Realistic Infrastructure Scenario Platform
# File: ap/files/setup-radius-server.sh
#
# Install and configure FreeRADIUS for WPA2-Enterprise (PEAP/MSCHAPv2).
# Reads credentials and secrets from .env — do not hardcode passwords here.
#
# Usage:
#   sudo ./setup-radius-server.sh [--start]
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FILES_DIR="${FILES_DIR:-$SCRIPT_DIR}"
AP_IP="${AP_IP:-192.168.140.1}"

# Load .env
ENV_FILE="$REPO_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
  . "$ENV_FILE"
else
  echo "[!] No .env file found at $REPO_ROOT/.env"
  echo "    Copy .env.example to .env and configure it before running this script."
  exit 1
fi

# Pull values from .env with fallbacks
RADIUS_SECRET="${RADIUS_SECRET:-changeme-radius-secret}"
RADIUS_USER1_NAME="${RADIUS_USER1_NAME:-user1}"
RADIUS_USER1_PASS="${RADIUS_USER1_PASS:-Password1!}"
RADIUS_USER2_NAME="${RADIUS_USER2_NAME:-user2}"
RADIUS_USER2_PASS="${RADIUS_USER2_PASS:-Password2!}"
RADIUS_USER3_NAME="${RADIUS_USER3_NAME:-user3}"
RADIUS_USER3_PASS="${RADIUS_USER3_PASS:-Password3!}"

CLIENT_TMPL="$FILES_DIR/clients.conf.tmpl"
USERS_TMPL="$FILES_DIR/radius-users"

# Generated files (written to runtime location)
RADIUS_SECRET_FILE="$FILES_DIR/radius.secret"
USERS_FILE_SRC="$FILES_DIR/radius-users"

START_MODE=0
for a in "$@"; do
  case "$a" in
    --start) START_MODE=1 ;;
  esac
done

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

detect_layout() {
  if   [ -d /etc/freeradius/3.0 ]; then echo "/etc/freeradius/3.0"
  elif [ -d /etc/freeradius     ]; then echo "/etc/freeradius"
  else echo "/etc/freeradius/3.0"; fi
}

detect_group() {
  if getent group freerad >/dev/null; then echo freerad
  elif getent group radiusd >/dev/null; then echo radiusd
  else echo freerad; fi
}

ETC="$(detect_layout)"
CLIENTS_D="$ETC/clients.d"
CLIENTS_CONF="$ETC/clients.conf"
MODS_AV="$ETC/mods-available"
MODS_EN="$ETC/mods-enabled"
MODS_CFG="$ETC/mods-config"
SERVICE_NAME="freeradius"
FR_GROUP="$(detect_group)"

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then echo "[!] Run as root: sudo $0" >&2; exit 1; fi
}

# ─────────────────────────────────────────
# Generate credential files from .env
# ─────────────────────────────────────────

generate_radius_secret() {
  echo "[*] Writing radius.secret from .env..."
  echo "$RADIUS_SECRET" > "$RADIUS_SECRET_FILE"
  chmod 640 "$RADIUS_SECRET_FILE"
  echo "[✓] radius.secret written."
}

generate_users_file() {
  echo "[*] Generating RADIUS users file from .env..."
  if [ -f "$USERS_TMPL" ]; then
  sed \
    -e "s/\${RADIUS_USER1_NAME}/$RADIUS_USER1_NAME/g" \
    -e "s/\${RADIUS_USER1_PASS}/$RADIUS_USER1_PASS/g" \
    -e "s/\${RADIUS_USER2_NAME}/$RADIUS_USER2_NAME/g" \
    -e "s/\${RADIUS_USER2_PASS}/$RADIUS_USER2_PASS/g" \
    -e "s/\${RADIUS_USER3_NAME}/$RADIUS_USER3_NAME/g" \
    -e "s/\${RADIUS_USER3_PASS}/$RADIUS_USER3_PASS/g" \
    "$USERS_TMPL" > "$USERS_FILE_SRC"
  else
    cat > "$USERS_FILE_SRC" <<EOF
$RADIUS_USER1_NAME   Cleartext-Password := "$RADIUS_USER1_PASS"
$RADIUS_USER2_NAME   Cleartext-Password := "$RADIUS_USER2_PASS"
$RADIUS_USER3_NAME   Cleartext-Password := "$RADIUS_USER3_PASS"
EOF
  fi
  echo "[✓] RADIUS users file generated."
}

# ─────────────────────────────────────────
# Installation and configuration
# ─────────────────────────────────────────

install_pkgs() {
  echo "[*] Installing packages..."
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y freeradius freeradius-utils iptables-persistent >/dev/null
}

fix_clients_dir_perms() {
  mkdir -p "$CLIENTS_D"
  chown root:"$FR_GROUP" "$CLIENTS_D" || true
  chmod 0750 "$CLIENTS_D" || true
}

write_client_entry() {
  echo "[*] Writing AP client entry..."
  local out="$CLIENTS_D/SISEN-ap.conf"
  if [ -s "$CLIENT_TMPL" ]; then
    sed -e "s#__RADIUS_SECRET__#${RADIUS_SECRET}#g" \
        -e "s#__AP_IP__#${AP_IP}#g" \
        "$CLIENT_TMPL" > "$out"
  else
    cat > "$out" <<EOF
client SISEN-ap {
  ipaddr   = ${AP_IP}
  secret   = ${RADIUS_SECRET}
  nastype  = other
}
EOF
  fi
  chown root:"$FR_GROUP" "$out"; chmod 0640 "$out"
}

ensure_localhost_client() {
  echo "[*] Normalizing localhost client..."
  for f in "$CLIENTS_CONF" "$CLIENTS_D"/*.conf; do
    [ -f "$f" ] || continue
    cp -a "$f" "$f.bak.$(date +%s)" || true
    perl -0777 -pe 's/\n?client\s+[^{]*\{\s*[^}]*ipaddr\s*=\s*127\.0\.0\.1[^}]*\}\s*//sg' -i "$f"
  done
  cat > "$CLIENTS_D/localhost.conf" <<EOF
client localhost {
  ipaddr = 127.0.0.1
  secret = ${RADIUS_SECRET}
  nastype = other
}
EOF
  chown root:"$FR_GROUP" "$CLIENTS_D/localhost.conf"; chmod 0640 "$CLIENTS_D/localhost.conf"
}

ensure_clients_include() {
  echo "[*] Rewriting clients.conf with explicit includes..."
  mkdir -p "$CLIENTS_D"
  {
    echo "# Auto-generated by setup-radius-server.sh"
    for f in "$CLIENTS_D"/*.conf; do
      [ -f "$f" ] || continue
      echo "\$INCLUDE clients.d/$(basename "$f")"
    done
  } > "$CLIENTS_CONF"
  chown root:"$FR_GROUP" "$CLIENTS_CONF"
  chmod 0640 "$CLIENTS_CONF"
}

enable_site_inner_tunnel() {
  echo "[*] Ensuring inner-tunnel site enabled..."
  if [ -d "$ETC/sites-available" ] && [ -d "$ETC/sites-enabled" ] && [ -e "$ETC/sites-available/inner-tunnel" ]; then
    [ -e "$ETC/sites-enabled/inner-tunnel" ] || ln -s "$ETC/sites-available/inner-tunnel" "$ETC/sites-enabled/inner-tunnel"
  fi
}

enable_modules() {
  echo "[*] Enabling eap, mschap, files modules..."
  [ -e "$MODS_EN/eap"    ] || [ ! -e "$MODS_AV/eap"    ] || ln -s "$MODS_AV/eap"    "$MODS_EN/eap"
  [ -e "$MODS_EN/mschap" ] || [ ! -e "$MODS_AV/mschap" ] || ln -s "$MODS_AV/mschap" "$MODS_EN/mschap"
  [ -e "$MODS_EN/files"  ] || [ ! -e "$MODS_AV/files"  ] || ln -s "$MODS_AV/files"  "$MODS_EN/files"
  if [ -f "$MODS_AV/eap" ]; then
    if grep -Eq '^[[:space:]]*default_eap_type[[:space:]]*=' "$MODS_AV/eap"; then
      sed -ri 's|^[[:space:]]*default_eap_type[[:space:]]*=.*|        default_eap_type = peap|' "$MODS_AV/eap" || true
    fi
  fi
}

install_users() {
  echo "[*] Installing users file..."
  cp -a "$USERS_FILE_SRC" "$ETC/users"
  chown root:"$FR_GROUP" "$ETC/users"; chmod 0640 "$ETC/users"
}

fix_permissions() {
  if [ -d "$MODS_CFG/files" ]; then
    chown -R root:"$FR_GROUP" "$MODS_CFG/files" || true
    chmod 0750 "$MODS_CFG/files" || true
    [ -f "$MODS_CFG/files/authorize" ] && chmod 0640 "$MODS_CFG/files/authorize" || true
  fi
}

check_config() {
  echo "[*] Validating freeradius config..."
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  freeradius -XC || { echo "[!] freeradius -XC failed"; exit 3; }
}

restart_service() {
  if [ "$START_MODE" -eq 1 ]; then
    echo "[*] Starting and enabling $SERVICE_NAME..."
    systemctl restart "$SERVICE_NAME"
    systemctl enable "$SERVICE_NAME" || true
    systemctl status --no-pager "$SERVICE_NAME" || true
  else
    echo "[i] Service not started. Use --start to enable after a clean config check."
  fi
}

enable_icmp_persistent() {
  iptables -C INPUT -p icmp --icmp-type echo-request -j ACCEPT 2>/dev/null || \
    iptables -I INPUT 1 -p icmp --icmp-type echo-request -j ACCEPT
  iptables-save > /etc/iptables/rules.v4 || true
  command -v netfilter-persistent >/dev/null && netfilter-persistent save || true
}

summary() {
  echo "[✓] FreeRADIUS configured."
  echo "    ETC:       $ETC"
  echo "    Clients.d: $CLIENTS_D"
  echo "    Users:     $ETC/users"
  echo "    Users set: $RADIUS_USER1_NAME, $RADIUS_USER2_NAME, $RADIUS_USER3_NAME"
  echo "    (Credentials loaded from .env)"
}

main() {
  require_root
  generate_radius_secret
  generate_users_file
  install_pkgs
  fix_clients_dir_perms
  write_client_entry
  ensure_localhost_client
  ensure_clients_include
  enable_site_inner_tunnel
  enable_modules
  install_users
  fix_permissions
  check_config
  restart_service
  enable_icmp_persistent
  summary
}

main "$@"
