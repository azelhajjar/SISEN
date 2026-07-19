#!/usr/bin/env python3

import random
import os
import time
import paho.mqtt.publish as publish

BROKER = "192.168.60.1"
TOPIC = "building/humidity"
NODE_ID = os.getenv("SISEN_NODE_ID", "")
NODE_TOPIC = f"building/nodes/{NODE_ID}/humidity" if NODE_ID else ""

def main():
    print("Humidity sensor started...")

    while True:
        humidity = round(random.uniform(40.0, 65.0), 2)
        publish.single(TOPIC, str(humidity), hostname=BROKER)
        if NODE_TOPIC:
            publish.single(NODE_TOPIC, str(humidity), hostname=BROKER)
        print(f"Published humidity: {humidity}%")
        time.sleep(5)

if __name__ == "__main__":
    main()
