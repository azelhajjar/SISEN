#!/usr/bin/env python3
import argparse
import json
import socket
import subprocess


REQUIRED_FIELDS = {"sensor_id", "unit", "timestamp"}
DASHBOARD_FIELD_TOPICS = {
    "temperature": "building/temperature",
    "humidity": "building/humidity",
    "occupancy": "building/occupancy",
    "air_quality": "building/air_quality",
    "gas_leak": "building/gas_leak",
    "pressure_status": "building/pressure_status",
    "machine_overheat": "building/machine_overheat",
    "emergency_stop": "building/emergency_stop",
}
SIXLOWPAN_NODE_TOPIC_PREFIX = "industrial/6lowpan/nodes"


def validate_reading(reading):
    missing = sorted(REQUIRED_FIELDS - set(reading))
    if missing:
        return False, f"missing required fields: {', '.join(missing)}"

    telemetry_fields = sorted(set(reading) & set(DASHBOARD_FIELD_TOPICS))
    if not telemetry_fields:
        return False, "missing supported telemetry field"

    return True, "valid"


def publish_mqtt(payload, mqtt_host, mqtt_port, mqtt_topic):
    subprocess.run(
        [
            "mosquitto_pub",
            "-h",
            mqtt_host,
            "-p",
            str(mqtt_port),
            "-t",
            mqtt_topic,
            "-m",
            payload,
        ],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Receive minimal UDP JSON sensor readings over IPv6.")
    parser.add_argument("--bind", required=True, help="IPv6 address to listen on.")
    parser.add_argument("--port", type=int, default=9999, help="UDP port to listen on.")
    parser.add_argument("--count", type=int, default=1, help="Number of readings to receive before exiting. Use 0 for continuous mode.")
    parser.add_argument("--mqtt-host", default=None, help="MQTT broker host/address for optional publishing.")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port.")
    parser.add_argument(
        "--mqtt-topic",
        default="industrial/6lowpan/temp-01/telemetry",
        help="MQTT topic for validated sensor readings.",
    )
    parser.add_argument("--dashboard-topic", default=None, help="Optional dashboard-compatible MQTT topic.")
    parser.add_argument("--dashboard-field", default=None, help="JSON field to publish as a scalar dashboard payload.")
    parser.add_argument(
        "--dashboard-map",
        action="store_true",
        help="Publish supported telemetry fields to their existing dashboard-compatible MQTT topics.",
    )
    parser.add_argument("--no-mqtt", action="store_true", help="Receive UDP readings without MQTT publishing.")
    args = parser.parse_args()
    mqtt_enabled = bool(args.mqtt_host) and not args.no_mqtt
    dashboard_enabled = mqtt_enabled and bool(args.dashboard_topic) and bool(args.dashboard_field)
    dashboard_map_enabled = mqtt_enabled and args.dashboard_map

    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.port))

    print(f"gateway listening on [{args.bind}]:{args.port}", flush=True)
    if mqtt_enabled:
        print(f"mqtt publishing enabled: [{args.mqtt_host}]:{args.mqtt_port} topic={args.mqtt_topic}", flush=True)
        if dashboard_enabled:
            print(
                f"dashboard publishing enabled: field={args.dashboard_field} topic={args.dashboard_topic}",
                flush=True,
            )
        if dashboard_map_enabled:
            print("dashboard field mapping enabled", flush=True)
    else:
        print("mqtt publishing disabled", flush=True)

    received = 0
    while args.count == 0 or received < args.count:
        payload, sender = sock.recvfrom(2048)
        payload_text = payload.decode("utf-8")
        try:
            reading = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            print(f"received invalid JSON from [{sender[0]}]:{sender[1]}: {exc}", flush=True)
            continue

        valid, message = validate_reading(reading)
        total = "continuous" if args.count == 0 else str(args.count)
        print(f"received reading {received + 1}/{total} from [{sender[0]}]:{sender[1]}", flush=True)
        print(json.dumps(reading, indent=2, sort_keys=True), flush=True)
        print(f"validation: {message}", flush=True)

        if not valid:
            raise SystemExit(1)

        if mqtt_enabled:
            publish_mqtt(payload_text, args.mqtt_host, args.mqtt_port, args.mqtt_topic)
            print(f"published to MQTT topic {args.mqtt_topic}", flush=True)

        if dashboard_enabled:
            if args.dashboard_field not in reading:
                print(f"dashboard field missing: {args.dashboard_field}", flush=True)
                raise SystemExit(1)

            dashboard_payload = str(reading[args.dashboard_field])
            publish_mqtt(dashboard_payload, args.mqtt_host, args.mqtt_port, args.dashboard_topic)
            print(
                f"published dashboard scalar {args.dashboard_field}={dashboard_payload} "
                f"to MQTT topic {args.dashboard_topic}",
                flush=True,
            )

        if dashboard_map_enabled:
            published_any_dashboard_field = False
            for field, topic in DASHBOARD_FIELD_TOPICS.items():
                if field not in reading:
                    continue

                dashboard_payload = str(reading[field])
                publish_mqtt(dashboard_payload, args.mqtt_host, args.mqtt_port, topic)
                node_id = reading.get("node_id")
                if node_id:
                    node_topic = f"{SIXLOWPAN_NODE_TOPIC_PREFIX}/{node_id}/{field}"
                    publish_mqtt(dashboard_payload, args.mqtt_host, args.mqtt_port, node_topic)
                print(
                    f"published dashboard scalar {field}={dashboard_payload} "
                    f"to MQTT topic {topic}",
                    flush=True,
                )
                published_any_dashboard_field = True

            if not published_any_dashboard_field:
                print("no dashboard-compatible telemetry field found", flush=True)
                raise SystemExit(1)

        received += 1


if __name__ == "__main__":
    main()

