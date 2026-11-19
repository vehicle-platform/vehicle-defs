# Vehicle data catalog — every signal we read, can read, or can derive

Working list (2026-10-15), **not a decision**. It collects what the platform reads today, what it could read, and what can be derived, so the anomaly and context models can pick features (D-068). The sources of truth stay where they are: `uds/vehicle_cl250.yaml` (ECU DIDs), `ble/ble_schema.json` (conn BLE), `dbc/platform.dbc`, `uds/dids.yaml`. Nothing here is polled, sent or computed because it is listed; each new item goes through `/signal-change` or a D-xxx.

Status legend:

| Tag | Meaning |
|---|---|
| **LIVE** | Read and recorded today (conn Phase 0 build, verified DID or sensor) |
| **POLLED?** | Polled since D-068, `verified: false`: flows only if the CL250 ECU serves it |
| **DEF** | Standard, but needs a decode definition before it can be polled |
| **DISC** | Exists only if discovery finds it (proprietary DID, passive CAN broadcast, Q-001) |
| **HW** | Needs a sensor or a wiring tap (hardware decision) |
| **PLAN** | Planned on a node that does not run yet (rt-core board, Q-019) |
| **DERIV** | Computed from the above (offline, server or rt-core) |

## 1. Vehicle bus load today

The vehicle bus (the CL250 DLC: classic CAN 500 kbps; rt-core's FDCAN1 once the board exists, conn's TWAI today) carries only our tester's requests and the ECU's answers. Per DID read: a request on the 29-bit and on the 11-bit ID, one 29-bit answer (8-byte frames, ~131/111 bits, ~155/134 with worst-case stuffing); tester present every 1000 ms.

| Table | Reads/s | Data bytes/s | Bus load (nominal / worst stuffing) | ECU slot budget (D-029, ≤ 0.8) |
|---|---|---|---|---|
| Before D-068 (5 DIDs) | 25.7 | 36 | 9.8 kbit/s = 2.0 % / 2.3 % | 0.514 |
| D-068, all 40 served | 36.8 | 51 | 14.0 kbit/s = 2.8 % / 3.3 % | 0.736 |

