#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POC_DIR="$REPO_ROOT/6lowpan"
PROJECT_PYTHON="$REPO_ROOT/.venv/bin/python"
if [ -n "${SISEN_PYTHON:-}" ]; then
  PYTHON="$SISEN_PYTHON"
elif [ -e "$PROJECT_PYTHON" ]; then
  if [ ! -x "$PROJECT_PYTHON" ]; then
    echo "ERROR: project Python exists but is not executable: $PROJECT_PYTHON" >&2
    echo "Run setup.sh again or fix the virtual environment permissions." >&2
    exit 1
  fi
  PYTHON="$PROJECT_PYTHON"
else
  PYTHON="python3"
fi

AP_MODE=""
KEEP_AP=0
AP_PID=""

usage() {
  cat >&2 <<'EOF'
Usage: bash attacks/run_attack_mode.sh <normal|spoofed|spoof|missing|extreme|replay|malformed|boiler-pressure-masked|emergency-stop-hidden|machine-overheat-hidden> [--interactive] [--ap-mode <mode>] [--keep-ap]

Runs a selected Milestone 9 mode using the existing 6LoWPAN PoC runner.
The underlying topology and attack traffic remain implemented by 6lowpan/run_poc.sh.

AP modes reuse the existing AP scripts:
  open, wpa2, wpa2-enterprise
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1" >&2
    exit 1
  fi
}

ap_script_for_mode() {
  case "$1" in
    open)
      echo "$REPO_ROOT/ap/open-ap.sh"
      ;;
    wpa2)
      echo "$REPO_ROOT/ap/wpa2-ap.sh"
      ;;
    wpa2-enterprise|wpa2e)
      echo "$REPO_ROOT/ap/wpa2e-ap.sh"
      ;;
    *)
      echo "ERROR: unsupported AP mode: $1" >&2
      echo "Supported AP modes: open, wpa2, wpa2-enterprise" >&2
      exit 1
      ;;
  esac
}

stop_started_ap() {
  if [ -z "$AP_PID" ]; then
    return
  fi

  if [ "$KEEP_AP" -eq 1 ]; then
    echo "Leaving AP running because --keep-ap was set."
    return
  fi

  echo
  echo "Stopping AP with existing teardown script..."
  sudo bash "$REPO_ROOT/ap/teardown-ap.sh" || true

  if kill -0 "$AP_PID" >/dev/null 2>&1; then
    kill "$AP_PID" >/dev/null 2>&1 || true
  fi
}

start_selected_ap() {
  if [ -z "$AP_MODE" ]; then
    return
  fi

  ap_script="$(ap_script_for_mode "$AP_MODE")"
  ap_log="/tmp/sisen-milestone9-ap-${AP_MODE}.log"

  if [ ! -f "$ap_script" ]; then
    echo "ERROR: AP script not found: $ap_script" >&2
    exit 1
  fi

  echo "Starting AP mode '$AP_MODE' with existing script:"
  echo "  sudo bash $ap_script"
  echo "AP output log: $ap_log"

  sudo bash "$ap_script" >"$ap_log" 2>&1 &
  AP_PID="$!"
  trap stop_started_ap EXIT INT TERM
  sleep 5

  if ! kill -0 "$AP_PID" >/dev/null 2>&1; then
    echo "ERROR: AP script exited early. Output:" >&2
    cat "$ap_log" >&2
    exit 1
  fi

  echo "AP mode '$AP_MODE' is running alongside the 6LoWPAN scenario."
}

mode="${1:-}"
interactive_arg=""

if [ -z "$mode" ]; then
  usage
  exit 1
fi
shift || true

while [ "$#" -gt 0 ]; do
  case "$1" in
    --interactive|--pause-before-traffic)
      interactive_arg="--interactive"
      shift
      ;;
    --ap-mode)
      if [ "$#" -lt 2 ]; then
        usage
        exit 1
      fi
      AP_MODE="$2"
      shift 2
      ;;
    --keep-ap)
      KEEP_AP=1
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

require_command sudo
require_command ip
require_command mosquitto_sub

if [ ! -x "$POC_DIR/run_poc.sh" ]; then
  echo "ERROR: PoC runner not found or not executable: $POC_DIR/run_poc.sh" >&2
  exit 1
fi

echo "SISEN Milestone 9 mode: $mode"
echo "PoC directory: $POC_DIR"
echo "Python helper interpreter: $PYTHON"

