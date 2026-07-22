





#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.wireless import (
    HWSIM_MACFILTER_AP_MODES,
    hwsim_ap_mode_state,
    hwsim_client_network_config,
    hwsim_hostapd_mode_config,
)


def choose_python():
    for candidate in (
        PROJECT_ROOT / ".venv" / "bin" / "python3",
        PROJECT_ROOT / ".venv" / "bin" / "python",
        Path(sys.executable),
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return Path(sys.executable)


PYTHON = choose_python()


AP_INTERFACE = "wlan0"
AP_SSID = "SISEN-SMART-BUILDING"
AP_IP = "192.168.60.1"
MQTT_PORT = 1883
MOSQUITTO_CONFIG = Path("/etc/mosquitto/hwsim-mosquitto.conf")
MOSQUITTO_LOG = Path("/tmp/hwsim-mosquitto.log")
MOSQUITTO_PID = Path("/tmp/hwsim-mosquitto.pid")
AP_MODE_STATE = Path("/tmp/sisen-ap-mode")
MACFILTER_ALLOWED_MACS = Path("/tmp/sisen-smart-building-allowed-macs.txt")
DEFAULT_SENSOR_COUNT = 4
MAX_SENSOR_COUNT = 10

ROOM_PROFILES = [
    {
        "label": "Room 101",
        "prefix": "room-101",
        "sensor_ids": ["TEMP-R101", "FIRE-R101", "OCC-R101", "GAS-R101"],
        "sensors": [
            {"sensor_id": "TEMP-R101", "sensor": "iot/sensors/temperature_sensor.py"},
            {
                "sensor_id": "FIRE-R101",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "fire_alarm",
                "hazard_label": "Fire Alarm",
                "normal_values": "Normal",
                "hazard_values": "Fire detected",
            },
            {"sensor_id": "OCC-R101", "sensor": "iot/sensors/occupancy_sensor.py"},
            {
                "sensor_id": "GAS-R101",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "gas_leak",
                "hazard_label": "Gas Leak Detector",
                "normal_values": "Normal",
                "hazard_values": "Gas detected",
            },
        ],
    },
    {
        "label": "Plant Room",
        "prefix": "plant-room",
        "sensor_ids": ["HUM-PLANT", "AIR-PLANT", "SMOKE-PLANT", "CO2-PLANT"],
        "sensors": [
            {"sensor_id": "HUM-PLANT", "sensor": "iot/sensors/humidity_sensor.py"},
            {"sensor_id": "AIR-PLANT", "sensor": "iot/sensors/air_quality_sensor.py"},
            {
                "sensor_id": "SMOKE-PLANT",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "smoke",
                "hazard_label": "Smoke Detector",
                "normal_values": "Clear",
                "hazard_values": "Smoke detected",
            },
            {
                "sensor_id": "CO2-PLANT",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "co2",
                "hazard_label": "CO2 Detector",
                "normal_values": "Normal",
                "hazard_values": "High CO2",
            },
        ],
    },
    {
        "label": "Server Room",
        "prefix": "server-room",
        "sensor_ids": ["TEMP-SRV", "SMOKE-SRV", "SPRINKLER-SRV", "EXIT-SRV"],
        "sensors": [
            {"sensor_id": "TEMP-SRV", "sensor": "iot/sensors/temperature_sensor.py"},
            {
                "sensor_id": "SMOKE-SRV",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "smoke",
                "hazard_label": "Smoke Detector",
                "normal_values": "Clear",
                "hazard_values": "Smoke detected",
            },
            {
                "sensor_id": "SPRINKLER-SRV",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "sprinkler_status",
                "hazard_label": "Sprinkler Status",
                "normal_values": "Standby",
                "hazard_values": "Disabled",
            },
            {
                "sensor_id": "EXIT-SRV",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "exit_status",
                "hazard_label": "Emergency Exit",
                "normal_values": "Clear",
                "hazard_values": "Blocked",
            },
        ],
    },
    {
        "label": "Workshop",
        "prefix": "workshop",
        "sensor_ids": ["TEMP-WORK", "AIR-WORK", "OCC-WORK", "GAS-WORK"],
        "sensors": [
            {"sensor_id": "TEMP-WORK", "sensor": "iot/sensors/temperature_sensor.py"},
            {"sensor_id": "AIR-WORK", "sensor": "iot/sensors/air_quality_sensor.py"},
            {"sensor_id": "OCC-WORK", "sensor": "iot/sensors/occupancy_sensor.py"},
            {
                "sensor_id": "GAS-WORK",
                "sensor": "iot/sensors/hazard_sensor.py",
                "hazard_field": "gas_leak",
                "hazard_label": "Gas Leak Detector",
                "normal_values": "Normal",
                "hazard_values": "Gas detected",
            },
        ],
    },
]


def sensor_count_from_env():
    raw_count = os.getenv("SISEN_SENSOR_COUNT", str(DEFAULT_SENSOR_COUNT))
    try:
        sensor_count = int(raw_count)
    except ValueError:
        print(f"ERROR: SISEN_SENSOR_COUNT must be a number, got {raw_count!r}")
        sys.exit(1)

    if sensor_count < 1 or sensor_count > MAX_SENSOR_COUNT:
        print(f"ERROR: SISEN_SENSOR_COUNT must be between 1 and {MAX_SENSOR_COUNT}")
        sys.exit(1)

    return sensor_count


def build_devices():
    devices = []
    for index in range(sensor_count_from_env()):
        room = ROOM_PROFILES[index % len(ROOM_PROFILES)]
        instance = (index // len(ROOM_PROFILES)) + 1
        suffix = f"-{instance}" if instance > 1 else ""

        devices.append(
            {
                "node_id": f"node-{index + 1:02d}",
                "namespace": f"{room['prefix']}{suffix}",
                "label": room["label"] if instance == 1 else f"{room['label']} {instance}",
                "wlan": f"wlan{index + 1}",
                "mac": f"02:60:00:00:00:{index + 1:02x}",
                "ip": f"192.168.60.{10 + index}",
                "sensor_ids": room["sensor_ids"],
                "sensors": room["sensors"],
            }
        )

    return devices


DEVICES = build_devices()

def run(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


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
        print("Cleaning up HWSIM IoT lab...")
        subprocess.run([sys.executable, str(PROJECT_ROOT / "launch_sisen.py"), "--stop"], check=False)
        print("HWSIM IoT lab cancelled.")
        sys.exit(130)


def print_capture_hints(ap_mode):
    capture_dir = PROJECT_ROOT / "captures"
    print()
    print("Smart Building capture points")
    print(f"Scenario: smart-building")
    print(f"SSID/AP: {AP_SSID} on {AP_INTERFACE}")
    print(f"Room/zone groups: {len(DEVICES)}")
    print("MQTT topics: building/#")
    print("Topology is up and clients are associated. Suggested capture commands:")
    print(f"  sudo tcpdump -i {AP_INTERFACE} -n -vv -s 0 -Z \"$USER\" -w {capture_dir / 'smart-building-ap-wlan0.pcap'}")
    print(f"  sudo tcpdump -i any -n -vv -s 0 -Z \"$USER\" -w {capture_dir / 'smart-building-mqtt-building.pcap'} port 1883")
    for device in DEVICES:
        print(
            "  sudo ip netns exec "
            f"{device['namespace']} tcpdump -i {device['wlan']} -n -vv -s 0 -Z \"$USER\" "
            f"-w {capture_dir / ('smart-building-' + device['namespace'] + '.pcap')}"
        )
    print("  mosquitto_sub -h localhost -v -t 'building/#'")
    print()
    print("Dashboard:")
    print("  python3 web/dashboard.py --scenario building")
    print("  http://localhost:5000")


def write_macfilter_allow_list(ap_mode):
    if ap_mode != "macfilter":
        return

    MACFILTER_ALLOWED_MACS.write_text(
        "".join(f"{device['mac']}\n" for device in DEVICES),
        encoding="utf-8",
    )
    print(f"MAC filter allow-list: {MACFILTER_ALLOWED_MACS}")


def load_hwsim():
    existing_interfaces = subprocess.run(
        ["iw", "dev"],
        capture_output=True,
        text=True,
        check=False,
    )

    if existing_interfaces.returncode == 0:
        existing = existing_interfaces.stdout
        required_interfaces = [AP_INTERFACE] + [device["wlan"] for device in DEVICES]
        if all(f"Interface {interface}" in existing for interface in required_interfaces):
            print("Using existing mac80211_hwsim radios.")
            return

    run(["sudo", "modprobe", "-r", "mac80211_hwsim"])
    run(["sudo", "modprobe", "mac80211_hwsim", f"radios={len(DEVICES) + 1}"])


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


def start_mqtt_broker():
    for path in (MOSQUITTO_CONFIG, MOSQUITTO_LOG, MOSQUITTO_PID):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    MOSQUITTO_CONFIG.write_text(
        f"""listener {MQTT_PORT} 0.0.0.0
allow_anonymous true
""",
        encoding="utf-8",
    )

    log_file = open(MOSQUITTO_LOG, "w", encoding="utf-8", errors="replace")
    process = subprocess.Popen(
        ["mosquitto", "-c", str(MOSQUITTO_CONFIG)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    MOSQUITTO_PID.write_text(str(process.pid), encoding="utf-8")
    time.sleep(1)
    ensure_process_running(process, "mosquitto", str(MOSQUITTO_LOG))
    print("MQTT broker started")
    print(f"  Log: {MOSQUITTO_LOG}")


def create_namespace(name):
    run(["sudo", "ip", "netns", "add", name])


def get_phy_for_interface(interface_name):
    result = subprocess.run(
        ["iw", "dev"],
        capture_output=True,
        text=True,
        check=True,
    )

    current_phy = None

    for line in result.stdout.splitlines():
        stripped = line.strip()

        if stripped.startswith("phy#"):
            phy_number = stripped.replace("phy#", "")
            current_phy = f"phy{phy_number}"

        if stripped == f"Interface {interface_name}":
            return current_phy

    raise RuntimeError(f"Could not find phy for interface {interface_name}")


def move_wlan_to_namespace(wlan, namespace):
    phy = get_phy_for_interface(wlan)
    print(f"Moving {wlan} ({phy}) into namespace {namespace}")
    run(["sudo", "iw", "phy", phy, "set", "netns", "name", namespace])


def start_hostapd(ap_mode):
    config = "/tmp/hwsim-hostapd.conf"

    with open(config, "w") as f:
        f.write(f"""interface={AP_INTERFACE}
driver=nl80211
ssid={AP_SSID}
hw_mode=g
channel=6
auth_algs=1
{hwsim_hostapd_mode_config(ap_mode, HWSIM_MACFILTER_AP_MODES, MACFILTER_ALLOWED_MACS)}
""")

    run(["sudo", "ip", "link", "set", AP_INTERFACE, "down"])
    run(["sudo", "ip", "addr", "flush", "dev", AP_INTERFACE])
    run(["sudo", "iw", "dev", AP_INTERFACE, "set", "type", "__ap"])
    run(["sudo", "ip", "addr", "replace", f"{AP_IP}/24", "dev", AP_INTERFACE])
    run(["sudo", "ip", "link", "set", AP_INTERFACE, "up"])

    log_path = "/tmp/hwsim-hostapd.log"
    process = subprocess.Popen(
        ["sudo", "hostapd", config],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    time.sleep(2)
    ensure_process_running(process, "hostapd", log_path)


def start_dnsmasq():
    run(["sudo", "ip", "addr", "replace", f"{AP_IP}/24", "dev", AP_INTERFACE])

    log_path = "/tmp/hwsim-dnsmasq.log"
    process = subprocess.Popen(
        [
            "sudo",
            "dnsmasq",
            "--interface=wlan0",
            "--bind-interfaces",
            "--dhcp-range=192.168.60.10,192.168.60.100,12h",
            "--no-daemon",
        ],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    time.sleep(1)
    ensure_process_running(process, "dnsmasq", log_path)


def connect_client(device, ap_mode):
    
    namespace = device["namespace"]
    wlan = device["wlan"]

    config = f"/tmp/{namespace}.conf"

    with open(config, "w") as f:
        f.write(
            "p2p_disabled=1\n\n"
            f"{hwsim_client_network_config(ap_mode, AP_SSID, HWSIM_MACFILTER_AP_MODES)}"
        )

    run([
        "sudo", "ip", "netns", "exec", namespace,
        "ip", "link", "set", "dev", wlan, "address", device["mac"],
    ])

    run([
        "sudo", "ip", "netns", "exec", namespace,
        "ip", "link", "set", wlan, "up",
    ])

    log_path = f"/tmp/{namespace}-wpa.log"
    process = subprocess.Popen(
        [
            "sudo",
            "ip",
            "netns",
            "exec",
            namespace,
            "wpa_supplicant",
            "-i",
            wlan,
            "-c",
            config,
            "-D",
            "nl80211",
        ],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    time.sleep(5)
    ensure_process_running(process, f"{namespace} wpa_supplicant", log_path)

    run([
        "sudo", "ip", "netns", "exec", namespace,
        "ip", "addr", "add",
        f"{device['ip']}/24",
        "dev",
        wlan,
    ])


def launch_sensor(device, sensor):
    log_path = f"/tmp/hwsim-{device['namespace']}-{sensor['sensor_id']}.log"

    log_file = open(log_path, "w")

    process = subprocess.Popen(
        [
            "sudo",
            "ip",
            "netns",
            "exec",
            device["namespace"],
            "env",
            f"SISEN_NODE_ID={device['node_id']}",
            f"SISEN_SENSOR_ID={sensor['sensor_id']}",
            f"SISEN_HAZARD_FIELD={sensor.get('hazard_field', '')}",
            f"SISEN_HAZARD_LABEL={sensor.get('hazard_label', '')}",
            f"SISEN_NORMAL_VALUES={sensor.get('normal_values', '')}",
            f"SISEN_HAZARD_VALUES={sensor.get('hazard_values', '')}",
            str(PYTHON),
            "-u",
            str(PROJECT_ROOT / sensor["sensor"]),
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    time.sleep(1)
    ensure_process_running(process, f"{device['namespace']} {sensor['sensor_id']} sensor", log_path)
    print(f"Started {sensor['sensor_id']} for {device['namespace']}")
    print(f"  Log: {log_path}")

def launch_dashboard():
    if os.environ.get("SISEN_SKIP_DASHBOARD") == "1":
        print("Dashboard launch skipped because SISEN_SKIP_DASHBOARD=1")
        return

    subprocess.Popen(
        [
        str(PYTHON),
	str(PROJECT_ROOT / "web" / "dashboard.py"),
        "--scenario",
        "building",
        ],
        stdout=open("/tmp/hwsim-dashboard.log", "w"),
        stderr=subprocess.STDOUT,
    )
    print("Dashboard launched")
    print("  Log: /tmp/hwsim-dashboard.log")
    print("  URL: http://localhost:5000")


def main():
    parser = argparse.ArgumentParser(description="Start the SISEN Smart Building HWSIM IoT lab.")
    parser.add_argument(
        "--ap-mode",
        choices=HWSIM_MACFILTER_AP_MODES,
        default="open",
        help="HWSIM AP mode to use. Defaults to open.",
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
        help="Print suggested tcpdump commands for this scenario.",
    )
    args = parser.parse_args()

    print("=== Starting HWSIM IoT Lab ===")
    print(f"AP mode: {args.ap_mode}")
    print(f"Sensor namespaces requested: {len(DEVICES)}")
    AP_MODE_STATE.write_text(hwsim_ap_mode_state("smart-building", args.ap_mode))

    load_hwsim()
    write_macfilter_allow_list(args.ap_mode)
    start_hostapd(args.ap_mode)
    time.sleep(3)
    start_dnsmasq()
    start_mqtt_broker()

    for device in DEVICES:
        create_namespace(device["namespace"])
        move_wlan_to_namespace(device["wlan"], device["namespace"])

    for device in DEVICES:
        connect_client(device, args.ap_mode)

    launch_dashboard()

    should_wait = not args.no_wait

    if args.capture_hints or should_wait:
        print_capture_hints(args.ap_mode)

    for device in DEVICES:
        for sensor in device["sensors"]:
            launch_sensor(device, sensor)

    print("HWSIM IoT lab started")
    if should_wait:
        print()
        wait_for_enter("Telemetry is running. Start captures, observe the dashboard, or run attacks now.")


if __name__ == "__main__":
    main()
