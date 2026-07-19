#!/usr/bin/env python3

import json
import os
import random
import time
from pathlib import Path


OUTPUT_FILE = Path("/tmp/sisen-wearable-data.json")
DEFAULT_PATIENT_COUNT = 1
MAX_PATIENT_COUNT = 10
INCIDENT_MODE = os.getenv("SISEN_INCIDENT_MODE") == "1"


def patient_count():
    try:
        count = int(os.environ.get("SISEN_PATIENT_COUNT", str(DEFAULT_PATIENT_COUNT)))
    except ValueError:
        count = DEFAULT_PATIENT_COUNT
    return max(1, min(count, MAX_PATIENT_COUNT))


def ble_address(patient_index):
    return f"D0:7A:5E:10:{patient_index:02X}:01"


def generate_vitals(patient_index):
    heart_rate = random.randint(60, 100)
    spo2 = random.randint(95, 100)

    systolic = random.randint(110, 130)
    diastolic = random.randint(70, 85)
    if INCIDENT_MODE:
        fall_alert = "Fall detected" if random.random() < 0.04 else "No fall"
        panic_button = "Pressed" if random.random() < 0.03 else "Not pressed"
        battery_status = "Battery critical" if random.random() < 0.04 else "Normal"
        wearable_link = "Disconnected" if random.random() < 0.03 else "Connected"
    else:
        fall_alert = "No fall"
        panic_button = "Not pressed"
        battery_status = "Normal"
        wearable_link = "Connected"

    return {
        "patient_id": f"patient-{patient_index}",
        "label": f"Patient {patient_index}",
        "ble_address": ble_address(patient_index),
        "heart_rate": heart_rate,
        "spo2": spo2,
        "blood_pressure": f"{systolic}/{diastolic}",
        "fall_alert": fall_alert,
        "panic_button": panic_button,
        "battery_status": battery_status,
        "wearable_link": wearable_link,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    count = patient_count()
    print("Wearable data generator started")
    print(f"Patients/wearables: {count}")
    print(f"Writing simulated BLE readings to {OUTPUT_FILE}")
    print()

    while True:
        patients = [generate_vitals(index) for index in range(1, count + 1)]
        payload = {
            "patients": patients,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        OUTPUT_FILE.write_text(json.dumps(payload))

        summary = ", ".join(
            f"{patient['label']}: HR={patient['heart_rate']} bpm, "
            f"SpO2={patient['spo2']}%, BP={patient['blood_pressure']}, "
            f"Fall={patient['fall_alert']}, Panic={patient['panic_button']}"
            for patient in patients
        )
        print(f"Wearable generated: {summary}")

        time.sleep(5)


if __name__ == "__main__":
    main()
