# WPA2-PSK HW-AP Activity

## Purpose

This activity introduces WPA2-PSK handshake capture and offline password testing. Students learn that WPA2-PSK does not reveal the passphrase directly, but a captured handshake can be tested against candidate passwords offline.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter supporting monitor mode
- controlled WPA2-PSK lab AP
- authorised client device
- lab wordlist where provided

## Setup

Confirm the adapter is available:

```bash
iw dev
```

Enable monitor mode when capturing handshakes.

## Start The AP

Start the WPA2-PSK AP using the HW-AP lab script or instructor-provided setup.

## Student Activity

- Identify the AP SSID, BSSID, channel, and security mode.
- Capture the WPA2 four-way handshake.
- If instructed, use a controlled deauthentication event to force a reconnect.
- Test the captured handshake against the lab wordlist.
- Open the capture in Wireshark and inspect EAPOL frames.

## What To Observe

- EAPOL four-way handshake frames
- the difference between capturing a handshake and knowing the passphrase
- why weak PSK choices are vulnerable to dictionary testing
- why client reconnection can create a new handshake capture opportunity

## Captures

Useful Wireshark filter:

```text
eapol
```

Capture only the authorised AP and client.

## Safety And Scope

Use only the supplied lab AP, test client, and lab password material. Do not run deauthentication or password testing against live networks.

## Stop And Cleanup

Stop capture tools and restore the wireless adapter to normal managed mode.
