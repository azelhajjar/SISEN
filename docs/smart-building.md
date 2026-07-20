# Smart Building IoT

## Purpose

The Smart Building scenario demonstrates how building telemetry and automation can become safety-relevant when sensor data is spoofed, replayed, manipulated, or disrupted.

Students observe environmental and occupancy telemetry, inspect the wireless and MQTT paths, and run bounded attacks against the simulated building environment.

Use this guide with the lab worksheet provided in `teaching-materials/labs/`.
The worksheet contains the activity questions and safety/hazard analysis prompts.

## Scenario Overview

The scenario creates a HWSIM wireless access point and a configurable number of simulated building room or zone groups. Each group runs in a Linux namespace and publishes several telemetry fields through MQTT to the dashboard.

Typical telemetry includes temperature, humidity, air quality, occupancy, fire alarm, smoke, CO2, gas leak, emergency exit, and sprinkler status.

With `--nodes 4`, the dashboard shows four room/zone cards: Room 101, Plant Room, Server Room, and Workshop. Each card combines several readings and shows the related Sensor IDs.

## Topology

```text
Smart Building room/zone groups in namespaces
        |
        | Wi-Fi association to HWSIM AP
        v
wlan0 / SISEN-SMART-BUILDING
        |
        v
MQTT broker on localhost:1883
        |
        v
SISEN dashboard
```

The AP interface is normally `wlan0`. Room/zone namespace interfaces are assigned as `wlan1`, `wlan2`, and so on.

## Launch Commands

Interactive launch:

```bash
python3 launch_sisen.py
```

Direct launch:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode open --nodes 4 --capture-hints
```

Supported AP modes:

```text
open, hidden, wep, wpa2, macfilter
```

The Smart Building example can be launched with `macfilter`:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode macfilter --nodes 4 --capture-hints
```

## MAC Filtering Mode

Use `--ap-mode macfilter` when the Smart Building activity needs the AP to allow only the configured sensor MAC addresses.

The scenario still launches normally through `launch_sisen.py`, but the MAC filtering observation or bypass is a manual infrastructure activity. Run it from a separate terminal and record the AP SSID, BSSID, channel, allowed sensor MAC address, and capture filename.

See [Manual Attacks](manual-attacks.md) for monitor-mode and capture guidance.

The launcher accepts between 1 and 10 Smart Building room/zone groups.

## Dashboard View

Open:

```text
http://localhost:5000
```

The dashboard shows:

- telemetry status
- MQTT connection status
- AP mode, SSID, IP address, and associated stations
- Smart Building room/zone cards built from active telemetry groups
- student attack and capture guidance

## MQTT Topics

Subscribe to all Smart Building telemetry:

```bash
mosquitto_sub -h localhost -v -t 'building/#'
```

Node-level topics follow this pattern:

```text
building/nodes/node-01/temperature
building/nodes/node-01/fire_alarm
building/nodes/node-01/occupancy
building/nodes/node-01/gas_leak
```

## Attacks To Try

List attacks:

```bash
python3 attacks/run_attack.py --list --scenario building
```

Example attacks:

```bash
python3 attacks/run_attack.py --category authenticity --scenario building --attack spoofed
python3 attacks/run_attack.py --category integrity --scenario building --attack extreme
python3 attacks/run_attack.py --category replay --scenario building --attack replay
python3 attacks/run_attack.py --category availability --scenario building --attack noise --count 5
sudo python3 attacks/run_attack.py --category availability --scenario building --attack client-drop --target room-101
sudo python3 attacks/run_attack.py --category availability --scenario building --attack sensor-blackout --duration 10
```

Scenario-focused examples:

```bash
python3 attacks/run_attack.py --category authenticity --scenario building --attack false-occupancy
python3 attacks/run_attack.py --category integrity --scenario building --attack environment-extreme
```

## Captures To Collect

Inspect interfaces before capture:

```bash
sudo ip -all netns exec ip -brief addr
ip -brief addr
```

Capture AP-side traffic:

```bash
sudo tcpdump -i wlan0 -n -vv -s 0 -Z "$USER" -w captures/smart-building-ap-wlan0.pcap
```

Capture one room/zone namespace path:

```bash
sudo ip netns exec room-101 tcpdump -i wlan1 -n -vv -s 0 -Z "$USER" -w captures/smart-building-room-101.pcap
```

Capture MQTT telemetry and attack impact:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/smart-building-mqtt-building.pcap port 1883
```

## Stop And Cleanup

Stop from another terminal:

```bash
python3 launch_sisen.py --stop
```

Or press `Ctrl+C` in the launcher terminal.
