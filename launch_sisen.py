#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON_CANDIDATES = (
    PROJECT_ROOT / ".venv" / "bin" / "python3",
    PROJECT_ROOT / ".venv" / "bin" / "python",
)
SISEN_LAB = ["bash", "6lowpan/sisen_lab.sh"]
LOG_FALLBACK_DIR = "/tmp/sisen-launcher-logs"
BACKGROUND_PROCESSES = []
FOREGROUND_LOGS = []
AP_MODES = ("open", "hidden", "wep", "wpa2", "macfilter")
DEFAULT_NODE_COUNT = 4
DEFAULT_PATIENT_COUNT = 1
MAX_NODE_COUNT = 10
LAUNCHER_SCENARIOS = ("smart-building", "medical", "6lowpan")
EXPERIMENTAL_SCENARIOS = ("all", "scada")
SCENARIOS = (*LAUNCHER_SCENARIOS, *EXPERIMENTAL_SCENARIOS)
AP_SCRIPT_MAP = {
    "open": "ap/open-ap.sh",
    "hidden": "ap/hidden-ap.sh",
    "wep": "ap/wep-ap.sh",
    "wpa2": "ap/wpa2-ap.sh",
    "macfilter": "ap/macfilter-ap.sh",
}
SCENARIO_MENU = (
    ("smart-building", "IoT Smart Building"),
    ("medical", "Medical IoT"),
    ("6lowpan", "6LoWPAN IoT"),
)
AP_MODE_MENU = (
    ("open", "Open AP"),
    ("hidden", "Hidden SSID AP"),
    ("wep", "WEP AP"),
    ("wpa2", "WPA2-PSK AP"),
)
SMART_BUILDING_ROOM_PREFIXES = (
    "room-101",
    "plant-room",
    "server-room",
    "workshop",
)
SMART_BUILDING_LEGACY_NAMESPACE_PREFIXES = (
    "temp-sensor",
    "humidity-sensor",
    "air-quality",
    "occupancy",
    "fire-alarm",
    "smoke-detector",
    "co2-detector",
    "gas-leak",
    "exit-status",
    "sprinkler-status",
)
SMART_BUILDING_PROCESS_PATTERNS = (
    "temperature_sensor.py",
    "humidity_sensor.py",
    "air_quality_sensor.py",
    "occupancy_sensor.py",
    "hazard_sensor.py",
    "web/dashboard.py",
)
MEDICAL_PROCESS_PATTERNS = (
    "wearable_data_generator.py",
    "ble_wifi_gateway.py",
    "medical-hwsim-hostapd.conf",
    "medical-gateway.conf",
    "medical-mosquitto.conf",
    "192.168.70.10,192.168.70.50",
)
MEDICAL_GATEWAY_NAMESPACE = "medical-gateway"
AP_MODE_STATE = Path("/tmp/sisen-ap-mode")


def choose_python():
    for candidate in VENV_PYTHON_CANDIDATES:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def ensure_python_environment():
    for candidate in VENV_PYTHON_CANDIDATES:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return

    print()
    print("ERROR: SISEN Python environment is not ready.")
    print()
    print("Run:")
    print("  ./setup.sh")
    print()
    print("Expected interpreter:")
    print(f"  {PROJECT_ROOT / '.venv' / 'bin' / 'python3'}")
    sys.exit(1)


PYTHON = choose_python()


def ensure_root_or_reexec():
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        return

    print()
    print("=== Elevating SISEN Launcher ===")
    print("SISEN lab networking needs root for namespaces, hwsim radios and 6LoWPAN setup.")
    print("Re-running the launcher with sudo now.")
    os.execvp("sudo", ["sudo", sys.executable, *sys.argv])


def log_name(name):
    return "".join(character if character.isalnum() else "-" for character in name.lower()).strip("-")


