import subprocess
import shutil
import sys
import time
from pathlib import Path


AP_SCRIPT_MAP = {
    "open": "ap/open-ap.sh",
    "hidden": "ap/hidden-ap.sh",
    "macfilter": "ap/macfilter-ap.sh",
    "openwrt": "ap/openwrt-ap.sh",
    "rogue": "ap/rogue-ap.sh",
    "wep": "ap/wep-ap.sh",
    "wpa2": "ap/wpa2-ap.sh",
    "wpa2-enterprise": "ap/wpa2e-ap.sh",
}

HWSIM_AP_MODES = ("open", "hidden", "wep", "wpa2")
HWSIM_MACFILTER_AP_MODES = (*HWSIM_AP_MODES, "macfilter")
WEP_KEY_HEX = "AABBCCDDEE"
WPA2_PASSPHRASE = "changeme123"
ALLOWED_MACS_FILE = Path(__file__).resolve().parents[1] / "ap" / "files" / "allowed_macs.txt"


def validate_hwsim_ap_mode(ap_mode, supported_modes=HWSIM_AP_MODES):
    if ap_mode not in supported_modes:
        print(f"ERROR: unsupported HWSIM AP mode: {ap_mode}")
        print(f"Supported HWSIM AP modes: {', '.join(supported_modes)}")
        sys.exit(1)


def hwsim_hostapd_mode_config(ap_mode, supported_modes=HWSIM_AP_MODES, allowed_macs_file=ALLOWED_MACS_FILE):
    validate_hwsim_ap_mode(ap_mode, supported_modes)

    lines = [
        "ignore_broadcast_ssid=1" if ap_mode == "hidden" else "ignore_broadcast_ssid=0",
    ]

    if ap_mode == "wep":
        lines.extend(
            [
                "wep_default_key=0",
                f"wep_key0={WEP_KEY_HEX}",
                "ieee8021x=0",
                "wpa=0",
            ]
        )
    elif ap_mode == "wpa2":
        lines.extend(
            [
                "wpa=2",
                "wpa_key_mgmt=WPA-PSK",
                "wpa_pairwise=CCMP",
                "rsn_pairwise=CCMP",
                f"wpa_passphrase={WPA2_PASSPHRASE}",
            ]
        )
    elif ap_mode == "macfilter":
        lines.extend(
            [
                "macaddr_acl=1",
                f"accept_mac_file={allowed_macs_file}",
            ]
        )

    return "\n".join(lines) + "\n"


def hwsim_client_network_config(ap_mode, ssid, supported_modes=HWSIM_AP_MODES):
    validate_hwsim_ap_mode(ap_mode, supported_modes)

    lines = [
        "network={",
        f'    ssid="{ssid}"',
    ]

    if ap_mode == "hidden":
        lines.extend(
            [
                "    scan_ssid=1",
                "    key_mgmt=NONE",
            ]
        )
    elif ap_mode == "wep":
        lines.extend(
            [
                "    key_mgmt=NONE",
                f"    wep_key0={WEP_KEY_HEX}",
                "    wep_tx_keyidx=0",
            ]
        )
    elif ap_mode == "wpa2":
        lines.extend(
            [
                "    key_mgmt=WPA-PSK",
                f'    psk="{WPA2_PASSPHRASE}"',
            ]
        )
    else:
        lines.append("    key_mgmt=NONE")

    lines.append("}")
    return "\n".join(lines) + "\n"


def hwsim_ap_mode_state(prefix, ap_mode):
    validate_hwsim_ap_mode(ap_mode, HWSIM_MACFILTER_AP_MODES)
    return f"{prefix}-{ap_mode}\n"


def interface_driver(interface):
    driver_path = Path("/sys/class/net") / interface / "device" / "driver"
    if not driver_path.exists():
        return ""

    try:
        return driver_path.resolve(strict=True).name
    except OSError:
        return ""


def wait_for_hwsim_interfaces(required_interfaces, timeout=10):
    deadline = time.time() + timeout

    while time.time() < deadline:
        missing_or_wrong_driver = [
            interface
            for interface in required_interfaces
            if interface_driver(interface) != "mac80211_hwsim"
        ]
        if not missing_or_wrong_driver:
            return
        time.sleep(0.5)

    print("ERROR: required HWSIM interfaces were not created with mac80211_hwsim.")
    for interface in required_interfaces:
        driver = interface_driver(interface) or "missing"
        print(f"  {interface}: {driver}")
    sys.exit(1)


def networkmanager_is_active():
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", "NetworkManager"],
        check=False,
    )
    return result.returncode == 0


def networkmanager_device_state(interface):
    result = subprocess.run(
        ["nmcli", "-t", "-f", "DEVICE,STATE", "device", "status"],
        capture_output=True,
        text=True,
        check=True,
    )

    for line in result.stdout.splitlines():
        device, _, state = line.partition(":")
        if device == interface:
            return state

    return "not-listed"


