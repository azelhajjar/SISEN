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
    "room-101": ("room-101", "wlan1"),
    "plant-room": ("plant-room", "wlan2"),
    "server-room": ("server-room", "wlan3"),
    "workshop": ("workshop", "wlan4"),
    "room-101-2": ("room-101-2", "wlan5"),
    "plant-room-2": ("plant-room-2", "wlan6"),
    "server-room-2": ("server-room-2", "wlan7"),
    "workshop-2": ("workshop-2", "wlan8"),
    "room-101-3": ("room-101-3", "wlan9"),
    "plant-room-3": ("plant-room-3", "wlan10"),
}


def require_root():
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() != 0:
        print("ERROR: Wi-Fi layer demos need root privileges for ip netns operations.", file=sys.stderr)
        print("Run with sudo, for example:", file=sys.stderr)
        print(
            "  sudo python3 attacks/run_attack.py --category availability --scenario building --attack client-drop --target room-101",
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
        print(f"ERROR: target {target} is not present in the running Smart Building room/zone set.", file=sys.stderr)
        print("Start the scenario with enough nodes for this room/zone, or choose a visible target.", file=sys.stderr)
        sys.exit(1)
    print(f"Temporarily disconnecting {target} room/zone interface ({namespace}/{interface}) for {duration}s")
    set_client_link(target, "down")
    time.sleep(duration)
    set_client_link(target, "up")
    print(f"Restored {target} room/zone interface")


def run_sensor_blackout(duration):
    print(f"Temporarily disconnecting all Smart Building room/zone interfaces for {duration}s")
    active_targets = [
        target
        for target, (namespace, _interface) in BUILDING_CLIENTS.items()
        if namespace_exists(namespace)
    ]
    if not active_targets:
        print("ERROR: no Smart Building room/zone namespaces are present.", file=sys.stderr)
        sys.exit(1)
    for target in active_targets:
        set_client_link(target, "down")
    time.sleep(duration)
    for target in active_targets:
        set_client_link(target, "up")
    print("Restored all Smart Building room/zone interfaces")


def main():
    parser = argparse.ArgumentParser(description="Run bounded Wi-Fi layer SISEN attack demonstrations.")
    parser.add_argument("--scenario", choices=("building",), default="building")
    parser.add_argument("--attack", choices=("client-drop", "sensor-blackout"), required=True)
    parser.add_argument("--target", choices=sorted(BUILDING_CLIENTS), default="room-101")
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
