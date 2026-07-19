#!/usr/bin/env bash
set -euo pipefail

PAN_ID="0xbeef"
PAGE="0"
CHANNEL="26"
PREFIX="fd00:6:1::"
MQTT_UPLINK_PREFIX="fd00:6:2::"
IP_FACING_PREFIX="fd00:6:3::"
SENSOR_PORT="9999"
READING_COUNT="4"
MQTT_PORT="1884"
DASHBOARD_MQTT_PORT="1883"
MQTT_TOPIC="industrial/6lowpan/temp-01/telemetry"
TEMPERATURE_TOPIC="building/temperature"
HUMIDITY_TOPIC="building/humidity"
OCCUPANCY_TOPIC="building/occupancy"
AIR_QUALITY_TOPIC="building/air_quality"
MQTT_HOST_ADDR="${MQTT_UPLINK_PREFIX}1"
GATEWAY_LOG="/tmp/6lowpan-gateway-receiver.log"
MQTT_JSON_SUB_LOG="/tmp/6lowpan-mqtt-json-subscriber.log"
MQTT_TEMPERATURE_SUB_LOG="/tmp/6lowpan-mqtt-temperature-subscriber.log"
MQTT_HUMIDITY_SUB_LOG="/tmp/6lowpan-mqtt-humidity-subscriber.log"
MQTT_OCCUPANCY_SUB_LOG="/tmp/6lowpan-mqtt-occupancy-subscriber.log"
MQTT_AIR_QUALITY_SUB_LOG="/tmp/6lowpan-mqtt-air-quality-subscriber.log"
MQTT_RELAY_DIR="/tmp/6lowpan-dashboard-relay"
MQTT_BROKER_LOG="/tmp/6lowpan-mosquitto.log"
MQTT_BROKER_CONF="/etc/mosquitto/6lowpan-poc.conf"
MQTT_BROKER_PID="/tmp/6lowpan-mosquitto.pid"
DASHBOARD_WAIT_SECONDS="${DASHBOARD_WAIT_SECONDS:-0}"
dashboard_relay_enabled=0
ATTACK_MODE=""
INTERACTIVE_MODE=0
BORDER_LOWPAN_ADDR="${PREFIX}ff"
BORDER_IP_ADDR="${IP_FACING_PREFIX}1"
GATEWAY_ADDR="${IP_FACING_PREFIX}2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  echo "Usage: sudo ./run_poc.sh [--interactive|--pause-before-traffic] [--attack spoof|replay|extreme|missing]" >&2
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --attack)
        if [ "$#" -lt 2 ]; then
          usage
          exit 1
        fi
        ATTACK_MODE="$2"
        shift 2
        ;;
      --interactive|--pause-before-traffic)
        INTERACTIVE_MODE=1
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        usage
        exit 1
        ;;
    esac
  done

  case "$ATTACK_MODE" in
    ""|spoof|replay|extreme|missing)
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run as root, for example: sudo ./run_poc.sh" >&2
    exit 1
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1" >&2
    exit 1
  fi
}

run() {
  echo
  echo "+ $*"
  "$@"
}

run_in() {
  ns="$1"
  shift
  run ip netns exec "$ns" "$@"
}

stop_poc_mosquitto() {
  if [ -s "$MQTT_BROKER_PID" ]; then
    kill "$(cat "$MQTT_BROKER_PID")" >/dev/null 2>&1 || true
  fi

  if command -v pgrep >/dev/null 2>&1; then
    for pid in $(pgrep -f "mosquitto.*6lowpan-poc.conf" || true); do
      [ "$pid" != "$$" ] || continue
      kill "$pid" >/dev/null 2>&1 || true
    done
  fi

  sleep 0.5

  if command -v pgrep >/dev/null 2>&1; then
    for pid in $(pgrep -f "mosquitto.*6lowpan-poc.conf" || true); do
      [ "$pid" != "$$" ] || continue
      kill -9 "$pid" >/dev/null 2>&1 || true
    done
  fi
}

