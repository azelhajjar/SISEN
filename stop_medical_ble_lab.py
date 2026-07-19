#!/usr/bin/env python3

from pathlib import Path
import os
import subprocess
import sys


PROCESS_PATTERNS = [
    "wearable_data_generator.py",
    "ble_wifi_gateway.py",
    "medical-hwsim-hostapd.conf",
    "medical-gateway.conf",
    "192.168.70.10,192.168.70.50",
]
AP_MODE_STATE = Path("/tmp/sisen-ap-mode")
GATEWAY_NAMESPACE = "medical-gateway"


def ensure_root_or_reexec():
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        return

    print()
    print("=== Elevating Medical BLE Cleanup ===")
    print("Medical cleanup needs root for namespaces and root-owned lab processes.")
    print("Re-running this script with sudo now.")
    os.execvp("sudo", ["sudo", sys.executable, *sys.argv])


def run(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


def namespace_exists(namespace):
    result = subprocess.run(
        ["ip", "netns", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    return any(line.split()[0] == namespace for line in result.stdout.splitlines() if line.strip())


def delete_namespace_if_exists(namespace):
    if namespace_exists(namespace):
        run(["ip", "netns", "delete", namespace])
    else:
        print(f"Namespace {namespace} is already absent")


def main():
    print("=== Stopping Medical BLE Lab ===")
    ensure_root_or_reexec()

    for pattern in PROCESS_PATTERNS:
        run(["pkill", "-f", pattern])

    delete_namespace_if_exists(GATEWAY_NAMESPACE)

    try:
        if AP_MODE_STATE.exists() and AP_MODE_STATE.read_text(encoding="utf-8").startswith("medical-hwsim-"):
            AP_MODE_STATE.unlink()
    except OSError:
        pass

    print("Medical BLE lab stopped")


if __name__ == "__main__":
    main()
