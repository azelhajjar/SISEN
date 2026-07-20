#!/usr/bin/env python3

import argparse
import json
import os
import re
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template
import paho.mqtt.client as mqtt


SCENARIOS = ("all", "building", "medical", "6lowpan", "scada")
SCENARIO_ALIASES = {}
SCENARIO_LABELS = {
    "all": "All SISEN Scenarios",
    "building": "Smart Building",
    "medical": "Medical IoT",
    "6lowpan": "6LoWPAN Industrial IoT",
    "scada": "SCADA",
}
REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_STATE_DIR = Path("/tmp/sisen-6lowpan-lab")
AP_MODE_STATE_FILE = Path("/tmp/sisen-ap-mode")
AP_RUNTIME_DIRS = (Path("/tmp/cybok-ap"), Path("/tmp/SISEN"))
LEGACY_HWSIM_AP = {
    "mode": "smart-building",
    "ssid": "SISEN-SMART-BUILDING",
    "interface": "wlan0",
    "ip": "192.168.60.1",
    "hostapd_log": Path("/tmp/hwsim-hostapd.log"),
    "dnsmasq_log": Path("/tmp/hwsim-dnsmasq.log"),
}
MEDICAL_HWSIM_AP = {
    "mode": "medical",
    "ssid": "SISEN-MEDICAL-IOT",
    "interface": "wlan0",
    "ip": "192.168.70.1",
    "hostapd_log": Path("/tmp/medical-hwsim-hostapd.log"),
    "dnsmasq_log": Path("/tmp/medical-hwsim-dnsmasq.log"),
}
STALE_AFTER_SECONDS = 15
DEFAULT_PATIENT_COUNT = 1
MAX_PATIENT_COUNT = 10

BUILDING_TOPICS = {
    "building/temperature": "temperature",
    "building/humidity": "humidity",
    "building/air_quality": "air_quality",
    "building/occupancy": "occupancy",
    "building/fire_alarm": "fire_alarm",
    "building/smoke": "smoke",
    "building/co2": "co2",
    "building/gas_leak": "gas_leak",
    "building/exit_status": "exit_status",
    "building/sprinkler_status": "sprinkler_status",
    "building/pressure_status": "pressure_status",
    "building/machine_overheat": "machine_overheat",
    "building/emergency_stop": "emergency_stop",
}
NODE_FIELDS = "|".join(BUILDING_TOPICS.values())
BUILDING_NODE_RE = re.compile(
    rf"^building/nodes/(?P<node_id>node-\d+)/(?P<field>{NODE_FIELDS})$"
)
SIXLOWPAN_NODE_RE = re.compile(
    rf"^industrial/6lowpan/nodes/(?P<node_id>node-\d+)/(?P<field>{NODE_FIELDS})$"
)
PATIENT_VITAL_RE = re.compile(r"^patient/(?P<patient_id>patient-\d+)/vitals/(?P<field>heart_rate|spo2|blood_pressure)$")
PATIENT_ALERT_RE = re.compile(
    r"^patient/(?P<patient_id>patient-\d+)/alerts/(?P<field>fall_alert|panic_button|battery_status|wearable_link)$"
)
PATIENT_META_RE = re.compile(r"^patient/(?P<patient_id>patient-\d+)/meta/(?P<field>ble_address)$")

KNOWN_AP_CLIENTS = {
    "02:60:00:00:00:01": {"device": "Temperature Sensor", "role": "Building telemetry"},
    "02:60:00:00:00:02": {"device": "Fire Alarm", "role": "Building telemetry"},
    "02:60:00:00:00:03": {"device": "Occupancy Sensor", "role": "Building telemetry"},
    "02:60:00:00:00:04": {"device": "Gas Leak Detector", "role": "Building telemetry"},
    "02:60:00:00:00:05": {"device": "Humidity Sensor", "role": "Building telemetry"},
    "02:60:00:00:00:06": {"device": "Air Quality Sensor", "role": "Building telemetry"},
    "02:60:00:00:00:07": {"device": "Smoke Detector", "role": "Building telemetry"},
    "02:60:00:00:00:08": {"device": "CO2 Detector", "role": "Building telemetry"},
    "02:60:00:00:00:09": {"device": "Emergency Exit", "role": "Building telemetry"},
    "02:60:00:00:00:0a": {"device": "Sprinkler Status", "role": "Building telemetry"},
    "02:00:00:00:05:00": {"device": "Medical Gateway", "role": "BLE-to-Wi-Fi gateway"},
}


BUILDING_SENSOR_TYPES = [
    {
        "label": "Temperature",
        "field": "temperature",
        "unit": "°C",
        "locations": ["Room 101", "Room 102", "Room 103"],
    },
    {
        "label": "Fire Alarm",
        "field": "fire_alarm",
        "unit": "",
        "locations": ["Main Hall", "Room 102", "Server Room"],
    },
    {
        "label": "Occupancy",
        "field": "occupancy",
        "unit": "",
        "locations": ["Room 101", "Meeting Room", "Corridor"],
    },
    {
        "label": "Gas Leak Detector",
        "field": "gas_leak",
        "unit": "",
        "locations": ["Boiler Room", "Plant Room", "Kitchen"],
    },
    {
        "label": "Humidity",
        "field": "humidity",
        "unit": "%",
        "locations": ["Plant Room", "Storage Room", "Room 102"],
    },
    {
        "label": "Air Quality",
        "field": "air_quality",
        "unit": "ppm",
        "locations": ["Lab", "Workshop", "Corridor"],
    },
    {
        "label": "Smoke Detector",
        "field": "smoke",
        "unit": "",
        "locations": ["Kitchen", "Corridor", "Plant Room"],
    },
    {
        "label": "CO2 Detector",
        "field": "co2",
        "unit": "",
        "locations": ["Car Park", "Loading Bay", "Workshop"],
    },
    {
        "label": "Emergency Exit",
        "field": "exit_status",
        "unit": "",
        "locations": ["North Exit", "West Stairwell", "Ground Floor"],
    },
    {
        "label": "Sprinkler Status",
        "field": "sprinkler_status",
        "unit": "",
        "locations": ["Main Hall", "Server Room", "Plant Room"],
    },
]

