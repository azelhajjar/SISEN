# Troubleshooting

## Purpose

This guide covers common issues when launching SISEN scenarios, viewing the dashboard, running attacks, and collecting captures.

Start with the launcher output. It prints the scenario, AP mode, dashboard URL, log paths, MQTT validation command, and stop command.

## Launcher Issues

If the launcher says the Python environment is not ready, run setup from the repository root:

```bash
./setup.sh
```

Then launch again:

```bash
python3 launch_sisen.py
```

If a scenario fails to start, check the log path printed by the launcher. Common log locations include:

```text
/tmp/sisen-launcher-dashboard.log
/tmp/sisen-start-smart-building---hwsim-iot.log
/tmp/sisen-start-medical-iot.log
/tmp/sisen-6lowpan-launcher.log
```

Use:

```bash
tail -n 80 /tmp/sisen-launcher-dashboard.log
```

Replace the log path with the one printed by your launcher output.

## Sudo And Permissions

SISEN networking uses namespaces, HWSIM radios, AP setup, and packet capture. These need root privileges.

The launcher re-runs itself with `sudo` when needed:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode open --nodes 4
```

Capture commands normally need `sudo`:

```bash
sudo tcpdump -i wlan0 -n -vv -s 0 -Z "$USER" -w captures/test.pcap
```

If sudo authentication fails, re-run the command and enter the correct VM password.

## Namespace Issues

List active namespaces:

```bash
sudo ip netns list
```

Inspect namespace interfaces:

```bash
sudo ip -all netns exec ip -brief addr
```

If expected namespaces are missing, the scenario may not have started correctly or may have been cleaned up. Relaunch the scenario and check the launcher logs.

If old namespaces remain from a failed run, stop SISEN:

```bash
python3 launch_sisen.py --stop
```

Then launch again.

## Wireless Interface Issues

Inspect host interfaces:

```bash
ip -brief addr
```

Inspect wireless interfaces:

```bash
iw dev
```

For HWSIM scenarios, `wlan0` is normally the AP-side interface. Client interfaces may move into namespaces, so they may not appear on the host after the scenario starts.

If `wlan0` is missing or the AP does not start, stop and relaunch:

```bash
python3 launch_sisen.py --stop
python3 launch_sisen.py --scenario smart-building --ap-mode open --nodes 4
```

## AP Issues

The dashboard infrastructure panel shows the active AP/backhaul mode, SSID, IP address, AP status, and associated stations where relevant.

For Smart Building, associated stations usually correspond to simulated sensor nodes.

For Medical IoT, associated stations usually means the Wi-Fi gateway station. Patients/wearables are shown separately in the dashboard.

For 6LoWPAN, sensor nodes are low-power topology nodes, not normal Wi-Fi stations.

## MQTT Issues

Validate MQTT from another terminal:

```bash
mosquitto_sub -h localhost -t '#' -v
```

Scenario-specific subscriptions:

```bash
mosquitto_sub -h localhost -v -t 'building/#'
mosquitto_sub -h localhost -v -t 'patient/#'
mosquitto_sub -h localhost -v -t 'industrial/6lowpan/#'
```

If no messages arrive:

- confirm the scenario is still running
- check the launcher logs
- check the dashboard MQTT status
- run `python3 launch_sisen.py --stop` and relaunch if the lab is in a stale state

## Dashboard Issues

Open:

```text
http://localhost:5000
```

If the dashboard does not load, check:

```bash
tail -n 80 /tmp/sisen-launcher-dashboard.log
```

If the dashboard loads but shows stale or missing data:

- confirm the correct scenario was launched
- check MQTT with `mosquitto_sub`
- refresh the browser
- stop and relaunch the scenario if old state appears to remain

## Capture Issues

The `captures/` folder is included in the repository. If a capture command
fails, first confirm that the command is being run from the repository root.

If tcpdump says an interface does not exist, inspect the current interfaces:

```bash
sudo ip -all netns exec ip -brief addr
ip -brief addr
```

Make sure the capture command matches the running scenario and namespace.

Stop packet capture with `Ctrl+C` in the capture terminal.

## Cleanup And Reset

Use the launcher stop command:

```bash
python3 launch_sisen.py --stop
```

Then confirm the relevant dashboard/scenario processes have stopped by relaunching cleanly.

If you are unsure whether the lab is in a clean state, run:

```bash
python3 launch_sisen.py --stop
python3 launch_sisen.py
```
