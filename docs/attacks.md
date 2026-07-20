# Attacks

## Purpose

SISEN attacks are controlled lab activities for exploring how security failures can affect safety-relevant telemetry and decisions.

Run attacks only after the relevant SISEN scenario is already running.

## Controlled Lab Warning

SISEN attack activities are intended for the prepared lab environment only. They run against local simulated scenarios, Linux namespaces, MQTT topics, HWSIM wireless paths, and controlled lab infrastructure.

Do not run these commands against live networks, production systems, or devices outside the SISEN lab.

## Listing Available Attacks

List everything:

```bash
python3 attacks/run_attack.py --list
```

Filter by scenario:

```bash
python3 attacks/run_attack.py --list --scenario building
python3 attacks/run_attack.py --list --scenario medical
python3 attacks/run_attack.py --list --scenario 6lowpan
```

Filter by category:

```bash
python3 attacks/run_attack.py --list --category authenticity
python3 attacks/run_attack.py --list --category integrity
python3 attacks/run_attack.py --list --category replay
python3 attacks/run_attack.py --list --category availability
python3 attacks/run_attack.py --list --category protocol
```

## Attack Categories

The command-line category keys are:

| Category key | Meaning |
| --- | --- |
| `authenticity` | Identity, authenticity, and spoofing activities. |
| `integrity` | Correctly formatted but unsafe, implausible, malformed, or manipulated data. |
| `replay` | Stale telemetry replayed as if it were current. |
| `availability` | Missing, noisy, dropped, or disrupted telemetry. |
| `protocol` | Communication-path and protocol-path activity. |
| `confidentiality` | Observation and capture-focused activity. |
| `safety-case` | Scenario-focused safety cases where the safety context is the main teaching point. |

The security focus is not separate from safety. Spoofing, replay, integrity manipulation, and availability disruption can all create safety hazards when systems or operators act on the resulting telemetry.

## Smart Building Attacks

Start Smart Building first, for example:

```bash
python3 launch_sisen.py --scenario smart-building --ap-mode open --nodes 4 --capture-hints
```

Then run attacks from another terminal:

```bash
python3 attacks/run_attack.py --category authenticity --scenario building --attack spoofed
python3 attacks/run_attack.py --category integrity --scenario building --attack extreme
python3 attacks/run_attack.py --category replay --scenario building --attack replay
python3 attacks/run_attack.py --category availability --scenario building --attack noise --count 5
```

Availability attacks that affect interfaces need `sudo`:

```bash
sudo python3 attacks/run_attack.py --category availability --scenario building --attack client-drop --target room-101
sudo python3 attacks/run_attack.py --category availability --scenario building --attack sensor-blackout --duration 10
```

Scenario-focused examples:

```bash
python3 attacks/run_attack.py --category authenticity --scenario building --attack false-occupancy
python3 attacks/run_attack.py --category integrity --scenario building --attack environment-extreme
```

Smart Building also supports the manual MAC filtering activity when launched with `--ap-mode macfilter`.

## Medical IoT Attacks

Start Medical IoT first, for example:

```bash
python3 launch_sisen.py --scenario medical --ap-mode wep --patients 4 --capture-hints
```

Then run attacks from another terminal:

```bash
python3 attacks/run_attack.py --category authenticity --scenario medical --attack spoofed
python3 attacks/run_attack.py --category integrity --scenario medical --attack extreme
python3 attacks/run_attack.py --category integrity --scenario medical --attack malformed
python3 attacks/run_attack.py --category replay --scenario medical --attack replay
```

Scenario-focused examples:

```bash
python3 attacks/run_attack.py --category integrity --scenario medical --attack critical-vitals
python3 attacks/run_attack.py --category replay --scenario medical --attack stale-vitals
```

## 6LoWPAN Attacks

Start 6LoWPAN first, for example:

```bash
python3 launch_sisen.py --scenario 6lowpan --ap-mode open --nodes 4 --capture-hints
```

Then run protocol-path attacks from another terminal:

```bash
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack spoofed
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack extreme
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack missing
python3 attacks/run_attack.py --category protocol --scenario 6lowpan --attack replay
```

Scenario-focused example:

```bash
python3 attacks/run_attack.py --category authenticity --scenario 6lowpan --attack rogue-sensor
```

## Manual Infrastructure Activities

Some activities are listed by the attack runner but are manual rather than helper-based. These should be performed from a separate terminal after the scenario is already running.

Manual activities include:

- open AP traffic observation
- hidden SSID observation
- WEP frame and IV capture
- WPA2 handshake capture
- rogue AP or evil-twin observation
- Smart Building MAC filter bypass
- Medical gateway path capture
- 6LoWPAN path tracing

The runner prints these as manual infrastructure activities and points to:

```text
docs/manual-attacks.md
```

Keep manual activity instructions separate from helper-based attack commands.

## Reading Attack Results

Use the dashboard and MQTT subscription together:

```bash
mosquitto_sub -h localhost -v -t '#'
```

Look for:

- dashboard cards changing state
- implausible but correctly formatted telemetry
- stale values appearing current
- missing or interrupted telemetry
- differences between AP, namespace, and MQTT capture points

## Stop And Cleanup

Stop launcher-managed labs:

```bash
python3 launch_sisen.py --stop
```
