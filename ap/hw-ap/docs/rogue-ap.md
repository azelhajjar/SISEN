# Rogue AP HW-AP Activity

## Purpose

This activity demonstrates how a rogue or evil-twin access point can imitate a legitimate network and attract client connections.

The security point is trust in wireless network identity. Clients may choose a network based on SSID alone, even though the SSID is not a trustworthy identity by itself.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter capable of AP mode
- second adapter for monitor-mode capture when the activity requires simultaneous AP operation and wireless capture
- controlled client device or lab VM
- instructor-provided AP scripts or configuration files

## Setup

Agree the SSID, channel, and AP MAC address for the lab group when instructed. In an evil-twin activity, the rogue AP may intentionally use the same SSID as the genuine AP. In a classroom activity, modified names may be used to avoid confusion between groups.

Check the adapter:

```bash
iw dev
```

## Start The AP

Start the rogue AP from the HW-AP lab materials or instructor-provided script. This is separate from the SISEN launcher.

## Student Activity

- Identify the legitimate AP SSID, BSSID, channel, and security mode.
- Start the rogue or evil-twin AP in the controlled lab environment.
- Compare what the client sees in its Wi-Fi list with what is visible in monitor-mode tools.
- Connect a controlled client and observe association, DHCP, DNS, or captive-portal behaviour where the lab requires it.
- Discuss why SSID matching alone is not enough to trust a wireless network.

## What To Observe

- legitimate AP and rogue AP may share the same SSID
- BSSID, channel, signal strength, security mode, and certificate identity can differ
- clients may probe for known SSIDs
- clients may connect to a rogue AP when the network appears familiar or stronger
- DNS spoofing or captive portal behaviour can redirect client traffic in controlled demonstrations

## Captures

Use monitor mode when observing beacon, probe, authentication, association, or deauthentication frames.

Useful Wireshark filters include:

```text
wlan.fc.type_subtype == 0x04
wlan.fc.type_subtype == 0x05
wlan.ssid
```

Capture only the authorised lab APs and clients.

## Safety And Scope

Run rogue AP activities only in the prepared classroom or lab setup. Do not imitate real networks, collect real credentials, or redirect traffic from uninvolved users.

## Stop And Cleanup

Stop the rogue AP, DNS/captive-portal services, and any monitor-mode capture tools. Restore the wireless adapter to normal managed mode before ordinary Wi-Fi use.
