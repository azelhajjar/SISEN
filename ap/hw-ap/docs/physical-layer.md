# Physical Layer HW-AP Activity

## Purpose

This activity introduces lower-layer wireless disruption and observation, including deauthentication, beacon flooding, probe observation, and RF disruption demonstrations.

The point is to show that some wireless attacks affect availability or trust before application-layer security controls are reached.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter supporting monitor mode and packet injection
- controlled lab AP and client
- instructor approval before any disruptive activity

## Setup

Confirm the adapter is visible:

```bash
iw dev
```

Use monitor mode only in the controlled lab setting.

## Start The AP

Use the instructor-provided AP setup for the activity. Students should agree SSID, BSSID, and channel values when working in groups.

## Student Activity

- Observe the AP, channel, and client station MAC addresses.
- Demonstrate targeted deauthentication only against the lab client.
- Observe probe requests and beacon frames.
- Where authorised, observe beacon flooding or RF disruption effects in the lab.
- Discuss why availability and management-frame behaviour matter for safety-relevant wireless systems.

## What To Observe

- unencrypted management frames
- BSSID and station MAC addresses
- client disconnection and reconnection
- possible handshake capture after reconnect
- channel disruption or noisy scan results during beacon/RF demonstrations

## Captures

Useful Wireshark filters include:

```text
wlan.fc.type_subtype == 0x0c
wlan.fc.type_subtype == 0x08
wlan.fc.type_subtype == 0x04
```

Capture only the authorised lab AP and client.

## Safety And Scope

These activities can disrupt wireless communication. Run them only in the prepared lab environment and only when instructed.

## Stop And Cleanup

Stop disruptive tools immediately after the observation is complete. Restore the adapter to managed mode and confirm the lab AP/client reconnect normally.
