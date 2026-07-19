#!/usr/bin/env bash
set -euo pipefail

RULE_COMMENT="sisen-milestone9-drop"
PORT="${SISEN_6LOWPAN_PORT:-9999}"
NAMESPACE="${SISEN_6LOWPAN_DROP_NS:-border}"

usage() {
  cat >&2 <<EOF
Usage: sudo bash attacks/drop_telemetry.sh <start|stop|status>

Temporarily drops forwarded UDP telemetry to port $PORT in the $NAMESPACE namespace.
Use "stop" to remove the rule.
EOF
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run as root, for example: sudo bash attacks/drop_telemetry.sh start" >&2
    exit 1
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1" >&2
    exit 1
  fi
}

rule_exists() {
  ip netns exec "$NAMESPACE" ip6tables -C FORWARD -p udp --dport "$PORT" -m comment --comment "$RULE_COMMENT" -j DROP >/dev/null 2>&1
}

start_drop() {
  if rule_exists; then
    echo "Telemetry drop rule already active in namespace $NAMESPACE."
    return
  fi

  ip netns exec "$NAMESPACE" ip6tables -I FORWARD 1 -p udp --dport "$PORT" -m comment --comment "$RULE_COMMENT" -j DROP
  echo "Started telemetry drop in namespace $NAMESPACE for UDP destination port $PORT."
}

stop_drop() {
  while rule_exists; do
    ip netns exec "$NAMESPACE" ip6tables -D FORWARD -p udp --dport "$PORT" -m comment --comment "$RULE_COMMENT" -j DROP
  done
  echo "Stopped telemetry drop in namespace $NAMESPACE."
}

status_drop() {
  if rule_exists; then
    echo "Telemetry drop rule is active in namespace $NAMESPACE."
  else
    echo "Telemetry drop rule is not active in namespace $NAMESPACE."
  fi
}

action="${1:-}"
if [ -z "$action" ]; then
  usage
  exit 1
fi

require_root
require_command ip
require_command ip6tables

if ! ip netns list | grep -Eq "(^| )$NAMESPACE($| )"; then
  echo "ERROR: namespace $NAMESPACE does not exist. Start the PoC topology first." >&2
  exit 1
fi

case "$action" in
  start)
    start_drop
    ;;
  stop)
    stop_drop
    ;;
  status)
    status_drop
    ;;
  *)
    usage
    exit 1
    ;;
esac

