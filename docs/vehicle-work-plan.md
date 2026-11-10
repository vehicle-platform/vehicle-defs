# On-Vehicle Work Plan — Honda CL250

> Translated from the Turkish original (`archive/tr/motor-uzeri-calisma-plani.md`). Where this document conflicts with `ARCHITECTURE.md` or `DECISIONS.md`, those take precedence.

**Project:** Embedded diagnostics and driver assistance unit / HIL validation infrastructure
**Document scope:** All on-motorcycle hardware integration, parameter measurement, data collection, and field testing activities
**Version:** 1.0 — September 2026

---

## 1. Purpose and Scope

This document defines the integration of the developed unit into the vehicle, the measurement of vehicle parameters, data collection protocols, and field validation tests.

**Out of scope:** modifying the ECU software, changing engine control parameters, tampering with the emissions system. Rationale in section 12.

---

## 2. Baseline Vehicle Data

The values below are taken from the manufacturer specification and will be used as the baseline data for calculations.

| Parameter | Value |
|---|---|
| Engine | 249 cc, liquid-cooled, DOHC 4-valve, single-cylinder |
| Bore × stroke | 76.0 × 55.0 mm |
| Compression ratio | 10.7 |
| Maximum power | 18 kW (24 PS) / 8500 rpm |
| Maximum torque | 23 N·m / 6250 rpm |
| Fuel system | PGM-FI |
| Transmission | 6-speed, constant mesh |
| Weight (wet) | 172 kg |
| Wheelbase | 1485 mm |
| Caster angle | 27°00′ |
| Trail | 108 mm |
| Seat height | 790 mm |
| Ground clearance | 163 mm |
| Front tire | 110/80 R19 |
| Rear tire | 150/70 R17 |
| Brakes | Front/rear hydraulic disc, ABS |
| Fuel tank | 12 L |

### 2.1 Drivetrain Ratios

| Position | Ratio |
|---|---|
| Primary reduction | 2.807 |
| Secondary reduction | 2.642 |
| 1st gear | 3.416 |
| 2nd gear | 2.250 |
| 3rd gear | 1.650 |
| 4th gear | 1.350 |
| 5th gear | 1.166 |
| 6th gear | 1.038 |

**Total reduction** = primary × gear × secondary

| Gear | Total ratio |
|---|---|
| 1 | 25.33 |
| 2 | 16.68 |
| 3 | 12.23 |
| 4 | 10.01 |
| 5 | 8.645 |
| 6 | 7.698 |

This table will be used for gear detection, the virtual dynamometer, and speed validation.

### 2.2 Rear Wheel Radius (calculated)

Tire 150/70 R17:
- Rim diameter: 17″ = 431.8 mm → rim radius 215.9 mm
- Sidewall height: 150 × 0.70 = 105.0 mm
- Unloaded radius: 215.9 + 105.0 = **320.9 mm**
- Dynamic (loaded) radius ≈ 2-4% smaller → **~311 mm** (to be verified by measurement)
- Rolling circumference (unloaded): 2π × 0.3209 = **2.016 m**

**Validation method:** With the rider on board, a chalk mark is placed on the tire, the bike is rolled 10 full turns on flat ground, the distance covered is measured and divided by 10. This value is compared against the calculated circumference. The measured value will be used.

### 2.3 Speed Validation Formula

```
v [m/s] = (rpm / 60) / total_ratio × rolling_circumference
```

Example: 6th gear, 6000 rpm
v = (6000/60) / 7.698 × 2.016 = 100 / 7.698 × 2.016 = **26.2 m/s = 94.3 km/h**

This calculation will be used to independently check the accuracy of the speed signal read from CAN. If there is a deviation, the speedometer error (motorcycles typically read 5-10% high) will be characterized.

---

## 3. Hardware to Be Mounted on the Vehicle

### 3.1 Main Unit (DUT)

