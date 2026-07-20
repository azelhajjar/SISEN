#!/usr/bin/env python3
import argparse
import json
import os
import random
import socket
import time
from datetime import datetime, timezone


ASSET_PROFILES = [
    {
        "sensor_id": "TEMP-BLR,GAS-BLR,PRESS-BLR,ESTOP-BLR",
        "label": "Boiler Room",
        "unit": "mixed",
        "fields": {
            "temperature": {"base": 24.0, "step": 0.1},
            "gas_leak": {"normal_values": ["Normal"], "hazard_values": ["Gas detected"]},
            "pressure_status": {"normal_values": ["Normal"], "hazard_values": ["Pressure abnormal"]},
            "emergency_stop": {"normal_values": ["Ready"], "hazard_values": ["Emergency stop active"]},
        },
    },
    {
        "sensor_id": "TEMP-LINE,HUM-LINE,OVERHEAT-LINE,ESTOP-LINE",
        "label": "Process Line",
        "unit": "mixed",
        "fields": {
            "temperature": {"base": 26.0, "step": 0.2},
            "humidity": {"base": 48.0, "step": 0.2},
            "machine_overheat": {"normal_values": ["Normal"], "hazard_values": ["Overheat detected"]},
            "emergency_stop": {"normal_values": ["Ready"], "hazard_values": ["Emergency stop active"]},
        },
    },
    {
        "sensor_id": "TEMP-COLD,HUM-COLD,DOOR-COLD,AIR-COLD",
        "label": "Cold Storage",
        "unit": "mixed",
        "fields": {
            "temperature": {"base": 5.0, "step": 0.1},
            "humidity": {"base": 42.0, "step": 0.2},
            "occupancy": {"values": ["Vacant", "Occupied"]},
            "air_quality": {"base": 410.0, "step": 4.0},
        },
    },
    {
        "sensor_id": "TEMP-BAY,GAS-BAY,OCC-BAY,AIR-BAY",
        "label": "Loading Bay",
        "unit": "mixed",
        "fields": {
            "temperature": {"base": 21.0, "step": 0.1},
            "gas_leak": {"normal_values": ["Normal"], "hazard_values": ["Gas detected"]},
            "occupancy": {"values": ["Occupied", "Vacant"]},
            "air_quality": {"base": 460.0, "step": 5.0},
        },
    },
]

INCIDENT_MODE = os.getenv("SISEN_INCIDENT_MODE") == "1"


def build_reading(sequence, sensor_nodes):
    sensor_nodes = max(1, sensor_nodes)
    node_index = (sequence % sensor_nodes) + 1
    profile = ASSET_PROFILES[(node_index - 1) % len(ASSET_PROFILES)]
    instance = ((node_index - 1) // len(ASSET_PROFILES)) + 1
    reading = {
        "sensor_id": profile["sensor_id"],
        "node_id": f"node-{node_index:02d}",
        "label": profile["label"] if instance == 1 else f"{profile['label']} {instance}",
        "unit": profile["unit"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    cycle = sequence // sensor_nodes
    for field, spec in profile["fields"].items():
        if "normal_values" in spec:
            values = spec["normal_values"]
            if INCIDENT_MODE and random.random() < 0.08:
                values = spec.get("hazard_values", values)
            reading[field] = random.choice(values)
        elif "values" in spec:
            reading[field] = spec["values"][(sequence + instance - 1) % len(spec["values"])]
        else:
            jitter = random.uniform(-0.3, 0.3) if field != "air_quality" else random.uniform(-8.0, 8.0)
            reading[field] = round(
                spec["base"] + (instance * spec["step"]) + (cycle * spec["step"]) + jitter,
                1,
            )

    return reading


def legacy_temperature_reading(sequence):
    return {
        "sensor_id": "temp-01",
        "temperature": round(22.4 + (sequence * 0.1), 1),
        "unit": "C",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Send minimal UDP JSON sensor readings over IPv6.")
    parser.add_argument("--source", default=None, help="Optional source IPv6 address to bind.")
    parser.add_argument("--dest", required=True, help="Destination IPv6 address.")
    parser.add_argument("--port", type=int, default=9999, help="Destination UDP port.")
    parser.add_argument("--count", type=int, default=1, help="Number of readings to send. Use 0 for continuous mode.")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between readings.")
    parser.add_argument("--sensor-nodes", type=int, default=4, help="Number of logical industrial assets to cycle through.")
    parser.add_argument(
        "--legacy-temperature-only",
        action="store_true",
        help="Send only the Milestone 4 temperature payload shape.",
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    if args.source:
        sock.bind((args.source, 0))

    sequence = 0
    while args.count == 0 or sequence < args.count:
        if args.legacy_temperature_only:
            reading = legacy_temperature_reading(sequence)
        else:
            reading = build_reading(sequence, args.sensor_nodes)
        payload = json.dumps(reading, separators=(",", ":")).encode("utf-8")
        sock.sendto(payload, (args.dest, args.port))
        total = "continuous" if args.count == 0 else str(args.count)
        print(f"sent reading {sequence + 1}/{total}: {json.dumps(reading)}", flush=True)
        sequence += 1
        if args.count == 0 or sequence < args.count:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()

