#!/usr/bin/env python3

import subprocess


SENSOR_NAMESPACE_PREFIXES = [
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
]
MAX_SENSOR_COUNT = 10


def known_namespaces():
    return [
        f"{prefix}-{index}"
        for index in range(1, MAX_SENSOR_COUNT + 1)
        for prefix in SENSOR_NAMESPACE_PREFIXES
    ]

PROCESS_PATTERNS = [
    "temperature_sensor.py",
    "humidity_sensor.py",
    "air_quality_sensor.py",
    "occupancy_sensor.py",
    "hazard_sensor.py",
    "web/dashboard.py",
]

def run(cmd, check=False):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=check)


def kill_processes():
    print("Stopping HWSIM IoT lab processes...")

    run(["pkill", "wpa_supplicant"])
    run(["pkill", "hostapd"])
    run(["pkill", "dnsmasq"])

    for pattern in PROCESS_PATTERNS:
        run(["pkill", "-f", pattern])


def delete_namespaces():
    print("Deleting HWSIM IoT namespaces...")

    for namespace in known_namespaces():
        run(["ip", "netns", "delete", namespace])


def unload_hwsim():
    print("Unloading mac80211_hwsim...")

    run(["modprobe", "-r", "mac80211_hwsim"])


def delete_temp_files():
    print("Deleting HWSIM temporary files...")

    temp_files = [
        "/tmp/hwsim-hostapd.conf",
        "/tmp/hwsim-hostapd.log",
        "/tmp/hwsim-dnsmasq.conf",
        "/tmp/hwsim-dnsmasq.log",
        "/tmp/hwsim-dashboard.log",
        "/tmp/sisen-ap-mode",
    ]

    for namespace in known_namespaces():
        temp_files.extend(
            [
                f"/tmp/{namespace}.conf",
                f"/tmp/{namespace}-wpa.log",
                f"/tmp/{namespace}-wpa.pid",
                f"/tmp/hwsim-{namespace}-sensor.log",
            ]
        )
    for temp_file in temp_files:
        run(["rm", "-f", temp_file])


def main():
    print("=== Stopping HWSIM IoT Lab ===")

    kill_processes()
    delete_namespaces()
    unload_hwsim()
    delete_temp_files()

    print("HWSIM IoT lab stopped and cleaned up.")


if __name__ == "__main__":
    main()