| Feature | Decision |
|---|---|
| Processor | STM32H755 Cortex-M7 (rt-core, the DUT, D-001, D-072) |
| Enclosure | ABS or aluminum box, minimum IP54 |
| Mounting location | Under-seat or inside the side panel (preferred: under-seat) |
| Vibration isolation | Silicone mount or double-sided vibration-damping tape |
| Connection | Detachable connector (must be removable from the vehicle) |
| Target size | Under 100 × 70 × 30 mm |

**Mounting location rationale:** Under the seat is both far from heat (exhaust, cylinder) and not directly exposed to rain. Mounting near the engine block will be avoided — both temperature and vibration double there.

### 3.2 Bus Connection

| Item | Detail |
|---|---|
| Point | Diagnostic connector (DLC) |
| Lines used | CANH, CANL, GND |
| Connection type | Y-cable — parallel to the original connector, no cutting |
| Termination | **Additional termination not used.** The line is already terminated at both ends; a third resistor would disrupt it |
| Cable | Twisted pair, shielded if possible |
| Length | Under 50 cm |

**Critical note:** No additional termination resistor will be added to the CAN line. On the bench, the simulator side is a separate line so termination is needed there; it is not needed on the vehicle.

**Safety note (updated for D-019..D-021, D-037):** The CL250 ECU does not broadcast its data; it answers UDS read requests (D-019). So the tester has to transmit, and "listen-only" cannot collect the data. Rules on the bike:
- The first connection is made with the engine off, first listen-only to answer Q-001 (is there any passive broadcast traffic?).
- Then exactly one tester (rt-core; connectivity-node until then, D-023) polls, and it sends only the read and session requests in `uds/vehicle_cl250.yaml` `tester_policy` (D-020), enforced by the generated gate. Nothing that writes, resets, unlocks or reprograms the ECU is ever sent.
- The first polling session is done in a closed area with the engine idling.

### 3.3 Power Supply

| Item | Detail |
|---|---|
| Supply point | Ignition-switched line (not the always-on battery line) |
| Fuse | 2 A, glass or blade type, at the unit input |
| Reverse polarity protection | Series Schottky diode or P-MOSFET |
| Transient overvoltage | TVS diode (bidirectional, 24-30 V clamp) |
| Voltage step-down | Wide-input buck (6-40 V input, 5 V output) |
| Filtering | Electrolytic + ceramic on the input side |
| Ground | Directly to the vehicle's negative line, not the chassis |

**Rationale:** Powering from the ignition-switched line prevents battery drain while the motorcycle is parked. If an always-on line is used instead, sleep current must be kept below 1 mA and this must be verified by measurement.

### 3.4 IMU (Accelerometer + Gyroscope)

| Item | Detail |
|---|---|
| Sensor | 6-axis MEMS (accel + gyro), preferably 9-axis |
| Mounting location | Inside the main unit or at a fixed point on the chassis |
| Mounting rigidity | Rigid — vibration isolation **will not** be used |
| Sampling | Minimum 100 Hz, preferably 200 Hz |
| Axis alignment | Aligned with the vehicle's longitudinal axis; deviation measured and corrected in software |

**Critical note:** The IMU must not be mounted on a vibration-damping mount. The mount would add its own resonance to the measurement and corrupt the lean angle estimate. Engine vibration (pronounced in a single-cylinder engine), on the other hand, will be suppressed with a low-pass filter.

**Alignment procedure (detailed in section 5.4):** The motorcycle is held upright on flat ground and a zero reference is taken; it is then tilted to a known angle (e.g., 10° using the kickstand) and the measurement is validated.

### 3.5 GPS Module

| Item | Detail |
|---|---|
| Module | u-blox NEO-M8N or equivalent |
| Update rate | Minimum 5 Hz, preferably 10 Hz |
| Antenna | Active, ceramic patch |
| Mounting location | Clear sky view — handlebar area or behind the seat |
| Use | Position, ground speed, turn radius calculation, lap analysis |

**Note:** Must not be placed inside a metal enclosure. GPS ground speed data will be used as a second independent reference for validating the CAN speed signal.

### 3.6 Voice Command Hardware (for the ESP32-S3 voice node)

