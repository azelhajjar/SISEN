#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOWPAN_DIR="$REPO_ROOT/6lowpan"
STATE_DIR="/tmp/sisen-6lowpan-lab"
AP_MODE_STATE_FILE="${AP_MODE_STATE_FILE:-/tmp/sisen-ap-mode}"

PAN_ID="0xbeef"
PAGE="0"
CHANNEL="26"
LOWPAN_PREFIX="fd00:6:1::"
MQTT_PREFIX="fd00:6:2::"
IP_PREFIX="fd00:6:3::"
SENSOR_PORT="9999"
MQTT_PORT="1884"
DASHBOARD_MQTT_PORT="1883"
MQTT_TOPIC="industrial/6lowpan/temp-01/telemetry"
MQTT_HOST_ADDR="${MQTT_PREFIX}1"
TEMPERATURE_TOPIC="building/temperature"
HUMIDITY_TOPIC="building/humidity"
OCCUPANCY_TOPIC="building/occupancy"
AIR_QUALITY_TOPIC="building/air_quality"
BORDER_LOWPAN_ADDR="${LOWPAN_PREFIX}ff"
BORDER_IP_ADDR="${IP_PREFIX}1"
GATEWAY_ADDR="${IP_PREFIX}2"

MODE="${1:-}"
AP_MODE="open"
NO_AP=0
NO_CLEANUP=0
CAPTURE_HINTS=0
INTERVAL="2"
COUNT="4"
SENSOR_NODES="${SISEN_6LOWPAN_SENSOR_COUNT:-4}"
AP_PID=""
AP_INTERFACE=""

usage() {
  cat >&2 <<'EOF'
Usage:
  sudo ./6lowpan/sisen_lab.sh smoke-test --ap-mode open [--count 4] [--sensor-nodes 4] [--no-ap] [--no-cleanup]
  sudo ./6lowpan/sisen_lab.sh full --ap-mode open [--interval 2] [--sensor-nodes 4] [--capture-hints] [--no-ap]
  sudo ./6lowpan/sisen_lab.sh status
  sudo ./6lowpan/sisen_lab.sh stop

AP modes: open, wpa2, wpa2e, wep, hidden, macfilter, rogue
EOF
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run as root, for example: sudo ./6lowpan/sisen_lab.sh smoke-test --ap-mode open" >&2
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

pid_path() {
  echo "$STATE_DIR/$1.pid"
}

ap_script_for_mode() {
  case "$1" in
    open) echo "$REPO_ROOT/ap/open-ap.sh" ;;
    wpa2) echo "$REPO_ROOT/ap/wpa2-ap.sh" ;;
    wpa2e|wpa2-enterprise) echo "$REPO_ROOT/ap/wpa2e-ap.sh" ;;
    wep) echo "$REPO_ROOT/ap/wep-ap.sh" ;;
    hidden) echo "$REPO_ROOT/ap/hidden-ap.sh" ;;
    macfilter) echo "$REPO_ROOT/ap/macfilter-ap.sh" ;;
    rogue) echo "$REPO_ROOT/ap/rogue-ap.sh" ;;
    *)
      echo "ERROR: unsupported AP mode: $1" >&2
      exit 1
      ;;
  esac
}

ap_mode_state_label() {
  case "$1" in
    rogue|openwrt) return 1 ;;
    wpa2e|wpa2-enterprise) echo "6lowpan-wpa2-enterprise" ;;
    *) echo "6lowpan-$1" ;;
  esac
}

load_repo_env() {
  if [ -f "$REPO_ROOT/.env" ]; then
    # shellcheck disable=SC1090
    . "$REPO_ROOT/.env"
  elif [ -f "$REPO_ROOT/.env.example" ]; then
    # shellcheck disable=SC1090
    . "$REPO_ROOT/.env.example"
  fi
  AP_INTERFACE="${INTERFACE:-wlan0}"
}

