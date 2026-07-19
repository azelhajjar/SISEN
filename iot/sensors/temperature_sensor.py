#!/usr/bin/env python3

import random
import os
import time

import paho.mqtt.publish as publish


BROKER = "192.168.60.1"
TOPIC = "building/temperature"
NODE_ID = os.getenv("SISEN_NODE_ID", "")
NODE_TOPIC = f"building/nodes/{NODE_ID}/temperature" if NODE_ID else ""


def generate_temperature():
    return round(random.uniform(20.0, 26.0), 2)


def main():
    print("Temperature sensor started...")

    while True:
        temperature = generate_temperature()

        publish.single(
            TOPIC,
            str(temperature),
            hostname=BROKER,
        )
        if NODE_TOPIC:
            publish.single(NODE_TOPIC, str(temperature), hostname=BROKER)

        print(f"Published temperature: {temperature}°C")
        time.sleep(5)


if __name__ == "__main__":
    main()