cleanup_existing() {
  for ns in node1 node2 border; do
    ip netns del "$ns" >/dev/null 2>&1 || true
  done

  stop_poc_mosquitto
  ip link del host-uplink >/dev/null 2>&1 || true
  ip link del border-ip >/dev/null 2>&1 || true
  ip link del host-mqtt >/dev/null 2>&1 || true
  rm -f "$GATEWAY_LOG"
  rm -f "$MQTT_JSON_SUB_LOG"
  rm -f "$MQTT_TEMPERATURE_SUB_LOG"
  rm -f "$MQTT_HUMIDITY_SUB_LOG"
  rm -f "$MQTT_OCCUPANCY_SUB_LOG"
  rm -f "$MQTT_AIR_QUALITY_SUB_LOG"
  rm -rf "$MQTT_RELAY_DIR"
}

configure_lowpan_node() {
  ns="$1"
  phy="$2"
  addr="$3"

  run ip netns add "$ns"
  run iwpan phy "$phy" set netns name "$ns"

  wpan_dev="$(ip netns exec "$ns" iwpan dev | awk '/Interface/ { print $2; exit }')"
  wpan_phy="$(ip netns exec "$ns" iwpan phy | awk '/^wpan_phy/ { print $2; exit }')"

  if [ -z "$wpan_dev" ]; then
    echo "ERROR: no IEEE 802.15.4 interface found in namespace $ns" >&2
    exit 1
  fi

  if [ -z "$wpan_phy" ]; then
    echo "ERROR: no IEEE 802.15.4 PHY found in namespace $ns" >&2
    exit 1
  fi

  run_in "$ns" ip link set "$wpan_dev" down
  run_in "$ns" iwpan dev "$wpan_dev" set pan_id "$PAN_ID"
  run_in "$ns" iwpan phy "$wpan_phy" set channel "$PAGE" "$CHANNEL"
  run_in "$ns" ip link add link "$wpan_dev" name lowpan0 type lowpan
  run_in "$ns" ip link set "$wpan_dev" up
  run_in "$ns" ip link set lowpan0 up
  run_in "$ns" sysctl -w "net.ipv6.conf.lowpan0.accept_dad=0"
  run_in "$ns" ip -6 addr add "$addr/64" dev lowpan0
}

configure_mqtt_uplink() {
  run ip link add host-mqtt type veth peer name node2-mqtt
  run ip link set node2-mqtt netns node2
  run sysctl -w "net.ipv6.conf.host-mqtt.accept_dad=0"
  run ip -6 addr add "${MQTT_UPLINK_PREFIX}1/64" dev host-mqtt
  run ip link set host-mqtt up
  run_in node2 sysctl -w "net.ipv6.conf.node2-mqtt.accept_dad=0"
  run_in node2 ip -6 addr add "${MQTT_UPLINK_PREFIX}2/64" dev node2-mqtt
  run_in node2 ip link set node2-mqtt up
}

configure_border_gateway() {
  run ip netns add node2
  run ip link add border-ip type veth peer name node2-border
  run ip link set border-ip netns border
  run ip link set node2-border netns node2

  run_in border sysctl -w "net.ipv6.conf.all.forwarding=1"
  run_in border sysctl -w "net.ipv6.conf.default.forwarding=1"
  run_in border sysctl -w "net.ipv6.conf.lowpan0.forwarding=1"
  run_in border sysctl -w "net.ipv6.conf.border-ip.forwarding=1"
  run_in border sysctl -w "net.ipv6.conf.border-ip.accept_dad=0"
  run_in border ip -6 addr add "$BORDER_IP_ADDR/64" dev border-ip
  run_in border ip link set border-ip up

  run_in node2 sysctl -w "net.ipv6.conf.node2-border.accept_dad=0"
  run_in node2 ip -6 addr add "$GATEWAY_ADDR/64" dev node2-border
  run_in node2 ip link set node2-border up
  run_in node2 ip -6 route add "$PREFIX/64" via "$BORDER_IP_ADDR" dev node2-border

  run_in node1 ip -6 route add "$IP_FACING_PREFIX/64" via "$BORDER_LOWPAN_ADDR" dev lowpan0
}

