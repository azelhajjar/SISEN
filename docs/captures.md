# Captures

## Purpose

Packet captures help students connect the dashboard view to the actual communication paths used by each scenario.

The goal is to collect evidence from the right point in the topology: AP-side traffic, namespace interfaces, gateway paths, low-power interfaces, forwarding paths, and MQTT telemetry.

## Controlled Lab Warning

Capture commands are intended for the controlled SISEN lab environment only. Do not capture traffic from live networks or devices outside the lab.

## Before Capturing

Inspect active namespace interfaces:

```bash
sudo ip -all netns exec ip -brief addr
```

Inspect host interfaces:

```bash
ip -brief addr
```

The dashboard Capture Guidance panel also shows scenario-specific capture commands.

## Smart Building Capture Points

Launch example:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode open --nodes 4 --capture-hints
```

AP-side capture:

```bash
sudo tcpdump -i wlan0 -n -vv -s 0 -Z "$USER" -w captures/smart-building-ap-wlan0.pcap
```

One sensor namespace path:

```bash
sudo ip netns exec temp-sensor-1 tcpdump -i wlan1 -n -vv -s 0 -Z "$USER" -w captures/smart-building-temp-sensor-1.pcap
```

MQTT path:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/smart-building-mqtt-building.pcap port 1883
```

MQTT observation:

```bash
mosquitto_sub -h localhost -v -t 'building/#'
```

## Medical IoT Capture Points

Launch example:

```bash
python3 launch_sisen.py --scenario medical --ap-mode wep --patients 4 --capture-hints
```

Wearable state and gateway logs:

```bash
watch -n 1 cat /tmp/sisen-wearable-data.json
tail -f /tmp/sisen-ble-wifi-gateway.log
```

AP-side capture:

```bash
sudo tcpdump -i wlan0 -n -vv -s 0 -Z "$USER" -w captures/medical-ap-wlan0.pcap
```

Gateway namespace capture:

```bash
sudo ip netns exec medical-gateway tcpdump -i wlan1 -n -vv -s 0 -Z "$USER" -w captures/medical-gateway-wlan1.pcap
```

MQTT path:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/medical-mqtt-patient-vitals.pcap port 1883
```

MQTT observation:

```bash
mosquitto_sub -h localhost -v -t 'patient/#'
```

## 6LoWPAN Capture Points

Launch example:

```bash
python3 launch_sisen.py --scenario 6lowpan --ap-mode open --nodes 4 --capture-hints
```

IEEE 802.15.4 and 6LoWPAN-side evidence:

```bash
sudo ip netns exec node1 tcpdump -i wpan1 -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node1-wpan.pcap
sudo ip netns exec node1 tcpdump -i lowpan0 -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node1-lowpan.pcap
sudo ip netns exec border tcpdump -i lowpan0 -n -vv -s 0 -Z "$USER" -w captures/6lowpan-border-lowpan.pcap
```

Border-router and forwarding path:

```bash
sudo ip netns exec border tcpdump -i border-ip -n -vv -s 0 -Z "$USER" -w captures/6lowpan-border-ip.pcap
sudo ip netns exec node2 tcpdump -i node2-border -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node2-border.pcap
sudo ip netns exec node2 tcpdump -i node2-mqtt -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node2-mqtt.pcap
```

MQTT relay and dashboard path:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/6lowpan-mqtt-dashboard.pcap port 1883
```

MQTT observation:

```bash
mosquitto_sub -h localhost -v -t 'industrial/6lowpan/temp-01/telemetry'
mosquitto_sub -h localhost -v -t 'industrial/6lowpan/#'
```

## MQTT Capture

All SISEN scenarios use MQTT for dashboard-visible telemetry. A broad MQTT capture is:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/sisen-mqtt.pcap port 1883
```

A broad MQTT subscription is:

```bash
mosquitto_sub -h localhost -v -t '#'
```

## Opening Captures In Wireshark

Open the `.pcap` files from the `captures/` folder in Wireshark.

Useful filters include:

```text
mqtt
tcp.port == 1883
udp
ipv6
```

For 6LoWPAN, captures on `lowpan0` may show IPv6/UDP after Linux 6LoWPAN processing. Captures on `wpan` interfaces are closer to the low-power side, but decoding depends on kernel, libpcap, and Wireshark support in the VM.

## Evidence To Save

For each exercise, save:

- the launch command used
- the attack command used, if any
- the capture command used
- the `.pcap` file
- a short note explaining what changed in the dashboard
- a short note explaining which packet path showed the evidence

## Stop And Cleanup

Stop capture with `Ctrl+C` in the capture terminal.

Stop launcher-managed labs:

```bash
python3 launch_sisen.py --stop
```
