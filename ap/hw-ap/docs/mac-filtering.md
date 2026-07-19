# MAC Filtering HW-AP Activity

## Purpose

This activity shows why MAC filtering is a weak access-control mechanism. The AP only allows clients whose MAC addresses appear in an allowed list, but an attacker who observes an allowed client MAC address can spoof it.

The security point is that MAC addresses identify interfaces, not users. The safety and operational point is that an infrastructure control can look effective while still being bypassable.

## Hardware Requirements

- Debian-based Linux machine or VM with the required wireless tools installed
- USB Wi-Fi adapter visible as `wlan0` or equivalent
- controlled lab AP with MAC filtering enabled
- at least one authorised client MAC address in the allowed list

## Allowed MAC Addresses

The allowed list should contain the MAC addresses of the clients that are expected to connect during the lab.

For paired work, agree the AP SSID, AP MAC address, channel, and allowed client MACs before starting. This avoids clashes between groups.

## Start The AP

Start the MAC-filtering AP from the HW-AP lab materials or the instructor-provided setup. This is not a SISEN scenario launcher mode for the HW-AP activity.

## Student Activity

- Observe the AP and identify its SSID, BSSID, and channel.
- Observe an authorised client association.
- Record the authorised client MAC address from the controlled lab activity.
- Change the attacker interface MAC address to match the authorised client when instructed.
- Attempt to connect again and compare the result.

Typical inspection commands:

```bash
iw dev
ip -brief addr
```

Typical MAC spoofing sequence, using the MAC address authorised for the lab:

```bash
sudo ip link set wlan0 down
sudo ip link set wlan0 address <allowed-client-mac>
sudo ip link set wlan0 up
```

## What To Observe

- the AP accepts clients based on MAC address
- the allowed MAC can be observed from wireless activity or lab records
- spoofing an allowed MAC can bypass the filter
- duplicate MACs can cause unstable behaviour if the genuine client remains connected

## Captures

Use monitor mode only when the activity requires over-the-air observation of clients and AP association. Capture only the lab AP and channel.

Useful Wireshark fields include:

```text
wlan.sa
wlan.da
wlan.bssid
```

## Safety And Scope

Use only the MAC addresses assigned for the lab. Do not spoof addresses from surrounding live networks or devices.

## Stop And Cleanup

Disconnect from the AP and restore the adapter MAC address before returning to normal use. If a temporary spoofed MAC was configured, reset the interface or reboot the VM if needed.