INDUSTRIAL_SENSOR_TYPES = [
    {
        "label": "Temperature",
        "field": "temperature",
        "unit": "°C",
        "locations": ["Cold Storage", "Process Line", "Loading Bay"],
    },
    {
        "label": "Gas Leak Detector",
        "field": "gas_leak",
        "unit": "",
        "locations": ["Chemical Store", "Boiler Room", "Loading Bay"],
    },
    {
        "label": "Pressure Safety Sensor",
        "field": "pressure_status",
        "unit": "",
        "locations": ["Pressure Vessel", "Process Line", "Pump Station"],
    },
    {
        "label": "Emergency Stop Monitor",
        "field": "emergency_stop",
        "unit": "",
        "locations": ["Assembly Line", "Control Room", "Packaging Area"],
    },
    {
        "label": "Humidity",
        "field": "humidity",
        "unit": "%",
        "locations": ["Packaging Area", "Material Store", "Clean Room"],
    },
    {
        "label": "Air Quality",
        "field": "air_quality",
        "unit": "ppm",
        "locations": ["Boiler Room", "Workshop", "Compressor Room"],
    },
    {
        "label": "Occupancy",
        "field": "occupancy",
        "unit": "",
        "locations": ["Assembly Bay", "Control Room", "Service Corridor"],
    },
    {
        "label": "Machine Overheat Sensor",
        "field": "machine_overheat",
        "unit": "",
        "locations": ["CNC Cell", "Compressor Room", "Motor Control"],
    },
]

BUILDING_ROOM_CARDS = [
    {
        "label": "Room 101",
        "sensor_ids": "TEMP-R101, FIRE-R101, OCC-R101, GAS-R101",
        "items": [
            ("Temperature", "temperature", "°C"),
            ("Fire alarm", "fire_alarm", ""),
            ("Occupancy", "occupancy", ""),
            ("Gas leak", "gas_leak", ""),
        ],
    },
    {
        "label": "Plant Room",
        "sensor_ids": "HUM-PLANT, AIR-PLANT, SMOKE-PLANT, CO2-PLANT",
        "items": [
            ("Humidity", "humidity", "%"),
            ("Air quality", "air_quality", "ppm"),
            ("Smoke", "smoke", ""),
            ("CO2", "co2", ""),
        ],
    },
    {
        "label": "Server Room",
        "sensor_ids": "TEMP-SRV, SMOKE-SRV, SPRINKLER-SRV, EXIT-SRV",
        "items": [
            ("Temperature", "temperature", "°C"),
            ("Smoke", "smoke", ""),
            ("Sprinkler", "sprinkler_status", ""),
            ("Emergency exit", "exit_status", ""),
        ],
    },
    {
        "label": "Workshop",
        "sensor_ids": "TEMP-WORK, AIR-WORK, OCC-WORK, GAS-WORK",
        "items": [
            ("Temperature", "temperature", "°C"),
            ("Air quality", "air_quality", "ppm"),
            ("Occupancy", "occupancy", ""),
            ("Gas leak", "gas_leak", ""),
        ],
    },
]

INDUSTRIAL_ASSET_CARDS = [
    {
        "label": "Boiler Room",
        "sensor_ids": "TEMP-BLR, GAS-BLR, PRESS-BLR, ESTOP-BLR",
        "items": [
            ("Temperature", "temperature", "°C"),
            ("Gas leak", "gas_leak", ""),
            ("Pressure", "pressure_status", ""),
            ("Emergency stop", "emergency_stop", ""),
        ],
    },
    {
        "label": "Process Line",
        "sensor_ids": "TEMP-LINE, HUM-LINE, OVERHEAT-LINE, ESTOP-LINE",
        "items": [
            ("Temperature", "temperature", "°C"),
            ("Humidity", "humidity", "%"),
            ("Machine overheat", "machine_overheat", ""),
            ("Emergency stop", "emergency_stop", ""),
        ],
    },
    {
        "label": "Cold Storage",
        "sensor_ids": "TEMP-COLD, HUM-COLD, DOOR-COLD, AIR-COLD",
        "items": [
            ("Temperature", "temperature", "°C"),
            ("Humidity", "humidity", "%"),
            ("Occupancy", "occupancy", ""),
            ("Air quality", "air_quality", "ppm"),
        ],
    },
    {
        "label": "Loading Bay",
        "sensor_ids": "TEMP-BAY, GAS-BAY, OCC-BAY, AIR-BAY",
        "items": [
            ("Temperature", "temperature", "°C"),
            ("Gas leak", "gas_leak", ""),
            ("Occupancy", "occupancy", ""),
            ("Air quality", "air_quality", "ppm"),
        ],
    },
]


def hwsim_client_index(mac):
    parts = str(mac or "").lower().split(":")
    if len(parts) != 6 or parts[:5] != ["02", "60", "00", "00", "00"]:
        return None
    try:
        return int(parts[-1], 16)
    except ValueError:
        return None


def node_status(field, value, online):
    if not online:
        return "WAITING"

    if value in (None, "", "No data yet"):
        return "WAITING"

    if field in {"temperature", "humidity", "air_quality", "occupancy"}:
        return "RUNNING"

    value_text = str(value or "").lower()
    critical_terms = (
        "detected",
        "blocked",
        "disabled",
        "abnormal",
        "overheat",
        "emergency stop active",
        "high co2",
    )
    if any(term in value_text for term in critical_terms):
        return "CRITICAL"
    if value_text in {"normal", "clear", "standby", "ready"}:
        return "NORMAL"
    return "WARNING"


def strongest_status(statuses):
    if "CRITICAL" in statuses:
        return "CRITICAL"
    if "WARNING" in statuses:
        return "WARNING"
    if "NORMAL" in statuses:
        return "NORMAL"
    if "RUNNING" in statuses:
        return "RUNNING"
    return "WAITING"


def node_value(data, collection_name, node_id, field):
    node_values = data.get(collection_name, {}).get(node_id, {})
    return node_values.get(field, data.get(field))


def composite_metric(label, field, unit, value, online):
    return {
        "label": label,
        "value": value,
        "unit": unit,
        "status": node_status(field, value, online),
    }


