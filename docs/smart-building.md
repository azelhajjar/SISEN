# Smart Building IoT

## Purpose

The Smart Building scenario demonstrates how building telemetry and automation can become safety-relevant when sensor data is spoofed, replayed, manipulated, or disrupted.

Students observe environmental and occupancy telemetry, inspect the wireless and MQTT paths, and run bounded attacks against the simulated building environment.

## Scenario Overview

The scenario creates a HWSIM wireless access point and a configurable number of simulated building sensor nodes. Each node runs in a Linux namespace and publishes telemetry through MQTT to the dashboard.

Typical telemetry includes temperature, humidity, air quality, occupancy, fire alarm, smoke, CO2, gas leak, emergency exit, sprinkler, pressure, machine overheat, and emergency stop status.

## Topology

```text
Smart Building sensors in namespaces
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

The AP interface is normally `wlan0`. Sensor namespace interfaces are assigned as `wlan1`, `wlan2`, and so on.

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

The launcher accepts between 1 and 10 Smart Building sensor nodes.

## Dashboard View

Open:

```text
http://localhost:5000
```

The dashboard shows:

- telemetry status
- MQTT connection status
- AP mode, SSID, IP address, and associated stations
- one card per active Smart Building sensor node
- student attack and capture guidance

## MQTT Topics

Subscribe to all Smart Building telemetry:

```bash
mosquitto_sub -h localhost -v -t 'building/#'
```

Node-level topics follow this pattern:

```text
building/nodes/node-01/temperature
building/nodes/node-02/humidity
building/nodes/node-03/air_quality
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
sudo python3 attacks/run_attack.py --category availability --scenario building --attack client-drop --target temperature
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

Capture one sensor namespace path:

```bash
sudo ip netns exec temp-sensor-1 tcpdump -i wlan1 -n -vv -s 0 -Z "$USER" -w captures/smart-building-temp-sensor-1.pcap
```

Capture MQTT telemetry and attack impact:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/smart-building-mqtt-building.pcap port 1883
```

## Safety Discussion

Use the scenario to discuss questions such as:

- Can the system detect that a correctly formatted value is implausible or unsafe?
- Could spoofed occupancy, air quality, fire, smoke, or gas data cause an unsafe response?
- What is the difference between detecting a network attack and detecting unsafe operational state?
- Which controls would reduce unsafe decisions caused by false telemetry?

## Stop And Cleanup

Stop from another terminal:

```bash
python3 launch_sisen.py --stop
```

Or press `Ctrl+C` in the launcher terminal.