| Item | Detail |
|---|---|
| Microphone | Noise-canceling electret or an off-the-shelf intercom microphone |
| Placement | Inside the helmet, at mouth level (helmet microphone on vehicle-connectivity-node for ESP-SR; the engine sound uses a separate engine-facing microphone on linux-node, D-044) |
| Connection | Wired (preferred) or via existing intercom over BT |
| Trigger | Handlebar-mounted push-to-talk button (primary); ESP-SR wake word optional (D-047) |
| Button placement | Left handlebar, in a position operable with gloves |
| Feedback | In-helmet speaker or intercom speaker |

**Rationale:** Push-to-talk as the primary trigger eliminates false triggering caused by wind noise and reduces processor load. The wake word is an optional second trigger for hands-free use (D-047; default and conditions open, Q-024).

### 3.7 Optional — Suspension Instrumentation

| Item | Detail |
|---|---|
| Sensor | Linear potentiometer or draw-wire encoder |
| Location | Alongside the front fork and rear shock |
| Measurement | Suspension stroke, velocity |
| Use | Road surface classification, front-rear load distribution, setup effect |

This item is in extended scope. If added, it significantly improves the input quality of the road surface classification model.

### 3.8 Optional — Temperature Sensors

| Point | Sensor | Purpose |
|---|---|---|
| Ambient | Digital (inside the unit) | Reference, correction |
| Inside the unit | Digital | Thermal behavior monitoring |
| Brake disc | Non-contact IR | Brake load analysis |
| Exhaust (optional) | Type K thermocouple | Combustion quality indicator |

Exhaust temperature measurement is valuable for fault detection work but is in Phase 2 scope.

---

## 4. Wiring and Electrical Integration

### 4.1 General Rules

- The original wiring harness **will not be cut**. All connections are parallel or via connectors.
- The unit must be removable from the vehicle via a single detachable connector (for testing, servicing, inspection).
- Cables will be protected from vibration: inside spiral wrap or corrugated conduit.
- Routing will stay away from moving parts (steering, suspension, chain).
- Minimum 15 cm clearance from heat sources (exhaust, cylinder, radiator), or a heat shield.
- Every cable end will be labeled; the wiring diagram will be documented.

### 4.2 Noise and EMC Measures

Single-cylinder engines' ignition systems produce strong electromagnetic noise. Measures:

- Signal cables kept away from the ignition coil and spark plug wire
- CAN line will be twisted pair
- Analog signals (if any) shielded cable, shield grounded at one end only
- LC filter at the power input
- If the unit enclosure is metal, it will be bonded to chassis ground

**Validation:** The same measurement will be taken and compared with the engine running and stopped. If there is a marked increase in signal noise with the engine running, filtering will be reviewed.

### 4.3 Sleep Current Validation

The current drawn by the unit with the ignition off will be measured with a multimeter or an INA sensor. Target: **< 1 mA**. If exceeded, the supply line will be switched with the ignition.

---

## 5. Measuring Vehicle Parameters

These parameters are required for the virtual dynamometer, the cornering safety module, and the HIL plant model alike.

### 5.1 Total Mass

| Method | Detail |
|---|---|
| Scale | Front and rear wheels weighed separately |
| Measurement conditions | Empty tank / full tank / with rider / rider + load |
| Recording | Separate value table for each scenario |

If a scale is not available, the manufacturer value (172 kg) + rider weight + fuel (12 L × 0.75 kg/L = 9 kg) is used; the method will be noted in the thesis.

### 5.2 Weight Distribution and Center of Gravity

**Longitudinal distribution:** Found by weighing the front and rear wheels separately.

```
x_CG = L × (W_rear / W_total)      (distance from front axle)
```

**Height (h_CG):** With the motorcycle's rear wheel raised (at a known angle), the change in load at the front axle is measured and h_CG is calculated. This measurement requires care; alternatively, a value from the literature for a similar-class motorcycle (typically 0.45-0.60 m) can be used and stated as an assumption in the thesis.

