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

## Installation

Install Git, clone SISEN, install the system dependencies, set up the Python
environment, and start the launcher:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/azelhajjar/SISEN.git
cd SISEN
sudo ./setup/setup-dependencies.sh
./setup.sh
python3 launch_sisen.py
```

**Note:** All commands in this repository assume that you are running them from the repository root directory.

`setup/setup-dependencies.sh` installs the operating-system, networking,
wireless, capture and analysis dependencies. Wireshark is required for the
practical activities.

`setup.sh` creates the Python virtual environment and installs the Python
packages listed in `requirements.txt`. Students do not need to activate `.venv`
manually.

```text
flask
paho-mqtt
pyyaml
```

## Environment Configuration

During system setup, SISEN creates `.env` from `.env.example` if `.env` does not already exist.

The default configuration is suitable for the simulated scenarios, so students normally do not need to edit `.env` before launching SISEN.

Use `.env.example` as the reference for the available settings and expected values. Edit `.env` only when using a physical wireless adaptor or changing access point settings.

To identify an available wireless interface, run:

```bash
iw dev
```

Do not commit passwords, keys or other local `.env` values to the repository.

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
| `--nodes N` | Set Smart Building room/zone count or 6LoWPAN industrial asset count, 1-10. |
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

The project website, [sisen.uk](https://sisen.uk), provides further
explanations, video recordings, and demonstrations.

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

## Future Extensions

Possible future extensions include BLE-specific attacks, additional IoT infrastructure attacks, and further manual wireless activities. These are not required for the current SISEN lab scenarios.

## Acknowledgments

The initial repository was used for wireless security teaching at the University of Westminster for the BSc Cyber Security and Forensics. This project extends that work to focus on security-informed safety aspects of IoT systems.

SISEN forms part of the CyBOK Security-Informed Safety educational resources programme and was developed with support from the 2025-2026 CyBOK funding round. We are grateful to everyone who contributed ideas, expertise, and feedback during the development of this project.
