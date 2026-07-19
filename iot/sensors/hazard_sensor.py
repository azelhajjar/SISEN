#!/usr/bin/env python3

import os
import random
import time

import paho.mqtt.publish as publish


BROKER = "192.168.60.1"
NODE_ID = os.getenv("SISEN_NODE_ID", "")
FIELD = os.getenv("SISEN_HAZARD_FIELD", "fire_alarm")
LABEL = os.getenv("SISEN_HAZARD_LABEL", FIELD.replace("_", " ").title())
NORMAL_VALUES = [value.strip() for value in os.getenv("SISEN_NORMAL_VALUES", "Normal").split("|") if value.strip()]
HAZARD_VALUES = [value.strip() for value in os.getenv("SISEN_HAZARD_VALUES", "Hazard detected").split("|") if value.strip()]
INCIDENT_MODE = os.getenv("SISEN_INCIDENT_MODE") == "1"
TOPIC = f"building/{FIELD}"
NODE_TOPIC = f"building/nodes/{NODE_ID}/{FIELD}" if NODE_ID else ""


def generate_state():
    if INCIDENT_MODE and HAZARD_VALUES and random.random() < 0.08:
        return random.choice(HAZARD_VALUES)
    return random.choice(NORMAL_VALUES or ["Normal"])


def main():
    print(f"{LABEL} sensor started...")

    while True:
        state = generate_state()
        publish.single(TOPIC, state, hostname=BROKER)
        if NODE_TOPIC:
            publish.single(NODE_TOPIC, state, hostname=BROKER)
        print(f"Published {LABEL}: {state}")
        time.sleep(5)


if __name__ == "__main__":
    main()