h_CG feeds directly into the critical lean angle calculation in the cornering safety module.

### 5.3 Wheel Radius

The rolling measurement from section 2.2. To be done with the rider on board and at normal tire pressure. Tire pressure will be recorded (the same pressure will be used in subsequent measurements).

### 5.4 IMU Alignment and Calibration

| Step | Action |
|---|---|
| 1 | Motorcycle upright on flat, level ground, on the center stand |
| 2 | 60-second static recording → accelerometer offset and gyroscope bias are calculated |
| 3 | Tilt to a known angle (e.g., 10° and 20°, verified with an inclinometer) → axis scale validation |
| 4 | Longitudinal axis alignment: ride at constant speed on a straight road, longitudinal acceleration should be near zero |
| 5 | The resulting correction matrix is embedded in the software |

**Temperature effect:** MEMS gyroscope bias varies with temperature. Static measurement will be repeated at different ambient temperatures (morning/midday) and the bias-temperature relationship will be derived.

### 5.5 Extracting the CAN Signal Map

| Step | Action | Expected output |
|---|---|---|
| 1 | Ignition on, engine off, 5 min listen-only raw recording (Q-001) | Which IDs are on the bus, their periods (if any passive traffic exists) |
| 2 | 5 min recording at idle | Identification of bytes that vary with RPM |
| 3 | Controlled throttle blip (stationary) | Isolation of RPM and TPS bytes |
| 4 | Low-speed riding | Identification of the speed byte |
| 5 | Engine warm-up process (from cold) | Identification of the temperature byte |
| 6 | Brake application | Brake switch bit |
| 7 | Standard OBD2 PID scan | List of supported PIDs |

At each step, the bytes that change will be flagged to build a signal definition file (DBC-like). This file will be used as the CL250 definition within the vehicle-agnostic architecture of the HIL bench.

**Note:** If the meaning of manufacturer-specific messages cannot be pinned down, they will be recorded in the definition file with an "unverified" tag. No speculative interpretation will be made.

---

## 6. Data Collection Plan

### 6.1 Signals to Record

| Source | Signal | Frequency |
|---|---|---|
| CAN | Engine RPM | 10-20 Hz |
| CAN | Vehicle speed | 10 Hz |
| CAN | Throttle position | 10-20 Hz |
| CAN | Engine temperature | 1 Hz |
| CAN | Intake pressure / air flow | 10 Hz |
| CAN | Fuel trim (if available) | 1 Hz |
| CAN | Battery voltage | 1 Hz |
| CAN | Fault codes | Event-based |
| IMU | 3-axis acceleration | 100-200 Hz |
| IMU | 3-axis angular rate | 100-200 Hz |
| Derived | Lean angle | 100 Hz |
| GPS | Latitude, longitude, ground speed, heading | 5-10 Hz |
| Unit | Supply voltage, current | 10 Hz |
| Unit | Internal temperature | 0.1 Hz |
| Unit | Stack usage, task timings | 1 Hz |

**Profile-based frequency:** Lower sampling in the urban profile, higher in the sport profile (assistant profiles in section 9).

### 6.2 Metadata (per session)

The following will be recorded at the start of each recording session:

- Date, time, session ID
- Ambient temperature, weather (dry/wet)
- Tire pressure (front/rear)
- Fuel level
- Rider weight, additional load
- Motorcycle configuration (gearing, exhaust, filter — for modification experiments)
- Route type (urban / rural / highway / closed course)
- Free-text note field

This metadata is mandatory for labeling the models to be built later. A recording without metadata becomes unusable later.

### 6.3 Storage

| Item | Decision |
|---|---|
| Format | Binary recording + JSON metadata |
| Timestamp | Microsecond, monotonic counter + GPS synchronization |
| Medium | microSD (on the vehicle) → server (after the session) |
| File splitting | One file per session, maximum 100 MB |
| Integrity | CRC per block, last block must be recoverable on sudden interruption |
| Backup | Copy to computer after each session, second copy in the cloud |

**Critical:** Data loss is irreversible. Recording format and backup discipline must be solid from the very first session.

