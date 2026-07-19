#!/usr/bin/env bash
set -euo pipefail

HOST="${MQTT_HOST:-localhost}"
PORT="${MQTT_PORT:-1883}"
COUNT="${MQTT_COUNT:-0}"

if ! command -v mosquitto_sub >/dev/null 2>&1; then
  echo "ERROR: required command not found: mosquitto_sub" >&2
  exit 1
fi

echo "Subscribing to SISEN 6LoWPAN telemetry topics on $HOST:$PORT..."
echo "Topics:"
echo "  building/temperature"
echo "  building/humidity"
echo "  building/occupancy"
echo "  building/air_quality"
echo "  industrial/6lowpan/temp-01/telemetry"
echo

if [ "$COUNT" -gt 0 ]; then
  exec mosquitto_sub -h "$HOST" -p "$PORT" \
    -t "building/temperature" \
    -t "building/humidity" \
    -t "building/occupancy" \
    -t "building/air_quality" \
    -t "industrial/6lowpan/temp-01/telemetry" \
    -v \
    -C "$COUNT"
fi

exec mosquitto_sub -h "$HOST" -p "$PORT" \
  -t "building/temperature" \
  -t "building/humidity" \
  -t "building/occupancy" \
  -t "building/air_quality" \
  -t "industrial/6lowpan/temp-01/telemetry" \
  -v

