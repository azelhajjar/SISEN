# HW-AP Documentation

The HW-AP activities are separate wireless security exercises used at the University of Westminster. They are not launched through the main SISEN scenario launcher.

Use these materials when the activity needs a real wireless adapter, a hardware or lab access point, monitor mode, or packet injection.

## Lab Environment

Typical setup:

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter attached to the Linux environment, usually `wlan0`
- adapter support for monitor mode and packet injection
- controlled lab access point provided by the instructor
- isolated lab network, not a live production network

Check that Linux can see the wireless adapter:

```bash
iw dev
ip -brief addr
```

For monitor-mode activities, use the interface name shown by the tools. On some systems the monitor interface may remain `wlan0`; on others it may become `wlan0mon` or another name.

## Activities

- [Open AP Traffic](open-ap-traffic.md)
- [WEP](wep.md)
- [WPA2-PSK](wpa2-psk.md)
- [WPA2-Enterprise](wpa2-enterprise.md)
- [Hidden SSID](hidden-ssid.md)
- [MAC Filtering](mac-filtering.md)
- [Rogue AP](rogue-ap.md)
- [Client Attacks](client-attacks.md)
- [Physical Layer](physical-layer.md)

This folder keeps the student-facing notes short and focused on the HW-AP activities that sit outside the main SISEN launcher.

## Main Scripts And Files

Common AP scripts:

```text
open-ap.sh
hidden-ap.sh
wep-ap.sh
wpa2-ap.sh
wpa2e-ap.sh
macfilter-ap.sh
teardown-ap.sh
prepare-hw-interface.sh
```

Client supplicant examples are kept in:

```text
supplicants/
```

The WPA2-Enterprise activity also depends on files in:

```text
files/
```

Important WPA2-Enterprise dependency files:

| File | Purpose |
| --- | --- |
| `setup-radius-server.sh` | Configures the local FreeRADIUS service for the genuine WPA2-Enterprise AP. |
| `radius-users` | Defines the test users accepted by the lab RADIUS server. |
| `radius.secret` | Shared secret used between the AP and the RADIUS server. |
| `hostapd-wpe.conf` | Configuration for the evil-twin WPA2-Enterprise AP activity. |
| `dictionary.txt` | Small lab wordlist used for controlled credential/password testing. |

Do not use real credentials in these files.

## Safety And Scope

Run these activities only in the prepared lab environment and only against authorised lab access points. Do not scan, capture, spoof, deauthenticate, or interfere with surrounding live networks.