ensure_ap_interface() {
  load_repo_env
  require_command iw

  if ip link show "$AP_INTERFACE" >/dev/null 2>&1; then
    echo "AP interface $AP_INTERFACE already exists."
    return
  fi

  echo "AP interface $AP_INTERFACE not found."
  echo "+ modprobe mac80211_hwsim radios=2"
  modprobe mac80211_hwsim radios=2
  echo "loaded-by-runner" >"$STATE_DIR/mac80211-hwsim"
  sleep 2

  if ! ip link show "$AP_INTERFACE" >/dev/null 2>&1; then
    echo "ERROR: AP interface $AP_INTERFACE still does not exist after loading mac80211_hwsim." >&2
    echo "Available Wi-Fi interfaces:" >&2
    iw dev >&2 || true
    echo "Set INTERFACE in .env if your AP-capable interface has a different name." >&2
    exit 1
  fi

  echo "AP interface $AP_INTERFACE is available."
}

parse_args() {
  if [ -z "$MODE" ]; then
    usage
    exit 1
  fi
  shift || true

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --ap-mode)
        if [ "$#" -lt 2 ]; then
          usage
          exit 1
        fi
        AP_MODE="$2"
        shift 2
        ;;
      --interval)
        if [ "$#" -lt 2 ]; then
          usage
          exit 1
        fi
        INTERVAL="$2"
        shift 2
        ;;
      --count)
        if [ "$#" -lt 2 ]; then
          usage
          exit 1
        fi
        COUNT="$2"
        shift 2
        ;;
      --sensor-nodes)
        if [ "$#" -lt 2 ]; then
          usage
          exit 1
        fi
        SENSOR_NODES="$2"
        shift 2
        ;;
      --capture-hints)
        CAPTURE_HINTS=1
        shift
        ;;
      --no-ap)
        NO_AP=1
        shift
        ;;
      --no-cleanup)
        NO_CLEANUP=1
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
}

save_pid() {
  name="$1"
  pid="$2"
  mkdir -p "$STATE_DIR"
  echo "$pid" >"$(pid_path "$name")"
}

stop_pid() {
  name="$1"
  path="$(pid_path "$name")"
  if [ ! -s "$path" ]; then
    return
  fi

  pid="$(cat "$path")"
  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "+ kill $name $pid"
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "$pid" >/dev/null 2>&1; then
      echo "+ kill -9 $name $pid"
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$path"
}

start_ap() {
  if [ "$NO_AP" -eq 1 ]; then
    echo "AP startup skipped because --no-ap was set."
    return
  fi

  ap_script="$(ap_script_for_mode "$AP_MODE")"
  if [ ! -f "$ap_script" ]; then
    echo "ERROR: AP script not found: $ap_script" >&2
    exit 1
  fi

  mkdir -p "$STATE_DIR"
  ensure_ap_interface
  echo "$AP_MODE" >"$STATE_DIR/ap-mode"
  echo "+ SSID_PREFIX=SISEN-6LOWPAN bash $ap_script > $STATE_DIR/ap.log 2>&1 &"
  SSID_PREFIX="SISEN-6LOWPAN" bash "$ap_script" >"$STATE_DIR/ap.log" 2>&1 &
  AP_PID="$!"
  save_pid ap "$AP_PID"
  sleep 5

  if ! kill -0 "$AP_PID" >/dev/null 2>&1; then
    echo "ERROR: AP failed to stay running. Output:" >&2
    cat "$STATE_DIR/ap.log" >&2
    exit 1
  fi

  echo "AP mode '$AP_MODE' is running. Log: $STATE_DIR/ap.log"
  if label="$(ap_mode_state_label "$AP_MODE")"; then
    echo "$label" >"$AP_MODE_STATE_FILE"
  fi
}

stop_ap() {
  if [ -f "$REPO_ROOT/ap/teardown-ap.sh" ]; then
    echo "+ bash $REPO_ROOT/ap/teardown-ap.sh"
    bash "$REPO_ROOT/ap/teardown-ap.sh" >/dev/null 2>&1 || true
  fi

  ap_pid_path="$(pid_path ap)"
  if [ -s "$ap_pid_path" ]; then
    ap_pid="$(cat "$ap_pid_path")"
    if kill -0 "$ap_pid" >/dev/null 2>&1; then
      echo "+ kill ap $ap_pid"
      kill "$ap_pid" >/dev/null 2>&1 || true
      for _ in 1 2 3; do
        kill -0 "$ap_pid" >/dev/null 2>&1 || break
        sleep 1
      done
    fi
    if kill -0 "$ap_pid" >/dev/null 2>&1; then
      echo "+ kill -9 ap $ap_pid"
      kill -9 "$ap_pid" >/dev/null 2>&1 || true
    fi
    rm -f "$ap_pid_path"
  fi
}

