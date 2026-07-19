from pathlib import Path
import sys
import yaml


REQUIRED_TOP_LEVEL_FIELDS = [
    "scenario",
    "ap",
    "devices",
    "traffic",
    "security",
    "failures",
    "anomalies",
    "sensor_data",
]

SUPPORTED_SCENARIO_TYPES = [
    "scada",
    "iot",
    "medical_ble",
    "mqtt_testbed",
    "sisen_full",
]

SUPPORTED_AP_MODES = [
    "open",
    "hidden",
    "macfilter",
    "openwrt",
    "rogue",
    "wep",
    "wpa2",
    "wpa2-enterprise",
]

SUPPORTED_TRAFFIC_INTENSITIES = [
    "low",
    "medium",
    "high",
]


def load_config(config_path):
    path = Path(config_path)

    if not path.exists():
        print(f"ERROR: config file not found: {config_path}")
        sys.exit(1)

    try:
        with path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
    except yaml.YAMLError as error:
        print(f"ERROR: invalid YAML in {config_path}")
        print(error)
        sys.exit(1)

    if config is None:
        print(f"ERROR: config file is empty: {config_path}")
        sys.exit(1)

    return config


def require_field(config, field_path):
    current = config

    for field in field_path.split("."):
        if not isinstance(current, dict) or field not in current:
            print(f"ERROR: missing required field: {field_path}")
            sys.exit(1)

        current = current[field]

    return current


def require_int_range(config, field_path, minimum, maximum):
    value = require_field(config, field_path)

    if not isinstance(value, int):
        print(f"ERROR: field '{field_path}' must be an integer")
        sys.exit(1)

    if value < minimum or value > maximum:
        print(f"ERROR: field '{field_path}' must be between {minimum} and {maximum}")
        sys.exit(1)

    return value


def require_bool(config, field_path):
    value = require_field(config, field_path)

    if not isinstance(value, bool):
        print(f"ERROR: field '{field_path}' must be true or false")
        sys.exit(1)

    return value


def validate_config(config):
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in config:
            print(f"ERROR: missing required top-level section: {field}")
            sys.exit(1)

    scenario_type = require_field(config, "scenario.type")
    if scenario_type not in SUPPORTED_SCENARIO_TYPES:
        print(f"ERROR: unsupported scenario type: {scenario_type}")
        print(f"Supported scenario types: {', '.join(SUPPORTED_SCENARIO_TYPES)}")
        sys.exit(1)

    ap_mode = require_field(config, "ap.mode")
    if ap_mode not in SUPPORTED_AP_MODES:
        print(f"ERROR: unsupported AP mode: {ap_mode}")
        print(f"Supported AP modes: {', '.join(SUPPORTED_AP_MODES)}")
        sys.exit(1)

    traffic_intensity = require_field(config, "traffic.intensity")
    if traffic_intensity not in SUPPORTED_TRAFFIC_INTENSITIES:
        print(f"ERROR: unsupported traffic intensity: {traffic_intensity}")
        print(f"Supported traffic intensities: {', '.join(SUPPORTED_TRAFFIC_INTENSITIES)}")
        sys.exit(1)

    require_field(config, "scenario.name")
    require_field(config, "scenario.description")
    require_field(config, "ap.interface")
    require_field(config, "ap.ssid")
    require_field(config, "ap.channel")
    require_field(config, "traffic.protocol")

    require_int_range(config, "devices.hmi", 1, 1)
    require_int_range(config, "devices.scada_server", 1, 1)
    require_int_range(config, "devices.plc", 1, 5)
    require_int_range(config, "devices.rtu", 1, 5)
    require_int_range(config, "devices.sensors", 1, 10)

    require_bool(config, "security.weak_device_authentication")
    require_bool(config, "security.default_credentials_enabled")
    require_bool(config, "failures.random_device_dropoff")
    require_bool(config, "anomalies.enabled")
    require_bool(config, "anomalies.out_of_range_values")
    require_bool(config, "anomalies.unexpected_commands")

    require_field(config, "sensor_data.temperature.min")
    require_field(config, "sensor_data.temperature.max")
    require_field(config, "sensor_data.pressure.min")
    require_field(config, "sensor_data.pressure.max")
    require_field(config, "sensor_data.flow_rate.min")
    require_field(config, "sensor_data.flow_rate.max")

    return config