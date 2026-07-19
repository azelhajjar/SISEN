#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root, for example: sudo ./cleanup_poc.sh" >&2
  exit 1
fi

stop_poc_mosquitto() {
  if [ -s /tmp/6lowpan-mosquitto.pid ]; then
    echo "+ kill $(cat /tmp/6lowpan-mosquitto.pid)"
    kill "$(cat /tmp/6lowpan-mosquitto.pid)" >/dev/null 2>&1 || true
  fi

  if command -v pgrep >/dev/null 2>&1; then
    for pid in $(pgrep -f "mosquitto.*6lowpan-poc.conf" || true); do
      [ "$pid" != "$$" ] || continue
      echo "+ kill stale PoC mosquitto $pid"
      kill "$pid" >/dev/null 2>&1 || true
    done
  fi

  sleep 0.5

  if command -v pgrep >/dev/null 2>&1; then
    for pid in $(pgrep -f "mosquitto.*6lowpan-poc.conf" || true); do
      [ "$pid" != "$$" ] || continue
      echo "+ kill -9 stale PoC mosquitto $pid"
      kill -9 "$pid" >/dev/null 2>&1 || true
    done
  fi
}

for ns in node1 node2 border; do
  echo "+ ip netns del $ns"
  ip netns del "$ns" >/dev/null 2>&1 || true
done

echo "+ ip link del host-uplink"
ip link del host-uplink >/dev/null 2>&1 || true

echo "+ ip link del border-ip"
ip link del border-ip >/dev/null 2>&1 || true

echo "+ ip link del host-mqtt"
ip link del host-mqtt >/dev/null 2>&1 || true

echo "+ rm -f /tmp/6lowpan-gateway-receiver.log"
rm -f /tmp/6lowpan-gateway-receiver.log

echo "+ rm -f /tmp/6lowpan-mqtt-json-subscriber.log /tmp/6lowpan-mqtt-*-subscriber.log"
rm -f /tmp/6lowpan-mqtt-json-subscriber.log /tmp/6lowpan-mqtt-*-subscriber.log

if [ -d /tmp/6lowpan-dashboard-relay ]; then
  for pid_file in /tmp/6lowpan-dashboard-relay/*.pid; do
    [ -e "$pid_file" ] || continue
    echo "+ kill $(cat "$pid_file")"
    kill "$(cat "$pid_file")" >/dev/null 2>&1 || true
  done
fi

echo "+ rm -rf /tmp/6lowpan-dashboard-relay"
rm -rf /tmp/6lowpan-dashboard-relay

stop_poc_mosquitto

echo "+ rm -f /etc/mosquitto/6lowpan-poc.conf /tmp/6lowpan-mosquitto.log /tmp/6lowpan-mosquitto.pid"
rm -f /etc/mosquitto/6lowpan-poc.conf /tmp/6lowpan-mosquitto.log /tmp/6lowpan-mosquitto.pid

echo "+ modprobe -r mac802154_hwsim"
modprobe -r mac802154_hwsim >/dev/null 2>&1 || true

echo "Cleanup complete."
