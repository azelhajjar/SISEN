# WEP HW-AP Activity

## Purpose

This activity demonstrates why WEP is no longer secure. Students observe WEP traffic, collect IVs, and discuss how weaknesses in the protocol allow key recovery or packet manipulation in controlled conditions.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter supporting monitor mode and packet injection
- controlled WEP lab AP
- authorised test client

## Setup

Confirm the adapter is visible:

```bash
iw dev
```

Use monitor mode when capturing WEP frames.

## Start The AP

Start the WEP AP using the HW-AP lab script or instructor-provided setup. WEP is used only for demonstration in the isolated lab.

## Student Activity

- Identify the WEP AP SSID, BSSID, and channel.
- Capture WEP frames from the lab AP.
- Observe IV collection and client association.
- Where instructed, use controlled replay or injection to increase traffic.
- Discuss why WEP fails even when the password is not directly disclosed.

## What To Observe

- WEP encryption type in scan results
- IVs in captured frames
- relationship between traffic volume and WEP analysis
- how packet replay can generate more encrypted traffic
- why WEP should not be used in real deployments

## Captures

Capture only the lab AP and channel. Typical WEP analysis uses monitor-mode captures opened in Wireshark or aircrack-ng tools.

## Safety And Scope

Do not target any non-lab WEP or Wi-Fi network. Packet injection is authorised only inside the controlled lab.

## Stop And Cleanup

Stop capture and replay tools, then restore the adapter to normal managed mode.