cleanup_wifi_hwsim() {
  if [ -f "$STATE_DIR/mac80211-hwsim" ]; then
    echo "+ modprobe -r mac80211_hwsim"
    modprobe -r mac80211_hwsim >/dev/null 2>&1 || true
  fi
}

cleanup_lowpan() {
  if [ -x "$LOWPAN_DIR/cleanup_poc.sh" ]; then
    echo "+ $LOWPAN_DIR/cleanup_poc.sh"
    "$LOWPAN_DIR/cleanup_poc.sh" >/dev/null 2>&1 || true
  fi
}

stop_lab() {
  stop_pid relay-temperature
  stop_pid relay-humidity
  stop_pid relay-occupancy
  stop_pid relay-air-quality
  stop_pid sensor
  stop_pid gateway
  stop_pid mqtt
  if ip netns list | grep -Eq '(^| )border($| )' && command -v ip6tables >/dev/null 2>&1; then
    "$REPO_ROOT/attacks/drop_telemetry.sh" stop >/dev/null 2>&1 || true
  fi
  stop_ap
  cleanup_wifi_hwsim
  cleanup_lowpan
  rm -rf "$STATE_DIR"
  echo "SISEN 6LoWPAN lab stopped."
}

configure_lowpan_node() {
  ns="$1"
  phy="$2"
  addr="$3"

  run ip netns add "$ns"
  run iwpan phy "$phy" set netns name "$ns"

  wpan_dev="$(ip netns exec "$ns" iwpan dev | awk '/Interface/ { print $2; exit }')"
  wpan_phy="$(ip netns exec "$ns" iwpan phy | awk '/^wpan_phy/ { print $2; exit }')"

  if [ -z "$wpan_dev" ] || [ -z "$wpan_phy" ]; then
    echo "ERROR: no IEEE 802.15.4 interface or PHY found in $ns" >&2
    exit 1
  fi

  echo "$wpan_dev" >"$STATE_DIR/$ns-wpan"
  run_in "$ns" ip link set "$wpan_dev" down
  run_in "$ns" iwpan dev "$wpan_dev" set pan_id "$PAN_ID"
  run_in "$ns" iwpan phy "$wpan_phy" set channel "$PAGE" "$CHANNEL"
  run_in "$ns" ip link add link "$wpan_dev" name lowpan0 type lowpan
  run_in "$ns" ip link set "$wpan_dev" up
  run_in "$ns" ip link set lowpan0 up
  run_in "$ns" sysctl -w "net.ipv6.conf.lowpan0.accept_dad=0"
  run_in "$ns" ip -6 addr add "$addr/64" dev lowpan0
}

setup_lowpan_topology() {
  mkdir -p "$STATE_DIR"
  cleanup_lowpan

  run modprobe mac802154_hwsim
  run modprobe ieee802154_6lowpan || echo "NOTICE: ieee802154_6lowpan may be built in; continuing."

  mapfile -t phys < <(iwpan phy | awk '/^wpan_phy/ { print $2 }' | head -n 2)
  if [ "${#phys[@]}" -lt 2 ]; then
    echo "ERROR: expected at least two hwsim WPAN PHYs" >&2
    exit 1
  fi

  configure_lowpan_node node1 "${phys[0]}" "${LOWPAN_PREFIX}1"
  configure_lowpan_node border "${phys[1]}" "$BORDER_LOWPAN_ADDR"

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
  run_in node2 ip -6 route add "$LOWPAN_PREFIX/64" via "$BORDER_IP_ADDR" dev node2-border
  run_in node1 ip -6 route add "$IP_PREFIX/64" via "$BORDER_LOWPAN_ADDR" dev lowpan0

  run ip link add host-mqtt type veth peer name node2-mqtt
  run ip link set node2-mqtt netns node2
  run sysctl -w "net.ipv6.conf.host-mqtt.accept_dad=0"
  run ip -6 addr add "${MQTT_PREFIX}1/64" dev host-mqtt
  run ip link set host-mqtt up
  run_in node2 sysctl -w "net.ipv6.conf.node2-mqtt.accept_dad=0"
  run_in node2 ip -6 addr add "${MQTT_PREFIX}2/64" dev node2-mqtt
  run_in node2 ip link set node2-mqtt up
}

