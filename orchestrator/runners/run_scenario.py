import sys
import subprocess
import argparse
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config_parser import load_config, validate_config
from orchestrator.wireless import calculate_required_radios, load_hwsim, start_ap
from orchestrator.topology import build_interface_plan


LEGACY_SCENARIO_NAMES = {
    "iot-medical-basic.yml": "smart-building-basic.yml",
}
SCENARIO_LAUNCHER_MAP = {
    "iot": "smart-building",
    "medical_ble": "medical",
    "mqtt_testbed": "mqtt",
    "scada": "scada",
    "sisen_full": "all",
}


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


def python_command(requires_root=False):
    if (
        requires_root
        and os.name == "posix"
        and hasattr(os, "geteuid")
        and os.geteuid() != 0
    ):
        return ["sudo", PYTHON]
    return [PYTHON]


def print_summary(config, radio_count):
    print("=== Scenario Config Loaded ===")
    print(f"Scenario name: {config['scenario']['name']}")
    print(f"Scenario type: {config['scenario']['type']}")
    print(f"AP mode: {config['ap']['mode']}")
    print(f"AP interface: {config['ap']['interface']}")
    print(f"SSID: {config['ap']['ssid']}")
    print(f"Required radios: {radio_count}")


def choose_scenario_file():
    scenarios_dir = PROJECT_ROOT / "scenarios"
    scenario_files = sorted(
        list(scenarios_dir.glob("*.yml")) + list(scenarios_dir.glob("*.yaml"))
    )

    if not scenario_files:
        print("ERROR: no scenario files found in scenarios/")
        sys.exit(1)

    print()
    print("=== Scenario Selection ===")

    for index, scenario_file in enumerate(scenario_files, start=1):
        print(f"{index}) {scenario_file}")

    print()
    choice = input("Select scenario number: ").strip()

    if not choice.isdigit():
        print("ERROR: selection must be a number")
        sys.exit(1)

    choice_number = int(choice)

    if choice_number < 1 or choice_number > len(scenario_files):
        print(f"ERROR: selection must be between 1 and {len(scenario_files)}")
        sys.exit(1)

    return str(scenario_files[choice_number - 1])


def resolve_config_path(config_path):
    path = Path(config_path)
    if path.exists():
        return str(path)

    replacement = LEGACY_SCENARIO_NAMES.get(path.name)
    if replacement:
        replacement_path = path.with_name(replacement)
        if replacement_path.exists():
            print(f"NOTICE: {path} has been renamed to {replacement_path}.")
            return str(replacement_path)

    return config_path


def start_sisen_launcher(scenario, ap_mode=None, no_wait=False, capture_hints=False):
    print()
    print("=== Starting SISEN Launcher ===")
    print(f"Delegating to launch_sisen.py --scenario {scenario}")

    cmd = [
        PYTHON,
        str(PROJECT_ROOT / "launch_sisen.py"),
        "--scenario",
        scenario,
        *(["--ap-mode", ap_mode] if ap_mode else []),
        *(["--no-wait"] if no_wait else []),
        *(["--capture-hints"] if capture_hints else []),
    ]

    try:
        subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))
    except subprocess.CalledProcessError:
        print("ERROR: SISEN launcher failed")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compatibility wrapper for YAML scenario files. "
            "For normal use, prefer launch_sisen.py."
        )
    )
    parser.add_argument("config", nargs="?", help="Scenario YAML file to start.")
    parser.add_argument("--ap-mode", help="Override the AP mode from the scenario YAML.")
    parser.add_argument(
        "--no-wait",
        "--test",
        action="store_true",
        dest="no_wait",
        help="Start the selected scenario and return instead of waiting.",
    )
    parser.add_argument(
        "--capture-hints",
        action="store_true",
        help="Print capture hints in labs that support them.",
    )
    args = parser.parse_args()

    config_path = resolve_config_path(args.config or choose_scenario_file())

    config = load_config(config_path)
    scenario_type = config["scenario"]["type"]
    ap_mode = args.ap_mode or config.get("ap", {}).get("mode", "open")

    if scenario_type == "iot":
        print("=== Scenario Config Loaded ===")
        print(f"Scenario name: {config['scenario']['name']}")
        print(f"Scenario type: {config['scenario']['type']}")
        print(f"Description: {config['scenario'].get('description', 'No description')}")

        start_sisen_launcher(
            SCENARIO_LAUNCHER_MAP[scenario_type],
            ap_mode=ap_mode,
            no_wait=args.no_wait,
            capture_hints=args.capture_hints,
        )
        return

    if scenario_type == "medical_ble":
        print("=== Scenario Config Loaded ===")
        print(f"Scenario name: {config['scenario']['name']}")
        print(f"Scenario type: {config['scenario']['type']}")
        print(f"Description: {config['scenario'].get('description', 'No description')}")

        start_sisen_launcher(
            SCENARIO_LAUNCHER_MAP[scenario_type],
            ap_mode=ap_mode,
            no_wait=args.no_wait,
            capture_hints=args.capture_hints,
        )
        return

    if scenario_type == "mqtt_testbed":
        print("=== Scenario Config Loaded ===")
        print(f"Scenario name: {config['scenario']['name']}")
        print(f"Scenario type: {config['scenario']['type']}")
        print(f"Description: {config['scenario'].get('description', 'No description')}")

        start_sisen_launcher(
            SCENARIO_LAUNCHER_MAP[scenario_type],
            ap_mode=ap_mode,
            no_wait=args.no_wait,
            capture_hints=args.capture_hints,
        )
        return

    if scenario_type == "sisen_full":
        print("=== Scenario Config Loaded ===")
        print(f"Scenario name: {config['scenario']['name']}")
        print(f"Scenario type: {config['scenario']['type']}")
        print(f"Description: {config['scenario'].get('description', 'No description')}")

        start_sisen_launcher(
            SCENARIO_LAUNCHER_MAP[scenario_type],
            ap_mode=ap_mode,
            no_wait=args.no_wait,
            capture_hints=args.capture_hints,
        )
        return

    if scenario_type == "scada":
        print("=== Scenario Config Loaded ===")
        print(f"Scenario name: {config['scenario']['name']}")
        print(f"Scenario type: {config['scenario']['type']}")
        print(f"Description: {config['scenario'].get('description', 'No description')}")

        start_sisen_launcher(
            SCENARIO_LAUNCHER_MAP[scenario_type],
            ap_mode=ap_mode,
            no_wait=args.no_wait,
            capture_hints=args.capture_hints,
        )
        return

    validate_config(config)

    radio_count = calculate_required_radios(config)
    interface_plan = build_interface_plan(config)

    print_summary(config, radio_count)

    print()
    print("=== Interface Plan ===")

    for device in interface_plan:
        print(f"{device['interface']} -> {device['name']} ({device['role']})")

    # Disabled for now because running hwsim/AP scripts can destabilise the VM during development.
    # load_hwsim(radio_count)

    start_ap(config, dry_run=False, ap_mode=args.ap_mode)

if __name__ == "__main__":
    main()
