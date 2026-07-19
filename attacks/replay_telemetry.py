#!/usr/bin/env python3
import argparse
import json
import socket
import sys
import time


def load_payload(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        print(f"ERROR: input file not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if not isinstance(payload, dict):
        print("ERROR: replay payload must be a JSON object", file=sys.stderr)
        raise SystemExit(1)

    return payload


def main():
    parser = argparse.ArgumentParser(description="Replay a stored JSON telemetry payload over UDP/IPv6.")
    parser.add_argument("--input", required=True, help="JSON payload file to replay.")
    parser.add_argument("--source", default=None, help="Optional source IPv6 address to bind.")
    parser.add_argument("--dest", default="fd00:6:3::2", help="Gateway receiver IPv6 address.")
    parser.add_argument("--port", type=int, default=9999, help="Gateway receiver UDP port.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of replay attempts.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between replay attempts.")
    args = parser.parse_args()

    if args.repeat < 1:
        print("ERROR: --repeat must be at least 1", file=sys.stderr)
        raise SystemExit(1)

    reading = load_payload(args.input)
    payload = json.dumps(reading, separators=(",", ":")).encode("utf-8")

    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    if args.source:
        sock.bind((args.source, 0))

    for attempt in range(1, args.repeat + 1):
        sock.sendto(payload, (args.dest, args.port))
        print(f"replay attempt {attempt}/{args.repeat} to [{args.dest}]:{args.port}")
        print(json.dumps(reading, sort_keys=True))
        if attempt < args.repeat:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()

