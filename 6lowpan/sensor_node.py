#!/usr/bin/env python3
import argparse
import json
import os
import random
import socket
import time
from datetime import datetime, timezone


SENSOR_SEQUENCE = [
    {
        "prefix": "temp",
        "label": "Temperature Sensor",
        "field": "temperature",
        "unit": "C",
        "base": 22.4,
        "step": 0.1,
    },
    {
        "prefix": "gas-leak",
        "label": "Gas Leak Detector",
        "field": "gas_leak",
        "unit": "state",
        "normal_values": ["Normal"],
        "hazard_values": ["Gas detected"],
    },
    {
        "prefix": "pressure",
        "label": "Pressure Safety Sensor",
        "field": "pressure_status",
        "unit": "state",
        "normal_values": ["Normal"],
        "hazard_values": ["Pressure abnormal"],
    },
    {
        "prefix": "emergency-stop",
        "label": "Emergency Stop Monitor",
        "field": "emergency_stop",
        "unit": "state",
        "normal_values": ["Ready"],
        "hazard_values": ["Emergency stop active"],
    },
    {
        "prefix": "humidity",
        "label": "Humidity Sensor",
        "field": "humidity",
        "unit": "%",
        "base": 48.0,
        "step": 0.2,
    },
    {
        "prefix": "occupancy",
        "label": "Occupancy Sensor",
        "field": "occupancy",
        "unit": "state",
        "values": ["Occupied", "Vacant"],
    },
    {
        "prefix": "air-quality",
        "label": "Air Quality Sensor",
        "field": "air_quality",
        "unit": "ppm",
        "base": 420.0,
        "step": 5.0,
    },
    {
        "prefix": "overheat",
        "label": "Machine Overheat Sensor",
        "field": "machine_overheat",
        "unit": "state",
        "normal_values": ["Normal"],
        "hazard_values": ["Overheat detected"],
    },
]

INCIDENT_MODE = os.getenv("SISEN_INCIDENT_MODE") == "1"


def build_reading(sequence, sensor_nodes):
    sensor_nodes = max(1, sensor_nodes)
    node_index = (sequence % sensor_nodes) + 1
    sensor = SENSOR_SEQUENCE[(node_index - 1) % len(SENSOR_SEQUENCE)]
    instance = ((node_index - 1) // len(SENSOR_SEQUENCE)) + 1
    sensor_id = f"{sensor['prefix']}-{instance:02d}"
    reading = {
        "sensor_id": sensor_id,
        "node_id": f"node-{node_index:02d}",
        "label": f"{sensor['label']} {instance}",
        "unit": sensor["unit"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if "normal_values" in sensor:
        values = sensor["normal_values"]
        if INCIDENT_MODE and random.random() < 0.08:
            values = sensor.get("hazard_values", values)
        reading[sensor["field"]] = random.choice(values)
    elif "values" in sensor:
        reading[sensor["field"]] = sensor["values"][(sequence + instance - 1) % len(sensor["values"])]
    else:
        cycle = sequence // sensor_nodes
        jitter = random.uniform(-0.3, 0.3) if sensor["field"] != "air_quality" else random.uniform(-8.0, 8.0)
        reading[sensor["field"]] = round(
            sensor["base"] + (instance * sensor["step"]) + (cycle * sensor["step"]) + jitter,
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
    parser.add_argument("--sensor-nodes", type=int, default=4, help="Number of logical sensor nodes to cycle through.")
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