start_mqtt() {
  cat >/etc/mosquitto/6lowpan-poc.conf <<EOF
listener $MQTT_PORT $MQTT_HOST_ADDR
allow_anonymous true
EOF
  echo "+ mosquitto -c /etc/mosquitto/6lowpan-poc.conf > $STATE_DIR/mosquitto.log 2>&1 &"
  mosquitto -c /etc/mosquitto/6lowpan-poc.conf >"$STATE_DIR/mosquitto.log" 2>&1 &
  save_pid mqtt "$!"
  sleep 1
  if ! kill -0 "$(cat "$(pid_path mqtt)")" >/dev/null 2>&1; then
    echo "ERROR: Mosquitto failed to stay running. Output:" >&2
    cat "$STATE_DIR/mosquitto.log" >&2
    exit 1
  fi
}

start_dashboard_relay() {
  topic="$1"
  name="$2"
  log_path="$STATE_DIR/relay-$name.log"

  echo "+ relay $topic from $MQTT_HOST_ADDR:$MQTT_PORT to localhost:$DASHBOARD_MQTT_PORT"
  (
    mosquitto_sub -h "$MQTT_HOST_ADDR" -p "$MQTT_PORT" -t "$topic" -v |
      while IFS= read -r line; do
        relay_topic="${line%% *}"
        payload="${line#* }"
        mosquitto_pub -h localhost -p "$DASHBOARD_MQTT_PORT" -t "$relay_topic" -m "$payload" || true
        echo "$relay_topic $payload"
      done
  ) >"$log_path" 2>&1 &
  save_pid "relay-$name" "$!"
}

start_dashboard_relays() {
  if ! timeout 2 mosquitto_pub \
    -h localhost \
    -p "$DASHBOARD_MQTT_PORT" \
    -t "sisen/6lowpan/relay-check" \
    -m "ready" >/dev/null 2>&1; then
    echo
    echo "NOTICE: no MQTT broker accepted localhost:$DASHBOARD_MQTT_PORT."
    echo "Dashboard relay disabled. Start the normal SISEN Mosquitto service before launching the dashboard."
    return
  fi

  start_dashboard_relay "$TEMPERATURE_TOPIC" "temperature"
  start_dashboard_relay "$HUMIDITY_TOPIC" "humidity"
  start_dashboard_relay "$OCCUPANCY_TOPIC" "occupancy"
  start_dashboard_relay "$AIR_QUALITY_TOPIC" "air-quality"
  start_dashboard_relay "building/gas_leak" "gas-leak"
  start_dashboard_relay "building/pressure_status" "pressure-status"
  start_dashboard_relay "building/machine_overheat" "machine-overheat"
  start_dashboard_relay "building/emergency_stop" "emergency-stop"
  start_dashboard_relay "industrial/6lowpan/nodes/#" "industrial-nodes"
}

start_gateway() {
  count="$1"
  echo "+ ip netns exec node2 python3 $LOWPAN_DIR/gateway_receiver.py --count $count ..."
  ip netns exec node2 python3 "$LOWPAN_DIR/gateway_receiver.py" \
    --bind "$GATEWAY_ADDR" \
    --port "$SENSOR_PORT" \
    --count "$count" \
    --mqtt-host "$MQTT_HOST_ADDR" \
    --mqtt-port "$MQTT_PORT" \
    --mqtt-topic "$MQTT_TOPIC" \
    --dashboard-map >"$STATE_DIR/gateway.log" 2>&1 &
  save_pid gateway "$!"
}

start_sensor() {
  count="$1"
  echo "+ ip netns exec node1 python3 $LOWPAN_DIR/sensor_node.py --count $count --sensor-nodes $SENSOR_NODES --interval $INTERVAL ..."
  echo "$SENSOR_NODES" >"$STATE_DIR/sensor-nodes"
  ip netns exec node1 python3 "$LOWPAN_DIR/sensor_node.py"     --source "${LOWPAN_PREFIX}1"     --dest "$GATEWAY_ADDR"     --port "$SENSOR_PORT"     --count "$count"     --sensor-nodes "$SENSOR_NODES"     --interval "$INTERVAL" >"$STATE_DIR/sensor.log" 2>&1 &
  save_pid sensor "$!"
}

