#!/usr/bin/env python3
"""Category-aware SISEN attack runner.

This is a teaching wrapper around the bounded attack helpers in this directory.
It groups attacks using the same categories as the SISEN documentation while
leaving the scenario/lab lifecycle under the normal launcher scripts.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


ATTACK_ROOT = Path(__file__).resolve().parent
REPO_ROOT = ATTACK_ROOT.parent
REEXEC_ENV = "SISEN_ATTACK_RUNNER_REEXEC"


def _project_python():
    return REPO_ROOT / ".venv" / "bin" / "python"


def _running_project_python(project_python):
    current = Path(sys.executable or "").absolute()
    venv_bin = project_python.parent.absolute()
    return current == project_python.absolute() or current.parent == venv_bin


def _reexec_with_project_python():
    project_python = _project_python()
    if not project_python.exists():
        return

    if not os.access(project_python, os.X_OK):
        raise SystemExit(
            f"ERROR: project Python exists but is not executable: {project_python}\n"
            "Run setup.sh again or fix the virtual environment permissions."
        )

    if os.environ.get(REEXEC_ENV) == "1" or _running_project_python(project_python):
        return

    env = os.environ.copy()
    env[REEXEC_ENV] = "1"
    os.execve(str(project_python), [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]], env)


_reexec_with_project_python()

PYTHON = sys.executable or "python3"
GREEN = "\033[32m"
RESET = "\033[0m"

CATEGORY_LABELS = {
    "confidentiality": "Observation and Confidentiality Attacks",
    "authenticity": "Identity, Authenticity, and Spoofing Attacks",
    "integrity": "Data Integrity and Manipulation Attacks",
    "replay": "Replay and Message Freshness Attacks",
    "availability": "Availability and Disruption Attacks",
    "protocol": "Protocol and Communication-Path Attacks",
    "safety-case": "Scenario-Focused Safety Cases",
}

LIST_CATEGORY_ORDER = {
    "safety-case": 0,
    "authenticity": 1,
    "integrity": 2,
    "replay": 3,
    "availability": 4,
    "protocol": 5,
    "confidentiality": 6,
}

SCENARIO_ALIASES = {
    "smart-building": "building",
}

CATALOG = [
    {
        "category": "availability",
        "scenario": "building",
        "attack": "client-drop",
        "description": "Temporarily disconnect one Smart Building room/zone interface.",
        "engine": "wifi",
    },
    {
        "category": "availability",
        "scenario": "building",
        "attack": "sensor-blackout",
        "description": "Temporarily disconnect all Smart Building room/zone interfaces.",
        "engine": "wifi",
    },
    {
        "category": "authenticity",
        "scenario": "6lowpan",
        "attack": "spoofed",
        "description": "Inject spoofed 6LoWPAN telemetry through the validated path.",
        "engine": "6lowpan",
    },
    {
        "category": "availability",
        "scenario": "6lowpan",
        "attack": "missing",
        "description": "Inject missing-telemetry activity in the 6LoWPAN path.",
        "engine": "6lowpan",
    },
    {
        "category": "integrity",
        "scenario": "6lowpan",
        "attack": "extreme",
        "description": "Inject an extreme 6LoWPAN telemetry value.",
        "engine": "6lowpan",
    },
    {
        "category": "replay",
        "scenario": "6lowpan",
        "attack": "replay",
        "description": "Replay stale 6LoWPAN telemetry through the validated path.",
        "engine": "6lowpan",
    },
]

for attack, description in (
    ("spoofed", "6LoWPAN protocol-path spoofing over the validated UDP telemetry path."),
    ("missing", "6LoWPAN protocol-path missing-telemetry activity."),
    ("extreme", "6LoWPAN protocol-path delivery of an extreme telemetry value."),
    ("replay", "6LoWPAN protocol-path replay of stale telemetry."),
):
    CATALOG.append(
        {
            "category": "protocol",
            "scenario": "6lowpan",
            "attack": attack,
            "description": description,
            "engine": "6lowpan",
        }
    )

for scenario in ("building", "medical"):
    for category, attack in (
        ("authenticity", "spoofed"),
        ("integrity", "extreme"),
        ("replay", "replay"),
        ("availability", "noise"),
        ("integrity", "malformed"),
    ):
        CATALOG.append(
            {
                "category": category,
                "scenario": scenario,
                "attack": attack,
                "description": f"Publish bounded {attack} telemetry for {scenario}.",
                "engine": "mqtt",
            }
        )

WIFI_MANUAL_ACTIVITIES = [
    {
        "category": "confidentiality",
        "attack": "open-ap-capture",
        "description": "Observe open-AP traffic for the selected scenario.",
        "manual_focus": "wireless observation",
    },
    {
        "category": "confidentiality",
        "attack": "wep-capture",
        "description": "Capture WEP protected frames and IVs for the selected scenario.",
        "manual_focus": "WEP capture",
    },
    {
        "category": "confidentiality",
        "attack": "wpa2-handshake-capture",
        "description": "Capture WPA2 EAPOL handshake traffic for the selected scenario.",
        "manual_focus": "WPA2 handshake capture",
    },
    {
        "category": "protocol",
        "attack": "hidden-ssid-observation",
        "description": "Observe hidden SSID disclosure during client association.",
        "manual_focus": "hidden SSID observation",
    },
    {
        "category": "authenticity",
        "attack": "rogue-ap-observation",
        "description": "Compare legitimate AP identity with a rogue or evil-twin AP.",
        "manual_focus": "infrastructure impersonation",
    },
]

for scenario in ("building", "medical", "6lowpan"):
    for activity in WIFI_MANUAL_ACTIVITIES:
        CATALOG.append(
            {
                **activity,
                "scenario": scenario,
                "engine": "manual",
            }
        )

CATALOG.extend(
    [
        {
            "category": "authenticity",
            "scenario": "building",
            "attack": "mac-filter-bypass",
            "description": "Spoof an allowed Smart Building sensor MAC to test MAC-filter trust assumptions.",
            "engine": "manual",
            "manual_focus": "MAC identity bypass",
        },
        {
            "category": "protocol",
            "scenario": "medical",
            "attack": "gateway-path-capture",
            "description": "Capture Medical IoT AP, gateway namespace, and patient MQTT path.",
            "engine": "manual",
            "manual_focus": "medical gateway path",
        },
        {
            "category": "protocol",
            "scenario": "6lowpan",
            "attack": "lowpan-path-capture",
            "description": "Capture wpan, lowpan0, border, node2, and MQTT relay paths.",
            "engine": "manual",
            "manual_focus": "6LoWPAN path tracing",
        },
        {
            "category": "safety-case",
            "scenario": "building",
            "attack": "gas-leak-hidden",
            "description": "Room 101 shows gas leak as normal while occupancy and temperature remain plausible.",
            "engine": "mqtt",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "building",
            "attack": "fire-alarm-suppressed",
            "description": "Room 101 shows the fire alarm as normal while temperature suggests unsafe conditions.",
            "engine": "mqtt",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "building",
            "attack": "blocked-exit-hidden",
            "description": "Server Room shows smoke while exit and sprinkler status remain falsely reassuring.",
            "engine": "mqtt",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "medical",
            "attack": "critical-vitals",
            "description": "Medical IoT shorthand for unsafe patient vital signs.",
            "engine": "mqtt",
            "engine_attack": "extreme",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "medical",
            "attack": "fall-alert-suppressed",
            "description": "Patient 1 shows concerning vitals while the fall alert remains falsely normal.",
            "engine": "mqtt",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "medical",
            "attack": "panic-button-suppressed",
            "description": "Patient 1 shows unsafe vitals while the panic button remains falsely normal.",
            "engine": "mqtt",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "medical",
            "attack": "battery-falsely-normal",
            "description": "Patient 1 reports battery as normal, illustrating hidden wearable reliability risk.",
            "engine": "mqtt",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "6lowpan",
            "attack": "boiler-pressure-masked",
            "description": "Boiler Room pressure is reported normal while other process readings suggest danger.",
            "engine": "6lowpan",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "6lowpan",
            "attack": "emergency-stop-hidden",
            "description": "Boiler Room emergency stop remains falsely ready during abnormal pressure.",
            "engine": "6lowpan",
            "featured": True,
        },
        {
            "category": "safety-case",
            "scenario": "6lowpan",
            "attack": "machine-overheat-hidden",
            "description": "Process Line overheat is hidden while the temperature is unsafe.",
            "engine": "6lowpan",
            "featured": True,
        },
    ]
)


def normalize_scenario(scenario):
    return SCENARIO_ALIASES.get(scenario, scenario)


def catalog_matches(category=None, scenario=None, attack=None):
    scenario = normalize_scenario(scenario) if scenario else None
    matches = []
    for item in CATALOG:
        if category and item["category"] != category:
            continue
        if scenario and item["scenario"] != scenario:
            continue
        if attack and item["attack"] != attack:
            continue
        matches.append(item)
    return matches


def list_attacks(args):
    matches = catalog_matches(args.category, args.scenario, args.attack)
    if not matches:
        print("No attacks matched the selected filters.")
        return

    helpers = [item for item in matches if item["engine"] != "manual"]
    manuals = [item for item in matches if item["engine"] == "manual"]

    print()
    print(f"{GREEN}SISEN activities are for the controlled lab only; run them inside the prepared namespaces/scenarios, not on live networks.{RESET}")

    if helpers:
        print()
        print("Helper-based activities")
        print(
            f"{'Scenario':13} {'Security Focus':16} {'Activity':26} "
            f"Safety context"
        )
        print(
            f"{'-' * 13} {'-' * 16} {'-' * 26} "
            f"{'-' * 60}"
        )
    for item in sorted(helpers, key=list_sort_key):
        print(
            f"{item['scenario']:13} {item['category']:16} "
            f"{item['attack']:26} {item['description']}"
        )

    if manuals:
        print()
        print("Manual infrastructure activities")
        print("Run these from a separate terminal; use monitor mode where required. See teaching-materials/manual-attacks/.")
        print(
            f"{'Scenario':13} {'Activity':26} {'Focus':30} "
            f"Notes"
        )
        print(
            f"{'-' * 13} {'-' * 26} {'-' * 30} "
            f"{'-' * 50}"
        )
    for item in sorted(manuals, key=list_sort_key):
        print(
            f"{item['scenario']:13} {item['attack']:26} "
            f"{item.get('manual_focus', item['category']):30} {item['description']}"
        )


def list_sort_key(item):
    manual = item["engine"] == "manual"
    if manual:
        manual_group_order = {
            "lowpan-path-capture": 0,
            "gateway-path-capture": 1,
            "mac-filter-bypass": 2,
            "rogue-ap-observation": 3,
            "hidden-ssid-observation": 4,
            "open-ap-capture": 5,
            "wep-capture": 6,
            "wpa2-handshake-capture": 7,
        }
        scenario_order = {"building": 0, "medical": 1, "6lowpan": 2}
        return (
            1,
            manual_group_order.get(item["attack"], 99),
            scenario_order.get(item["scenario"], 99),
            item["attack"],
        )

    return (
        0,
        0 if item.get("featured") else 1,
        LIST_CATEGORY_ORDER.get(item["category"], 99),
        item["scenario"],
        item["attack"],
    )


def wifi_command(item, args):
    command = [
        PYTHON,
        str(ATTACK_ROOT / "run_wifi_attack.py"),
        "--attack",
        item.get("engine_attack", item["attack"]),
        "--duration",
        str(args.duration),
    ]
    if item["attack"] == "client-drop":
        command.extend(["--target", args.target])
    return command


def mqtt_command(item, args):
    command = [
        PYTHON,
        str(ATTACK_ROOT / "run_mqtt_attack.py"),
        "--scenario",
        item["scenario"],
        "--attack",
        item.get("engine_attack", item["attack"]),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--count",
        str(args.count),
        "--delay",
        str(args.delay),
        "--duration",
        str(args.duration),
    ]
    return command


def sixlowpan_command(item, args):
    command = [
        "bash",
        str(ATTACK_ROOT / "run_attack_mode.sh"),
        item.get("engine_attack", item["attack"]),
    ]
    if args.ap_mode:
        command.extend(["--ap-mode", args.ap_mode])
    if args.interactive:
        command.append("--interactive")
    if args.keep_ap:
        command.append("--keep-ap")
    return command


ENGINE_COMMANDS = {
    "wifi": wifi_command,
    "mqtt": mqtt_command,
    "6lowpan": sixlowpan_command,
}


def manual_placeholder(item):
    return (
        "This is a manual infrastructure activity.\n"
        "Run the scenario first, then perform the capture, monitor-mode, or "
        "infrastructure observation steps from a separate terminal. "
        "Detailed instructions: teaching-materials/manual-attacks/."
    )


def run_selected_attack(args):
    if not args.category or not args.scenario or not args.attack:
        raise SystemExit("--category, --scenario, and --attack are required unless --list is used")

    matches = catalog_matches(args.category, args.scenario, args.attack)
    if not matches:
        raise SystemExit("No matching attack. Run with --list to see available attacks.")
    if len(matches) > 1:
        raise SystemExit("Attack selection is ambiguous. Add more filters.")

    item = matches[0]
    if item["engine"] == "manual":
        print(f"Category: {CATEGORY_LABELS[item['category']]}")
        print(f"Scenario: {item['scenario']}")
        print(f"Attack: {item['attack']}")
        print("Engine: manual")
        print(manual_placeholder(item))
        return

    command = ENGINE_COMMANDS[item["engine"]](item, args)
    print(f"Category: {CATEGORY_LABELS[item['category']]}")
    print(f"Scenario: {item['scenario']}")
    print(f"Attack: {item['attack']}")
    print(f"Engine: {item['engine']}")
    print(f"+ {' '.join(command)}")
    env = os.environ.copy()
    env["SISEN_PYTHON"] = PYTHON
    subprocess.run(command, check=False, env=env)


def parse_args():
    parser = argparse.ArgumentParser(description="Run or list categorized SISEN attack demonstrations.")
    parser.add_argument("--list", action="store_true", help="List available attacks instead of running one.")
    parser.add_argument("--category", choices=sorted(CATEGORY_LABELS))
    parser.add_argument("--scenario", help="Scenario name, for example building, medical, or 6lowpan.")
    parser.add_argument("--attack", help="Attack name within the selected category and scenario.")
    parser.add_argument("--target", default="room-101", help="Smart Building client-drop target.")
    parser.add_argument("--duration", type=int, default=10, help="Infrastructure disruption or MQTT refresh duration in seconds.")
    parser.add_argument("--host", default="localhost", help="MQTT broker host.")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port.")
    parser.add_argument("--count", type=int, default=5, help="Repeat count for replay/noise telemetry attacks.")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between MQTT publishes.")
    parser.add_argument("--ap-mode", choices=("open", "wpa2", "wpa2-enterprise", "wpa2e"))
    parser.add_argument("--interactive", action="store_true", help="Pass interactive mode to supported 6LoWPAN attacks.")
    parser.add_argument("--keep-ap", action="store_true", help="Keep AP running after supported 6LoWPAN attacks.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.list:
        list_attacks(args)
        return

    run_selected_attack(args)


if __name__ == "__main__":
    main()