def mark_hwsim_interfaces_unmanaged(required_interfaces, timeout=10):
    wait_for_hwsim_interfaces(required_interfaces, timeout=timeout)

    if shutil.which("nmcli") is None:
        if networkmanager_is_active():
            print("ERROR: NetworkManager is active but nmcli is not available.")
            sys.exit(1)
        print("NetworkManager is not active; skipping HWSIM unmanaged check.")
        return

    for interface in required_interfaces:
        try:
            subprocess.run(
                ["nmcli", "device", "set", interface, "managed", "no"],
                check=True,
            )
        except subprocess.CalledProcessError:
            print(f"ERROR: failed to mark HWSIM interface unmanaged: {interface}")
            sys.exit(1)

    deadline = time.time() + timeout
    states = {}

    while time.time() < deadline:
        try:
            states = {
                interface: networkmanager_device_state(interface)
                for interface in required_interfaces
            }
        except subprocess.CalledProcessError:
            print("ERROR: failed to query NetworkManager device state with nmcli.")
            sys.exit(1)

        if all(state == "unmanaged" for state in states.values()):
            print(
                "Marked HWSIM interfaces unmanaged by NetworkManager: "
                + ", ".join(required_interfaces)
            )
            return

        time.sleep(0.5)

    print("ERROR: NetworkManager still manages required HWSIM interfaces.")
    for interface, state in states.items():
        print(f"  {interface}: {state}")
    sys.exit(1)


def choose_ap_mode(current_mode):
    modes = list(AP_SCRIPT_MAP.keys())

    print()
    print("=== AP Mode Selection ===")
    print(f"YAML default mode: {current_mode}")
    print()

    for index, mode in enumerate(modes, start=1):
        print(f"{index}) {mode}")

    print()
    choice = input("Select AP mode number, or press Enter to use YAML default: ").strip()

    if choice == "":
        return current_mode

    if not choice.isdigit():
        print("ERROR: selection must be a number")
        sys.exit(1)

    choice_number = int(choice)

    if choice_number < 1 or choice_number > len(modes):
        print(f"ERROR: selection must be between 1 and {len(modes)}")
        sys.exit(1)

    return modes[choice_number - 1]


def calculate_required_radios(config):
    devices = config["devices"]

    client_count = (
        devices["hmi"]
        + devices["scada_server"]
        + devices["plc"]
        + devices["rtu"]
        + devices["sensors"]
    )

    ap_radio_count = 1
    total_radios = ap_radio_count + client_count

    return total_radios


def load_hwsim(radio_count):
    print(f"Loading mac80211_hwsim with {radio_count} radios...")

    try:
        subprocess.run(
            ["sudo", "modprobe", "-r", "mac80211_hwsim"],
            check=False,
        )

        subprocess.run(
            ["sudo", "modprobe", "mac80211_hwsim", f"radios={radio_count}"],
            check=True,
        )

    except subprocess.CalledProcessError:
        print("ERROR: failed to load mac80211_hwsim")
        sys.exit(1)


def update_env_values(values):
    env_path = Path(".env")

    if not env_path.exists():
        print("ERROR: .env file not found")
        print("Create it from .env.example before running the orchestrator.")
        sys.exit(1)

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated_lines = []
    found_keys = set()

    for line in lines:
        updated = False

        for key, value in values.items():
            if line.startswith(f"{key}="):
                updated_lines.append(f'{key}="{value}"')
                found_keys.add(key)
                updated = True
                break

        if not updated:
            updated_lines.append(line)

    for key, value in values.items():
        if key not in found_keys:
            updated_lines.append(f'{key}="{value}"')

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    for key, value in values.items():
        print(f"Updated .env {key} to {value}")


def start_ap(config, dry_run=True, ap_mode=None):
    if ap_mode is None:
        ap_mode = choose_ap_mode(config["ap"]["mode"])

    if ap_mode not in AP_SCRIPT_MAP:
        print(f"ERROR: unsupported AP mode: {ap_mode}")
        print(f"Supported AP modes: {', '.join(AP_SCRIPT_MAP.keys())}")
        sys.exit(1)

    script_path = Path(AP_SCRIPT_MAP[ap_mode])

    if not script_path.exists():
        print(f"ERROR: AP script not found: {script_path}")
        sys.exit(1)

    print(f"Selected AP mode: {ap_mode}")
    print(f"Selected AP script: {script_path}")

    if dry_run:
        print("Dry-run enabled: AP script not executed.")
        return

    try:
        subprocess.run(
            ["sudo", "bash", str(script_path)],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(f"ERROR: AP script failed: {script_path}")
        sys.exit(1)