### 6.4 Collection Schedule

Data collection will run continuously starting from week 4 of the project schedule. Each ride is one data session. Target: minimum **40 hours** of labeled ride data by the end of the term.

---

## 7. Field Test Protocols

### 7.1 Test Classes and Environments

| Class | Environment | Speed range |
|---|---|---|
| T0 — Static | Garage/workshop | 0 |
| T1 — Low speed | Closed parking lot | 0-30 km/h |
| T2 — Medium speed | Empty industrial road / closed area | 30-70 km/h |
| T3 — High speed | Rural road (off-peak hours) | 70-100 km/h |
| T4 — Limit tests | **Closed area / track only** | Variable |

**Rule:** T4-class tests will never be conducted on public roads under any circumstances.

### 7.2 T0 — Static Tests

| Test | Procedure | Success criterion |
|---|---|---|
| Connection validation | Ignition on, is CAN traffic being read | Messages received, error counter not increasing |
| Sleep current | Ignition off, current measurement | < 1 mA |
| Starter-cranking behavior | Recording while pressing the starter | Unit does not reset, recording is not corrupted |
| Idle stability | 10 min idle recording | RPM fluctuation characterized |
| Warm-up profile | From cold to operating temperature | Temperature signal validated |
| Noise measurement | Engine on/off signal comparison | Noise increase within acceptable limit |
| Voice command (in the garage) | 20 commands × 10 repetitions | Recognition rate > 90% |

### 7.3 T1 — Low-Speed Tests

| Test | Procedure |
|---|---|
| Speed signal validation | Known distance, constant speed; CAN speed vs. GPS speed vs. calculation |
| Gear detection | Constant speed in each gear; validation of gear inference from RPM/speed ratio |
| IMU lean validation | Tight circle at low speed, lean angle recording |
| Brake signal | Gradual braking, signal and acceleration correlation |
| Recording integrity | Ignition cut during a ride, file recoverability |

### 7.4 T2/T3 — Road Tests

| Test | Procedure |
|---|---|
| Constant-speed cruising | 2 min constant speed in each gear; consumption and load data |
| Acceleration runs | Virtual dynamometer (section 8) |
| Brake tests | Gradual deceleration, brake acceleration characterization |
| Cornering data | Corners during normal riding, lean angle distribution |
| Long cruise | 1+ hour uninterrupted, thermal and memory behavior |
| Voice command (while riding) | Recognition rate at different speeds: 30/50/70/90 km/h |

**Voice command test note:** Wind noise increases with speed. How the recognition rate changes with speed will be measured and reported — this becomes an actual experimental result in the thesis.

### 7.5 T4 — Limit and Safety Tests

**These tests will only be conducted in a closed area, with protective equipment, and with a gradual approach.**

| Test | Procedure | Safety rule |
|---|---|---|
| Cornering limit calibration | Known-radius circle, speed increased in steps | Each step +5 km/h, lean angle monitored, stop at any sense of discomfort |
| Warning threshold validation | Warning trigger point recorded | Limit is not pushed further after the warning |
| Emergency braking | Maximum braking on dry ground | ABS active, gradual approach |
| Low friction (optional) | Wet ground, low speed | Below 30 km/h only |

**Mandatory safety rules:**

1. Full protective equipment: helmet, back protector, jacket, gloves, boots
2. A second person present at the test site
3. Limit-test duration per session will not exceed 30 minutes (fatigue)
4. Whether the data recording is working will not be checked while riding — it will be verified before the session
5. A new software version will not be tried on T4 for the first time; it will first be validated on T1
6. If weather conditions are unsuitable (wet, windy), the session will be postponed

**Methodological note:** The goal of cornering limit calibration is not to "find the limit," but **to approach the model-predicted limit from a safe margin and validate the model's consistency.** The actual fall/slide limit will not be reached.

---

## 8. Virtual Dynamometer Protocol

### 8.1 Method

Wheel power is calculated from longitudinal acceleration and resistive forces:

```
F_wheel = m·a + F_rolling + F_aero + m·g·sin(grade)

F_rolling = C_rr · m · g
F_aero = 0.5 · ρ · C_d · A · v²

P_wheel = F_wheel · v
T_engine = (F_wheel · r_wheel) / total_ratio
```

### 8.2 Measurement Procedure

| Step | Action |
|---|---|
| 1 | A flat, gradeless, empty road section is chosen (grade verified with GPS) |
| 2 | Engine brought to operating temperature |
| 3 | Full-throttle acceleration in a fixed gear (3rd or 4th) from low RPM to redline |
| 4 | The same run is repeated **in both directions** (to cancel wind and grade effects) |
| 5 | Minimum 5 repetitions |
| 6 | Outliers are removed, the average is taken |

### 8.3 Determining the Coefficients

**Rolling and aerodynamic resistance — coast-down test:**

The engine is put in neutral, the bike is left to decelerate freely from a given speed, and the speed-time curve is recorded. C_rr and C_d·A are jointly estimated by fitting a resistance model to this curve.

| Parameter | Expected range (motorcycle) |
|---|---|
| C_rr | 0.012 - 0.020 |
| C_d · A | 0.35 - 0.60 m² (upright riding position) |
| ρ (air density) | Calculated from temperature and pressure |

The coast-down test will also be performed in both directions.

### 8.4 Validation

| Step | Method | Purpose |
|---|---|---|
| Repeatability | 10 runs under the same conditions, standard deviation | Measurement uncertainty (target < 5%) |
| Sensitivity | Known change (gear ratio), expected vs. measured | Does the system correctly capture the change |
| Accuracy | Real dynamometer session | Absolute error percentage |

**Comparison against expected values:** The manufacturer states 18 kW at 8500 rpm and 23 N·m at 6250 rpm. These are crankshaft output values; wheel power is typically **8-15% lower** due to drivetrain losses. The measurement result is expected to fall within this range; if it falls outside, the method will be reviewed.

---

## 9. Assistant Profiles (On-Vehicle Behavior)

Engine parameters are not changed; what changes is the unit's behavior.

| Profile | Sampling | Display | Warning threshold | Voice feedback |
|---|---|---|---|---|
| Urban | Low (10 Hz) | Simple: speed, gear, temperature | Conservative | Minimal |
| Touring | Medium (20 Hz) | Range, consumption, gear suggestion | Conservative | Fuel and rest-stop warnings |
| Sport | High (100 Hz) | Lean angle, acceleration, lap time | Late (experienced rider) | Critical only |
| Eco | Low (10 Hz) | Instantaneous/average consumption, driving score | Conservative | Throttle and gear coaching |

**Eco profile experiment:** The same route, under the same conditions, is ridden with the eco profile on and off; the consumption difference is measured. This produces a measurable result in the thesis.

---

## 10. Modification Experiments (Measurement System Sensitivity Validation)

The purpose of these experiments is not a performance gain, but **to show that the measurement system correctly captures a known change.**

### 10.1 Primary Experiment — Gear Ratio Change

| Item | Detail |
|---|---|
| Change | Front sprocket down 1 tooth (or rear up 2-3 teeth) |
| Why primary | The expected result is **mathematically calculable** |
| Expected effect | Wheel torque increases by the ratio, top speed drops by the same ratio |
| Measurement | Before/after virtual dynamometer + 0-60 km/h time |
| Success criterion | Measured change agrees with the calculated change within 5% |
| Cost | 300-600 TL |
| Reversible | Yes |

Example: If the front sprocket goes 14T→13T, the ratio change is 14/13 = 1.0769, i.e., a **7.7% increase** in wheel torque is expected. If the device can measure this value, the system is validated.

### 10.2 Secondary Experiments

| Experiment | Expected effect | Measurability | Reversible |
|---|---|---|---|
| Tire pressure change | Change in C_rr, coast-down curve | High | Yes |
| Additional load (rider + passenger/luggage) | Mass increase, acceleration decrease | High | Yes |
| Partial air filter clogging | Volumetric efficiency drop, fuel trim deviation | Medium | Yes |
| Riding position (upright/tucked) | Change in C_d·A | Medium | Yes |
| Exhaust change (if any) | Small power change | Low | Yes |