print_capture_hints() {
  capture_dir="$REPO_ROOT/captures"
  cat <<EOF

Capture hints:
  Scenario: 6lowpan
  SSID/AP: SISEN-6LOWPAN-* on ${AP_INTERFACE:-wlan0} when AP mode is enabled
  Industrial sensor nodes: $SENSOR_NODES
  MQTT topics: $MQTT_TOPIC and industrial/6lowpan/nodes/#

  sudo tcpdump -i any -n -vv -s 0 -Z "\$USER" -w $capture_dir/6lowpan-mqtt-dashboard.pcap port $DASHBOARD_MQTT_PORT
  sudo ip netns exec node1 tcpdump -i $(cat "$STATE_DIR/node1-wpan" 2>/dev/null || echo wpan1) -n -vv -s 0 -Z "\$USER" -w $capture_dir/6lowpan-node1-wpan.pcap
  sudo ip netns exec node1 tcpdump -i lowpan0 -n -vv -s 0 -Z "\$USER" -w $capture_dir/6lowpan-node1-lowpan.pcap
  sudo ip netns exec border tcpdump -i lowpan0 -n -vv -s 0 -Z "\$USER" -w $capture_dir/6lowpan-border-lowpan.pcap
  sudo ip netns exec border tcpdump -i border-ip -n -vv -s 0 -Z "\$USER" -w $capture_dir/6lowpan-border-ip.pcap
  sudo ip netns exec node2 tcpdump -i node2-border -n -vv -s 0 -Z "\$USER" -w $capture_dir/6lowpan-node2-border.pcap
  sudo ip netns exec node2 tcpdump -i node2-mqtt -n -vv -s 0 -Z "\$USER" -w $capture_dir/6lowpan-node2-mqtt.pcap

MQTT observation:
  mosquitto_sub -h $MQTT_HOST_ADDR -p $MQTT_PORT -t '$MQTT_TOPIC' -v
  mosquitto_sub -h localhost -p $DASHBOARD_MQTT_PORT -t 'industrial/6lowpan/#' -v
EOF
}

status_lab() {
  echo "SISEN 6LoWPAN lab status"
  echo
  for name in ap mqtt gateway sensor; do
    path="$(pid_path "$name")"
    if [ -s "$path" ] && kill -0 "$(cat "$path")" >/dev/null 2>&1; then
      echo "$name: running (pid $(cat "$path"))"
    else
      echo "$name: not running"
    fi
  done

  echo
  echo "Namespaces:"
  ip netns list | grep -E '(^| )(node1|border|node2)($| )' || echo "none"

  echo
  echo "6LoWPAN interfaces:"
  for ns in node1 border; do
    if ip netns list | grep -Eq "(^| )$ns($| )"; then
      ip netns exec "$ns" ip -brief link show lowpan0 2>/dev/null || true
    fi
  done

  echo
  echo "MQTT topics:"
  echo "  $MQTT_TOPIC"
  echo "  building/temperature"
  echo "  building/gas_leak"
  echo "  building/pressure_status"
  echo "  building/emergency_stop"
  echo
  echo "Dashboard relay logs:"
  found_relay_log=0
  for name in temperature gas-leak pressure-status emergency-stop; do
    log_path="$STATE_DIR/relay-$name.log"
    if [ -f "$log_path" ]; then
      echo "  $log_path"
      found_relay_log=1
    fi
  done
  if [ "$found_relay_log" -eq 0 ]; then
    echo "  none found"
  fi
}

