#!/usr/bin/env python3

import random
import os
import time

import paho.mqtt.publish as publish


BROKER = "192.168.60.1"
TOPIC = "building/air_quality"
NODE_ID = os.getenv("SISEN_NODE_ID", "")
NODE_TOPIC = f"building/nodes/{NODE_ID}/air_quality" if NODE_ID else ""


def main():
    print("Air quality sensor started...")

    while True:
        air_quality = round(random.uniform(350.0, 900.0), 2)

        publish.single(
            TOPIC,
            str(air_quality),
            hostname=BROKER,
        )
        if NODE_TOPIC:
            publish.single(NODE_TOPIC, str(air_quality), hostname=BROKER)

        print(f"Published air quality: {air_quality} ppm")
        time.sleep(5)


if __name__ == "__main__":
    main()
