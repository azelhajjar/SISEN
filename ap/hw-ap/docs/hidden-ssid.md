# Hidden SSID HW-AP Activity

## Purpose

This activity shows that hiding an SSID is not a strong security control. A hidden SSID may disappear from normal Wi-Fi lists, but client association and probe behaviour can reveal it.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter supporting monitor mode
- controlled hidden-SSID lab AP
- authorised client device

## Setup

Confirm the adapter is available:

```bash
iw dev
```

Use monitor mode for over-the-air observation.

## Start The AP

Start the hidden AP using the HW-AP lab script or instructor-provided setup.

## Student Activity

- Observe the AP before any client connects.
- Note that the SSID may appear blank or as a length value in wireless tools.
- Connect a controlled client to the hidden network.
- Observe how association or probe traffic can reveal the SSID.
- Discuss why hidden SSID should not be treated as authentication or encryption.

## What To Observe

- beacon frames without a visible SSID
- probe requests and association frames
- SSID disclosure when a client connects or searches for the network
- how this information can support rogue AP preparation

## Captures

Useful Wireshark filters include:

```text
wlan.ssid
wlan.fc.type_subtype == 0x04
wlan.fc.type_subtype == 0x05
```

Capture only the authorised lab AP and client.

## Safety And Scope

Do not collect probe data from uninvolved devices. Keep capture scoped to the lab activity.

## Stop And Cleanup

Stop captures and return the adapter to managed mode.