def building_nodes(ap_status, data):
    clients = []
    for client in ap_status.get("clients", []):
        index = hwsim_client_index(client.get("mac"))
        if index and index >= 1:
            clients.append((index, client))

    if not clients:
        clients = [
            (
                index,
                {"mac": f"02:60:00:00:00:{index:02x}", "ip": ""},
            )
            for index in range(1, 5)
        ]

    online = data.get("status") == "ONLINE"
    client_map = {index: client for index, client in clients}
    visible_cards = []
    visible_indexes = {index for index, _client in clients}
    if not visible_indexes:
        visible_indexes = {1, 2, 3, 4}

    for index in sorted(visible_indexes):
        card = BUILDING_ROOM_CARDS[(index - 1) % len(BUILDING_ROOM_CARDS)]
        instance = ((index - 1) // len(BUILDING_ROOM_CARDS)) + 1
        label = card["label"] if instance == 1 else f"{card['label']} {instance}"
        node_id = f"node-{index:02d}"
        if index not in visible_indexes:
            continue
        metrics = []
        for metric_label, field, unit in card["items"]:
            value = node_value(data, "building_node_values", node_id, field)
            metrics.append(composite_metric(metric_label, field, unit, value, online))
        statuses = [metric["status"] for metric in metrics]
        visible_cards.append(
            {
                "label": label,
                "metrics": metrics,
                "detail": f"{node_id} · Sensor IDs: {card['sensor_ids']}",
                "status": strongest_status(statuses),
            }
        )

    return visible_cards


def read_6lowpan_sensor_count():
    try:
        count = int(read_text(LAB_STATE_DIR / "sensor-nodes").strip())
    except ValueError:
        count = 4
    return max(1, min(count, 10))


def sixlowpan_nodes(data):
    sensor_count = read_6lowpan_sensor_count()
    online = data.get("status") == "ONLINE"
    visible_cards = []
    for index in range(1, sensor_count + 1):
        card = INDUSTRIAL_ASSET_CARDS[(index - 1) % len(INDUSTRIAL_ASSET_CARDS)]
        instance = ((index - 1) // len(INDUSTRIAL_ASSET_CARDS)) + 1
        label = card["label"] if instance == 1 else f"{card['label']} {instance}"
        node_id = f"node-{index:02d}"
        metrics = []
        for metric_label, field, unit in card["items"]:
            value = node_value(data, "sixlowpan_node_values", node_id, field)
            metrics.append(composite_metric(metric_label, field, unit, value, online))
        statuses = [metric["status"] for metric in metrics]
        visible_cards.append(
            {
                "label": label,
                "metrics": metrics,
                "detail": f"{node_id} · Sensor IDs: {card['sensor_ids']}",
                "status": strongest_status(statuses),
            }
        )
    return visible_cards


def patient_sort_key(item):
    patient_id = item[0]
    match = re.search(r"\d+$", patient_id)
    if match:
        return int(match.group(0))
    return patient_id


def patient_ble_address(patient_id):
    match = re.search(r"\d+$", patient_id)
    if match:
        return f"D0:7A:5E:10:{int(match.group(0)):02X}:01"
    return "unknown"


def configured_patient_count():
    try:
        count = int(os.environ.get("SISEN_PATIENT_COUNT", str(DEFAULT_PATIENT_COUNT)))
    except ValueError:
        count = DEFAULT_PATIENT_COUNT
    return max(1, min(count, MAX_PATIENT_COUNT))


def patient_card(patient_id, patient=None):
    patient = patient or {}
    alert_status = patient.get("alert_status", "NORMAL")
    return {
        "patient_id": patient_id,
        "label": patient.get("label", patient_id.replace("-", " ").title()),
        "ble_address": patient.get("ble_address", patient_ble_address(patient_id)),
        "heart_rate": patient.get("heart_rate", "No data yet"),
        "heart_rate_status": patient.get("heart_rate_status", "UNKNOWN"),
        "spo2": patient.get("spo2", "No data yet"),
        "spo2_status": patient.get("spo2_status", "UNKNOWN"),
        "blood_pressure": patient.get("blood_pressure", "No data yet"),
        "blood_pressure_status": patient.get("blood_pressure_status", "UNKNOWN"),
        "fall_alert": patient.get("fall_alert", "No fall"),
        "panic_button": patient.get("panic_button", "Not pressed"),
        "battery_status": patient.get("battery_status", "Normal"),
        "wearable_link": patient.get("wearable_link", "Connected"),
        "alert_status": alert_status,
    }


def medical_patients(data):
    configured_count = configured_patient_count()
    if configured_count:
        patient_data = data.get("patients", {})
        return [
            patient_card(f"patient-{index}", patient_data.get(f"patient-{index}"))
            for index in range(1, configured_count + 1)
        ]

    patients = []
    for patient_id, patient in sorted(data.get("patients", {}).items(), key=patient_sort_key):
        patients.append(patient_card(patient_id, patient))

    if patients:
        return patients

    return [
        patient_card(
            "patient-1",
            {
                "heart_rate": data.get("heart_rate", "No data yet"),
                "heart_rate_status": data.get("heart_rate_status", "UNKNOWN"),
                "spo2": data.get("spo2", "No data yet"),
                "spo2_status": data.get("spo2_status", "UNKNOWN"),
                "blood_pressure": data.get("blood_pressure", "No data yet"),
                "blood_pressure_status": data.get("blood_pressure_status", "UNKNOWN"),
            },
        )
    ]

app = Flask(__name__)
data_lock = threading.Lock()

latest_data = {
    "temperature": "No data yet",
    "humidity": "No data yet",
    "air_quality": "No data yet",
    "occupancy": "No data yet",
    "fire_alarm": "No data yet",
    "smoke": "No data yet",
    "co2": "No data yet",
    "gas_leak": "No data yet",
    "exit_status": "No data yet",
    "sprinkler_status": "No data yet",
    "pressure_status": "No data yet",
    "machine_overheat": "No data yet",
    "emergency_stop": "No data yet",
    "heart_rate": "No data yet",
    "heart_rate_status": "UNKNOWN",
    "spo2": "No data yet",
    "spo2_status": "UNKNOWN",
    "blood_pressure": "No data yet",
    "blood_pressure_status": "UNKNOWN",
    "heart_rate_history": [],
    "patients": {},
    "building_node_values": {},
    "sixlowpan_node_values": {},
    "last_update": "Never",
    "last_update_epoch": 0,
    "last_topic": "None",
    "status": "OFFLINE",
    "topics": {},
}

mqtt_state = {
    "connected": False,
    "status": "DISCONNECTED",
    "last_connect": "Never",
    "last_disconnect": "Never",
    "last_error": "",
    "broker": "localhost:1883",
}


def timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def classify_temperature(value):
    try:
        temperature = float(value)
    except (ValueError, TypeError):
        return "UNKNOWN"

    if temperature < 15 or temperature > 30:
        return "CRITICAL"
    if temperature < 18 or temperature > 27:
        return "WARNING"
    return "NORMAL"


def classify_air_quality(value):
    try:
        air_quality = float(value)
    except (ValueError, TypeError):
        return "UNKNOWN"

    if air_quality > 1200:
        return "CRITICAL"
    if air_quality > 800:
        return "WARNING"
    return "NORMAL"


def classify_heart_rate(value):
    try:
        heart_rate = int(value)
    except (ValueError, TypeError):
        return "UNKNOWN"

    if heart_rate < 50 or heart_rate > 120:
        return "CRITICAL"
    if heart_rate < 60 or heart_rate > 100:
        return "WARNING"
    return "NORMAL"


def classify_spo2(value):
    try:
        spo2 = int(value)
    except (ValueError, TypeError):
        return "UNKNOWN"

    if spo2 < 90:
        return "CRITICAL"
    if spo2 < 95:
        return "WARNING"
    return "NORMAL"


def classify_blood_pressure(value):
    try:
        systolic_text, diastolic_text = value.split("/")
        systolic = int(systolic_text)
        diastolic = int(diastolic_text)
    except (ValueError, AttributeError):
        return "UNKNOWN"

    if systolic > 160 or diastolic > 100:
        return "CRITICAL"
    if systolic > 140 or diastolic > 90:
        return "WARNING"
    return "NORMAL"


def classify_patient_alert(field, value):
    value_text = str(value or "").lower()
    if field == "fall_alert" and "detected" in value_text:
        return "CRITICAL"
    if field == "panic_button" and value_text == "pressed":
        return "CRITICAL"
    if field == "battery_status" and "critical" in value_text:
        return "WARNING"
    if field == "wearable_link" and "disconnected" in value_text:
        return "WARNING"
    return "NORMAL"


def update_patient_alert_status(patient):
    statuses = [
        classify_patient_alert("fall_alert", patient.get("fall_alert")),
        classify_patient_alert("panic_button", patient.get("panic_button")),
        classify_patient_alert("battery_status", patient.get("battery_status")),
        classify_patient_alert("wearable_link", patient.get("wearable_link")),
    ]
    if "CRITICAL" in statuses:
        patient["alert_status"] = "CRITICAL"
    elif "WARNING" in statuses:
        patient["alert_status"] = "WARNING"
    else:
        patient["alert_status"] = "NORMAL"


def update_topic(topic, payload):
    latest_data["last_update"] = timestamp()
    latest_data["last_update_epoch"] = time.time()
    latest_data["last_topic"] = topic
    latest_data["topics"][topic] = {
        "payload": payload,
        "updated": latest_data["last_update"],
        "updated_epoch": latest_data["last_update_epoch"],
    }


def on_connect(client, userdata, flags, rc, properties=None):
    with data_lock:
        mqtt_state["connected"] = rc == 0
        mqtt_state["status"] = "CONNECTED" if rc == 0 else f"ERROR {rc}"
        mqtt_state["last_connect"] = timestamp()
        mqtt_state["last_error"] = "" if rc == 0 else f"MQTT connect returned {rc}"

    if rc == 0:
        client.subscribe("building/#")
        client.subscribe("industrial/6lowpan/#")
        client.subscribe("patient/#")


def on_disconnect(client, userdata, rc, properties=None):
    with data_lock:
        mqtt_state["connected"] = False
        mqtt_state["status"] = "DISCONNECTED"
        mqtt_state["last_disconnect"] = timestamp()
        if rc:
            mqtt_state["last_error"] = f"Unexpected MQTT disconnect: {rc}"


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode(errors="replace")

    with data_lock:
        update_topic(topic, payload)

        if topic in BUILDING_TOPICS:
            latest_data[BUILDING_TOPICS[topic]] = payload

        building_node_match = BUILDING_NODE_RE.match(topic)
        if building_node_match:
            node_id = building_node_match.group("node_id")
            field = building_node_match.group("field")
            latest_data["building_node_values"].setdefault(node_id, {})[field] = payload

        sixlowpan_node_match = SIXLOWPAN_NODE_RE.match(topic)
        if sixlowpan_node_match:
            node_id = sixlowpan_node_match.group("node_id")
            field = sixlowpan_node_match.group("field")
            latest_data["sixlowpan_node_values"].setdefault(node_id, {})[field] = payload

        patient_match = PATIENT_VITAL_RE.match(topic)
        if patient_match:
            patient_id = patient_match.group("patient_id")
            field = patient_match.group("field")
            patient = latest_data["patients"].setdefault(
                patient_id,
                {"patient_id": patient_id, "label": patient_id.replace("-", " ").title()},
            )
            patient[field] = payload
            if field == "heart_rate":
                patient["heart_rate_status"] = classify_heart_rate(payload)
            if field == "spo2":
                patient["spo2_status"] = classify_spo2(payload)
            if field == "blood_pressure":
                patient["blood_pressure_status"] = classify_blood_pressure(payload)

        patient_alert_match = PATIENT_ALERT_RE.match(topic)
        if patient_alert_match:
            patient_id = patient_alert_match.group("patient_id")
            field = patient_alert_match.group("field")
            patient = latest_data["patients"].setdefault(
                patient_id,
                {"patient_id": patient_id, "label": patient_id.replace("-", " ").title()},
            )
            patient[field] = payload
            update_patient_alert_status(patient)

        patient_meta_match = PATIENT_META_RE.match(topic)
        if patient_meta_match:
            patient_id = patient_meta_match.group("patient_id")
            field = patient_meta_match.group("field")
            patient = latest_data["patients"].setdefault(
                patient_id,
                {"patient_id": patient_id, "label": patient_id.replace("-", " ").title()},
            )
            patient[field] = payload

        if topic == "patient/vitals/heart_rate":
            latest_data["heart_rate"] = payload
            latest_data["heart_rate_status"] = classify_heart_rate(payload)
            try:
                latest_data["heart_rate_history"].append(int(payload))
                latest_data["heart_rate_history"] = latest_data["heart_rate_history"][-20:]
            except ValueError:
                pass

        if topic == "patient/vitals/spo2":
            latest_data["spo2"] = payload
            latest_data["spo2_status"] = classify_spo2(payload)

        if topic == "patient/vitals/blood_pressure":
            latest_data["blood_pressure"] = payload
            latest_data["blood_pressure_status"] = classify_blood_pressure(payload)

def mqtt_listener(host, port):
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    with data_lock:
        mqtt_state["broker"] = f"{host}:{port}"

    while True:
        try:
            client.connect(host, port, 60)
            client.loop_forever()
        except Exception as exc:  # noqa: BLE001 - keep dashboard alive if broker is absent.
            with data_lock:
                mqtt_state["connected"] = False
                mqtt_state["status"] = "DISCONNECTED"
                mqtt_state["last_error"] = str(exc)
            time.sleep(5)


def pid_running(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_pid(path):
    text = read_text(path).strip()
    return text if text.isdigit() else ""


def safe_glob(directory, pattern):
    try:
        return list(directory.glob(pattern))
    except OSError:
        return []


def component_state(name, pid_file):
    pid = read_pid(pid_file)
    running = pid_running(pid)
    return {
        "name": name,
        "pid": pid or "unknown",
        "running": running,
        "status": "RUNNING" if running else "STOPPED",
    }


def first_component_state(name, pid_files):
    for pid_file in pid_files:
        state = component_state(name, pid_file)
        if state["running"]:
            state["source"] = str(pid_file)
            return state

    if pid_files:
        state = component_state(name, pid_files[0])
        state["source"] = str(pid_files[0])
        return state

    return {
        "name": name,
        "pid": "unknown",
        "running": False,
        "status": "STOPPED",
        "source": "",
    }


def component_state_from_cmdline(name, required_terms):
    for process_dir in safe_glob(Path("/proc"), "[0-9]*"):
        cmdline = read_text(process_dir / "cmdline").replace("\x00", " ").strip()
        if not cmdline:
            continue
        if all(term in cmdline for term in required_terms):
            return {
                "name": name,
                "pid": process_dir.name,
                "running": True,
                "status": "RUNNING",
                "source": "/proc",
            }

    return {
        "name": name,
        "pid": "unknown",
        "running": False,
        "status": "STOPPED",
        "source": "/proc",
    }


def component_group_state_from_cmdline(name, script_names):
    matches = []
    for process_dir in safe_glob(Path("/proc"), "[0-9]*"):
        cmdline = read_text(process_dir / "cmdline").replace("\x00", " ").strip()
        if not cmdline:
            continue
        if any(script_name in cmdline for script_name in script_names):
            matches.append(process_dir.name)

    running = bool(matches)
    return {
        "name": name,
        "pid": f"{len(matches)} process" + ("" if len(matches) == 1 else "es") if running else "unknown",
        "running": running,
        "status": "RUNNING" if running else "STOPPED",
        "source": "/proc",
    }


def component_state_with_cmdline_fallback(name, pid_file, script_names):
    state = component_state(name, pid_file)
    state["source"] = str(pid_file)
    if state["running"]:
        return state

    fallback = component_group_state_from_cmdline(name, script_names)
    if fallback["running"]:
        return fallback
    return state


def read_ap_mode():
    for path in (LAB_STATE_DIR / "ap-mode", LAB_STATE_DIR / "ap_mode"):
        value = read_text(path).strip()
        if value:
            return value
    return "unknown"


def parse_dhcp_leases():
    clients = {}
    for runtime_dir in AP_RUNTIME_DIRS:
        for lease_file in safe_glob(runtime_dir, "*lease*"):
            for line in read_text(lease_file).splitlines():
                parts = line.split()
                if len(parts) < 3:
                    continue
                lease_time = parts[0]
                mac = parts[1].lower()
                clients.setdefault(
                    mac,
                    {
                        "mac": mac,
                        "ip": "",
                        "hostname": "",
                        "lease_time": "",
                        "lease_expires": "",
                        "source": lease_file.name,
                    },
                )
                clients[mac]["ip"] = parts[2]
                clients[mac]["lease_time"] = lease_time
                try:
                    clients[mac]["lease_expires"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(lease_time)))
                except (ValueError, OSError, OverflowError):
                    clients[mac]["lease_expires"] = lease_time
                if len(parts) > 3 and parts[3] != "*":
                    clients[mac]["hostname"] = parts[3]
    return clients


def parse_ap_logs(clients):
    dhcpack_pattern = re.compile(
        r"DHCPACK.*?(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?P<mac>[0-9a-fA-F:]{17})(?:\s+(?P<host>\S+))?"
    )
    connected_pattern = re.compile(r"AP-STA-CONNECTED\s+(?P<mac>[0-9a-fA-F:]{17})")

    for runtime_dir in AP_RUNTIME_DIRS:
        log_files = safe_glob(runtime_dir, "*dnsmasq*.log") + safe_glob(runtime_dir, "*hostapd*.log")
        for log_file in log_files:
            for line in read_text(log_file).splitlines()[-200:]:
                dhcp_match = dhcpack_pattern.search(line)
                if dhcp_match:
                    mac = dhcp_match.group("mac").lower()
                    clients.setdefault(
                        mac,
                        {
                            "mac": mac,
                            "ip": "",
                            "hostname": "",
                            "lease_time": "",
                            "lease_expires": "",
                            "source": log_file.name,
                        },
                    )
                    clients[mac]["ip"] = dhcp_match.group("ip")
                    if dhcp_match.group("host"):
                        clients[mac]["hostname"] = dhcp_match.group("host")

                connected_match = connected_pattern.search(line)
                if connected_match:
                    mac = connected_match.group("mac").lower()
                    clients.setdefault(
                        mac,
                        {
                            "mac": mac,
                            "ip": "",
                            "hostname": "",
                            "lease_time": "",
                            "lease_expires": "",
                            "source": log_file.name,
                        },
                    )
    for log_file in (
        LEGACY_HWSIM_AP["dnsmasq_log"],
        LEGACY_HWSIM_AP["hostapd_log"],
        MEDICAL_HWSIM_AP["dnsmasq_log"],
        MEDICAL_HWSIM_AP["hostapd_log"],
    ):
        for line in read_text(log_file).splitlines()[-200:]:
            dhcp_match = dhcpack_pattern.search(line)
            if dhcp_match:
                mac = dhcp_match.group("mac").lower()
                clients.setdefault(
                    mac,
                    {
                        "mac": mac,
                        "ip": "",
                        "hostname": "",
                        "lease_time": "",
                        "lease_expires": "",
                        "source": log_file.name,
                    },
                )
                clients[mac]["ip"] = dhcp_match.group("ip")
                if dhcp_match.group("host"):
                    clients[mac]["hostname"] = dhcp_match.group("host")

            connected_match = connected_pattern.search(line)
            if connected_match:
                mac = connected_match.group("mac").lower()
                clients.setdefault(
                    mac,
                    {
                        "mac": mac,
                        "ip": "",
                        "hostname": "",
                        "lease_time": "",
                        "lease_expires": "",
                        "source": log_file.name,
                    },
                )
    return clients


def describe_ap_clients(clients):
    described = []
    for client in clients.values():
        mac = client["mac"].lower()
        details = KNOWN_AP_CLIENTS.get(mac, {})
        described.append(
            {
                "device": details.get("device", "Wi-Fi client"),
                "role": details.get("role", "Associated station"),
                "mac": client["mac"],
                "ip": client.get("ip", ""),
                "hostname": client.get("hostname", ""),
                "lease_expires": client.get("lease_expires", ""),
                "lease_time": client.get("lease_time", ""),
            }
        )
    return sorted(described, key=lambda item: (item["device"], item["mac"]))


def filter_smart_building_clients(ap_status):
    if not isinstance(ap_status, dict):
        return ap_status
    if not str(ap_status.get("mode", "")).startswith("smart-building-"):
        return ap_status

    clients = [
        client
        for client in ap_status.get("clients", [])
        if hwsim_client_index(client.get("mac")) is not None
    ]
    ap_status["clients"] = clients
    ap_status["client_count"] = len(clients)
    return ap_status


def scenario_devices(scenario, ap_status):
    scenario = normalize_scenario(scenario)
    ap_clients = ap_status.get("clients", [])

    if scenario == "building":
        return [
            {
                "device": client["device"],
                "network": "Wi-Fi / HWSIM",
                "address": client["mac"],
                "detail": client.get("ip") or "associated",
            }
            for client in ap_clients
            if client["mac"].lower() in KNOWN_AP_CLIENTS
            and KNOWN_AP_CLIENTS[client["mac"].lower()]["role"] == "Building telemetry"
        ]

    if scenario == "medical":
        gateway = next(
            (
                client
                for client in ap_clients
                if client["mac"].lower() == "02:00:00:00:05:00"
            ),
            {},
        )
        return [
            {
                "device": "Wearable vitals generator",
                "network": "Simulated BLE",
                "address": "local generator",
                "detail": "Publishes heart rate, SpO2, and blood pressure",
            },
            {
                "device": "BLE-to-Wi-Fi gateway",
                "network": "BLE / Wi-Fi bridge",
                "address": gateway.get("mac") or "02:00:00:00:05:00",
                "detail": gateway.get("ip") or "medical gateway namespace",
            },
            {
                "device": "Patient telemetry topic",
                "network": "MQTT",
                "address": "patient/#",
                "detail": "Dashboard patient monitor feed",
            },
        ]

    if scenario == "6lowpan":
        return [
            {
                "device": "Sensor node",
                "network": "IEEE 802.15.4 / 6LoWPAN",
                "address": "fd00:6:1::1",
                "detail": "Temperature telemetry source",
            },
            {
                "device": "Border router",
                "network": "6LoWPAN / IPv6 bridge",
                "address": "fd00:6:1::ff",
                "detail": "Forwards low-power network traffic",
            },
            {
                "device": "Gateway receiver",
                "network": "IPv6 / MQTT bridge",
                "address": "fd00:6:3::2",
                "detail": "Publishes 6LoWPAN telemetry into MQTT",
            },
            {
                "device": "Dashboard relay",
                "network": "MQTT",
                "address": "building/#",
                "detail": "Maps 6LoWPAN telemetry to dashboard topics",
            },
        ]

    if scenario == "all":
        return scenario_devices("building", ap_status) + scenario_devices("medical", ap_status) + scenario_devices("6lowpan", ap_status)

    return [
        {
            "device": client["device"],
            "network": "Wi-Fi / AP",
            "address": client["mac"],
            "detail": client.get("ip") or client.get("role") or "associated",
        }
        for client in ap_clients
    ]


def read_ap_status():
    wrapper = component_state("AP wrapper", LAB_STATE_DIR / "ap.pid")
    hostapd = first_component_state("hostapd", [runtime_dir / "hostapd.pid" for runtime_dir in AP_RUNTIME_DIRS])
    dnsmasq = first_component_state("dnsmasq", [runtime_dir / "dnsmasq.pid" for runtime_dir in AP_RUNTIME_DIRS])
    legacy_hostapd = component_state_from_cmdline("legacy hostapd", ["hostapd", "/tmp/hwsim-hostapd.conf"])
    legacy_dnsmasq = component_state_from_cmdline("legacy dnsmasq", ["dnsmasq", "192.168.60.10,192.168.60.100"])
    medical_hostapd = component_state_from_cmdline("medical hostapd", ["hostapd", "/tmp/medical-hwsim-hostapd.conf"])
    medical_dnsmasq = component_state_from_cmdline("medical dnsmasq", ["dnsmasq", "192.168.70.10,192.168.70.50"])
    clients = parse_ap_logs(parse_dhcp_leases())
    recent_log = read_text(LAB_STATE_DIR / "ap.log").splitlines()[-8:]
    legacy_recent_log = (
        read_text(LEGACY_HWSIM_AP["hostapd_log"]).splitlines()[-4:]
        + read_text(LEGACY_HWSIM_AP["dnsmasq_log"]).splitlines()[-4:]
    )
    medical_recent_log = (
        read_text(MEDICAL_HWSIM_AP["hostapd_log"]).splitlines()[-4:]
        + read_text(MEDICAL_HWSIM_AP["dnsmasq_log"]).splitlines()[-4:]
    )
    legacy_running = legacy_hostapd["running"]
    medical_running = medical_hostapd["running"]
    running = wrapper["running"] or hostapd["running"] or legacy_running or medical_running
    mode = read_ap_mode()
    if mode == "unknown" and legacy_running:
        mode = LEGACY_HWSIM_AP["mode"]
    if mode == "unknown" and medical_running:
        mode = MEDICAL_HWSIM_AP["mode"]
    if mode.startswith("smart-building-"):
        clients = {
            mac: client
            for mac, client in clients.items()
            if hwsim_client_index(mac) is not None
        }

    return {
        "mode": mode,
        "status": "RUNNING" if running else "STOPPED",
        "running": running,
        "pid": wrapper["pid"],
        "ssid": MEDICAL_HWSIM_AP["ssid"] if medical_running else LEGACY_HWSIM_AP["ssid"] if legacy_running else "",
        "interface": MEDICAL_HWSIM_AP["interface"] if medical_running else LEGACY_HWSIM_AP["interface"] if legacy_running else "",
        "ip": MEDICAL_HWSIM_AP["ip"] if medical_running else LEGACY_HWSIM_AP["ip"] if legacy_running else "",
        "wrapper": wrapper,
        "services": [hostapd, dnsmasq, legacy_hostapd, legacy_dnsmasq, medical_hostapd, medical_dnsmasq],
        "client_count": len(clients),
        "clients": describe_ap_clients(clients),
        "recent_log": recent_log or medical_recent_log or legacy_recent_log,
    }


def read_lab_status(scenario=None):
    scenario = normalize_scenario(scenario or _active_dashboard_scenario())
    all_components = {
        "6lowpan": [
            component_state_with_cmdline_fallback(
                "6LoWPAN border router",
                LAB_STATE_DIR / "gateway.pid",
                ["gateway_receiver.py"],
            ),
            component_state_with_cmdline_fallback(
                "6LoWPAN MQTT broker",
                LAB_STATE_DIR / "mqtt.pid",
                ["mosquitto", "6lowpan-poc.conf"],
            ),
        ],
        "building": [
            component_state_from_cmdline(
                "Smart Building AP",
                ["hostapd", "/tmp/hwsim-hostapd.conf"],
            ),
        ],
        "medical": [
            component_state_from_cmdline(
                "Medical Wi-Fi AP",
                ["hostapd", "/tmp/medical-hwsim-hostapd.conf"],
            ),
            component_group_state_from_cmdline(
                "BLE-to-Wi-Fi gateway",
                ["ble_wifi_gateway.py"],
            ),
        ],
    }

    if scenario == "all":
        components = [component for items in all_components.values() for component in items]
    else:
        components = all_components.get(scenario, [])

    return {
        "state_dir": str(LAB_STATE_DIR),
        "components": components,
        "relays": [],
    }


def normalize_scenario(scenario):
    return SCENARIO_ALIASES.get(scenario, scenario)


def scenario_label(scenario):
    return SCENARIO_LABELS.get(normalize_scenario(scenario), scenario)


def visible_sections(scenario):
    scenario = normalize_scenario(scenario)
    if scenario == "all":
        return ["building", "medical", "6lowpan", "scada"]
    if scenario == "6lowpan":
        return ["6lowpan"]
    return [scenario]


CAPTURE_DIRS = {
    "building": "captures",
    "medical": "captures",
    "6lowpan": "captures",
    "scada": "captures",
}


def capture_path(scenario, filename=None):
    directory = CAPTURE_DIRS[scenario]
    return f"{directory}/{filename}" if filename else directory


def _scenario_guidance():
    return {
        "building": {
            "commands": [
                "# Live telemetry observation",
                "mosquitto_sub -h localhost -v -t 'building/#'",
                "# Identity, authenticity, and spoofing attacks",
                "python3 attacks/run_attack.py --category authenticity --scenario building --attack spoofed",
                "# Data integrity and manipulation attacks",
                "python3 attacks/run_attack.py --category integrity --scenario building --attack extreme",
                "# Replay attacks",
                "python3 attacks/run_attack.py --category replay --scenario building --attack replay",
                "# Availability and disruption attacks",
                "python3 attacks/run_attack.py --category availability --scenario building --attack noise --count 5",
                "sudo python3 attacks/run_attack.py --category availability --scenario building --attack client-drop --target room-101",
                "sudo python3 attacks/run_attack.py --category availability --scenario building --attack sensor-blackout --duration 10",
                "# Scenario-focused examples",
                "python3 attacks/run_attack.py --category authenticity --scenario building --attack false-occupancy",
                "python3 attacks/run_attack.py --category integrity --scenario building --attack environment-extreme",
            ],
            "captures": [
                "# SSID/AP: SISEN-SMART-BUILDING on wlan0",
                "# Inspect interfaces before capture",
                "sudo ip -all netns exec ip -brief addr",
                "ip -brief addr",
                "# Observation and confidentiality evidence",
                f"sudo tcpdump -i wlan0 -n -vv -s 0 -Z \"$USER\" -w {capture_path('building', 'smart-building-ap-wlan0.pcap')}",
                "# 802.11 room/zone path evidence; --capture-hints prints the full current node list",
                f"sudo ip netns exec room-101 tcpdump -i wlan1 -n -vv -s 0 -Z \"$USER\" -w {capture_path('building', 'smart-building-room-101.pcap')}",
                "# MQTT telemetry and attack-impact evidence",
                f"sudo tcpdump -i any -n -vv -s 0 -Z \"$USER\" -w {capture_path('building', 'smart-building-mqtt-building.pcap')} port 1883",
                "mosquitto_sub -h localhost -v -t 'building/#'",
            ],
        },
        "medical": {
            "commands": [
                "# Live telemetry observation",
                "mosquitto_sub -h localhost -v -t 'patient/#'",
                "# Identity, authenticity, and spoofing attacks",
                "python3 attacks/run_attack.py --category authenticity --scenario medical --attack spoofed",
                "# Data integrity and manipulation attacks",
                "python3 attacks/run_attack.py --category integrity --scenario medical --attack extreme",
                "python3 attacks/run_attack.py --category integrity --scenario medical --attack malformed",
                "# Replay attacks",
                "python3 attacks/run_attack.py --category replay --scenario medical --attack replay",
                "# Scenario-focused examples",
                "python3 attacks/run_attack.py --category integrity --scenario medical --attack critical-vitals",
                "python3 attacks/run_attack.py --category replay --scenario medical --attack stale-vitals",
            ],
            "captures": [
                "# SSID/AP: SISEN-MEDICAL-IOT on wlan0",
                "# Inspect interfaces before capture",
                "sudo ip -all netns exec ip -brief addr",
                "ip -brief addr",
                "# Medical gateway and wearable-state evidence",
                "watch -n 1 cat /tmp/sisen-wearable-data.json",
                "tail -f /tmp/sisen-ble-wifi-gateway.log",
                "# 802.11/AP and gateway-path evidence",
                f"sudo tcpdump -i wlan0 -n -vv -s 0 -Z \"$USER\" -w {capture_path('medical', 'medical-ap-wlan0.pcap')}",
                f"sudo ip netns exec medical-gateway tcpdump -i wlan1 -n -vv -s 0 -Z \"$USER\" -w {capture_path('medical', 'medical-gateway-wlan1.pcap')}",
                "# MQTT patient telemetry and attack-impact evidence",
                f"sudo tcpdump -i any -n -vv -s 0 -Z \"$USER\" -w {capture_path('medical', 'medical-mqtt-patient-vitals.pcap')} port 1883",
                "mosquitto_sub -h localhost -v -t 'patient/#'",
            ],
        },
        "6lowpan": {
            "commands": [
                "# Communication and protocol attacks",
                "python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack spoofed",
                "python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack extreme",
                "python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack missing",
                "python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack replay",
                "# Scenario-focused examples",
                "python3 attacks/run_attack.py --category authenticity --scenario 6lowpan --attack rogue-sensor",
                "# MQTT/application observation",
                "mosquitto_sub -h localhost -v -t 'industrial/6lowpan/#'",
                "sudo ./6lowpan/sisen_lab.sh status",
                "sudo ./6lowpan/sisen_lab.sh stop",
            ],
            "captures": [
                "# SSID/AP: SISEN-6LOWPAN-* on wlan0 when AP mode is enabled",
                "# Inspect interfaces before capture",
                "sudo ip -all netns exec ip -brief addr",
                "ip -brief addr",
                "# IEEE 802.15.4 and 6LoWPAN evidence",
                f"sudo ip netns exec node1 tcpdump -i wpan1 -n -vv -s 0 -Z \"$USER\" -w {capture_path('6lowpan', '6lowpan-node1-wpan.pcap')}",
                f"sudo ip netns exec node1 tcpdump -i lowpan0 -n -vv -s 0 -Z \"$USER\" -w {capture_path('6lowpan', '6lowpan-node1-lowpan.pcap')}",
                f"sudo ip netns exec border tcpdump -i lowpan0 -n -vv -s 0 -Z \"$USER\" -w {capture_path('6lowpan', '6lowpan-border-lowpan.pcap')}",
                "# Border-router and forwarding-path evidence",
                f"sudo ip netns exec border tcpdump -i border-ip -n -vv -s 0 -Z \"$USER\" -w {capture_path('6lowpan', '6lowpan-border-ip.pcap')}",
                f"sudo ip netns exec node2 tcpdump -i node2-border -n -vv -s 0 -Z \"$USER\" -w {capture_path('6lowpan', '6lowpan-node2-border.pcap')}",
                f"sudo ip netns exec node2 tcpdump -i node2-mqtt -n -vv -s 0 -Z \"$USER\" -w {capture_path('6lowpan', '6lowpan-node2-mqtt.pcap')}",
                "# MQTT relay and dashboard-path evidence",
                f"sudo tcpdump -i any -n -vv -s 0 -Z \"$USER\" -w {capture_path('6lowpan', '6lowpan-mqtt-dashboard.pcap')} port 1883",
                "mosquitto_sub -h localhost -v -t 'industrial/6lowpan/temp-01/telemetry'",
                "mosquitto_sub -h localhost -v -t 'industrial/6lowpan/#'",
            ],
        },
        "scada": {
            "commands": [
                "# SCADA runtime",
                "python3 launch_sisen.py --scenario scada --ap-mode open",
                "python3 launch_sisen.py --scenario scada --ap-mode hidden",
                "python3 launch_sisen.py --scenario scada --ap-mode wep",
                "python3 launch_sisen.py --scenario scada --ap-mode wpa2",
                "# SCADA/AP observation",
                "sudo ip -brief link",
                "sudo iw dev",
                "# Scenario-specific attacks",
                "# Modbus/SCADA command injection guidance is not implemented yet; do not use generic MQTT attacks unless SCADA publishes through MQTT.",
                "bash ap/teardown-ap.sh",
            ],
            "captures": [
                f"sudo tcpdump -i wlan0 -n -vv -s 0 -Z \"$USER\" -w {capture_path('scada', 'ap-wlan0.pcap')}",
                f"sudo tcpdump -i any -n -vv -s 0 -Z \"$USER\" -w {capture_path('scada', 'scada-modbus-mqtt.pcap')} 'tcp port 502 or port 1883'",
                "sudo tcpdump -i any -n -vv -s 0 -Z \"$USER\" tcp port 502",
            ],
        },
    }


def _active_guidance_keys(scenario):
    scenario = normalize_scenario(scenario)
    if scenario == "all":
        return ["building", "medical", "6lowpan", "scada"]
    if scenario in _scenario_guidance():
        return [scenario]
    return ["building"]


def _guidance_items(kind):
    scenario = _active_dashboard_scenario()
    guidance = _scenario_guidance()
    items = []

    for key in _active_guidance_keys(scenario):
        if scenario == "all":
            items.append(f"# {key} guidance")
        items.extend(guidance[key][kind])

    return items


def current_snapshot():
    requested_scenario = app.config.get("SCENARIO", "all")
    scenario = normalize_scenario(requested_scenario)
    with data_lock:
        data = json.loads(json.dumps(latest_data))
        mqtt_snapshot = dict(mqtt_state)

    age = time.time() - data["last_update_epoch"] if data["last_update_epoch"] else None
    data["status"] = "ONLINE" if age is not None and age <= STALE_AFTER_SECONDS else "OFFLINE"
    data["age_seconds"] = round(age, 1) if age is not None else None
    ap_snapshot = read_ap_status()

    state = {
        "scenario": scenario,
        "scenario_label": scenario_label(scenario),
        "requested_scenario": requested_scenario,
        "repo_root": str(REPO_ROOT),
        "sections": visible_sections(scenario),
        "data": data,
        "mqtt": mqtt_snapshot,
        "ap": ap_snapshot,
        "devices": scenario_devices(_active_dashboard_scenario(), ap_snapshot),
        "building_nodes": building_nodes(ap_snapshot, data),
        "building_sensor_count": len(ap_snapshot.get("clients", [])),
        "medical_patients": medical_patients(data),
        "sixlowpan_nodes": sixlowpan_nodes(data),
        "sixlowpan_sensor_count": read_6lowpan_sensor_count(),
        "lab": read_lab_status(_active_dashboard_scenario()),
        "commands": student_commands(),
        "captures": capture_commands(),
        "topics": {
            "building": list(BUILDING_TOPICS.keys()),
            "medical": [
                "patient/+/vitals/heart_rate",
                "patient/+/vitals/spo2",
                "patient/+/vitals/blood_pressure",
                "patient/+/meta/ble_address",
                "patient/vitals/heart_rate",
                "patient/vitals/spo2",
                "patient/vitals/blood_pressure",
            ],
            "sixlowpan_json": ["industrial/6lowpan/temp-01/telemetry"],
            "scada": ["tcp/502", "scada/modbus"],
        },
    }
    return apply_ap_mode_state(state)


@app.route("/")
def dashboard():
    return render_template(
        "index.html",
        scenario=app.config.get("SCENARIO", "all"),
        initial_state=current_snapshot(),
    )


@app.route("/api/status")
def api_status():
    return jsonify(current_snapshot())


@app.route("/api/ap-status")
def api_ap_status():
    return jsonify(apply_ap_mode_state({"ap": read_ap_status()})["ap"])


@app.route("/api/lab-status")
def api_lab_status():
    return jsonify(read_lab_status(_active_dashboard_scenario()))


def parse_args():
    parser = argparse.ArgumentParser(description="SISEN scenario-aware observability dashboard.")
    parser.add_argument("--scenario", choices=SCENARIOS, default="all")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


def _active_dashboard_scenario():
    return app.config.get("SCENARIO") or app.config.get("scenario") or os.environ.get("SISEN_DASHBOARD_SCENARIO", "all")


def apply_ap_mode_state(state):
    if not AP_MODE_STATE_FILE.exists():
        return state

    try:
        mode = AP_MODE_STATE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return state

    if mode and isinstance(state.get("ap"), dict):
        state["ap"]["mode"] = mode
        filter_smart_building_clients(state["ap"])
    return state


def capture_commands():
    return _guidance_items("captures")


def student_commands():
    return _guidance_items("commands")


if __name__ == "__main__":
    args = parse_args()
    app.config["SCENARIO"] = args.scenario

    mqtt_thread = threading.Thread(target=mqtt_listener, args=(args.mqtt_host, args.mqtt_port), daemon=True)
    mqtt_thread.start()

    app.run(host=args.host, port=args.port)
