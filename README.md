# SISEN

SISEN is a Security-Informed Safety Education Network for controlled cybersecurity and safety labs. It provides simulated IoT, wireless, and low-power network scenarios that students can launch, observe, capture, and attack inside a lab environment.

SISEN is designed for teaching security-informed safety: students observe how security failures in telemetry, identity, communication paths, and availability can create unsafe decisions or unsafe operating conditions.

## Lab Scenarios

- Smart Building IoT
- Medical IoT
- 6LoWPAN Industrial IoT

## Prerequisites

SISEN was developed and validated on Ubuntu Linux running inside a virtual
machine.

Recommended environment:

- Ubuntu 24.04 or later
- Python 3.10 or later

Minimum required system packages:

```bash
sudo apt update

sudo apt install -y \
    hostapd \
    dnsmasq \
    mosquitto \
    mosquitto-clients \
    iw \
    iproute2 \
    net-tools \
    python3 \
    python3-venv \
    python3-pip \
    dos2unix \
    netcat-openbsd
```

Package purpose:

| Package | Purpose |
| --- | --- |
| `hostapd` | Wireless access point |
| `dnsmasq` | DHCP / DNS support |
| `mosquitto` | MQTT broker |
| `mosquitto-clients` | MQTT diagnostics |
| `iw` | Wireless inspection |
| `iproute2` | Namespaces / networking |
| `net-tools` | Diagnostics |
| `python3` | Runtime |
| `python3-venv` | Virtual environments |
| `python3-pip` | Python packages |
| `dos2unix` | Windows line ending fixes |
| `netcat-openbsd` | Broker connectivity testing |

## Setup

Run setup from the repository root:

```bash
./setup.sh
```

The setup script installs the required system packages with `apt-get`, creates
the project Python environment under `.venv/`, and installs the Python package
dependencies listed in `requirements.txt`:

```text
flask
paho-mqtt
pyyaml
```

## Launch

Start the interactive menu:

```bash
python3 launch_sisen.py
```

Direct launch examples, without using the menu:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode open --nodes 4 --capture-hints
python3 launch_sisen.py --scenario medical --ap-mode wep --patients 4 --capture-hints
python3 launch_sisen.py --scenario 6lowpan --ap-mode open --nodes 4 --capture-hints
```

Common direct launcher options:

| Option | Use |
| --- | --- |
| `--scenario smart-building` | Start the Smart Building scenario. |
| `--scenario medical` | Start the Medical IoT scenario. |
| `--scenario 6lowpan` | Start the 6LoWPAN scenario. |
| `--ap-mode open` | Use an open AP. |
| `--ap-mode hidden` | Use a hidden SSID AP. |
| `--ap-mode wep` | Use a WEP AP for lab observation. |
| `--ap-mode wpa2` | Use a WPA2-PSK AP. |
| `--ap-mode macfilter` | Use MAC filtering for the Smart Building example activity. |
| `--nodes N` | Set Smart Building or 6LoWPAN node count, 1-10. |
| `--patients N` | Set Medical IoT patient/wearable count, 1-10. |
| `--capture-hints` | Print capture guidance for the selected scenario. |
| `--stop` | Stop launcher-managed labs and dashboard processes. |

The AP modes are:

- `open`
- `hidden`
- `wep`
- `wpa2`
- `macfilter` for the Smart Building example activity

Smart Building includes the `macfilter` example activity:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode macfilter --nodes 4 --capture-hints
```

## Dashboard

The unified dashboard runs at:

```text
http://localhost:5000
```

The dashboard is read-only. Lab start, stop, attack, and capture commands remain terminal-controlled.

## Attacks

List available attacks:

```bash
python3 attacks/run_attack.py --list
```

Attack commands are intended for the controlled SISEN lab environment only. Run them after the relevant scenario is already running.

## Captures

Capture guidance is shown in the launcher when `--capture-hints` is used and in the dashboard Capture Guidance panel.

Before capturing, inspect the active interfaces:

```bash
sudo ip -all netns exec ip -brief addr
ip -brief addr
```

Capture files should be written under:

```text
captures/
```

## Documentation

Scenario and lab documentation:

- [Smart Building IoT](docs/smart-building.md)
- [Medical IoT](docs/medical-iot.md)
- [6LoWPAN Industrial IoT](docs/6lowpan-iot.md)
- [Attacks](docs/attacks.md)
- [Manual Attacks](docs/manual-attacks.md)
- [Captures](docs/captures.md)
- [Troubleshooting](docs/troubleshooting.md)

Hardware AP documentation is kept separately from the SISEN scenario docs:

```text
ap/hw-ap/docs/
```

The HW-AP materials support separate wireless security activities used at the University of Westminster. They are not part of the main SISEN scenario launcher, but are kept for students who want to explore wireless threats and infrastructure behaviour separately.

## Stop

Stop launcher-managed labs and dashboard processes:

```bash
python3 launch_sisen.py --stop
```

## Acknowledgments

The initial repository was used for wireless security teaching at the University of Westminster for the BSc Cyber Security and Forensics. This project extends that work to focus on security-informed safety aspects of IoT systems.

SISEN forms part of the CyBOK Security-Informed Safety educational resources programme and was developed with support from the 2025-2026 CyBOK funding round. We are grateful to everyone who contributed ideas, expertise, and feedback during the development of this project.
