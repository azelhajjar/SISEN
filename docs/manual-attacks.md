# Manual Attacks

## Purpose

Manual attacks are wireless or infrastructure activities that students perform from a separate terminal. They are not executed automatically by `attacks/run_attack.py`.

Use this page with the dashboard, capture guidance, and the relevant scenario or HW-AP documentation.

## When To Use Manual Attacks

Manual activities include:

- open AP traffic observation
- hidden SSID observation
- WEP frame and IV capture
- WPA2 handshake capture
- rogue AP or evil-twin observation
- MAC filtering observation and bypass
- BLE, IoT infrastructure, and additional wireless attacks in future development

## Monitor Mode

Monitor mode is manual. Do not wire it into the SISEN launcher.

Create or enable a monitor-mode interface only when the activity requires over-the-air wireless frames. Use the interface name shown by your tools.

Example:

```bash
sudo iw dev wlan0 interface add mon-sisen type monitor
sudo ip link set mon-sisen up
```

Do not use `-I` with tcpdump once the interface is already in monitor mode.

## Capturing

Write capture files under `captures/`.

Example:

```bash
sudo tcpdump -i mon-sisen -n -vv -s 0 -w captures/manual-wireless.pcap
```

For manual commands, explain only the values students must choose or replace, such as interface name, AP BSSID, channel, client MAC address, and capture filename. Do not describe launcher or orchestration internals unless the activity directly depends on them.

For namespace and host interface checks, use:

```bash
sudo ip -all netns exec ip -brief addr
ip -brief addr
```

## Running Manual Activities

Use a separate terminal from the launcher. Keep the scenario, dashboard, monitor interface, and capture command visible where possible.

Record:

- scenario or HW-AP mode
- AP SSID, BSSID, and channel
- interface used for capture
- capture filename
- attack or observation performed
- visible dashboard or client impact

## Safety And Scope

Run manual attacks only in the controlled lab environment. Do not capture, spoof, deauthenticate, or interfere with surrounding live networks or uninvolved devices.

## Cleanup

Stop capture tools with `Ctrl+C`.

Remove a temporary monitor interface when finished:

```bash
sudo iw dev mon-sisen del
```

Stop SISEN scenarios with:

```bash
python3 launch_sisen.py --stop
```