start_mqtt_broker() {
  cat >"$MQTT_BROKER_CONF" <<EOF
listener $MQTT_PORT $MQTT_HOST_ADDR
allow_anonymous true
EOF
  chmod 0644 "$MQTT_BROKER_CONF"

  echo
  echo "+ mosquitto -c $MQTT_BROKER_CONF > $MQTT_BROKER_LOG 2>&1 &"
  mosquitto -c "$MQTT_BROKER_CONF" >"$MQTT_BROKER_LOG" 2>&1 &
  echo "$!" >"$MQTT_BROKER_PID"
  sleep 1

  if ! kill -0 "$(cat "$MQTT_BROKER_PID")" >/dev/null 2>&1; then
    echo "ERROR: Mosquitto failed to stay running on $MQTT_HOST_ADDR:$MQTT_PORT" >&2
    echo "Mosquitto output:" >&2
    cat "$MQTT_BROKER_LOG" >&2
    exit 1
  fi
}

start_dashboard_relay() {
  topic="$1"
  name="$2"
  count="$3"
  relay_timeout="60"
  if [ "$INTERACTIVE_MODE" -eq 1 ]; then
    relay_timeout="3600"
  fi
  mkdir -p "$MQTT_RELAY_DIR"
  log_path="$MQTT_RELAY_DIR/$name.log"
  pid_path="$MQTT_RELAY_DIR/$name.pid"

  echo "+ relay $count message(s) for $topic from $MQTT_HOST_ADDR:$MQTT_PORT to localhost:$DASHBOARD_MQTT_PORT"
  (
    timeout "$relay_timeout" mosquitto_sub \
      -h "$MQTT_HOST_ADDR" \
      -p "$MQTT_PORT" \
      -t "$topic" \
      -C "$count" |
      while IFS= read -r payload; do
        mosquitto_pub \
          -h localhost \
          -p "$DASHBOARD_MQTT_PORT" \
          -t "$topic" \
          -m "$payload"
        echo "$payload"
      done
  ) >"$log_path" 2>&1 &
  echo "$!" >"$pid_path"
}

start_dashboard_relays() {
  if ! timeout 2 mosquitto_pub \
    -h localhost \
    -p "$DASHBOARD_MQTT_PORT" \
    -t "sisen/6lowpan/relay-check" \
    -m "ready" >/dev/null 2>&1; then
    echo
    echo "NOTICE: no MQTT broker accepted localhost:$DASHBOARD_MQTT_PORT."
    echo "Dashboard relay disabled. Start the normal SISEN Mosquitto service to test the dashboard."
    return
  fi

  dashboard_relay_enabled=1
  if [ -n "$ATTACK_MODE" ]; then
    start_dashboard_relay "$TEMPERATURE_TOPIC" "temperature" "$(attack_expected_topic_count "$ATTACK_MODE" temperature)"
    start_dashboard_relay "$HUMIDITY_TOPIC" "humidity" "$(attack_expected_topic_count "$ATTACK_MODE" humidity)"
    start_dashboard_relay "$OCCUPANCY_TOPIC" "occupancy" "$(attack_expected_topic_count "$ATTACK_MODE" occupancy)"
    start_dashboard_relay "$AIR_QUALITY_TOPIC" "air-quality" "$(attack_expected_topic_count "$ATTACK_MODE" air_quality)"
  else
    start_dashboard_relay "$TEMPERATURE_TOPIC" "temperature" 1
    start_dashboard_relay "$HUMIDITY_TOPIC" "humidity" 1
    start_dashboard_relay "$OCCUPANCY_TOPIC" "occupancy" 1
    start_dashboard_relay "$AIR_QUALITY_TOPIC" "air-quality" 1
  fi

  if [ "$DASHBOARD_WAIT_SECONDS" -gt 0 ]; then
    echo
    echo "Dashboard test wait: start or refresh web/dashboard.py now."
    echo "+ sleep $DASHBOARD_WAIT_SECONDS"
    sleep "$DASHBOARD_WAIT_SECONDS"
  fi
}