def run_step(name, cmd, env_extra=None, log_path=None, quiet=False, required=False):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    if log_path is None:
        log_path = f"/tmp/sisen-{log_name(name)}.log"

    log_file, actual_log_path = open_log_file(log_path)
    if not quiet:
        print()
        print(f"=== {name} ===")
        print(f"Log: {actual_log_path}")
    FOREGROUND_LOGS.append(actual_log_path)

    with log_file:
        log_file.write(f"$ {' '.join(cmd)}\n\n")
        log_file.flush()
        result = subprocess.run(
            cmd,
            check=False,
            env=env,
            cwd=str(PROJECT_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    if required and result.returncode != 0:
        print()
        print(f"ERROR: {name} failed. See log: {actual_log_path}")
        print_log_tail(actual_log_path)
        cleanup_labs()
        sys.exit(result.returncode)

    return actual_log_path


def open_log_file(log_path):
    try:
        if os.path.exists(log_path):
            os.unlink(log_path)
        return open(log_path, "w", encoding="utf-8", errors="replace"), log_path
    except OSError as exc:
        os.makedirs(LOG_FALLBACK_DIR, exist_ok=True)
        fallback = os.path.join(LOG_FALLBACK_DIR, os.path.basename(log_path))
        print(f"WARNING: could not open {log_path}: {exc}")
        print(f"Using fallback log: {fallback}")
        return open(fallback, "w", encoding="utf-8", errors="replace"), fallback


def launch_background_step(name, cmd, log_path, env_extra=None):
    print()
    print(f"=== {name} ===")
    print(f"Running: {' '.join(cmd)}")

    log_file, actual_log_path = open_log_file(log_path)
    print(f"Log: {actual_log_path}")
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        env=env,
        start_new_session=True,
    )
    BACKGROUND_PROCESSES.append((name, process))
    return process, actual_log_path


def print_log_tail(log_path, line_count=20):
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
            lines = log_file.readlines()[-line_count:]
    except OSError as exc:
        print(f"Could not read {log_path}: {exc}")
        return

    if lines:
        print()
        print(f"Last {len(lines)} lines from {log_path}:")
        for line in lines:
            print(line.rstrip())


def cleanup_command(cmd):
    subprocess.run(cmd, check=False)


def smart_building_namespaces():
    current_namespaces = []
    for index in range(MAX_NODE_COUNT):
        prefix = SMART_BUILDING_ROOM_PREFIXES[index % len(SMART_BUILDING_ROOM_PREFIXES)]
        instance = (index // len(SMART_BUILDING_ROOM_PREFIXES)) + 1
        suffix = f"-{instance}" if instance > 1 else ""
        current_namespaces.append(f"{prefix}{suffix}")

    legacy_namespaces = [
        f"{prefix}-{index}"
        for index in range(1, MAX_NODE_COUNT + 1)
        for prefix in SMART_BUILDING_LEGACY_NAMESPACE_PREFIXES
    ]

    return [*current_namespaces, *legacy_namespaces]


def cleanup_smart_building_lab():
    print("Stopping Smart Building lab processes...")

    cleanup_command(["systemctl", "stop", "wpa_supplicant"])
    for process_name in ("wpa_supplicant", "hostapd", "dnsmasq"):
        cleanup_command(["pkill", process_name])
    for pattern in SMART_BUILDING_PROCESS_PATTERNS:
        cleanup_command(["pkill", "-f", pattern])
    cleanup_command(["pkill", "-f", "hwsim-mosquitto.conf"])

    for namespace in smart_building_namespaces():
        if namespace_exists(namespace):
            cleanup_command(["ip", "netns", "delete", namespace])

    cleanup_command(["modprobe", "-r", "mac80211_hwsim"])

    temp_files = [
        Path("/tmp/hwsim-hostapd.conf"),
        Path("/tmp/hwsim-hostapd.log"),
        Path("/tmp/hwsim-dnsmasq.conf"),
        Path("/tmp/hwsim-dnsmasq.log"),
        Path("/etc/mosquitto/hwsim-mosquitto.conf"),
        Path("/tmp/hwsim-mosquitto.log"),
        Path("/tmp/hwsim-mosquitto.pid"),
        Path("/tmp/hwsim-dashboard.log"),
        AP_MODE_STATE,
    ]
    for namespace in smart_building_namespaces():
        temp_files.extend(
            [
                Path(f"/tmp/{namespace}.conf"),
                Path(f"/tmp/{namespace}-wpa.log"),
                Path(f"/tmp/{namespace}-wpa.pid"),
                Path(f"/tmp/hwsim-{namespace}-sensor.log"),
            ]
        )
    for temp_file in temp_files:
        try:
            temp_file.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def namespace_exists(namespace):
    result = subprocess.run(
        ["ip", "netns", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    return any(line.split()[0] == namespace for line in result.stdout.splitlines() if line.strip())


def cleanup_medical_lab():
    print("Stopping Medical IoT lab processes...")

    for pattern in MEDICAL_PROCESS_PATTERNS:
        cleanup_command(["pkill", "-f", pattern])

    if namespace_exists(MEDICAL_GATEWAY_NAMESPACE):
        cleanup_command(["ip", "netns", "delete", MEDICAL_GATEWAY_NAMESPACE])

    try:
        if AP_MODE_STATE.exists() and AP_MODE_STATE.read_text(encoding="utf-8").startswith("medical-hwsim-"):
            AP_MODE_STATE.unlink()
    except OSError:
        pass

    for temp_file in (
        Path("/etc/mosquitto/medical-mosquitto.conf"),
        Path("/tmp/medical-mosquitto.log"),
        Path("/tmp/medical-mosquitto.pid"),
    ):
        try:
            temp_file.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def cleanup_labs():
    print()
    print("=== Stopping SISEN Launcher ===")

    try:
        for name, process in BACKGROUND_PROCESSES:
            if process.poll() is None:
                print(f"Stopping background {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

        print("Stopping 6LoWPAN lab processes...")
        run_step("Stop 6LoWPAN Lab", [*SISEN_LAB, "stop"], quiet=True)
        run_step("Stop standalone AP", ["bash", "ap/teardown-ap.sh"], quiet=True)
        cleanup_medical_lab()
        cleanup_smart_building_lab()
    except KeyboardInterrupt:
        print()
        print("Cleanup interrupted before all stop steps finished.")
        print(f"Run again if needed: {stop_command()}")
        sys.exit(130)

    print()
    print("SISEN launcher stopped.")


def stop_command():
    return "python3 launch_sisen.py --stop"


def run_command(selected_scenario, ap_mode, args, node_count=None, patient_count=None):
    command = [
        "python3",
        "launch_sisen.py",
        "--scenario",
        selected_scenario,
        "--ap-mode",
        ap_mode,
    ]
    if node_count is not None:
        command.extend(["--nodes", str(node_count)])
    if patient_count is not None:
        command.extend(["--patients", str(patient_count)])
    if args.capture_hints:
        command.append("--capture-hints")
    if args.no_wait:
        command.append("--no-wait")
    return " ".join(command)



def validate_limited_count(value, label):
    try:
        count = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"{label} must be a number")

    if count < 1 or count > MAX_NODE_COUNT:
        raise argparse.ArgumentTypeError(f"{label} must be between 1 and {MAX_NODE_COUNT}")

    return count


def validate_node_count(value):
    return validate_limited_count(value, "node count")


def validate_patient_count(value):
    return validate_limited_count(value, "patient count")


def prompt_for_count(title, prompt, default):
    print()
    print("Select network size:")
    print(title)

    while True:
        choice = input(f"{prompt} [{default}]: ").strip()
        if not choice:
            return default
        try:
            return validate_limited_count(choice, prompt.lower())
        except argparse.ArgumentTypeError as exc:
            print(f"ERROR: {exc}")


def choose_runtime_counts(selected_scenario, args):
    sensor_count = DEFAULT_NODE_COUNT
    patient_count = DEFAULT_PATIENT_COUNT
    sixlowpan_count = DEFAULT_NODE_COUNT

    if selected_scenario == "smart-building":
        if args.nodes is not None:
            sensor_count = args.nodes
        elif not args.no_wait:
            sensor_count = prompt_for_count(
                f"Default Smart Building sensor nodes: {DEFAULT_NODE_COUNT}",
                "Number of sensor nodes",
                DEFAULT_NODE_COUNT,
            )

    if selected_scenario == "medical":
        if args.patients is not None:
            patient_count = args.patients
        elif not args.no_wait:
            patient_count = prompt_for_count(
                f"Default Medical IoT patients/wearables: {DEFAULT_PATIENT_COUNT}",
                "Number of patients/wearables",
                DEFAULT_PATIENT_COUNT,
            )

    if selected_scenario == "6lowpan":
        if args.nodes is not None:
            sixlowpan_count = args.nodes
        elif not args.no_wait:
            sixlowpan_count = prompt_for_count(
                f"Default 6LoWPAN sensor nodes: {DEFAULT_NODE_COUNT}",
                "Number of 6LoWPAN sensor nodes",
                DEFAULT_NODE_COUNT,
            )

    return sensor_count, patient_count, sixlowpan_count


def choose_scenario():
    print()
    print("Select scenario:")
    for index, (scenario, label) in enumerate(SCENARIO_MENU, start=1):
        print(f"  {index}. {label}")

    while True:
        choice = input("Scenario [1]: ").strip()
        if not choice:
            return SCENARIO_MENU[0][0]
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(SCENARIO_MENU):
                return SCENARIO_MENU[index - 1][0]
        if choice in SCENARIOS:
            return choice
        print("Please enter a valid number or scenario name.")


def choose_ap_mode():
    print()
    print("Select AP mode:")
    for index, (mode, label) in enumerate(AP_MODE_MENU, start=1):
        print(f"  {index}. {label}")

    while True:
        choice = input("AP mode [1]: ").strip()
        if not choice:
            return AP_MODE_MENU[0][0]
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(AP_MODE_MENU):
                return AP_MODE_MENU[index - 1][0]
        if choice in AP_MODES:
            return choice
        print("Please enter a valid number or AP mode name.")


def check_background_process(process, log_path, failure_message):
    time.sleep(2)
    if process.poll() is None:
        return

    print()
    print(failure_message)
    print_log_tail(log_path)
    cleanup_labs()
    sys.exit(1)


def start_dashboard(
    scenario="all",
    sensor_count=DEFAULT_NODE_COUNT,
    patient_count=DEFAULT_PATIENT_COUNT,
    sixlowpan_count=DEFAULT_NODE_COUNT,
):
    process, log_path = launch_background_step(
        "Unified Dashboard",
        [PYTHON, "web/dashboard.py", "--scenario", scenario],
        "/tmp/sisen-launcher-dashboard.log",
        env_extra={
            "SISEN_SENSOR_COUNT": str(sensor_count),
            "SISEN_PATIENT_COUNT": str(patient_count),
            "SISEN_6LOWPAN_SENSOR_COUNT": str(sixlowpan_count),
        },
    )
    check_background_process(process, log_path, "ERROR: unified dashboard did not stay running.")
    return log_path


def dashboard_scenario(selected_scenario):
    return {
        "smart-building": "building",
    }.get(selected_scenario, selected_scenario)


def start_standalone_ap(ap_mode):
    script = AP_SCRIPT_MAP[ap_mode]
    process, log_path = launch_background_step(
        f"Start {ap_mode} AP",
        ["bash", script],
        f"/tmp/sisen-{ap_mode}-ap.log",
    )
    check_background_process(process, log_path, f"ERROR: {ap_mode} AP did not stay running.")
    return log_path


def runtime_flags(args, include_wait=True):
    return [
        *(["--capture-hints"] if args.capture_hints else []),
        *(["--no-wait"] if args.no_wait or not include_wait else []),
    ]


def start_smart_building(ap_mode, args, sensor_count=DEFAULT_NODE_COUNT, include_wait=True):
    run_step(
        "Start Smart Building - HWSIM IoT",
        [
            PYTHON,
            "orchestrator/runners/run_iot_hwsim_lab.py",
            "--ap-mode",
            ap_mode,
            *runtime_flags(args, include_wait=include_wait),
        ],
        env_extra={"SISEN_SKIP_DASHBOARD": "1", "SISEN_SENSOR_COUNT": str(sensor_count)},
        required=True,
    )


def start_medical(args, ap_mode=None, patient_count=DEFAULT_PATIENT_COUNT, include_wait=True, use_ap_gateway=True):
    run_step(
        "Start Medical IoT",
        [
            PYTHON,
            "orchestrator/runners/run_medical_ble_lab.py",
            *(["--ap-mode", ap_mode] if use_ap_gateway and ap_mode else []),
            *(["--no-ap-gateway"] if not use_ap_gateway else []),
            *runtime_flags(args, include_wait=include_wait),
        ],
        env_extra={"SISEN_SKIP_DASHBOARD": "1", "SISEN_PATIENT_COUNT": str(patient_count)},
        required=True,
    )


def start_sixlowpan(ap_mode, args, sensor_count=DEFAULT_NODE_COUNT, no_ap=False):
    ap_args = ["--no-ap"] if no_ap else ["--ap-mode", ap_mode]
    process, log_path = launch_background_step(
        "Start 6LoWPAN",
        [
            *SISEN_LAB,
            "full",
            *ap_args,
            "--sensor-nodes",
            str(sensor_count),
            *(["--capture-hints"] if args.capture_hints else []),
        ],
        "/tmp/sisen-6lowpan-launcher.log",
    )
    check_background_process(process, log_path, "ERROR: 6LoWPAN lab did not stay running.")
    return log_path


def start_scada(ap_mode):
    process, log_path = launch_background_step(
        "Start SCADA",
        [
            PYTHON,
            "orchestrator/runners/run_scenario.py",
            "scenarios/scada-basic.yml",
            "--ap-mode",
            ap_mode,
        ],
        "/tmp/sisen-scada.log",
    )
    check_background_process(process, log_path, "ERROR: SCADA scenario did not stay running.")
    return log_path


def wait_for_observation():
    print()
    print("SISEN launcher is running. Start captures, observe dashboards, or run attacks now.")
    print("Press Ctrl+C in this terminal to stop.")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        cleanup_labs()


def main():
    parser = argparse.ArgumentParser(description="Launch SISEN lab scenarios.")
    parser.add_argument(
        "--interactive",
        "--pause-before-traffic",
        action="store_true",
        dest="interactive",
        help="Compatibility option. The launcher waits by default.",
    )
    parser.add_argument(
        "--no-wait",
        "--test",
        action="store_true",
        dest="no_wait",
        help="Start the selected lab path and return instead of waiting for observation.",
    )
    parser.add_argument(
        "--capture-hints",
        action="store_true",
        help="Print capture hints in labs that support them.",
    )
    parser.add_argument(
        "--ap-mode",
        choices=AP_MODES,
        help="AP mode to use for the selected scenario. If omitted, an interactive menu is shown.",
    )
    parser.add_argument(
        "--nodes",
        type=validate_node_count,
        help=(
            "Number of sensor nodes to create for Smart Building or 6LoWPAN. "
            f"Defaults to {DEFAULT_NODE_COUNT}; valid range is 1-{MAX_NODE_COUNT}."
        ),
    )
    parser.add_argument(
        "--patients",
        type=validate_patient_count,
        help=(
            "Number of Medical IoT patients/wearables to simulate. "
            f"Defaults to {DEFAULT_PATIENT_COUNT}; valid range is 1-{MAX_NODE_COUNT}."
        ),
    )
    parser.add_argument(
        "--scenario",
        help=(
            "Scenario to start: smart-building, medical, or 6lowpan. "
            "If omitted, an interactive menu is shown."
        ),
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop SISEN launcher-managed labs and dashboard processes.",
    )
    args = parser.parse_args()

    if args.scenario and args.scenario not in SCENARIOS:
        parser.error(f"unknown scenario: {args.scenario}")
    if args.ap_mode == "macfilter" and args.scenario and args.scenario != "smart-building":
        parser.error("--ap-mode macfilter is currently supported only with --scenario smart-building")

    if args.stop:
        print()
        print("=== Stopping SISEN ===")
        ensure_root_or_reexec()
        cleanup_labs()
        return

    print()
    print("=== Launching SISEN ===")

    ensure_python_environment()
    ensure_root_or_reexec()

    selected_scenario = args.scenario or choose_scenario()
    ap_mode = args.ap_mode or choose_ap_mode()
    if ap_mode == "macfilter" and selected_scenario != "smart-building":
        parser.error("--ap-mode macfilter is currently supported only with --scenario smart-building")
    sensor_count, patient_count, sixlowpan_count = choose_runtime_counts(selected_scenario, args)

    print()
    print("Cleaning previous lab processes...")

    run_step("Stop 6LoWPAN Lab", [*SISEN_LAB, "stop"], quiet=True)
    cleanup_medical_lab()
    cleanup_smart_building_lab()

    print()
    print("Starting labs...")

    dashboard_log = start_dashboard(
        dashboard_scenario(selected_scenario),
        sensor_count=sensor_count,
        patient_count=patient_count,
        sixlowpan_count=sixlowpan_count,
    )
    extra_logs = []

    if selected_scenario == "all":
        start_smart_building(ap_mode, args, sensor_count, include_wait=False)
        time.sleep(3)
        start_medical(args, ap_mode, patient_count, include_wait=False, use_ap_gateway=False)
        time.sleep(2)
        extra_logs.append(start_sixlowpan(ap_mode, args, sixlowpan_count, no_ap=True))
    elif selected_scenario == "smart-building":
        start_smart_building(ap_mode, args, sensor_count, include_wait=False)
    elif selected_scenario == "medical":
        start_medical(args, ap_mode, patient_count, include_wait=False)
    elif selected_scenario == "scada":
        extra_logs.append(start_scada(ap_mode))
    elif selected_scenario == "6lowpan":
        extra_logs.append(start_sixlowpan(ap_mode, args, sixlowpan_count))

    print()
    print("=== SISEN Launcher Started ===")
    print()
    print(f"Scenario: {selected_scenario}")
    print(f"AP mode: {ap_mode}")
    if selected_scenario == "smart-building":
        print(f"Sensor nodes: {sensor_count}")
    if selected_scenario == "medical":
        print(f"Patients/wearables: {patient_count}")
    if selected_scenario == "6lowpan":
        print(f"6LoWPAN sensor nodes: {sixlowpan_count}")
    print(f"Run:")
    print(f"  {run_command(selected_scenario, ap_mode, args, sensor_count if selected_scenario == 'smart-building' else sixlowpan_count if selected_scenario == '6lowpan' else None, patient_count if selected_scenario == 'medical' else None)}")
    print()
    print("Dashboard:")
    print("  http://localhost:5000")
    print(f"  Log: {dashboard_log}")
    print()
    print("Launcher logs:")
    for log_path in FOREGROUND_LOGS:
        print(f"  {log_path}")
    if extra_logs:
        for log_path in extra_logs:
            print(f"  {log_path}")
    print()
    print("Validate MQTT:")
    print("  mosquitto_sub -h localhost -t '#' -v")
    print()
    print("Stop:")
    if args.no_wait:
        print("  This scenario is still running because --no-wait was used.")
        print(f"  {stop_command()}")
    else:
        print("  Press Ctrl+C in this terminal.")
        print(f"  Or from another terminal: {stop_command()}")
    if not args.no_wait:
        wait_for_observation()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("Interrupted. Stopping SISEN launcher-managed labs...")
        cleanup_labs()
        sys.exit(130)
