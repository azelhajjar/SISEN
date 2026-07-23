# SISEN Demonstration Video 7: WPA2 Handshake Capture

## Video Purpose

This video demonstrates how to capture a WPA2 four-way handshake from the normal SISEN Smart Building scenario by creating a temporary monitor-mode interface and forcing one simulated node to reconnect.

---

## 1. Start the Smart Building Scenario

### Terminal Command

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode wpa2 --nodes 4 --capture-hints
```

### Recording Cue

Confirm that the scenario and dashboard are running.

---

## 2. Create the Monitor-Mode Interface

### Terminal Commands

```bash
sudo iw dev wlan0 interface add mon-sisen type monitor
sudo ip link set mon-sisen up
iw dev
```

### Recording Cue

Confirm that `mon-sisen` exists and its type is `monitor`.

---

## 3. Set the Monitor Interface to the SISEN AP Channel

### Terminal Command

```bash
sudo iw dev mon-sisen set channel 6
```

### Recording Cue

Use the channel shown for the running SISEN access point.

---

## 4. Start the Wireless Capture

### Terminal Command

```bash
sudo tcpdump -i mon-sisen -n -vv -s 0 -w captures/wpa2-handshake.pcap
```

### Recording Cue

Leave the capture running in a separate terminal.

---

## 5. Identify a Simulated Node Interface

### Terminal Commands

```bash
sudo ip netns list
sudo ip netns exec room-101 ip -brief link
```

### Recording Cue

Identify the wireless interface inside the selected namespace.

---

## 6. Force the Node to Reconnect

### Terminal Commands

```bash
sudo ip netns exec room-101 ip link set <wireless-interface> down
sudo ip netns exec room-101 ip link set <wireless-interface> up
```

### Recording Cue

Wait for the node to reconnect to the WPA2 access point.

---

## 7. Stop the Capture

Press:

```text
Ctrl+C
```

Open:

```text
captures/wpa2-handshake.pcap
```

---

## 8. Inspect the Handshake in Wireshark

### Display Filter

```text
eapol
```

### Recording Cue

Show the EAPOL packets generated when the node reconnects.

---

## 9. Cleanup

### Terminal Commands

```bash
sudo iw dev mon-sisen del
python3 launch_sisen.py --stop
```
