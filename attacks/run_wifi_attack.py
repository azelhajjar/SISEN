#!/usr/bin/env python3
"""Bounded SISEN Wi-Fi layer attack demonstrations.

These demos are intentionally conservative. They simulate availability impacts
inside the HWSIM Smart Building lab by temporarily bringing one or more sensor
interfaces down, then restoring them.
"""

import argparse
import os
import subprocess
import sys
import time


BUILDING_CLIENTS = {
    "temperature": ("temp-sensor-1", "wlan1"),
    "fire-alarm": ("fire-alarm-1", "wlan2"),
    "occupancy": ("occupancy-1", "wlan3"),
    "gas-leak": ("gas-leak-1", "wlan4"),
    "humidity": ("humidity-sensor-1", "wlan5"),
    "air-quality": ("air-quality-1", "wlan6"),
    "smoke": ("smoke-detector-1", "wlan7"),
    "co2": ("co2-detector-1", "wlan8"),
    "exit-status": ("exit-status-1", "wlan9"),
    "sprinkler-status": ("sprinkler-status-1", "wlan10"),
}


def require_root():
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() != 0:
        print("ERROR: Wi-Fi layer demos need root privileges for ip netns operations.", file=sys.stderr)
        print("Run with sudo, for example:", file=sys.stderr)
        print(
            "  sudo python3 attacks/run_attack.py --category availability --scenario building --attack client-drop --target temperature",
            file=sys.stderr,
        )
        sys.exit(1)


def run(cmd):
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


def namespace_exists(namespace):
    result = subprocess.run(
        ["ip", "netns", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    return any(line.split()[0] == namespace for line in result.stdout.splitlines() if line.strip())


def set_client_link(target, state):
    namespace, interface = BUILDING_CLIENTS[target]
    run(["ip", "netns", "exec", namespace, "ip", "link", "set", interface, state])


def run_client_drop(target, duration):
    namespace, interface = BUILDING_CLIENTS[target]
    if not namespace_exists(namespace):
        print(f"ERROR: target {target} is not present in the running Smart Building node set.", file=sys.stderr)
        print("Start the scenario with enough nodes for this sensor, or choose a visible target.", file=sys.stderr)
        sys.exit(1)
    print(f"Temporarily disconnecting {target} sensor ({namespace}/{interface}) for {duration}s")
    set_client_link(target, "down")
    time.sleep(duration)
    set_client_link(target, "up")
    print(f"Restored {target} sensor interface")


def run_sensor_blackout(duration):
    print(f"Temporarily disconnecting all Smart Building sensor interfaces for {duration}s")
    active_targets = [
        target
        for target, (namespace, _interface) in BUILDING_CLIENTS.items()
        if namespace_exists(namespace)
    ]
    if not active_targets:
        print("ERROR: no Smart Building sensor namespaces are present.", file=sys.stderr)
        sys.exit(1)
    for target in active_targets:
        set_client_link(target, "down")
    time.sleep(duration)
    for target in active_targets:
        set_client_link(target, "up")
    print("Restored all Smart Building sensor interfaces")


def main():
    parser = argparse.ArgumentParser(description="Run bounded Wi-Fi layer SISEN attack demonstrations.")
    parser.add_argument("--scenario", choices=("building",), default="building")
    parser.add_argument("--attack", choices=("client-drop", "sensor-blackout"), required=True)
    parser.add_argument("--target", choices=sorted(BUILDING_CLIENTS), default="temperature")
    parser.add_argument("--duration", type=int, default=10)
    args = parser.parse_args()

    if args.duration < 1 or args.duration > 120:
        parser.error("--duration must be between 1 and 120 seconds")

    require_root()

    print(f"SISEN Wi-Fi attack demo: {args.attack}")
    print(f"Scenario: {args.scenario}")
    print()

    if args.attack == "client-drop":
        run_client_drop(args.target, args.duration)
    elif args.attack == "sensor-blackout":
        run_sensor_blackout(args.duration)


if __name__ == "__main__":
    main()