run_sensor_exchange() {
  echo
  echo "Starting multi-sensor UDP JSON exchange with Milestone 5 dashboard-compatible MQTT publishing..."

  echo "+ timeout 15 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $MQTT_TOPIC -C $READING_COUNT"
  timeout 15 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$MQTT_TOPIC" \
    -C "$READING_COUNT" >"$MQTT_JSON_SUB_LOG" 2>&1 &
  mqtt_json_sub_pid="$!"

  echo "+ timeout 15 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $TEMPERATURE_TOPIC -C 1"
  timeout 15 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$TEMPERATURE_TOPIC" \
    -C 1 >"$MQTT_TEMPERATURE_SUB_LOG" 2>&1 &
  mqtt_temperature_sub_pid="$!"

  echo "+ timeout 15 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $HUMIDITY_TOPIC -C 1"
  timeout 15 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$HUMIDITY_TOPIC" \
    -C 1 >"$MQTT_HUMIDITY_SUB_LOG" 2>&1 &
  mqtt_humidity_sub_pid="$!"

  echo "+ timeout 15 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $OCCUPANCY_TOPIC -C 1"
  timeout 15 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$OCCUPANCY_TOPIC" \
    -C 1 >"$MQTT_OCCUPANCY_SUB_LOG" 2>&1 &
  mqtt_occupancy_sub_pid="$!"

  echo "+ timeout 15 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $AIR_QUALITY_TOPIC -C 1"
  timeout 15 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$AIR_QUALITY_TOPIC" \
    -C 1 >"$MQTT_AIR_QUALITY_SUB_LOG" 2>&1 &
  mqtt_air_quality_sub_pid="$!"

  sleep 1

  echo "+ ip netns exec node2 python3 gateway_receiver.py --bind $GATEWAY_ADDR --port $SENSOR_PORT --count $READING_COUNT --mqtt-host $MQTT_HOST_ADDR --mqtt-port $MQTT_PORT --mqtt-topic $MQTT_TOPIC --dashboard-map"
  ip netns exec node2 python3 "$SCRIPT_DIR/gateway_receiver.py" \
    --bind "$GATEWAY_ADDR" \
    --port "$SENSOR_PORT" \
    --count "$READING_COUNT" \
    --mqtt-host "$MQTT_HOST_ADDR" \
    --mqtt-port "$MQTT_PORT" \
    --mqtt-topic "$MQTT_TOPIC" \
    --dashboard-map >"$GATEWAY_LOG" 2>&1 &
  gateway_pid="$!"

  sleep 1

  run_in node1 python3 "$SCRIPT_DIR/sensor_node.py" \
    --source "${PREFIX}1" \
    --dest "$GATEWAY_ADDR" \
    --port "$SENSOR_PORT" \
    --count "$READING_COUNT"

  gateway_status=0
  mqtt_json_sub_status=0
  mqtt_temperature_sub_status=0
  mqtt_humidity_sub_status=0
  mqtt_occupancy_sub_status=0
  mqtt_air_quality_sub_status=0
  wait "$gateway_pid" || gateway_status="$?"
  wait "$mqtt_json_sub_pid" || mqtt_json_sub_status="$?"
  wait "$mqtt_temperature_sub_pid" || mqtt_temperature_sub_status="$?"
  wait "$mqtt_humidity_sub_pid" || mqtt_humidity_sub_status="$?"
  wait "$mqtt_occupancy_sub_pid" || mqtt_occupancy_sub_status="$?"
  wait "$mqtt_air_quality_sub_pid" || mqtt_air_quality_sub_status="$?"

  echo
  echo "Gateway receiver output:"
  cat "$GATEWAY_LOG"

  echo
  echo "MQTT JSON subscriber output:"
  cat "$MQTT_JSON_SUB_LOG"

  echo
  echo "MQTT dashboard-compatible subscriber output:"
  echo "$TEMPERATURE_TOPIC: $(cat "$MQTT_TEMPERATURE_SUB_LOG")"
  echo "$HUMIDITY_TOPIC: $(cat "$MQTT_HUMIDITY_SUB_LOG")"
  echo "$OCCUPANCY_TOPIC: $(cat "$MQTT_OCCUPANCY_SUB_LOG")"
  echo "$AIR_QUALITY_TOPIC: $(cat "$MQTT_AIR_QUALITY_SUB_LOG")"

  if [ "$gateway_status" -ne 0 ]; then
    echo "ERROR: gateway receiver exited with status $gateway_status" >&2
    exit "$gateway_status"
  fi

  if [ "$mqtt_json_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT JSON subscriber exited with status $mqtt_json_sub_status" >&2
    exit "$mqtt_json_sub_status"
  fi

  if [ "$mqtt_temperature_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT temperature subscriber exited with status $mqtt_temperature_sub_status" >&2
    exit "$mqtt_temperature_sub_status"
  fi

  if [ "$mqtt_humidity_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT humidity subscriber exited with status $mqtt_humidity_sub_status" >&2
    exit "$mqtt_humidity_sub_status"
  fi

  if [ "$mqtt_occupancy_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT occupancy subscriber exited with status $mqtt_occupancy_sub_status" >&2
    exit "$mqtt_occupancy_sub_status"
  fi

  if [ "$mqtt_air_quality_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT air-quality subscriber exited with status $mqtt_air_quality_sub_status" >&2
    exit "$mqtt_air_quality_sub_status"
  fi

  json_received_count="$(wc -l <"$MQTT_JSON_SUB_LOG")"
  if [ "$json_received_count" -ne "$READING_COUNT" ]; then
    echo "ERROR: expected $READING_COUNT JSON MQTT messages, received $json_received_count" >&2
    exit 1
  fi

  verify_scalar_log "$MQTT_TEMPERATURE_SUB_LOG" "$TEMPERATURE_TOPIC"
  verify_scalar_log "$MQTT_HUMIDITY_SUB_LOG" "$HUMIDITY_TOPIC"
  verify_scalar_log "$MQTT_OCCUPANCY_SUB_LOG" "$OCCUPANCY_TOPIC"
  verify_scalar_log "$MQTT_AIR_QUALITY_SUB_LOG" "$AIR_QUALITY_TOPIC"

  if [ "$dashboard_relay_enabled" -eq 1 ]; then
    wait_for_relay "temperature" "$TEMPERATURE_TOPIC"
    wait_for_relay "humidity" "$HUMIDITY_TOPIC"
    wait_for_relay "occupancy" "$OCCUPANCY_TOPIC"
    wait_for_relay "air-quality" "$AIR_QUALITY_TOPIC"
  fi
}

verify_scalar_log() {
  log_path="$1"
  topic="$2"
  received_count="$(wc -l <"$log_path")"
  if [ "$received_count" -ne 1 ]; then
    echo "ERROR: expected 1 dashboard MQTT message for $topic, received $received_count" >&2
    exit 1
  fi

  if grep -q '[{}]' "$log_path"; then
    echo "ERROR: dashboard MQTT topic $topic received JSON, expected scalar values only" >&2
    exit 1
  fi
}

wait_for_relay() {
  name="$1"
  topic="$2"
  pid_path="$MQTT_RELAY_DIR/$name.pid"
  log_path="$MQTT_RELAY_DIR/$name.log"
  relay_status=0

  wait "$(cat "$pid_path")" || relay_status="$?"
  if [ "$relay_status" -ne 0 ]; then
    echo "ERROR: dashboard relay for $topic exited with status $relay_status" >&2
    cat "$log_path" >&2
    exit "$relay_status"
  fi
}

print_capture_points() {
  echo
  echo "Milestone 7.5 interactive packet-capture mode"
  echo
  echo "Topology is up. Suggested capture points:"
  echo
  echo "  sudo ip netns exec node1 tcpdump -i lowpan0 -n -vv -w node1-lowpan.pcap"
  echo "  sudo ip netns exec border tcpdump -i lowpan0 -n -vv -w border-lowpan.pcap"
  echo "  sudo ip netns exec border tcpdump -i border-ip -n -vv -w border-ip.pcap"
  echo "  sudo ip netns exec node2 tcpdump -i node2-border -n -vv -w node2-border.pcap"
  echo "  sudo ip netns exec node2 tcpdump -i node2-mqtt -n -vv -w node2-mqtt.pcap"
  echo
  echo "Expected observations:"
  echo "  node1 lowpan0: IPv6/UDP traffic over the Linux lowpan interface."
  echo "  border lowpan0: 6LoWPAN-side traffic entering the border gateway."
  echo "  border-ip: routed IPv6 traffic after the border gateway."
  echo "  node2-border: IPv6/UDP traffic arriving at the gateway receiver."
  echo "  node2-mqtt: MQTT/TCP traffic towards the host broker path."
  echo
  echo "Note: captures on lowpan0 may show the decompressed IPv6 view rather than raw"
  echo "IEEE 802.15.4 frames, depending on the Linux kernel interface and capture method."
}

wait_for_enter() {
  prompt="$1"
  echo
  echo "$prompt"
  if [ -r /dev/tty ]; then
    read -r _ </dev/tty
  else
    read -r _
  fi
}

attack_packet_count() {
  case "$1" in
    spoof|replay|extreme)
      echo 1
      ;;
    missing)
      echo 3
      ;;
  esac
}

attack_expected_topic_count() {
  attack="$1"
  topic_name="$2"

  case "$attack:$topic_name" in
    spoof:temperature|replay:temperature|extreme:temperature)
      echo 2
      ;;
    missing:temperature|missing:humidity|missing:occupancy)
      echo 2
      ;;
    *)
      echo 1
      ;;
  esac
}

