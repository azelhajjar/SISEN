#!/usr/bin/env python3

import random
import os
import time

import paho.mqtt.publish as publish


BROKER = "192.168.60.1"
TOPIC = "building/occupancy"
NODE_ID = os.getenv("SISEN_NODE_ID", "")
NODE_TOPIC = f"building/nodes/{NODE_ID}/occupancy" if NODE_ID else ""


def main():
    print("Occupancy sensor started...")

    while True:
        occupancy = random.choice(["Occupied", "Vacant"])

        publish.single(
            TOPIC,
            occupancy,
            hostname=BROKER,
        )
        if NODE_TOPIC:
            publish.single(NODE_TOPIC, occupancy, hostname=BROKER)

        print(f"Published occupancy: {occupancy}")
        time.sleep(5)


if __name__ == "__main__":
    main()
