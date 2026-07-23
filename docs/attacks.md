# Attacks

## Purpose

SISEN attacks are controlled lab activities for exploring how security failures can affect safety-relevant telemetry and decisions.

Run attacks only after the relevant SISEN scenario is already running.

Helper-based telemetry attacks are bounded demonstrations. Where an attack
needs to remain visible, the helper refreshes the injected value for about 10
seconds at a short interval, then exits. Normal scenario telemetry continues
while the attack is running and should restore the dashboard after the helper
finishes.

Attack commands can be run from a fresh terminal in the repository root. The
runner selects the repository virtual-environment Python interpreter when it is
available, so students do not need to activate `.venv` separately for each
attack terminal.

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

Scenario-focused safety cases:

```bash
python3 attacks/run_attack.py --category safety-case --scenario building --attack gas-leak-hidden
python3 attacks/run_attack.py --category safety-case --scenario building --attack fire-alarm-suppressed
python3 attacks/run_attack.py --category safety-case --scenario building --attack blocked-exit-hidden
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

Medical MQTT attacks use the live `patient-N` identifier format, such as
`patient-1`, `patient-2`, `patient-3`, and `patient-4` when the scenario is
started with `--patients 4`. Some attacks target one patient; broader attacks
target several active patients.

Scenario-focused safety cases:

```bash
python3 attacks/run_attack.py --category safety-case --scenario medical --attack critical-vitals
python3 attacks/run_attack.py --category safety-case --scenario medical --attack fall-alert-suppressed
python3 attacks/run_attack.py --category safety-case --scenario medical --attack panic-button-suppressed
python3 attacks/run_attack.py --category safety-case --scenario medical --attack battery-falsely-normal
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

When the 6LoWPAN scenario is already running, these helpers inject through the
active lab namespace path instead of rebuilding the topology. General attacks
select one eligible industrial asset at the start of the run and keep that
target fixed for the full refresh or replay window.

With four active nodes, the general 6LoWPAN attacks can target:

| Node | Asset |
| --- | --- |
| `node-01` | Boiler Room |
| `node-02` | Process Line |
| `node-03` | Cold Storage |
| `node-04` | Loading Bay |

Target selection uses a shuffled per-attack rotation so repeated runs use all
eligible nodes before reshuffling and avoid immediate repeats when alternatives
exist. The payload remains node-specific; fields are not forced onto assets
that do not support them.

Scenario-focused safety cases:

```bash
python3 attacks/run_attack.py --category safety-case --scenario 6lowpan --attack boiler-pressure-masked
python3 attacks/run_attack.py --category safety-case --scenario 6lowpan --attack emergency-stop-hidden
python3 attacks/run_attack.py --category safety-case --scenario 6lowpan --attack machine-overheat-hidden
```

The specialised 6LoWPAN safety cases remain asset-specific:

| Attack | Eligible target |
| --- | --- |
| `boiler-pressure-masked` | Boiler Room (`node-01`) |
| `emergency-stop-hidden` | Boiler Room (`node-01`) or Process Line (`node-02`) |
| `machine-overheat-hidden` | Process Line (`node-02`) |

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

For 6LoWPAN-specific observation, use:

```bash
mosquitto_sub -h localhost -p 1883 -t 'industrial/6lowpan/#' -v
mosquitto_sub -h fd00:6:2::1 -p 1884 -t '#' -v
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