active_lab=0
if ip netns list | grep -Eq '(^| )node1($| )' && ip netns list | grep -Eq '(^| )node2($| )' && ip netns list | grep -Eq '(^| )border($| )'; then
  echo "Detected existing Milestone 10 lab namespaces."
  active_lab=1
else
  echo "No existing node1 namespace detected. The PoC runner will create a clean topology."
fi

echo
echo "Useful MQTT observation commands:"
echo "  mosquitto_sub -h localhost -p 1883 -t 'building/#' -v"
echo "  mosquitto_sub -h fd00:6:2::1 -p 1884 -t '#' -v"
echo

start_selected_ap

if [ "$active_lab" -eq 1 ] && [ -z "$interactive_arg" ]; then
  case "$mode" in
    spoof|spoofed)
      echo "Active full lab detected. Injecting spoofed telemetry without rebuilding topology."
      sudo ip netns exec node1 "$PYTHON" "$POC_DIR/attacks/send_attack.py" --attack spoof --source fd00:6:1::1 --dest fd00:6:3::2 --port 9999
      exit 0
      ;;
    missing)
      echo "Active full lab detected. Injecting missing-telemetry activity without rebuilding topology."
      sudo ip netns exec node1 "$PYTHON" "$POC_DIR/attacks/send_attack.py" --attack missing --source fd00:6:1::1 --dest fd00:6:3::2 --port 9999
      exit 0
      ;;
    extreme)
      echo "Active full lab detected. Injecting extreme telemetry without rebuilding topology."
      sudo ip netns exec node1 "$PYTHON" "$POC_DIR/attacks/send_attack.py" --attack extreme --source fd00:6:1::1 --dest fd00:6:3::2 --port 9999
      exit 0
      ;;
    replay)
      echo "Active full lab detected. Injecting replay telemetry without rebuilding topology."
      sudo ip netns exec node1 "$PYTHON" "$POC_DIR/attacks/send_attack.py" --attack replay --source fd00:6:1::1 --dest fd00:6:3::2 --port 9999
      exit 0
      ;;
    malformed)
      echo "Active full lab detected. Injecting malformed protocol telemetry without rebuilding topology."
      sudo ip netns exec node1 "$PYTHON" "$POC_DIR/attacks/send_attack.py" --attack malformed --source fd00:6:1::1 --dest fd00:6:3::2 --port 9999
      exit 0
      ;;
    boiler-pressure-masked|emergency-stop-hidden|machine-overheat-hidden)
      echo "Active full lab detected. Injecting safety-case telemetry without rebuilding topology."
      sudo ip netns exec node1 "$PYTHON" "$POC_DIR/attacks/send_attack.py" --attack "$mode" --source fd00:6:1::1 --dest fd00:6:3::2 --port 9999
      exit 0
      ;;
    normal)
      echo "Active full lab detected. Normal telemetry is already running."
      exit 0
      ;;
  esac
fi

cd "$POC_DIR"

case "$mode" in
  normal)
    echo "Running normal telemetry mode."
    sudo ./run_poc.sh ${interactive_arg:+"$interactive_arg"}
    ;;
  spoof|spoofed)
    echo "Running spoofed telemetry mode."
    sudo ./run_poc.sh ${interactive_arg:+"$interactive_arg"} --attack spoof
    ;;
  missing)
    echo "Running missing telemetry mode."
    sudo ./run_poc.sh ${interactive_arg:+"$interactive_arg"} --attack missing
    ;;
  extreme)
    echo "Running extreme value mode."
    sudo ./run_poc.sh ${interactive_arg:+"$interactive_arg"} --attack extreme
    ;;
  replay)
    echo "Running replay telemetry mode."
    sudo ./run_poc.sh ${interactive_arg:+"$interactive_arg"} --attack replay
    ;;
  malformed)
    echo "ERROR: malformed requires an already running 6LoWPAN scenario from launch_sisen.py." >&2
    echo "Start the scenario first, then run this attack from a separate terminal." >&2
    exit 1
    ;;
  boiler-pressure-masked|emergency-stop-hidden|machine-overheat-hidden)
    echo "ERROR: $mode requires an already running 6LoWPAN scenario from launch_sisen.py." >&2
    echo "Start the scenario first, then run this attack from a separate terminal." >&2
    exit 1
    ;;
  *)
    usage
    exit 1
    ;;
esac
