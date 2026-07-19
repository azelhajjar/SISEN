# Client Attacks HW-AP Activity

## Purpose

This activity focuses on attacks that target wireless clients rather than only the access point. Students observe how clients can reveal preferred networks, reconnect after disruption, or connect to a rogue AP.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter supporting monitor mode
- controlled client device
- authorised lab AP or rogue AP setup
- second adapter when simultaneous AP mode and monitor-mode capture are required

## Setup

Confirm the adapter is visible:

```bash
iw dev
```

Use the interface names shown by the tools.

## Start The AP

Use the HW-AP lab scripts or instructor-provided setup for the relevant client-side activity.

## Student Activity

- Observe client probe requests for known SSIDs.
- Observe client association and reassociation behaviour.
- For deauthentication demonstrations, capture the reconnect and handshake only against the lab AP.
- For rogue AP demonstrations, connect only controlled client devices.
- Discuss how client trust decisions can expose users even when the AP infrastructure looks normal.

## What To Observe

- client MAC addresses in monitor-mode tools
- probe requests and preferred-network names
- reconnect behaviour after deauthentication
- handshake capture opportunities
- rogue AP or captive-portal connection flow in controlled demonstrations

## Captures

Useful Wireshark filters include:

```text
wlan.fc.type_subtype == 0x04
wlan.fc.type_subtype == 0x0c
eapol
```

Capture only authorised lab clients.

## Safety And Scope

Do not deauthenticate, lure, or capture traffic from uninvolved users or surrounding networks. Use test clients and lab credentials only.

## Stop And Cleanup

Stop AP, capture, and client-side attack tools. Restore the wireless adapter to managed mode.