**Note:** The air filter and intake restriction experiments also produce data for the fault detection work in Phase 2.

### 10.3 Modifications That Will Not Be Made

| Modification | Rationale |
|---|---|
| ECU software change | Legal (illegal modification), warranty, safety risk; gain ~3-5% |
| Piggyback / tuning box | Blind tuning without wideband lambda and EGT; risk of engine damage |
| Tampering with the emissions system | Legal |
| Brake/suspension safety parts | Safety; the test vehicle's integrity must be preserved |
| Permanent wiring cuts/soldering | The vehicle must be able to return to its original state |

---

## 11. Real Dynamometer Reference Session

| Item | Detail |
|---|---|
| Purpose | Determining the absolute accuracy of the virtual dynamometer |
| Timing | After the measurement system has matured, before thesis writing |
| Duration | Half a day |
| Cost | 3000-6000 TL (commercial) |
| Alternative | A university mechanical engineering engine test lab (may be free — **ask first**) |
| Procedure | Measurement with both the dyno and our own system, same day, same conditions |
| Output | Torque-RPM and power-RPM curve comparison, error percentage |

**Note:** The motorcycle's own data will also be recorded during the dyno session; this data will be used to feed the HIL plant model's torque map.

---

## 12. Legal and Safety Framework

### 12.1 Legal Status

| Activity | Status |
|---|---|
| Reading data from the diagnostic connector | No issue: read-only UDS/OBD requests (D-020), as any OBD scan tool does; no ECU write |
| Installing an additional electronic unit (removable) | No issue |
| Gear ratio change | Common practice; no issue expected at inspection, will still be logged |
| ECU software change | **Will not be done** — may fall under unregistered modification |
| Tampering with the emissions system | **Will not be done** |
| Lighting/additional equipment | If done, will comply with regulations |

All additional equipment must be removable before inspection. This is one of the design requirements.

### 12.2 Safety Protocol

**Checklist before every session:**

- [ ] Tire pressure checked and recorded
- [ ] Brakes and chain checked
- [ ] All mounting points checked for tightness (vibration loosens them)
- [ ] Cables clear of moving parts, no pinching
- [ ] Recording system working (verified before the session)
- [ ] Protective equipment complete
- [ ] Weather and road conditions suitable
- [ ] Software version previously tested in a lower-risk environment

**Prohibited while riding:**

- Looking at a screen/phone
- Checking recording status
- Investigating a software bug
- Trying new software for the first time at high speed

**Design rule:** No failure of the unit should affect the ride. Even if the unit completely crashes, the motorcycle must continue to operate normally. This is guaranteed by the connection topology (passive listening, no cuts in the original wiring).

---

## 13. On-Vehicle Bill of Materials and Cost

| Item | Purpose | Estimate (TL) |
|---|---|---|
| NUCLEO-H745ZI-Q (STM32H745: M7 = rt-core, M4 = safety partition; D-001, D-072, D-094) | Main MCU | ~2900 |
| ESP32-S3 (connectivity-node: BLE/Wi-Fi bridge, Phase 0 tester until rt-core, D-023) | Connectivity | 300-450 |
| CAN transceiver | Physical layer | 80-150 |
| IMU (6/9-axis) | Motion data | 150-300 |
| GPS module + antenna | Position, speed, turn radius | 250-450 |
| microSD card + slot | Recording | 150-250 |
| Power circuit (buck, protection, filter) | Supply | 200-350 |
| Current/voltage sensor (INA226) | Power monitoring | 80-150 |
| OBD2/DLC Y-cable + connector | Connection | 150-250 |
| Microphone + button + speaker | Voice command | 250-450 |
| Enclosure (IP54) | Protection | 150-300 |
| Vibration mount, fasteners | Mounting | 100-200 |
| Cable, connectors, spiral wrap, fuse | Wiring | 250-400 |
| PCB fabrication (main unit) | Board | 400-700 |
| **Subtotal (mandatory)** | | **5410-7300** |
| Suspension potentiometers (opt.) | Instrumentation | 300-600 |
| Temperature sensors (opt.) | Thermal analysis | 150-400 |
| Sprocket (for experiment) | Sensitivity test | 300-600 |
| **Subtotal (optional)** | | **750-1600** |
| Dynamometer session | Accuracy reference | 0-6000 |
| Track day (optional) | Controlled data | 0-3000 |
| **Grand total** | | **6160-17900** |

