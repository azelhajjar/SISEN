#!/usr/bin/env python3

import argparse
import json
import time
from pathlib import Path

import paho.mqtt.publish as publish


INPUT_FILE = Path("/tmp/sisen-wearable-data.json")
DEFAULT_BROKER = "localhost"

TOPICS = {
    "heart_rate": "patient/vitals/heart_rate",
    "spo2": "patient/vitals/spo2",
    "blood_pressure": "patient/vitals/blood_pressure",
}
VITAL_FIELDS = ("heart_rate", "spo2", "blood_pressure")
ALERT_FIELDS = ("fall_alert", "panic_button", "battery_status", "wearable_link")
META_FIELDS = ("ble_address",)


def normalise_patients(vitals):
    if isinstance(vitals, dict) and isinstance(vitals.get("patients"), list):
        patients = vitals["patients"]
    elif isinstance(vitals, dict):
        patients = [vitals]
    else:
        patients = []

    normalised = []
    for index, patient in enumerate(patients, start=1):
        if not isinstance(patient, dict):
            continue
        patient_id = patient.get("patient_id") or f"patient-{index}"
        item = dict(patient)
        item["patient_id"] = patient_id
        item["label"] = patient.get("label") or f"Patient {index}"
        item["ble_address"] = patient.get("ble_address") or f"D0:7A:5E:10:{index:02X}:01"
        normalised.append(item)
    return normalised


def publish_patient_vitals(patient, broker, port):
    patient_id = patient["patient_id"]
    for field in VITAL_FIELDS:
        if field in patient:
            publish.single(f"patient/{patient_id}/vitals/{field}", str(patient[field]), hostname=broker, port=port)
    for field in ALERT_FIELDS:
        if field in patient:
            publish.single(f"patient/{patient_id}/alerts/{field}", str(patient[field]), hostname=broker, port=port)
    for field in META_FIELDS:
        if field in patient:
            publish.single(f"patient/{patient_id}/meta/{field}", str(patient[field]), hostname=broker, port=port)


def publish_aggregate_vitals(patient, broker, port):
    for field, topic in TOPICS.items():
        if field in patient:
            publish.single(topic, str(patient[field]), hostname=broker, port=port)


def publish_vitals(vitals, broker, port):
    patients = normalise_patients(vitals)
    if not patients:
        return []

    for patient in patients:
        publish_patient_vitals(patient, broker, port)

    publish_aggregate_vitals(patients[0], broker, port)
    return patients


def main():
    parser = argparse.ArgumentParser(description="Bridge simulated BLE wearable data to MQTT patient vitals.")
    parser.add_argument("--broker", default=DEFAULT_BROKER, help="MQTT broker hostname or IP.")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port.")
    args = parser.parse_args()

    print("BLE-to-WiFi gateway started")
    print(f"Reading simulated BLE data from {INPUT_FILE}")
    print(f"Publishing to MQTT topics under patient/# via {args.broker}:{args.port}")
    print()

    last_payload = None

    while True:
        if not INPUT_FILE.exists():
            print("Waiting for wearable data...")
            time.sleep(2)
            continue

        try:
            payload = INPUT_FILE.read_text()
            vitals = json.loads(payload)
        except json.JSONDecodeError:
            print("Invalid wearable data, skipping")
            time.sleep(2)
            continue

        if payload != last_payload:
            patients = publish_vitals(vitals, args.broker, args.port)
            last_payload = payload

            if patients:
                summary = ", ".join(
                    f"{patient['label']}: HR={patient.get('heart_rate')} bpm, "
                    f"SpO2={patient.get('spo2')}%, BP={patient.get('blood_pressure')}, "
                    f"Fall={patient.get('fall_alert')}, Panic={patient.get('panic_button')}"
                    for patient in patients
                )
                print(f"Gateway published: {summary}")

        time.sleep(1)


if __name__ == "__main__":
    main()
