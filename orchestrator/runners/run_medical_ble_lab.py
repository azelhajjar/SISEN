

#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from orchestrator.wireless import (
    HWSIM_AP_MODES,
    hwsim_ap_mode_state,
    hwsim_client_network_config,
    hwsim_hostapd_mode_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def choose_python():
    for candidate in (
        PROJECT_ROOT / ".venv" / "bin" / "python3",
        PROJECT_ROOT / ".venv" / "bin" / "python",
        Path(sys.executable),
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


PYTHON = choose_python()
LOG_FALLBACK_DIR = Path("/tmp/sisen-medical-logs")
AP_INTERFACE = "wlan0"
GATEWAY_INTERFACE = "wlan1"
GATEWAY_NAMESPACE = "medical-gateway"
AP_SSID = "SISEN-MEDICAL-IOT"
AP_IP = "192.168.70.1"
GATEWAY_IP = "192.168.70.10"
AP_MODE_STATE = Path("/tmp/sisen-ap-mode")
DEFAULT_PATIENT_COUNT = 1
MAX_PATIENT_COUNT = 10

WEARABLE_GENERATOR = {
    "name": "wearable data generator",
    "cmd": [
        PYTHON,
        str(PROJECT_ROOT / "iot" / "medical" / "wearable_data_generator.py"),
    ],
    "log": "/tmp/sisen-wearable-generator.log",
}

BLE_WIFI_GATEWAY = {
    "name": "BLE-to-WiFi gateway",
    "cmd": [
        PYTHON,
        str(PROJECT_ROOT / "iot" / "medical" / "ble_wifi_gateway.py"),
    ],
    "log": "/tmp/sisen-ble-wifi-gateway.log",
}

DASHBOARD = {
    "name": "SISEN dashboard",
    "cmd": [
        PYTHON,
        str(PROJECT_ROOT / "web" / "dashboard.py"),
        "--scenario",
        "medical",
    ],
    "log": "/tmp/sisen-dashboard.log",
}



def patient_count():
    try:
        count = int(os.environ.get("SISEN_PATIENT_COUNT", str(DEFAULT_PATIENT_COUNT)))
    except ValueError:
        count = DEFAULT_PATIENT_COUNT
    return max(1, min(count, MAX_PATIENT_COUNT))


def open_log_file(log_path):
    path = Path(log_path)
    try:
        if path.exists():
            path.unlink()
        return path.open("w", encoding="utf-8", errors="replace"), str(path)
    except OSError as exc:
        LOG_FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        fallback = LOG_FALLBACK_DIR / path.name
        print(f"WARNING: could not open {path}: {exc}")
        print(f"Using fallback log: {fallback}")
        return fallback.open("w", encoding="utf-8", errors="replace"), str(fallback)


def launch_process(process):
    log_file, actual_log_path = open_log_file(process["log"])

    try:
        subprocess.Popen(
            process["cmd"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
        )
    except OSError as exc:
        log_file.close()
        print(f"ERROR: failed to start {process['name']}: {exc}")
        print(f"Command: {' '.join(process['cmd'])}")
        raise

    print(f"Started {process['name']}")
    print(f"  Log: {actual_log_path}")


def gateway_process(broker):
    process = dict(BLE_WIFI_GATEWAY)
    process["cmd"] = [*BLE_WIFI_GATEWAY["cmd"], "--broker", broker]
    return process


def run(cmd, check=True):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=check)


def print_log_tail(log_path, line_count=20):
    path = Path(log_path)
    if not path.exists():
        print(f"Log not found: {log_path}")
        return

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-line_count:]
    if lines:
        print(f"Last {len(lines)} lines from {log_path}:")
        for line in lines:
            print(f"  {line}")


def ensure_process_running(process, name, log_path):
    if process.poll() is None:
        return

    print(f"ERROR: {name} failed to stay running.")
    print_log_tail(log_path)
    sys.exit(1)


