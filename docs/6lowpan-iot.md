# 6LoWPAN Industrial IoT

## Purpose

The 6LoWPAN Industrial IoT scenario demonstrates telemetry security effects across a low-power network path. Students observe IEEE 802.15.4, 6LoWPAN, border-router forwarding, MQTT relay, and dashboard telemetry.

The scenario focuses on controlled telemetry attacks and communication-path observation. Do not describe these activities as RPL attacks unless a separate RPL activity is explicitly introduced.

Use this guide with the lab worksheet provided in `teaching-materials/labs/`.
The worksheet contains the activity questions and safety/hazard analysis prompts.

## Scenario Overview

The scenario creates a Linux-native 6LoWPAN topology with sensor-side and border-router namespaces. Telemetry flows from the low-power side through a border path and into MQTT/dashboard topics.

With `--nodes 4`, the dashboard shows four industrial asset cards: Boiler Room, Process Line, Cold Storage, and Loading Bay. Each card combines several readings and shows the related Sensor IDs.

## Topology

```text
node1 namespace
  wpan1 / lowpan0
        |
        | 6LoWPAN path
        v
border namespace
  lowpan0 / border-ip
        |
        | forwarding path
        v
node2 namespace
  node2-border / node2-mqtt
        |
        v
MQTT broker and dashboard topics
```

When AP mode is enabled, the scenario also exposes an AP using an SSID with the `SISEN-6LOWPAN-*` prefix.

## Launch Commands

Interactive launch:

```bash
python3 launch_sisen.py
```

Direct launch:

```bash
python3 launch_sisen.py --scenario 6lowpan --ap-mode open --nodes 4 --capture-hints
```

Supported AP modes:

```text
open, hidden, wep, wpa2
```

The launcher accepts between 1 and 10 6LoWPAN industrial assets. The default is 4.

## Dashboard View

Open:

```text
http://localhost:5000
```

The dashboard shows:

- telemetry status
- MQTT connection status
- AP/backhaul mode when enabled
- 6LoWPAN industrial asset cards built from active telemetry groups
- 6LoWPAN gateway and MQTT broker status
- student attack and capture guidance

## MQTT Topics

Subscribe to all 6LoWPAN dashboard telemetry:

```bash
mosquitto_sub -h localhost -p 1883 -t 'industrial/6lowpan/#' -v
mosquitto_sub -h fd00:6:2::1 -p 1884 -t '#' -v
```

Common topics include:

```text
industrial/6lowpan/temp-01/telemetry
industrial/6lowpan/nodes/#
```

## Attacks To Try

List attacks:

```bash
python3 attacks/run_attack.py --list --scenario 6lowpan
```

Example protocol-path attacks:

```bash
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack spoofed
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack extreme
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack missing
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack replay
```

When the scenario is already running, these helpers inject through the active
6LoWPAN lab namespace path rather than rebuilding the topology. Applicable
attacks refresh the selected injected payload for about 10 seconds at 0.5
second intervals; replay remains count-based. Normal telemetry continues during
the attack and should restore the dashboard after the helper exits.

The general attacks `spoofed`, `extreme`, `replay`, `missing`, and `malformed`
support all four active industrial assets when `--nodes 4` is used:

| Node | Asset | Fields |
| --- | --- | --- |
| `node-01` | Boiler Room | `temperature`, `gas_leak`, `pressure_status`, `emergency_stop` |
| `node-02` | Process Line | `temperature`, `humidity`, `machine_overheat`, `emergency_stop` |
| `node-03` | Cold Storage | `temperature`, `humidity`, `occupancy`, `air_quality` |
| `node-04` | Loading Bay | `temperature`, `gas_leak`, `occupancy`, `air_quality` |

Each run selects one eligible target, keeps it fixed for the full run, and uses
a node-specific valid payload. Repeated runs use a shuffled rotation so all
eligible nodes are used before reshuffling and immediate repeats are avoided
when alternatives exist.

Scenario-focused safety cases:

```bash
python3 attacks/run_attack.py --category safety-case --scenario 6lowpan --attack boiler-pressure-masked
python3 attacks/run_attack.py --category safety-case --scenario 6lowpan --attack emergency-stop-hidden
python3 attacks/run_attack.py --category safety-case --scenario 6lowpan --attack machine-overheat-hidden
```

Safety-case attacks remain constrained to the assets where the safety condition
is meaningful: `boiler-pressure-masked` targets Boiler Room only,
`emergency-stop-hidden` targets Boiler Room or Process Line, and
`machine-overheat-hidden` targets Process Line only.

## Captures To Collect

Inspect interfaces before capture:

```bash
sudo ip -all netns exec ip -brief addr
ip -brief addr
```

Capture IEEE 802.15.4 and 6LoWPAN-side evidence:

```bash
sudo ip netns exec node1 tcpdump -i wpan1 -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node1-wpan.pcap
sudo ip netns exec node1 tcpdump -i lowpan0 -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node1-lowpan.pcap
sudo ip netns exec border tcpdump -i lowpan0 -n -vv -s 0 -Z "$USER" -w captures/6lowpan-border-lowpan.pcap
```

Capture border-router and forwarding-path evidence:

```bash
sudo ip netns exec border tcpdump -i border-ip -n -vv -s 0 -Z "$USER" -w captures/6lowpan-border-ip.pcap
sudo ip netns exec node2 tcpdump -i node2-border -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node2-border.pcap
sudo ip netns exec node2 tcpdump -i node2-mqtt -n -vv -s 0 -Z "$USER" -w captures/6lowpan-node2-mqtt.pcap
```

Capture MQTT relay/dashboard-path evidence:

```bash
sudo tcpdump -i any -n -vv -s 0 -Z "$USER" -w captures/6lowpan-mqtt-dashboard.pcap port 1883
```

## Stop And Cleanup

Stop from another terminal:

```bash
python3 launch_sisen.py --stop
```

Or press `Ctrl+C` in the launcher terminal.
