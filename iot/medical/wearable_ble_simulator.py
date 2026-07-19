#!/usr/bin/env python3

import json
import random
import time

import paho.mqtt.publish as publish


BROKER = "localhost"

TOPICS = {
    "heart_rate": "patient/vitals/heart_rate",
    "spo2": "patient/vitals/spo2",
    "blood_pressure": "patient/vitals/blood_pressure",
}


def generate_vitals():
    heart_rate = random.randint(60, 100)
    spo2 = random.randint(95, 100)

    systolic = random.randint(110, 130)
    diastolic = random.randint(70, 85)
    blood_pressure = f"{systolic}/{diastolic}"

    return {
        "heart_rate": heart_rate,
        "spo2": spo2,
        "blood_pressure": blood_pressure,
    }


def publish_vitals(vitals):
    publish.single(TOPICS["heart_rate"], str(vitals["heart_rate"]), hostname=BROKER)
    publish.single(TOPICS["spo2"], str(vitals["spo2"]), hostname=BROKER)
    publish.single(TOPICS["blood_pressure"], vitals["blood_pressure"], hostname=BROKER)


def main():
    print("Medical wearable BLE simulator started")
    print("Simulated BLE peripheral -> gateway -> MQTT")
    print("Publishing to patient/vitals/#")
    print()

    while True:
        vitals = generate_vitals()
        publish_vitals(vitals)

        print(
            "Gateway published vitals: "
            f"HR={vitals['heart_rate']} bpm, "
            f"SpO2={vitals['spo2']}%, "
            f"BP={vitals['blood_pressure']}"
        )

        time.sleep(5)


if __name__ == "__main__":
    main()
