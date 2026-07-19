# WPA2-Enterprise HW-AP Activity

## Purpose

This activity introduces WPA2-Enterprise security, where clients authenticate through 802.1X/EAP and a RADIUS server rather than a shared WPA2-PSK passphrase.

The security point is certificate and identity validation. A client that does not validate the server certificate can be tricked into connecting to an evil-twin access point and disclosing credentials.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- one or two USB Wi-Fi adapters, depending on whether the same machine is running the AP and capturing traffic
- controlled WPA2-Enterprise lab AP or instructor-provided AP setup
- instructor-provided SSID, test credentials, certificates, and configuration files where required

## Setup

Confirm the wireless adapter is visible:

```bash
iw dev
```

If the activity requires packet capture, put the capture adapter into monitor mode using the method specified by the instructor, then use the resulting interface name in capture commands.

## Start The AP

The genuine WPA2-Enterprise AP and any evil-twin AP are started from the HW-AP lab materials, not from `launch_sisen.py`.

Use the SSID, channel, RADIUS settings, certificate settings, and test accounts provided for the class. In paired activities, agree unique names or channels when instructed so groups do not interfere with each other.

## Student Activity

- Connect a client to the genuine WPA2-Enterprise AP using the supplied test account.
- Observe that WPA2-Enterprise uses EAP authentication and a RADIUS-backed identity check.
- Compare secure and insecure client behaviour when server certificate validation is enabled or disabled.
- For the evil-twin activity, compare the legitimate AP and the rogue AP configuration, certificate identity, SSID, BSSID, and channel.
- Discuss why accepting an untrusted certificate can expose credentials.

## What To Observe

- EAP identity exchange
- server certificate presented during authentication
- whether the client validates or ignores the server certificate
- client association to the legitimate or evil-twin AP
- credential exposure risk when certificate validation is disabled

## Captures

Capture only the authorised lab AP and channel. Typical analysis uses Wireshark filters such as:

```text
eap
eapol
```

Use the capture filename and interface name provided in the lab session. Do not capture surrounding networks.

## Safety And Scope

Use test accounts only. Do not use real university, personal, or production credentials.

This activity is for controlled WPA2-Enterprise lab networks only.

## Stop And Cleanup

Stop the AP, capture, and monitor-mode tools as instructed by the lab sheet or instructor. Restore the wireless adapter to normal managed mode before using it for ordinary Wi-Fi connections.
