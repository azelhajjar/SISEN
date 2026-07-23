# Captures

## Purpose

Packet captures help students connect the dashboard view to the actual communication paths used by each scenario.

The goal is to collect evidence from the right point in the topology: AP-side traffic, namespace interfaces, gateway paths, low-power interfaces, forwarding paths, and MQTT telemetry.

## Controlled Lab Warning

Capture commands are intended for the controlled SISEN lab environment only. Do not capture traffic from live networks or devices outside the lab.

## Before Capturing

Start the required SISEN scenario before looking for capture interfaces. The available namespaces and interfaces depend on the active scenario.

List all active network namespaces:

```bash
sudo ip netns list
```

Show all interfaces and addresses inside every active namespace:

```bash
sudo ip -all netns exec ip -brief addr
```

Show interfaces in one specific namespace:

```bash
sudo ip netns exec <namespace> ip -brief addr
```

For example:

```bash
sudo ip netns exec room-101 ip -brief addr
sudo ip netns exec medical-gateway ip -brief addr
sudo ip netns exec node1 ip -brief addr
```

Show host interfaces:

```bash
ip -brief addr
```

Show host interfaces with their operational state and additional details:

```bash
ip link show
```

For wireless interfaces, also inspect the wireless interface type and current mode:

```bash
iw dev
```

Typical capture points include:

- host interfaces such as `wlan0`, loopback, bridge, or virtual Ethernet interfaces;
- interfaces inside scenario namespaces, such as `wlan1`, `lowpan0`, `wpan1`, or namespace-specific forwarding interfaces;
- the `any` interface when the exact host-side path is not yet known;
- MQTT traffic on TCP port `1883`;
- the 6LoWPAN relay broker on TCP port `1884`.

Select the interface that corresponds to the communication path being investigated. Capturing on `any` is useful for broad observation, but an interface-specific capture usually provides clearer evidence about where traffic entered or left the system.

The dashboard Capture Guidance panel also shows scenario-specific capture commands.

**Note:** Capture files should be saved in the `captures/` folder included in the repository.

## Smart Building Capture Points

Launch example:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode open --nodes 4 --capture-hints
```

AP-side capture:

```bash
sudo tcpdump -i wlan0 -n -vv -s 0 -Z "$USER" -w captures/smart-building-ap-wlan0.pcap
```

One room/zone namespace path:

```bash
sudo ip netns exec room-101 tcpdump -i wlan1 -n -vv -s 0 -Z "$USER" -w captures/smart-building-room-101.pcap
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
mosquitto_sub -h localhost -p 1883 -t 'industrial/6lowpan/#' -v
mosquitto_sub -h fd00:6:2::1 -p 1884 -t '#' -v
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

The purpose is not to analyse every protocol field. Focus on evidence that explains normal scenario behaviour or the effect of a controlled attack.

Useful general filters include:

```text
mqtt
tcp.port == 1883
tcp.port == 1884
udp
ipv6
icmpv6
```

For MQTT traffic, inspect:

- the source and destination addresses;
- the MQTT `PUBLISH` message;
- the topic name;
- the message payload;
- the order and frequency of messages;
- repeated, stale, malformed, missing, or unexpected values.

Useful topic filters include:

```text
mqtt.topic contains "building"
mqtt.topic contains "patient"
mqtt.topic contains "industrial/6lowpan"
```

For Wi-Fi captures, useful filters include:

```text
wlan
wlan_mgt
eapol
```

Inspect the SSID, BSSID, channel, client addresses, authentication and association frames, normal data frames, and any unusual management traffic.

For IPv6, UDP, and 6LoWPAN-side captures, inspect:

- source and destination addresses;
- UDP ports;
- node or sensor identifiers in the payload;
- timestamps;
- telemetry fields and values;
- repeated or inconsistent payloads.

For 6LoWPAN, captures on `lowpan0` may show IPv6 and UDP after Linux 6LoWPAN processing. Captures on `wpan` interfaces are closer to the IEEE 802.15.4 side, but decoding depends on kernel, libpcap, and Wireshark support in the VM.

When comparing normal behaviour with an attack, look for changes in:

- the sender or claimed node identity;
- the destination or MQTT topic;
- payload values;
- message structure;
- timestamps;
- transmission frequency;
- repeated identical messages;
- the relationship between the captured traffic and the dashboard state.

The capture should support a simple explanation of what changed, where it changed, and how that change affected the monitored system.

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
