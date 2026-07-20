# Medical IoT

## Purpose

The Medical IoT scenario demonstrates how patient vital-sign telemetry can become safety-relevant when values are spoofed, replayed, malformed, or manipulated.

Students observe simulated patient wearables, a BLE-to-Wi-Fi gateway path, MQTT telemetry, and the dashboard.

Use this guide with the lab worksheet provided in `teaching-materials/labs/`.
The worksheet contains the activity questions and safety/hazard analysis prompts.

## Scenario Overview

The scenario simulates patient wearables and a Medical IoT gateway. The wearables are represented as simulated BLE sources. The gateway is the Wi-Fi station associated with the HWSIM AP and forwards patient telemetry toward MQTT and the dashboard.

This means the AP may show one associated station while the dashboard shows several patients/wearables.

## Topology

```text
Simulated patient wearables
        |
        | BLE-style source data
        v
medical-gateway namespace
        |
        | Wi-Fi association to HWSIM AP
        v
wlan0 / SISEN-MEDICAL-IOT
        |
        v
MQTT broker on localhost:1883
        |
        v
SISEN dashboard
```

## Launch Commands

Interactive launch:

```bash
python3 launch_sisen.py
```

Direct launch:

```bash
python3 launch_sisen.py --scenario medical --ap-mode wep --patients 4 --capture-hints
```

Supported AP modes:

```text
open, hidden, wep, wpa2
```

The launcher accepts between 1 and 10 patients/wearables. The default is 1.

## Dashboard View

Open:

```text
http://localhost:5000
```

The dashboard shows:

- telemetry status
- MQTT connection status
- Wi-Fi/AP mode, SSID, IP address, and associated stations
- patients/wearables count
- BLE gateway status
- one patient card per configured patient/wearable
- student attack and capture guidance

In this scenario, `Associated stations` means Wi-Fi stations associated with the AP. The simulated patients/wearables are shown separately.

## MQTT Topics

Subscribe to all Medical IoT telemetry:

```bash
mosquitto_sub -h localhost -v -t 'patient/#'
```

Patient topics include:

```text
patient/patient-1/vitals/heart_rate
patient/patient-1/vitals/spo2
patient/patient-1/vitals/blood_pressure
patient/patient-1/alerts/fall_alert
patient/patient-1/alerts/panic_button
patient/patient-1/alerts/battery_status
patient/patient-1/alerts/wearable_link
patient/patient-1/meta/ble_address
```

## Attacks To Try

List attacks:

```bash
python3 attacks/run_attack.py --list --scenario medical
```

Example attacks:

```bash
python3 attacks/run_attack.py --category authenticity --scenario medical --attack spoofed
python3 attacks/run_attack.py --category integrity --scenario medical --attack extreme
python3 attacks/run_attack.py --category integrity --scenario medical --attack malformed
python3 attacks/run_attack.py --category replay --scenario medical --attack replay
```

Scenario-focused safety cases:

```bash
python3 attacks/run_attack.py --category safety-case --scenario medical --attack critical-vitals
python3 attacks/run_attack.py --category safety-case --scenario medical --attack fall-alert-suppressed
python3 attacks/run_attack.py --category safety-case --scenario medical --attack panic-button-suppressed
python3 attacks/run_attack.py --category safety-case --scenario medical --attack battery-falsely-normal
```

## Captures To Collect

Inspect interfaces before capture:

```bash
sudo ip -all netns exec ip -brief addr
ip -brief addr
```

Observe wearable state and gateway logs:

```bash
watch -n 1 cat /tmp/sisen-wearable-data.json
tail -f /tmp/sisen-ble-wifi-gateway.log
```

Capture AP-side traffic:

```bash
sudo tcpdump -i wlan0 -n -vv -s 0 -Z "$USER" -w captures/medical-ap-wlan0.pcap
```

Capture the gateway namespace path:

```bash
sudo ip netns exec medical-gateway tcpdump -i wlan1 -n -vv -s 0 -Z "$USER" -w captures/medical-gateway-wlan1.pcap
```

Capture MQTT patient telemetry:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/medical-mqtt-patient-vitals.pcap port 1883
```

## Stop And Cleanup

Stop from another terminal:

```bash
python3 launch_sisen.py --stop
```

Or press `Ctrl+C` in the launcher terminal.