describe_attack() {
  case "$1" in
    spoof)
      echo "Sensor spoofing: fake sensor_id temp-rogue sends a valid temperature reading."
      echo "Expected impact: weak source validation lets unauthorised telemetry influence MQTT and the dashboard."
      ;;
    replay)
      echo "Replay attack: a previously valid temp-01 reading with an old timestamp is resent."
      echo "Expected impact: stale telemetry can appear as a fresh dashboard update when freshness is not checked."
      ;;
    extreme)
      echo "False extreme reading: temp-01 sends temperature=80.0 with valid JSON."
      echo "Expected impact: a safety-relevant abnormal value reaches MQTT and the dashboard."
      ;;
    missing)
      echo "Missing telemetry: temperature, humidity and occupancy report, but air quality is silent."
      echo "Expected impact: operations lose visibility for one sensor stream while other telemetry still looks healthy."
      ;;
  esac
}

run_attack_exchange() {
  attack_count="$(attack_packet_count "$ATTACK_MODE")"
  total_count="$((READING_COUNT + attack_count))"
  temperature_count="$(attack_expected_topic_count "$ATTACK_MODE" temperature)"
  humidity_count="$(attack_expected_topic_count "$ATTACK_MODE" humidity)"
  occupancy_count="$(attack_expected_topic_count "$ATTACK_MODE" occupancy)"
  air_quality_count="$(attack_expected_topic_count "$ATTACK_MODE" air_quality)"

  echo
  echo "Starting Milestone 6 controlled attack activity: $ATTACK_MODE"
  describe_attack "$ATTACK_MODE"
  echo "Normal baseline telemetry count: $READING_COUNT"
  echo "Attack telemetry count: $attack_count"

  echo "+ timeout 20 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $MQTT_TOPIC -C $total_count"
  timeout 20 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$MQTT_TOPIC" \
    -C "$total_count" >"$MQTT_JSON_SUB_LOG" 2>&1 &
  mqtt_json_sub_pid="$!"

  echo "+ timeout 20 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $TEMPERATURE_TOPIC -C $temperature_count"
  timeout 20 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$TEMPERATURE_TOPIC" \
    -C "$temperature_count" >"$MQTT_TEMPERATURE_SUB_LOG" 2>&1 &
  mqtt_temperature_sub_pid="$!"

  echo "+ timeout 20 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $HUMIDITY_TOPIC -C $humidity_count"
  timeout 20 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$HUMIDITY_TOPIC" \
    -C "$humidity_count" >"$MQTT_HUMIDITY_SUB_LOG" 2>&1 &
  mqtt_humidity_sub_pid="$!"

  echo "+ timeout 20 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $OCCUPANCY_TOPIC -C $occupancy_count"
  timeout 20 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$OCCUPANCY_TOPIC" \
    -C "$occupancy_count" >"$MQTT_OCCUPANCY_SUB_LOG" 2>&1 &
  mqtt_occupancy_sub_pid="$!"

  echo "+ timeout 20 mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t $AIR_QUALITY_TOPIC -C $air_quality_count"
  timeout 20 mosquitto_sub \
    -h "$MQTT_HOST_ADDR" \
    -p "$MQTT_PORT" \
    -t "$AIR_QUALITY_TOPIC" \
    -C "$air_quality_count" >"$MQTT_AIR_QUALITY_SUB_LOG" 2>&1 &
  mqtt_air_quality_sub_pid="$!"

  sleep 1

  echo "+ ip netns exec node2 python3 gateway_receiver.py --bind $GATEWAY_ADDR --port $SENSOR_PORT --count $total_count --mqtt-host $MQTT_HOST_ADDR --mqtt-port $MQTT_PORT --mqtt-topic $MQTT_TOPIC --dashboard-map"
  ip netns exec node2 python3 "$SCRIPT_DIR/gateway_receiver.py" \
    --bind "$GATEWAY_ADDR" \
    --port "$SENSOR_PORT" \
    --count "$total_count" \
    --mqtt-host "$MQTT_HOST_ADDR" \
    --mqtt-port "$MQTT_PORT" \
    --mqtt-topic "$MQTT_TOPIC" \
    --dashboard-map >"$GATEWAY_LOG" 2>&1 &
  gateway_pid="$!"

  sleep 1

  echo
  echo "Normal baseline telemetry:"
  run_in node1 python3 "$SCRIPT_DIR/sensor_node.py" \
    --source "${PREFIX}1" \
    --dest "$GATEWAY_ADDR" \
    --port "$SENSOR_PORT" \
    --count "$READING_COUNT"

  echo
  echo "Attack telemetry:"
  run_in node1 python3 "$SCRIPT_DIR/attacks/send_attack.py" \
    --attack "$ATTACK_MODE" \
    --source "${PREFIX}1" \
    --dest "$GATEWAY_ADDR" \
    --port "$SENSOR_PORT"

  gateway_status=0
  mqtt_json_sub_status=0
  mqtt_temperature_sub_status=0
  mqtt_humidity_sub_status=0
  mqtt_occupancy_sub_status=0
  mqtt_air_quality_sub_status=0
  wait "$gateway_pid" || gateway_status="$?"
  wait "$mqtt_json_sub_pid" || mqtt_json_sub_status="$?"
  wait "$mqtt_temperature_sub_pid" || mqtt_temperature_sub_status="$?"
  wait "$mqtt_humidity_sub_pid" || mqtt_humidity_sub_status="$?"
  wait "$mqtt_occupancy_sub_pid" || mqtt_occupancy_sub_status="$?"
  wait "$mqtt_air_quality_sub_pid" || mqtt_air_quality_sub_status="$?"

  echo
  echo "Gateway receiver output:"
  cat "$GATEWAY_LOG"

  echo
  echo "MQTT JSON subscriber output:"
  cat "$MQTT_JSON_SUB_LOG"

  echo
  echo "MQTT dashboard-compatible subscriber output:"
  echo "$TEMPERATURE_TOPIC:"
  cat "$MQTT_TEMPERATURE_SUB_LOG"
  echo "$HUMIDITY_TOPIC:"
  cat "$MQTT_HUMIDITY_SUB_LOG"
  echo "$OCCUPANCY_TOPIC:"
  cat "$MQTT_OCCUPANCY_SUB_LOG"
  echo "$AIR_QUALITY_TOPIC:"
  cat "$MQTT_AIR_QUALITY_SUB_LOG"

  if [ "$gateway_status" -ne 0 ]; then
    echo "ERROR: gateway receiver exited with status $gateway_status" >&2
    exit "$gateway_status"
  fi

  if [ "$mqtt_json_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT JSON subscriber exited with status $mqtt_json_sub_status" >&2
    exit "$mqtt_json_sub_status"
  fi

  if [ "$mqtt_temperature_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT temperature subscriber exited with status $mqtt_temperature_sub_status" >&2
    exit "$mqtt_temperature_sub_status"
  fi

  if [ "$mqtt_humidity_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT humidity subscriber exited with status $mqtt_humidity_sub_status" >&2
    exit "$mqtt_humidity_sub_status"
  fi

  if [ "$mqtt_occupancy_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT occupancy subscriber exited with status $mqtt_occupancy_sub_status" >&2
    exit "$mqtt_occupancy_sub_status"
  fi

  if [ "$mqtt_air_quality_sub_status" -ne 0 ]; then
    echo "ERROR: MQTT air-quality subscriber exited with status $mqtt_air_quality_sub_status" >&2
    exit "$mqtt_air_quality_sub_status"
  fi

  json_received_count="$(wc -l <"$MQTT_JSON_SUB_LOG")"
  if [ "$json_received_count" -ne "$total_count" ]; then
    echo "ERROR: expected $total_count JSON MQTT messages, received $json_received_count" >&2
    exit 1
  fi

  verify_topic_count "$MQTT_TEMPERATURE_SUB_LOG" "$TEMPERATURE_TOPIC" "$temperature_count"
  verify_topic_count "$MQTT_HUMIDITY_SUB_LOG" "$HUMIDITY_TOPIC" "$humidity_count"
  verify_topic_count "$MQTT_OCCUPANCY_SUB_LOG" "$OCCUPANCY_TOPIC" "$occupancy_count"
  verify_topic_count "$MQTT_AIR_QUALITY_SUB_LOG" "$AIR_QUALITY_TOPIC" "$air_quality_count"

  echo
  echo "Milestone 6 result for attack '$ATTACK_MODE':"
  describe_attack "$ATTACK_MODE"
  echo "Gateway accepted syntactically valid telemetry and published the resulting MQTT/dashboard-compatible topics."
}

verify_topic_count() {
  log_path="$1"
  topic="$2"
  expected_count="$3"
  received_count="$(wc -l <"$log_path")"
  if [ "$received_count" -ne "$expected_count" ]; then
    echo "ERROR: expected $expected_count MQTT messages for $topic, received $received_count" >&2
    exit 1
  fi

  if grep -q '[{}]' "$log_path"; then
    echo "ERROR: dashboard MQTT topic $topic received JSON, expected scalar values only" >&2
    exit 1
  fi
}

require_root
require_command ip
require_command iwpan
require_command modprobe
require_command ping
require_command awk
require_command python3
require_command mosquitto
require_command mosquitto_pub
require_command mosquitto_sub
require_command timeout
require_command grep

parse_args "$@"
cleanup_existing

run modprobe mac802154_hwsim
run modprobe ieee802154_6lowpan || echo "NOTICE: ieee802154_6lowpan is not a loadable module; continuing."

radio_count="$(iwpan phy | awk '/^wpan_phy/ { count++ } END { print count + 0 }')"

if [ "$radio_count" -lt 2 ]; then
  echo "ERROR: expected at least 2 hwsim radios, found $radio_count" >&2
  exit 1
fi

mapfile -t phys < <(iwpan phy | awk '/^wpan_phy/ { print $2 }' | head -n 2)

if [ "${#phys[@]}" -lt 2 ]; then
  echo "ERROR: unable to identify two wpan phy names" >&2
  exit 1
fi

configure_lowpan_node node1 "${phys[0]}" "${PREFIX}1"
configure_lowpan_node border "${phys[1]}" "$BORDER_LOWPAN_ADDR"
configure_border_gateway
configure_mqtt_uplink
start_mqtt_broker
start_dashboard_relays

run_in node1 ip -6 addr show dev lowpan0
run_in border ip -6 addr show dev lowpan0
run_in border ip -6 addr show dev border-ip
run_in node2 ip -6 addr show dev node2-border

run_in node1 ping -6 -c 3 -I lowpan0 "$GATEWAY_ADDR"

echo
echo "SUCCESS: node1 reached node2 through the border gateway over native Linux IEEE 802.15.4/6LoWPAN simulation."

if [ "$INTERACTIVE_MODE" -eq 1 ]; then
  print_capture_points
  wait_for_enter "Start tcpdump/Wireshark captures now, then press ENTER to send sensor traffic."
fi

if [ -n "$ATTACK_MODE" ]; then
  run_attack_exchange

  if [ "$INTERACTIVE_MODE" -eq 1 ]; then
    wait_for_enter "Attack traffic is complete. Stop captures or inspect interfaces, then press ENTER to clean up."
    cleanup_existing
  fi

  echo
  echo "SUCCESS: Milestone 6 attack activity '$ATTACK_MODE' completed over the validated 6LoWPAN telemetry path."
  exit 0
fi

run_sensor_exchange

if [ "$INTERACTIVE_MODE" -eq 1 ]; then
  wait_for_enter "Sensor traffic is complete. Stop captures or inspect interfaces, then press ENTER to clean up."
  cleanup_existing
fi

echo
echo "SUCCESS: node1 sent UDP JSON sensor readings to node2 over 6LoWPAN."
echo "SUCCESS: gateway published the validated readings to MQTT topic $MQTT_TOPIC."
echo "SUCCESS: gateway published scalar values to dashboard topics for temperature, humidity, occupancy and air quality."