The board price is the NUCLEO-H755ZI-Q list price of `hardware-procurement-list.md` (2,904.30 TL); the NUCLEO-H745ZI-Q bought on 2026-11-02 (D-094) is the same class. The itemised, current list with stores and prices is `hardware-procurement-list.md`; this table is the planning estimate. The wide range is due to the dyno and track-day line items. If university facilities can be used, the total stays close to the lower band.

---

## 14. On-Vehicle Work Schedule

| Week | Activity |
|---|---|
| 1 | CAN connection, listen-only check (Q-001), first polling session and raw recordings |
| 2 | Signal map extraction (section 5.5), OBD2 PID scan |
| 3 | Temporary mounting (perforated bracket, cable ties), power circuit testing |
| 4 | IMU alignment and calibration, T0 static tests |
| 4+ | **Continuous data collection begins** |
| 5-6 | Vehicle parameter measurement (mass, CG, wheel radius) |
| 6 | PCB order placed |
| 7-8 | T1 low-speed tests, speed/gear validation |
| 8-9 | Coast-down tests, determining resistance coefficients |
| 9-10 | Permanent mounting (PCB + enclosure), T2/T3 road tests |
| 10-11 | Virtual dynamometer runs, repeatability measurement |
| 11 | Sprocket experiment (sensitivity validation) |
| 12 | T4 limit tests (closed area), cornering module calibration |
| 12-13 | Dynamometer reference session (if it can be scheduled) |
| 13 | Voice command field tests, eco profile comparison experiment |
| 13-14 | Data analysis, reporting of results |

---

## 15. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Inability to interpret CAN messages | Medium | High | Standard OBD2 PIDs used as the baseline; raw message decoding is optional |
| Vibration-induced connection failure | High | Medium | Soldered connections, cable ties, regular inspection; pre-session checklist |
| Water/moisture ingress | Medium | High | IP54 enclosure, connector opening facing down, silicone gasket |
| Heat-induced failure | Medium | Medium | Mounting away from the exhaust, internal temperature monitoring |
| Ignition noise corrupting data | Medium | Medium | Shielded cable, filtering, engine on/off comparison test |
| Data loss (card failure, interruption) | Medium | Very high | CRC'd block structure, dual backup after each session |
| Accident/injury during testing | Low | Very high | Gradual approach, closed area, protective equipment, safety protocol |
| Motorcycle breakdown (project vehicle) | Low | High | Regular maintenance, no irreversible modifications |
| Schedule slip due to weather | High | Medium | T0/T1 tests weighted toward winter months, road tests scheduled flexibly |
| Dyno session cannot be scheduled | Medium | Medium | University lab alternative; otherwise settle for an uncertainty analysis, noted in the thesis |

---

## 16. Deliverables

At the end of this work plan, the following will be obtained:

1. A unit mounted on the vehicle, operational (removable)
2. CL250 signal definition file (vehicle definition for the HIL bench)
3. Measured vehicle parameter set (mass, CG, wheel radius, resistance coefficients)
4. Minimum 40 hours of labeled ride data
5. Virtual dynamometer torque/power curves and uncertainty analysis
6. Sprocket experiment sensitivity report
7. Dynamometer comparison report (if the session could be scheduled)
8. Graph of voice command recognition rate vs. speed
9. Eco profile consumption comparison result
10. Cornering safety module calibration data
11. Field test reports and video recordings