def namespace_exists(namespace):
    result = subprocess.run(
        ["sudo", "ip", "netns", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    return any(line.split()[0] == namespace for line in result.stdout.splitlines() if line.strip())


def delete_namespace_if_exists(namespace):
    if namespace_exists(namespace):
        run(["sudo", "ip", "netns", "delete", namespace])


def load_hwsim():
    run(["sudo", "modprobe", "-r", "mac80211_hwsim"], check=False)
    run(["sudo", "modprobe", "mac80211_hwsim", "radios=2"])


def cleanup_stale_medical_gateway():
    for pattern in (
        "medical-hwsim-hostapd.conf",
        "medical-gateway.conf",
        "192.168.70.10,192.168.70.50",
    ):
        run(["sudo", "pkill", "-f", pattern], check=False)
    delete_namespace_if_exists(GATEWAY_NAMESPACE)


def create_gateway_namespace():
    delete_namespace_if_exists(GATEWAY_NAMESPACE)
    run(["sudo", "ip", "netns", "add", GATEWAY_NAMESPACE])


def get_phy_for_interface(interface_name):
    result = subprocess.run(["iw", "dev"], capture_output=True, text=True, check=True)
    current_phy = None

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("phy#"):
            current_phy = f"phy{stripped.replace('phy#', '')}"
        if stripped == f"Interface {interface_name}":
            return current_phy

    raise RuntimeError(f"Could not find phy for interface {interface_name}")


def move_gateway_wlan_to_namespace():
    phy = get_phy_for_interface(GATEWAY_INTERFACE)
    print(f"Moving {GATEWAY_INTERFACE} ({phy}) into namespace {GATEWAY_NAMESPACE}")
    run(["sudo", "iw", "phy", phy, "set", "netns", "name", GATEWAY_NAMESPACE])


def start_hostapd(ap_mode):
    config = "/tmp/medical-hwsim-hostapd.conf"

    Path(config).write_text(
        f"""interface={AP_INTERFACE}
driver=nl80211
ssid={AP_SSID}
hw_mode=g
channel=6
auth_algs=1
{hwsim_hostapd_mode_config(ap_mode)}
""",
        encoding="utf-8",
    )

    run(["sudo", "ip", "link", "set", AP_INTERFACE, "down"])
    run(["sudo", "ip", "addr", "flush", "dev", AP_INTERFACE])
    run(["sudo", "iw", "dev", AP_INTERFACE, "set", "type", "__ap"])
    run(["sudo", "ip", "addr", "replace", f"{AP_IP}/24", "dev", AP_INTERFACE])
    run(["sudo", "ip", "link", "set", AP_INTERFACE, "up"])

    log_path = "/tmp/medical-hwsim-hostapd.log"
    process = subprocess.Popen(
        ["sudo", "hostapd", config],
        stdout=open(log_path, "w", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)
    ensure_process_running(process, "medical hostapd", log_path)


def start_dnsmasq():
    run(["sudo", "ip", "addr", "replace", f"{AP_IP}/24", "dev", AP_INTERFACE])
    log_path = "/tmp/medical-hwsim-dnsmasq.log"
    process = subprocess.Popen(
        [
            "sudo",
            "dnsmasq",
            f"--interface={AP_INTERFACE}",
            "--bind-interfaces",
            "--dhcp-range=192.168.70.10,192.168.70.50,12h",
            "--no-daemon",
        ],
        stdout=open(log_path, "w", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(1)
    ensure_process_running(process, "medical dnsmasq", log_path)


def gateway_network_config(ap_mode):
    return hwsim_client_network_config(ap_mode, AP_SSID)


def connect_gateway(ap_mode):
    config = f"/tmp/{GATEWAY_NAMESPACE}.conf"
    Path(config).write_text(
        "p2p_disabled=1\n\n" + gateway_network_config(ap_mode),
        encoding="utf-8",
    )

    run(["sudo", "ip", "netns", "exec", GATEWAY_NAMESPACE, "ip", "link", "set", "lo", "up"])
    run(["sudo", "ip", "netns", "exec", GATEWAY_NAMESPACE, "ip", "link", "set", GATEWAY_INTERFACE, "up"])
    log_path = f"/tmp/{GATEWAY_NAMESPACE}-wpa.log"
    process = subprocess.Popen(
        [
            "sudo",
            "ip",
            "netns",
            "exec",
            GATEWAY_NAMESPACE,
            "wpa_supplicant",
            "-i",
            GATEWAY_INTERFACE,
            "-c",
            config,
            "-D",
            "nl80211",
        ],
        stdout=open(log_path, "w", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(5)
    ensure_process_running(process, "medical gateway wpa_supplicant", log_path)
    run(
        [
            "sudo",
            "ip",
            "netns",
            "exec",
            GATEWAY_NAMESPACE,
            "ip",
            "addr",
            "add",
            f"{GATEWAY_IP}/24",
            "dev",
            GATEWAY_INTERFACE,
        ]
    )


def setup_medical_ap_gateway(ap_mode):
    print("Setting up Medical BLE-to-Wi-Fi/AP gateway")
    cleanup_stale_medical_gateway()
    AP_MODE_STATE.write_text(hwsim_ap_mode_state("medical", ap_mode), encoding="utf-8")
    load_hwsim()
    start_hostapd(ap_mode)
    time.sleep(3)
    start_dnsmasq()
    create_gateway_namespace()
    move_gateway_wlan_to_namespace()
    connect_gateway(ap_mode)


def launch_gateway_in_namespace(process):
    log_file, actual_log_path = open_log_file(process["log"])
    cmd = [
        "sudo",
        "ip",
        "netns",
        "exec",
        GATEWAY_NAMESPACE,
        process["cmd"][0],
        "-u",
        *process["cmd"][1:],
    ]

    try:
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
        )
    except OSError as exc:
        log_file.close()
        print(f"ERROR: failed to start {process['name']} in {GATEWAY_NAMESPACE}: {exc}")
        print(f"Command: {' '.join(cmd)}")
        raise

    print(f"Started {process['name']} in namespace {GATEWAY_NAMESPACE}")
    print(f"  Log: {actual_log_path}")


def wait_for_enter(message):
    print()
    try:
        print(message)
        print("Press Ctrl+C to stop this lab.")
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print()
        print("Interrupted during observation.")
        print("Cleaning up Medical BLE lab...")
        subprocess.run([sys.executable, str(PROJECT_ROOT / "launch_sisen.py"), "--stop"], check=False)
        print("Medical BLE lab cancelled.")
        sys.exit(130)


def print_capture_hints(ap_mode):
    capture_dir = "captures"
    print()
    print("Medical IoT capture points")
    print("Scenario: medical")
    print(f"SSID/AP: {AP_SSID} on {AP_INTERFACE}")
    print(f"Patients/wearables: {patient_count()}")
    print("MQTT topics: patient/#")
    print("Wearable source, gateway translation, Wi-Fi/AP, MQTT, and dashboard can be observed together.")
    print("Run these commands from the repository root.")
    print("  watch -n 1 cat /tmp/sisen-wearable-data.json")
    print("  tail -f /tmp/sisen-ble-wifi-gateway.log")
    print(f"  sudo tcpdump -i {AP_INTERFACE} -n -vv -s 0 -Z \"$USER\" -w {capture_dir}/medical-ap-wlan0.pcap")
    print(
        "  sudo ip netns exec "
        f"{GATEWAY_NAMESPACE} tcpdump -i {GATEWAY_INTERFACE} -n -vv -s 0 -Z \"$USER\" "
        f"-w {capture_dir}/medical-gateway-wlan1.pcap"
    )
    print(f"  sudo tcpdump -i any -n -vv -s 0 -Z \"$USER\" -w {capture_dir}/medical-mqtt-patient-vitals.pcap port 1883")
    print("  mosquitto_sub -h localhost -v -t 'patient/#'")
    print()
    print("Dashboard:")
    print("  python3 web/dashboard.py --scenario medical")
    print("  http://localhost:5000")


def launch_dashboard_if_enabled():
    if os.environ.get("SISEN_SKIP_DASHBOARD") == "1":
        print("Dashboard launch skipped because SISEN_SKIP_DASHBOARD=1")
        return
    launch_process(DASHBOARD)
    time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Start the SISEN Medical BLE lab.")
    parser.add_argument(
        "--ap-mode",
        choices=HWSIM_AP_MODES,
        default="open",
        help="Medical HWSIM AP mode to use. Defaults to open.",
    )
    parser.add_argument(
        "--no-ap-gateway",
        action="store_true",
        help="Run the legacy process-only gateway without HWSIM AP/client namespace setup.",
    )
    parser.add_argument(
        "--interactive",
        "--pause-before-traffic",
        action="store_true",
        dest="interactive",
        help="Compatibility option. The lab waits by default.",
    )
    parser.add_argument(
        "--no-wait",
        "--test",
        action="store_true",
        dest="no_wait",
        help="Start the lab and return instead of waiting for observation.",
    )
    parser.add_argument(
        "--capture-hints",
        action="store_true",
        help="Print suggested capture and observation commands for this scenario.",
    )
    args = parser.parse_args()

    count = patient_count()

    print("=== Starting Medical BLE Lab ===")
    print(f"AP mode: {args.ap_mode}")
    print(f"Patients/wearables: {count}")
    print("Starting wearable generator and BLE-to-WiFi/AP gateway")
    print()

    if not args.no_ap_gateway:
        setup_medical_ap_gateway(args.ap_mode)

    launch_dashboard_if_enabled()
    if args.no_ap_gateway:
        launch_process(gateway_process("localhost"))
    else:
        launch_gateway_in_namespace(gateway_process(AP_IP))
    time.sleep(1)
    launch_process(WEARABLE_GENERATOR)
    time.sleep(1)

    should_wait = not args.no_wait

    if args.capture_hints or should_wait:
        print_capture_hints(args.ap_mode)

    print()
    print("Medical BLE lab started")
    print()
    print("Validate MQTT:")
    print("  mosquitto_sub -h localhost -v -t 'patient/#'")
    print()
    print("Open dashboard:")
    print("  http://localhost:5000")
    if should_wait:
        print()
        wait_for_enter("Telemetry is running. Start captures, observe the dashboard, or run attacks now.")


if __name__ == "__main__":
    main()