The limit is not the bus but the ECU: one request in flight and an assumed 20 ms round trip (provisional, D-029; measured by D-058's round-trip records). Unserved D-068 DIDs stop after their first reads (D-068 item 2), so the real load is lower. The bitrate stays at 500 kbps; the paths to more data are listen-only capture, multi-DID reads and tier tuning, in that order (D-074).

Sampling rates of the verified DIDs: engine speed and vehicle speed 9.1 Hz (110 ms), throttle 5 Hz, coolant and battery 1.25 Hz.

## 2. ECU data over UDS (`uds/vehicle_cl250.yaml`)

Engine column: **run** = meaningful only with the engine running (key-on engine-off reads 0 or a fixed value, or the ECU may refuse it); **key** = meaningful at key-on too. These are expectations from J1979 practice, not CL250 facts; V0 (key on) and V1 (idle) in `hardware-integration.md` will show it. Caveat: under D-068 item 2 a DID refused or ignored at key-on stays stopped until the next session confirmation; D-069 item 3 re-asks the stopped ones once at engine start, so every DID is tried in both states (conn branch `claude/d068-engine-rearm`, rt-core with E-19).

| Signal | DID | Unit | Period | Status | Engine |
|---|---|---|---|---|---|
| Engine speed | F40C | rpm | 110 ms | LIVE | run |
| Vehicle speed | F40D | km/h | 110 ms | LIVE | key |
| Throttle position | F411 | % | 200 ms | LIVE | key |
| Coolant temperature | F405 | °C | 800 ms | LIVE | key |
| Control module voltage | F442 | V | 800 ms | LIVE | key |
| Calculated load | F404 | % | 2 s | POLLED? | run |
| Ignition timing advance | F40E | deg | 2 s | POLLED? | run |
| Absolute load | F443 | % | 2 s | POLLED? | run |
| Relative throttle | F445 | % | 2 s | POLLED? | key |
| Throttle B | F447 | % | 2 s | POLLED? | key |
| Grip position D | F449 | % | 2 s | POLLED? | key |
| Commanded throttle | F44C | % | 2 s | POLLED? | key |
| Relative grip | F45A | % | 2 s | POLLED? | key |
| Intake MAP | F40B | kPa | 2 s | POLLED? | key (≈ baro engine off) |
| Mass air flow | F410 | g/s | 2 s | POLLED? | run |
| Commanded lambda | F444 | ratio | 2 s | POLLED? | run |
| Short-term fuel trim | F406 | % | 2 s | POLLED? | run (closed loop only) |
| Injection timing | F45D | deg | 2 s | POLLED? | run |
| Engine fuel rate | F45E | L/h | 2 s | POLLED? | run |
| Demanded torque | F461 | % | 2 s | POLLED? | run |
| Actual torque | F462 | % | 2 s | POLLED? | run |
| Barometric pressure | F433 | kPa | 5 s | POLLED? | key |
| Long-term fuel trim | F407 | % | 5 s | POLLED? | run (learnt value) |
| Fuel pressure | F40A | kPa | 5 s | POLLED? | run |
| Rail pressure (relative) | F422 | kPa | 5 s | POLLED? | run |
| Rail pressure (gauge) | F423 | kPa | 5 s | POLLED? | run |
| EVAP purge | F42E | % | 5 s | POLLED? | run |
| Fuel level | F42F | % | 5 s | POLLED? | key |
| Ethanol | F452 | % | 5 s | POLLED? | key |
| Intake air temperature | F40F | °C | 5 s | POLLED? | key |
| Catalyst temperature | F43C | °C | 5 s | POLLED? | run |
| Ambient air temperature | F446 | °C | 5 s | POLLED? | key |
| Engine oil temperature | F45C | °C | 5 s | POLLED? | key |
| Run time since start | F41F | s | 10 s | POLLED? | run |
| Distance with MIL | F421 | km | 10 s | POLLED? | key |
| Warm-ups since clear | F430 | count | 10 s | POLLED? | key |
| Distance since clear | F431 | km | 10 s | POLLED? | key |
| Time with MIL | F44D | min | 10 s | POLLED? | key |
| Time since clear | F44E | min | 10 s | POLLED? | key |
| Reference torque | F463 | Nm | 10 s | POLLED? | key |

Standard but not yet defined (**DEF**, multi-value or enum, D-068 "Still open"): 0x01 monitor status (MIL, DTC count, readiness), 0x03 fuel system status (open/closed loop: tells when trims are valid), 0x12 secondary air, 0x13/0x1D O2 sensor location, 0x14–0x1B O2 voltage + trim, 0x24–0x2B / 0x34–0x3B wide-band O2 (lambda + voltage/current), 0x1C OBD standard, 0x1E auxiliary input (PTO), 0x51 fuel type. The CL250 has one cylinder and likely one O2 sensor, so 0x01, 0x03 and one O2 PID matter most.

One-shot data (D-059 probe scan, not a time series): supported-PID bitmaps, VIN (masked to the WMI, never published), CalID, CVN, ECU name, DTC count and list.

### 2.1 Standard data outside the polled table (added 2026-10-15)

Answer to "do we read everything we can?": **we read every scalar J1979 PID that D-066 judged plausible for a one-cylinder gasoline bike, but not everything that is standard and readable inside `tester_policy`.** What exists on the CL250 is unknown until the D-059 probe has run on the bike: its 0x22 0xF4xx bitmap chain covers every PID 0x01–0xFF, so the bitmap, not this list, decides. Everything below is a 0x22, 0x19 or OBD 0x01/0x09 read, so none of it widens `tester_policy` (D-020); each item still needs `/signal-change` (or a D-xxx where noted). Formulas are SAE J1979-DA / ISO 14229-1 values to be checked in that change, not CL250 facts.

**(a) Scalar PIDs left out of the D-066 list.** Add one only if the bitmap marks it supported.

| PID / DID | Signal | Why it was left out | Worth it if served |
|---|---|---|---|
| 0x08, 0x09 / F408, F409 | Short/long fuel trim bank 2 | One cylinder, no bank 2 | No |
| 0x2C, 0x2D / F42C, F42D | Commanded EGR, EGR error | No EGR expected | No |
| 0x32, 0x53, 0x54 / F432, F453, F454 | EVAP vapour pressure (3 forms) | EVAP leak monitoring is not expected on an L-category bike | Low |
| 0x3D, 0x3E, 0x3F / F43D–F43F | Catalyst temperature B2S1, B1S2, B2S2 | Only B1S1 (F43C) plausible | B1S2 only |
| 0x48, 0x4A, 0x4B / F448, F44A, F44B | Throttle C, grip E, grip F | Redundant channels | Low (plausibility residuals, §5) |
| 0x59 / F459 | Fuel rail absolute pressure | Port injection, F40A/F422/F423 cover it | Low |
| 0x5B / F45B | Hybrid battery life | Not a hybrid | No |
| 0x8E / F48E | Engine friction, % torque (A − 125) | Beyond 0x63, not reviewed by D-066 | Yes: torque model, warm-up friction |
| 0xA2 / F4A2 | Cylinder fuel rate, mg/stroke ((256A+B)/32) | Beyond 0x63 | Yes: fuelling per stroke, consumption |
| 0xA6 / F4A6 | Odometer, km (4 bytes / 10) | Beyond 0x63 | **Yes**: ECU odometer, distance cross-check (§5) |

**(b) Multi-value PIDs that need a decode definition** (D-068 "Still open"; the existing **DEF** paragraph above). Added here: **0x65** auxiliary I/O status (one bit is "manual transmission neutral/gear", a free neutral signal if the ECU reports it), **0xA4** transmission actual gear (gear number + ratio; unlikely on a bike without a gear sensor, but the bitmap tells), **0x7F** engine run time (total / idle / PTO, a real engine-hours counter), 0x5F emission requirement (enum, one-shot), 0x64 torque data points, 0x66–0x68 multi-sensor MAF/coolant/IAT. Priority for one cylinder: 0x01, 0x03, the O2 PID the bitmap reports, then 0x65, 0xA4, 0x7F.

**(c) OBD-on-UDS ranges beyond 0xF4xx** (SAE J1979-2 maps the OBD services onto 0x22). The CL250 answering 0x22 0xF4xx suggests these may exist too. Neither is in `discovery_scan` today.

| DID range | Content | Note |
|---|---|---|
| 0xF600–0xF6FF (support DIDs 0xF600, 0xF620 …) | Monitor test results (old mode 0x06): O2 sensor, catalyst, O2 heater and the **misfire monitors (cylinder 1)** with test values and limits | Misfire counts are a direct anomaly label. Answers are multi-frame (one 9-byte record per test), so only the probe env can receive them (D-059 item 3) |
| 0xF800–0xF8FF | Vehicle information (old mode 0x09): VIN, CalID, CVN, ECU name, in-use performance ratios | Same data as the mode 0x09 probe; a cross-check of the 0x22 path |

**(d) ISO 14229-1 identification DIDs 0xF180–0xF19F** (one-shot, key-on; multi-frame for the long strings): boot/application software IDs and fingerprints (F180–F185), active session (F186, a cheap check that the 0x10 0x03 session holds), spare part number (F187), ECU software number and version (F188, F189), supplier (F18A), manufacturing date (F18B), ECU serial (F18C, **personal-adjacent, never committed**), hardware/software numbers (F191–F195), type-approval number (F196), system name / engine type (F197), programming and calibration dates (F199, F19B), ODX file (F19E). Use: identify the ECU variant and software level once per ignition so a model can tell data from two calibrations apart. Same privacy rule as the VIN (D-033, D-059 item 3).

**(e) More of 0x19 (allowed, `tester_policy` does not restrict its sub-functions).** The probe reads only 0x01 (count) and 0x02 (list). Also readable: 0x03 snapshot identification, **0x04 DTC snapshot record = freeze frame** (the ECU's own sample of RPM, load, temperatures … at the moment the DTC was set), 0x06 extended data (occurrence and ageing counters), 0x0A supported DTCs. Freeze frames are the best labelled anomaly samples we can get, but they are event data: read them once per ignition when the DTC count is non-zero, as the strategy note's tier 3 says, not periodically. Decided by D-080: only when 0x19 0x01 reports a pending or confirmed DTC, at key-on and at warm idle, at most 8 DTCs per run, multi-frame through the D-059 FC.CTS.

**(f) Not readable without widening `tester_policy` (listed so nobody tries):** 0x2A ReadDataByPeriodicIdentifier (would save request overhead), 0x2C DynamicallyDefineDataIdentifier (bundles DIDs into one read, but writes a definition into the ECU), 0x23 ReadMemoryByAddress (raw RAM, needs addresses we do not have), OBD modes 0x02 (freeze frame), 0x03/0x07 (stored/pending DTCs; 0x19 covers them), 0x06 (covered by 0xF6xx). Each would need the user's approval, a versioned defs change and `safety-reviewer` (invariant 1); none is proposed.

## 3. Switches and chassis data the ECU may or may not have

None of these is defined anywhere yet. J1979 has no PID for them.

| Signal | Likely source on the CL250 | Paths to get it | Status |
|---|---|---|---|
| Clutch lever switch | Start/ignition interlock circuit; on Honda PGM-FI the ECU usually reads it (to verify) | (a) proprietary Honda DID found by strategy stage 2: read candidate DIDs while pulling the lever; (b) passive broadcast if any (Q-001); (c) wiring tap, optocoupler, high-impedance, parallel to the switch | DISC / HW |
| Neutral switch | Same interlock; dash neutral lamp | (a), (b), (c) as above | DISC / HW |
| Side stand switch | Same interlock (ignition cut in gear) | (a), (b), (c) | DISC / HW |
| Gear position | A gear position sensor only if the bike has one (to verify) | (a) proprietary DID; else **DERIV** from RPM/speed ratio (§5) | DISC / DERIV |
| Front/rear brake switch | Brake-light circuit (12 V when braking); ABS unit | (b) ABS broadcast if any; (c) tap the brake-light feed (easiest, 12 V, opto-isolated input); **DERIV** braking from IMU deceleration (§5) | DISC / HW / DERIV |
| Wheel speeds (front/rear) | ABS modulator wheel sensors | (b) only if the ABS unit broadcasts on the DLC bus (Q-001); its own diagnostics are a second ECU, not in our tester policy | DISC |
| ABS active / intervention | ABS unit | (b) | DISC |
| Kill switch, engine stop | Interlock / ECU | (a), (c) | DISC / HW |
| Turn signals, lights | Lighting circuit | (c); planned safety-MCU (G474) input for blind spot (hardware-architecture §5b.1, D-072, D-118) | HW / PLAN |
| Horn, high beam | Lighting circuit | (c) | HW |

Notes:
- (a) means new read-only discovery of non-standard DIDs (0x22 only, so inside `tester_policy`), but a range scan is a new probe mode: it needs a D-xxx (budget, which ranges, stop rules) before it is coded. The strategy note's 0x1000–0x2FFF range is an example, not a known range.
- (b) is the Q-001 listen-only capture (`esp32-s3-devkitc-1-listen-only`, `hardware-integration.md` §7.1). It costs nothing on the bus; do it first.
- (c) never cuts the OEM harness (vehicle-work-plan: parallel or via connectors). A tap is a hardware decision (which node reads it: the safety MCU (G474) per §5b.1, D-072 and D-118, or conn in Phase 0) and must not load the switch circuit.

### 3.1 Interactive discovery on the bike (proposal for Q-031 (b), added 2026-10-15)

No public source lists Honda's proprietary DIDs for its CAN-diagnosed motorcycles; Honda keeps them in its service tool (HDS). So proprietary data can only be found on the bike. The direction is decided (D-069 item 5); the procedure below is still a **proposal**: the range-scan probe mode needs its own decision (ranges, time budget, stop rules, power supply) and `safety-reviewer` before it is coded, after the Q-001 capture. It sends only 0x22 Single Frames and the D-059 FC.CTS, so `tester_policy` and the frame gate stay as they are.

**What a Honda PGM-FI ECU is likely to know** (hypotheses to look for, not signals). The HDS data list in the Honda service manual's PGM-FI chapter names what the ECU exposes; the CL250 manual is the best non-invented reference and should be read before the scan. Typical content of such lists:

| Group | Likely items | Stimulus that makes it change |
|---|---|---|
| Interlock switches | Neutral switch, clutch switch, side stand switch, engine stop (kill) switch, starter switch | Toggle each by hand, key on, engine off |
| Tip-over | Bank angle sensor state (on/off, sometimes its voltage) | Not stimulated (the bike stays upright); identify it only by the manual's description, never by tipping the bike or unplugging the sensor |
| Raw sensor voltages | TP sensor, ECT sensor, IAT sensor, MAP sensor, O2 sensor (and O2 heater state) | Throttle sweep (TP), warm-up (ECT, IAT), engine start (MAP), closed loop (O2) |
| Actuator states | Fuel pump relay, cooling fan relay, injector pulse width, idle air control / ISC position, EVAP purge, PAIR solenoid | Key on (pump primes ~2 s), warm idle until the fan starts, idle vs blip |
| Engine state | Ignition timing, fuel cut flag, O2 feedback (closed loop) flag, gear position if a sensor exists | Idle, throttle blips, engine braking (fuel cut) |
| Chassis | Vehicle speed source, ABS warning state | Rear wheel turned by hand on a rear paddock stand, engine off; in gear at idle only on a proper stand, nobody near the chain or wheel |

**Procedure** (stationary, side stand down, never while riding):

0. **Power.** Key on with the engine off draws the battery (the headlight is always on). Connect a battery maintainer for any scan longer than ~15 minutes, or run it with the engine idling in open air, and log the battery voltage (F442) throughout.
1. **Silence test.** Read ~20 IDs in an unused range and see how the ECU refuses an unsupported DID: NRC 0x31 within the round trip (fast scan, ~20 ms per ID) or no answer (each ID costs `response_timeout_base_ms` + `client_step_max_ms` = 110 ms). This sets the time budget of step 2.
2. **Coarse sweep.** ISO 14229-1 reserves 0x0100–0xEFFF (and 0xF010–0xF0FF, 0xF100–0xF17F, 0xF1A0–0xF1EF, 0xFD00–0xFEFF) for vehicle-manufacturer and supplier data. A full sweep of 0x0100–0xEFFF is ~61,000 reads: ~20 min with fast NRCs, ~1.9 h with silence. Start with the first 16 IDs of every 0xXX00 block (~3,800 reads: 1.3–7 min), since manufacturers cluster their DIDs, then sweep every block with a hit in full. Record per ID: NRC code (0x31 = absent; 0x22/0x33 = present but locked, never pursued with 0x27), or the positive answer bytes and length.
3. **Stop rules** (for the D-xxx): one request in flight; never more than one retry per ID; abort the scan if the ECU is absent for `ecu_absent_timeout_ms`, if the session falls back (NRC 0x7E/0x7F, re-request it once), or on a bus-off; answers longer than `max_ff_dl` are not received. The five verified DIDs keep being polled between scan blocks so the log shows the bike's state.
4. **Stimulus run.** Poll only the DIDs found in step 2, in rotation (~N × 20 ms per round), while the operator performs a scripted sequence, each action held ≥ 3 s and repeated 3 times, with a time marker per action (a button on the ESP32 or a marker in the phone app): clutch pull, neutral ↔ first (clutch in), side stand up/down, front brake lever, rear brake pedal, kill switch, starter button with the kill switch at stop (no crank), indicators left/right, high beam, horn, throttle sweep engine off, key-on fuel pump prime, engine start, idle until the fan runs, throttle blips, rear wheel turned on a paddock stand (see the table).
5. **Correlation (offline, vehicle-ml).** For every byte and bit of every found DID: does it flip in step with a marker? Bits that follow exactly one action name the switch; bytes that track a known DID (e.g. F411 throttle) with an offset/scale are the raw voltage or a twin channel; bytes that only move with the engine running are engine-state candidates. Output: a table *DID, byte, bit/scale, meaning, confidence, evidence (log file + time)*. A row enters `uds/vehicle_cl250.yaml` only through `/signal-change` with `verified: false`, like the D-068 DIDs (invariant 2).
6. **Stage 3 (optional).** Sniffing HDS while it shows its data list gives exact DIDs and scaling at once, but needs access to an HDS unit and a second tester on the bus for that session (D-037: our tester then stays off; a listen-only capture only).

Expected yield: the interlock switches (clutch, neutral, side stand, kill) are the most likely finds, because the ECU uses them for its own start/ignition-cut logic. Gear position appears only if the CL250 has a gear position sensor. Wheel speeds and ABS state live in the ABS unit, a second ECU outside our tester policy: only a broadcast (Q-001) or a tap gives them.

## 4. Node sensors and platform data

| Signal | Source | Rate | Status |
|---|---|---|---|
| Acceleration ax/ay/az (±8 g), rotation gx/gy/gz (±500 dps) | conn MPU-6050 (D-032), BLE IMU block | 100 Hz | LIVE (offline analysis only, not a safety input) |
| GPS ground speed, heading, their accuracies, fix type, satellites | conn NEO-M8N NAV-PVT (D-060), BLE GPS block | 10 Hz | LIVE (never a position, invariant 7) |
| CAN health: bus state, TX/RX error counters, bus-offs, unanswered DIDs, latch flags | conn telemetry v4 | 10 Hz | LIVE |
| Tester stats: step gap max/over count, per-DID round trip min/max/sum/count, NRC 0x78 count | conn telemetry v4 (D-058) | rotating | LIVE |
| Per-DID state (valid/stale/skipped/NRC) and age | conn vehicle-signal block (D-066) | 5 Hz per page | LIVE |
| Session metadata: rider weight, load, ambient, weather, tyre pressures, fuel level, condition, route type | vehicle-mobile `meta.json`, hand-entered | per ride | LIVE |
| Chassis IMU (LSM6DSO/BMI270 class) for the EKF | rt-core (D-044, D-065) | 100–200 Hz to EKF | PLAN |
| Engine-block accelerometer (vibration) | rt-core (D-044, Q-025) | ≥ 1 kHz | PLAN |
| Safety-node fallback IMU | safety-node (D-042) | ~1 kHz | PLAN |
| Lean angle, its state and quality | rt-core EKF, 0x020 (D-065) | 50 Hz | PLAN (code in SIL) |
| Friction coefficient, total mass | rt-core, 0x022 | 10 Hz | PLAN |
| Node heartbeats (mode, error count, uptime) | every node, 0x081–0x085 | 10 Hz | PLAN |
| rt-core health 0xFD02, lean health 0xFD03 | rt-core UDS (D-055, D-067) | on request | PLAN |
| Microphone / acoustic, thermal | anomaly model inputs (hardware-architecture §5b.9) | — | PLAN / HW |
| Phone sensors (phone IMU, phone GPS) | not recorded by vehicle-mobile today | — | possible, not planned |

## 5. Derived signals (DERIV)

Computed offline (vehicle-ml / vehicle-server) first; anything safety-related only on rt-core per its decisions. Inputs refer to §2–4.

| Derived signal | From | How | Use |
|---|---|---|---|
| Longitudinal acceleration, jerk | vehicle speed, GPS speed, IMU ax | d(speed)/dt, filtered; cross-check with IMU | braking/accel events, aggressiveness (F9) |
| Distance, trip time, idle time, stops | speed | ∫speed dt; speed = 0 and RPM > 0 | usage profile, context |
| Gear estimate | RPM, speed, gear ratios + wheel radius (vehicle-work-plan §2) | RPM / speed ratio matched to the nearest gear | F4, shift events |
| Clutch disengaged / slipping | RPM, speed, gear estimate, throttle | ratio matches no gear while moving; ratio drift under load = slip | clutch anomaly (strategy note) |
| Neutral / coasting | RPM, speed, throttle | moving, ratio undefined, throttle closed | context |
| Shift events and shift time | RPM, speed | RPM step with continuous speed | riding style |
| Braking events, deceleration peak | speed derivative, IMU ax | threshold on decel; stand-in for the brake switch | context, anomaly |
| Speedometer error / effective tyre radius | ECU speed vs GPS speed | ratio at steady speed, good fix | calibration, tyre wear |
| Wheel slip (approx.) | ECU speed vs GPS speed (vs wheel speeds if found) | relative difference under accel/brake | R8 |
| Yaw rate, lateral acceleration, turn radius | IMU gz, speed, GPS heading rate | a_lat ≈ v·ω, r = v/ω | cornering context, lean cross-check |
| Pitch events (wheelie/stoppie), road roughness | IMU gy, az | pitch-rate peaks; RMS of az in bands | context (road type), anomaly |
| Engine vibration features | IMU (later engine accelerometer), RPM | RMS, crest factor, order spectrum vs RPM | anomaly (D-044) |
| Engine torque estimate | actual torque %, reference torque | Nm = % × reference / 100 | dyno, load |
| Engine power estimate | torque, RPM; or virtual dyno | P = T·ω; or m·a·v + drag + rolling (§5b.10) | F3 |
| Air–fuel ratio | commanded lambda | AFR ≈ λ × 14.7 (gasoline) | fueling anomaly |
| Fuel consumption, L/100 km, range | fuel rate, or MAF and lambda; speed; fuel level | MAF/(AFR·ρ_fuel); per distance | F5 |
| Volumetric efficiency (approx.) | MAP, RPM, IAT, displacement | speed-density | intake/valve anomaly |
| Fuel-trim drift | STFT, LTFT over rides | trend of LTFT; STFT variance | fueling, O2 sensor ageing |
| Throttle–torque response lag | throttle, actual torque %, RPM | cross-correlation lag | drivability anomaly |
| Warm-up curve, thermal rate | coolant, oil, IAT, ambient, run time | dT/dt, time to operating temperature | cooling anomaly |
| Heat soak | IAT − ambient at low speed | difference vs speed | context, anomaly |
| Charging health | battery voltage vs RPM | regulated voltage plateau, ripple, dip at crank | rectifier/regulator anomaly |
| Cranking dip | battery voltage, RPM 0 → > 0 | minimum voltage during start | battery health |
| ECU/bus health trends | CAN errors, NRC counts, round trips | rates per ride | data-quality flag for the models |
| Data quality per sample | ages, states, valid flags | stale/never/NRC masks | feature masking in training |

Added 2026-10-15 (same rules: offline first, nothing safety-related outside rt-core):

| Derived signal | From | How | Use |
|---|---|---|---|
| Final-drive ratio drift (chain stretch, sprocket/tyre wear) | RPM, speed, gear estimate | RPM/speed ratio per gear at steady cruise, trended over weeks | maintenance, slow anomaly |
| Odometer cross-check | ECU odometer (0xA6 if served), ∫speed, GPS distance | three distances per ride | speed sensor fault, data gaps |
| Throttle sensor plausibility | throttle A (F411), B (F447), relative (F445), commanded (F44C), grips (F449, F45A) | residuals between redundant channels | TP sensor ageing, a fault before the ECU flags it |
| Intake plausibility (air leak) | MAP, MAF, RPM, throttle, IAT | MAF vs speed-density estimate; MAP at closed throttle vs idle RPM | intake leak, sensor drift |
| Total fuel trim, trim vs load map | STFT + LTFT, load, RPM | trim per (RPM, load) cell | injector/O2 ageing, fuel quality |
| Fuelling per stroke, BSFC | cylinder fuel rate (0xA2) or fuel rate, power estimate | g/kWh | efficiency, engine health |
| Torque structure | demanded vs actual torque, friction torque (0x8E), reference torque | gap and friction vs coolant/oil temperature | warm-up friction, drivability |
| Air density and power correction | baro, IAT | ρ = p/(R·T); SAE J1349-style correction factor | normalise dyno and anomaly features across weather |
| Altitude change, road grade | baro (F433, or MAP with the engine off), speed; IMU pitch | Δh from the barometric formula; grade = Δh / distance | context (climb/descent), load explanation; never a position (invariant 7) |
| Cold-engine abuse | RPM, load, coolant/oil temperature | time and revs above a threshold while coolant < operating temperature | wear index, rider feedback |
| Over-rev and lugging | RPM, load, gear estimate | RPM near the limiter; high load at low RPM | wear index, riding style |
| Operating-point histogram | RPM, load (or MAP) | time per (RPM, load) cell per ride | usage profile, model conditioning |
| Idle quality | RPM at idle, MAP, battery voltage | RPM standard deviation and drift at warm idle | idle control, misfire hint |
| Fuel-cut / engine-braking phases | throttle closed, RPM > idle, speed, (fuel rate ≈ 0) | flag | separate decel from braking, fuelling features |
| Cooling fan switch-on temperature | coolant, battery voltage | voltage step of the fan load near the hot end of the coolant curve | thermostat/fan anomaly |
| Thermal cycles, time at temperature | coolant, oil, run time | count of cold→hot cycles; time above thresholds | engine ageing |
| Cool-down rate after stop | coolant, IAT at the next key-on, time since key-off | Newton cooling constant | heat soak, cooling system |
| Battery rest voltage, self-discharge | key-on voltage before crank, time since last ride | V vs days parked | battery ageing (pairs with the cranking dip) |
| Refuel and fuel slosh filter | fuel level, speed, IMU | step up at rest = refuel; level averaged over acceleration | consumption from level, range |
| Coast-down drag | speed decay with the clutch in or in neutral (clutch from the ratio rule), baro, IAT | fit F = a + b·v² | CdA, rolling resistance for the virtual dyno |
| Launch and clutch engagement | RPM, speed, throttle, gear estimate | RPM dip and slip time when moving off | clutch wear, riding style |
| Rider aggressiveness score | throttle rate, longitudinal jerk, lateral acceleration, lean (later) | weighted features per ride | context (F9), anomaly conditioning |
| Misfire rate | misfire monitor (0xF6xx, if served), IMU/engine accelerometer vibration | counts per 1000 revolutions; vibration order features | ignition/fuelling anomaly label |
| ECU software change | identification DIDs (0xF181/0xF188/0xF189, CalID/CVN) | value differs from the previous ride | split data sets by calibration |

Added 2026-10-19 (D-079, provisional): five health-snapshot windows, each a class-B record that opens on its entry condition, accumulates online and closes into a fixed-size ride-summary record (first complete instance of the ride plus a count; `windows` in `derived/cl250_derived.yaml`):

| Derived signal | From | How | Use |
|---|---|---|---|
| Health window: key-on | battery voltage, fuel-pump current (pending), coolant, IAT, ambient, MAP, baro; engine speed 0 | rest voltage, pump prime profile, sensor spread, MAP vs baro; warm-restart flag | battery, pump, sensor drift |
| Health window: crank | 1 kHz battery voltage and current (pending), engine speed 0 → > 0 | minimum voltage, peak current, dV/dI, crank duration | battery and starter health |
| Health window: warm idle | coolant > 80 °C, speed 0, idle band, 20 s; RPM, MAP, STFT, engine accelerometer (pending) | RPM spread and drift, MAP spread, STFT statistics, 0.5x/1x order RMS | idle control, misfire hint |
| Health window: cruise | gear estimate ≥ 4, speed ±2 km/h for 10 s, steady throttle; engine and swing-arm accelerometers (pending) | final-drive and VE residuals, vibration RMS | drivetrain wear, intake |
| Health window: post-stop | coolant, ambient, engine stopped with key on | coolant decay time constant | cooling system |

### 5.1 Where each derived signal is computed (D-070)

Classes of D-070 item 1: **A** live on rt-core, **B** per-ride summary on rt-core, **C** across rides on vehicle-server/vehicle-ml (from class-B values), **D** server only (off-vehicle inputs). Before the rt-core board exists every class is computed offline by the Python reference on recorded data (D-070 item 2). "Needs" lists what must exist first besides the 40 DIDs on rt-core (E-19).

| Derived signal | Class | Needs |
|---|---|---|
| Longitudinal acceleration, jerk | A | rt-core chassis IMU (or speed only) |
| Distance, trip time, idle time, stops | A + B | — |
| Gear estimate | A | defs vehicle constants (D-070 item 3) |
| Clutch disengaged / slipping, neutral / coasting | A | gear estimate |
| Shift events and shift time; launch and clutch engagement | A | gear estimate |
| Braking events, deceleration peak | A | — |
| Speedometer error / effective tyre radius | B | GPS on rt-core (D-060 item 1) |
| Wheel slip (approx.) | A | GPS on rt-core |
| Yaw rate, lateral acceleration, turn radius | A | rt-core chassis IMU |
| Pitch events, road roughness | A | rt-core chassis IMU |
| Engine vibration features | A | engine accelerometer, Q-025 |
| Engine torque estimate, torque structure | A | F461/F462/F463 served; 0x8E defined |
| Engine power estimate | A | torque estimate or virtual dyno inputs |
| Air–fuel ratio | A | F444 served |
| Fuel consumption, L/100 km, range | A + B | F45E or F410 + F444 served; 0xA2 defined |
| Fuelling per stroke, BSFC | A | 0xA2 or F45E; power estimate |
| Volumetric efficiency | A | displacement in defs constants |
| Total fuel trim, trim per (RPM, load) cell | A + B | F406/F407 served; 0x03 defined (closed loop) |
| Fuel-trim drift | C | per-ride trim cells |
| Throttle–torque response lag | B | bounded window on rt-core |
| Throttle and intake plausibility residuals | A | redundant channels served |
| Air density, power correction | A | F433, F40F served |
| Altitude change, road grade | A | F433 (or MAP engine-off); IMU pitch |
| Warm-up curve, thermal rate, heat soak | A + B | — |
| Thermal cycles, time at temperature | B | — |
| Cooling fan switch-on temperature | B | — |
| Cool-down rate after stop | C | times across key-off |
| Charging health, cranking dip | A | — |
| Battery rest voltage | A | — |
| Battery self-discharge vs days parked | C | rest voltages across rides |
| Cold-engine abuse, over-rev, lugging | A + B | gear estimate |
| Operating-point histogram | B | — |
| Idle quality | A + B | — |
| Fuel-cut / engine-braking phases | A | — |
| Refuel detection, fuel-level slosh filter | A | F42F served |
| Coast-down drag | B | clutch/neutral flag; F433, F40F |
| Final-drive ratio per gear (this ride) | B | gear estimate |
| Final-drive ratio drift (chain, sprocket, tyre wear) | C | per-ride ratios |
| Odometer cross-check | B | 0xA6 defined, GPS on rt-core |
| Rider aggressiveness score | B | — |
| Misfire rate | A | 0xF6xx defined, or vibration features |
| ECU software change | B | identification DIDs defined |
| Health window: key-on | B | fuel-pump current sensor (pending) for the pump profile |
| Health window: crank | B | 1 kHz battery voltage and current sample (pending) |
| Health window: warm idle | B | engine accelerometer, Q-025 (pending) for the vibration |
| Health window: cruise | B | gear estimate; engine and swing-arm accelerometers (pending) for the vibration |
| Health window: post-stop | B | — |
| ECU/bus health per ride | B | — |
| ECU/bus health trends | C | per-ride health |
| Data quality per sample | A | — |
| Anything conditioned on rider weight, load, weather, tyre pressure | D | vehicle-mobile `meta.json` |

## 6. What to do next to grow the data set

1. Ride with conn on defs v0.12.0: the vehicle-signal block shows which D-068 DIDs the CL250 serves (LIVE vs NRC 0x31 vs skipped) at key-on and after the engine start.
2. Q-001 listen-only capture at key-on and while riding: any broadcast frame (ABS, dash) is a free source of wheel speeds, brake or gear.
3. Define the DEF PIDs that matter for one cylinder: 0x01, 0x03 and the O2 sensor the bitmap reports.
4. Decide (D-xxx) on proprietary-DID discovery (strategy stage 2) and/or switch taps (§3), with `architecture-guard` (which node) and `safety-reviewer` (tester or wiring).
5. Tune the D-068 tiers from the first rides: faster for the DIDs that carry information, drop the dead ones.
6. Run the D-059 probe env (`esp32-s3-devkitc-1-probe`) once on the bike: its 0x22 0xF4xx bitmaps settle §2.1 (a) and (b). Then propose adding the 0xF600/0xF620… and 0xF800 support DIDs and the identification DIDs (§2.1 (c), (d)) to `discovery_scan` (`/signal-change`, `safety-reviewer`).
7. Before the stimulus run (§3.1), read the HDS data list in the CL250 service manual's PGM-FI chapter (user) and draft the range-scan D-xxx.
8. Close the integration gaps of §7, in the order given there.

## 7. Where each signal flows in the code today (2026-10-15)

Checked on every repo's `origin/main`. "40" = the 5 verified + 35 D-068 DIDs of defs v0.12.0.

| Repo / artifact | defs pin | ECU DIDs handled | How | Derived signals |
|---|---|---|---|---|
| defs `gen/c` (conn, rt_core, hil_sim) | v0.12.0 | 40 | generated DID table (`VEHICLE_CL250_DID_COUNT` 40); not generated for safety/io (correct) | — |
| defs `gen/python`, `gen/dart` | v0.12.0 | 40 | merged catalog (`candidates: []`, so catalog = polled table) | — |
| defs `vss/overlay.vspec` | — | **5** | only the verified DIDs carry `platform_signal` / a VSS path | — |
| defs `dbc/platform.dbc` | — | **5** | 0x021 VehicleSpeed, 0x110 VehicleEngine (RPM, battery, coolant, TPS); `dbc/cl250.dbc` empty (Q-001) | — |
| defs `ble/ble_schema.json` | — | 5 fixed + 40 generic | telemetry v4 fixed fields; `vehicleSignalBlock` records keyed by DID | — |
| vehicle-connectivity-node | v0.12.0 | **40 polled**, 5 decoded | `HondaCANModule` polls the generated table with the D-068 stop rule; `storeValue` keeps only the 5 in `SystemState`, the 35 travel as raw bytes in the BLE vehicle-signal block | — |
| vehicle-rt-core | **v0.9.0** | **5** | generic client loop, but the pinned table has 5; republishes 5 on 0x021/0x110; serves 5 on 0xFD10–0xFD14 | lean EKF (0x020) |
| vehicle-mobile | v0.11.0 | 40 (generic) | catalog-driven Signals screen decodes any vsig record; records `signals.csv` | none (unit conversions only) |
| vehicle-server | v0.11.0 | 40 (generic) | `signals.parquet` long format (one row per record), MDF4 one channel per catalog signal; `telemetry.parquet` 5 columns | none |
| vehicle-linux-node, vehicle-ml, vehicle-mcp, vehicle-hil-bench | none | 0 | skeletons (README/CLAUDE.md only) | — |

Gaps, in the order they should be closed (each is its own change; none is started by this list):

1. **Which of the 40 the CL250 serves is unknown** until the first key-on/idle (V0/V1) and the probe run. Every later step depends on it, so the dead DIDs are dropped before anything is built on them.
2. **rt-core sees 5.** It must implement the D-068 tester rule before its pin passes v0.11.0 (ISSUES E-19). After that its generic client polls all 40, but nothing carries the 35 off rt-core: they need platform-side DIDs (an extension of 0xFD10–0xFD14 in `uds/dids.yaml`) and/or platform-bus frames in `platform.dbc` (bus load to check, ID plan in ARCHITECTURE §4). Until then conn is the only path for them.
3. **No VSS path for the 35.** Kuksa (linux-node) and vehicle-mcp read VSS only. Some have core COVESA paths under `Vehicle.Powertrain.*` (check against the pinned VSS 6.0; COVESA moved the OBD branch out of the core catalog into an optional overlay), the rest need a `Vehicle.Motorcycle.*` extension, which needs the user's approval (D-004).
4. **mobile/server pin v0.11.0**: they already decode the 40, but show the D-068 DIDs with v0.11.0 metadata until bumped to v0.12.0 (E-19 (4)).
5. **Time resolution of the 35 on the phone**: the vehicle-signal block sends the latest value per DID every 200 ms, so the recording holds one sample per poll at best (2/5/10 s). That matches the D-068 tiers; a faster tier needs no BLE change.
6. **No derived signal is computed anywhere** except the lean EKF. §5 is offline work for vehicle-ml/vehicle-server on the recorded `signals.parquet` first; a derived signal shown live in the app is a later, separate decision.

