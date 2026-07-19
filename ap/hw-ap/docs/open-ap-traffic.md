# Open AP Traffic HW-AP Activity

## Purpose

This activity introduces wireless observation on an open access point. Students compare normal managed-mode connectivity with monitor-mode capture and learn which parts of open Wi-Fi traffic are visible.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter visible as `wlan0` or equivalent
- controlled open lab AP
- Wireshark or tcpdump/tshark for capture review

## Setup

Confirm the adapter is available:

```bash
iw dev
ip -brief addr
```

## Start The AP

Start the open AP using the HW-AP lab script or the instructor-provided setup. This activity is separate from `launch_sisen.py`.

## Student Activity

- Scan for the lab AP and confirm its SSID, BSSID, and channel.
- Connect a controlled client to the open AP.
- Generate simple traffic such as ping or HTTP requests to the lab AP.
- Capture traffic in managed mode and, where instructed, in monitor mode.
- Compare what is visible in each capture.

## What To Observe

- open AP beacons and association frames
- client DHCP and IP traffic
- differences between managed-interface and monitor-mode captures
- why open Wi-Fi does not protect traffic confidentiality

## Captures

Use filenames and interfaces agreed for the lab. Capture only the authorised AP.

Useful Wireshark filters include:

```text
wlan
dns
dhcp
icmp
```

## Safety And Scope

Use only the controlled lab AP. Do not capture traffic from surrounding networks.

## Stop And Cleanup

Stop captures and disconnect from the AP. Restore the wireless adapter to managed mode if monitor mode was used.