smoke_test() {
  start_ap
  setup_lowpan_topology
  start_mqtt
  start_dashboard_relays

  run_in node1 ping -6 -c 3 -I lowpan0 "$GATEWAY_ADDR"
  start_gateway "$COUNT"

  timeout 20 mosquitto_sub -h "$MQTT_HOST_ADDR" -p "$MQTT_PORT" -t "$MQTT_TOPIC" -C "$COUNT" >"$STATE_DIR/mqtt-json.log" 2>&1 &
  mqtt_json_pid="$!"
  timeout 20 mosquitto_sub -h "$MQTT_HOST_ADDR" -p "$MQTT_PORT" -t building/temperature -C 1 >"$STATE_DIR/mqtt-temperature.log" 2>&1 &
  mqtt_temp_pid="$!"
  timeout 20 mosquitto_sub -h "$MQTT_HOST_ADDR" -p "$MQTT_PORT" -t building/gas_leak -C 1 >"$STATE_DIR/mqtt-gas-leak.log" 2>&1 &
  mqtt_gas_leak_pid="$!"
  timeout 20 mosquitto_sub -h "$MQTT_HOST_ADDR" -p "$MQTT_PORT" -t building/pressure_status -C 1 >"$STATE_DIR/mqtt-pressure-status.log" 2>&1 &
  mqtt_pressure_pid="$!"
  timeout 20 mosquitto_sub -h "$MQTT_HOST_ADDR" -p "$MQTT_PORT" -t building/emergency_stop -C 1 >"$STATE_DIR/mqtt-emergency-stop.log" 2>&1 &
  mqtt_emergency_stop_pid="$!"

  sleep 1
  start_sensor "$COUNT"

  wait "$(cat "$(pid_path sensor)")"
  wait "$(cat "$(pid_path gateway)")"
  wait "$mqtt_json_pid"
  wait "$mqtt_temp_pid"
  wait "$mqtt_gas_leak_pid"
  wait "$mqtt_pressure_pid"
  wait "$mqtt_emergency_stop_pid"

  echo
  echo "Smoke test gateway output:"
  cat "$STATE_DIR/gateway.log"
  echo
  echo "Smoke test MQTT JSON output:"
  cat "$STATE_DIR/mqtt-json.log"
  echo
  echo "Smoke test dashboard temperature output:"
  cat "$STATE_DIR/mqtt-temperature.log"
  echo "Smoke test dashboard gas leak output:"
  cat "$STATE_DIR/mqtt-gas-leak.log"
  echo "Smoke test dashboard pressure-status output:"
  cat "$STATE_DIR/mqtt-pressure-status.log"
  echo "Smoke test dashboard emergency-stop output:"
  cat "$STATE_DIR/mqtt-emergency-stop.log"

  echo
  echo "SUCCESS: smoke test validated AP, 6LoWPAN, border gateway, MQTT and dashboard-compatible topics."

  if [ "$NO_CLEANUP" -eq 0 ]; then
    stop_lab
  fi
}

full_lab() {
  trap stop_lab EXIT INT TERM
  start_ap
  setup_lowpan_topology
  start_mqtt
  start_dashboard_relays
  run_in node1 ping -6 -c 3 -I lowpan0 "$GATEWAY_ADDR"
  start_gateway 0
  sleep 1
  start_sensor 0
  print_capture_hints

  echo
  echo "SUCCESS: full lab is running."
  echo "Use another terminal for attacks, for example:"
  echo "  ./attacks/run_attack_mode.sh spoofed"
  echo "  ./attacks/run_attack_mode.sh extreme"
  echo
  echo "Press Ctrl+C to stop, or run: sudo ./6lowpan/sisen_lab.sh stop"

  while true; do
    sleep 5
    if ! kill -0 "$(cat "$(pid_path gateway)")" >/dev/null 2>&1; then
      echo "ERROR: gateway receiver stopped. See $STATE_DIR/gateway.log" >&2
      exit 1
    fi
    if ! kill -0 "$(cat "$(pid_path sensor)")" >/dev/null 2>&1; then
      echo "ERROR: sensor telemetry stopped. See $STATE_DIR/sensor.log" >&2
      exit 1
    fi
  done
}

parse_args "$@"

case "$MODE" in
  smoke-test|full|status|stop)
    ;;
  *)
    usage
    exit 1
    ;;
esac

require_root

if [ "$MODE" = "status" ]; then
  status_lab
  exit 0
fi

if [ "$MODE" = "stop" ]; then
  stop_lab
  exit 0
fi

for cmd in ip iwpan modprobe ping awk python3 mosquitto mosquitto_pub mosquitto_sub timeout; do
  require_command "$cmd"
done

case "$MODE" in
  smoke-test)
    smoke_test
    ;;
  full)
    full_lab
    ;;
esac
