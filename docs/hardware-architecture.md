# Hardware Architecture and Repository Structure — Decision Document

**Project:** Motorcycle embedded diagnostics, telemetry, and driver assistance platform
**Scope:** SDV-compatible vehicle hardware architecture, chip selections, HIL bench hardware, repository structure
**Version:** 1.0 — September 2026

> Translated from the Turkish original (`archive/tr/donanim-mimarisi-ve-repo-yapisi.md`). Where this document conflicts with `ARCHITECTURE.md` or `DECISIONS.md`, those take precedence.
>
> **Bus topology superseded (D-009, D-019, D-021, D-037).** This document predates the verified CL250 facts. The platform has **two classic 500 kbps CAN buses**: the vehicle bus (CL250 diagnostic connector), where rt-core is the single tester and reads ECU data by UDS polling with the requests allowed in `uds/vehicle_cl250.yaml` (`tester_policy`), and our own platform bus, where every other node talks. The topology is `ARCHITECTURE.md` §3. Use this document for subsystem rationale, not for the bus layout.

---

## 1. Architectural Philosophy

Modern SDV (software-defined vehicle) logic: a small number of powerful compute units + one safety monitor + as many edge nodes as needed. Avoids the old "one ECU per function" paradigm. New function = a software module on an existing unit, not new hardware.

**Core principle:** Real-time/safety-critical work and rich/compute-intensive work never share the same chip.
- Real-time, deterministic work → MCU (bare-metal/RTOS)
- Rich work that doesn't require determinism → Linux (Raspi)

---

## 2. Target Hardware Architecture (5 units)

> **Superseded in part by D-072/D-073 (2026-10-17).** The three STM32 units of this section became **one dual-core STM32H755** (NUCLEO-H755ZI-Q): the Cortex-M7 runs rt-core, the Cortex-M4 is the safety partition (cornering decision, own fallback IMU, blind spot, immobilizer, LED ring and mirror LEDs). The I/O node is retired; power management and park mode move to rt-core. A second ESP32-S3 sits in the helmet (HUD, microphone, voice, §5b.4a). Current unit table and topology: `ARCHITECTURE.md` §2-3. The text below is kept as the original rationale.

```
 VEHICLE CAN (CL250 DLC, classic 500 kbps) ══╤════════════════════
                                             │ rt-core = the single tester (UDS polling, D-021)
                                        ┌────┴───┐
                                        │STM32H7 │── SPI/UART ── ESP32-S3 (BLE/Wi-Fi, voice)
                                        │DOMAIN  │
                                        └────┬───┘
 PLATFORM CAN (ours, classic 500 kbps) ══════╧═══════╤══════════╤══════════╤═══
                                                ┌────┴───┐ ┌────┴───┐ ┌────┴───┐
                                                │STM32G4 │ │STM32G0 │ │ Raspi5 │
                                                │SAFETY  │ │I/O     │ │ LINUX  │
                                                └────────┘ └───┬────┘ └────────┘
                                                          actuators (lights, heating,
                                                          immobilizer, power)
```
Full diagram with interfaces: `ARCHITECTURE.md` §3.

| Unit | Chip | SDV role | Task |
|---|---|---|---|
| Main MCU | **STM32H7** (H743/H723) | Domain controller | CAN, telemetry, logging, fusion, maintenance tracking, coordination |
| Connectivity+voice | **ESP32-S3** | Auxiliary node | Wi-Fi/BLE, voice command (ESP-SR, D-044), server/phone sync |
| Safety | **STM32 G4/F3** (with FPU) | Safety monitor | Cornering safety warning, independent monitoring — isolated |
| I/O | **STM32 G0/F0** | Zone/edge | Actuators (lights, heating), immobilizer, power management |
| Linux | **Raspi 5** | HPC | Camera, image processing, heavy ML inference, HMI, maps |

**Decision (final):** The main MCU is **STM32H7**. The ESP32-S3 is not the main MCU — it is only the connectivity+voice auxiliary node. The work running on the main MCU (telemetry, logging, fusion, UDS/ISO-TP/bootloader, XCP, cornering EKF estimation, context classification (rt-core `context/`, D-008), virtual dynamometer computation, anomaly safety net) runs on **STM32H7**; the ESP32-S3 only handles Wi-Fi/BLE sync and voice command (ESP-SR wake word + fixed commands, D-044).

---

## 3. Standard Chip Selections (by task)

> Safety and I/O rows: superseded by D-072 (the safety class is the Cortex-M4 core of the STM32H755; no separate I/O chip). The AURIX/S32K note remains the production reference for a separate safety MCU.

| Role | Standard chip | Why this class |
|---|---|---|
| Domain (main) | STM32H7 (Cortex-M7, 480 MHz, FPU, DSP, CAN-FD) | Learnable equivalent of the automotive domain-controller class |
| Safety | STM32G4/F3 (FPU, deterministic) | Easy to learn; the real equivalent is AURIX/S32K (ASIL) → Phase 2 |
| I/O/edge | STM32G0/F0 (cheap, has CAN) | Edge node should be simple, not powerful |
| Connectivity+voice | ESP32-S3 (Wi-Fi/BLE, vector accelerator) | RF + offline voice (ESP-SR) on one chip; context classification is not here (D-008) |
| HPC | Raspi 5 | Real equivalent is an automotive SoC (S32G, NVIDIA); a learnable version |

---

## 4. CAN Connection Rules

- Two buses (D-009): the **vehicle bus** (OEM, reached through the DLC) and our own **platform bus**. Every MCU connects **directly, with its own transceiver**, to the platform bus (not through an intermediary/bridge) → eliminates inter-module latency
- CAN is a broadcast bus: every message is received by everyone simultaneously and deterministically (there is no such thing as "reception priority"; priority only applies to transmission arbitration)
- **Vehicle bus: exactly one tester, rt-core** (D-021). The CL250 ECU does not broadcast its data; it answers UDS read requests (D-019), so the tester must transmit. It sends only the read and session requests in `uds/vehicle_cl250.yaml` `tester_policy` (D-020), never anything that changes ECU state. No other node transmits there; the Raspi may tap it listen-only for raw logs
- **No extra termination resistor** is added in the vehicle (the vehicle is already terminated); on the bench, since its own bus is built there, termination is added there
- The Raspi connects to CAN via an MCP2515+transceiver or a CAN HAT (SocketCAN)

---

## 5. Real-Time / Latency Principle

Latency comes from the physical channel, not from repo/code partitioning.

| Channel | Between whom | Latency | Determinism |
|---|---|---|---|
| CAN | MCU ↔ vehicle | microseconds | High |
| SPI/UART bridge | MCU ↔ MCU/Raspi | µs-ms | Medium-high |
| BLE | phone ↔ ESP | 30-100+ ms | Low |
| WiFi | Raspi/phone ↔ server | 10-100+ ms | Low |

**Golden rule:** Critical work is never dependent on a slow/non-deterministic channel.
- Microsecond-critical (CAN warning, safety) → MCU + CAN, needs nothing else
- Millisecond-tolerant (HMI, camera) → Raspi, bridge
- Latency-indifferent (settings, reports, history) → phone BLE/WiFi

**Loose coupling:** Every unit does its core job without the others. If Linux crashes, the phone is gone, the bridge breaks → critical work continues. Raspi/phone add "richness," they are not "must-haves."

---

## 5b. Vehicle Subsystems

### 5b.0 Context Classification Layer (foundational layer — feeds the other models)

**Critical position:** Context classification is not a separate/independent feature but the **foundational layer** that conditions the rest of the system. All other ML models (anomaly, cornering, assistant, logging) are fed by this layer. That's why it is the first ML model to be built — it is both the easiest to label and the foundation for the others.

**Why central:** "Vibration that's normal at high RPM is abnormal at idle" — anomaly/warning models only work correctly if they know the context. Context tells the other models "which condition are we in right now"; they then check "what's normal/safe under this condition."

```
        IMU + CAN + GPS raw data
               │
       [CONTEXT CLASSIFICATION]  ← foundational layer
               │
    ┌──────┬───┼────────┬──────────┐
    ▼      ▼   ▼        ▼          ▼
 [Anomaly][Cornering][Assistant][Log freq.][Warning threshold]
 conditional threshold  behavior  setting        setting
```

**Sub-problems and their methods (from the literature):**

| Context | Input | Method | Weight | Where |
|---|---|---|---|---|
| Road type (urban/rural/highway) | CAN (speed, throttle, gear) + statistics | Classic ML / threshold | Light (~85%) | rt-core `context/` (H7) |
| Road surface (smooth/rough/cobblestone/dirt) | IMU vibration | 1D-CNN (TinyML) | Medium (~93%) | rt-core `context/` (H7) |
| Driving event (acceleration/braking/cornering) | IMU | Classic ML / 1D-CNN | Light | rt-core `context/` (H7) |
| Day/night | Light sensor / camera | Threshold / lightweight model | Very light | rt-core `context/` (H7) |
| Weather (dry/wet) | Surface vibration + temperature | Lightweight model | Light | rt-core `context/` (H7) |
| Traffic density | Speed variability + stop-and-go | Statistics | Very light | rt-core `context/` (H7) |

**Hardware:** Mostly achievable with existing hardware (IMU + CAN + GPS); Raspi is not required — inference runs in rt-core `context/` on the H7 (D-008). An optional light sensor for day/night (small addition).

**Labeling advantage:** Saying "I'm on the highway now / on a rough road" while riding is an easy and honest label — none of the dead-ends found in fault data. This is another reason it is the first ML model to be built.

**Generalizability warning:** The model must be tested on road/conditions it did not see during training. Shuffling all the data together and training on it gives "fake high accuracy" — it does not demonstrate generalization ability in an unknown context.

### 5b.0b Extended Conditioning Context Layer

The academic literature (context-aware ADAS) treats such systems in three categories — **driver, vehicle, environment** — and finds isolated single-feature approaches (only road, or only driver load) insufficient; the correct design treats all three as a whole. Under this triple framework, the factors that condition the system besides road context are:

**A) Vehicle state**

| Conditioner | What it affects | Source | Model or measurement |
|---|---|---|---|
| Mass / load (single-double rider, luggage) | Cornering limit, braking distance, torque need, virtual dynamometer | Acceleration-torque relationship | Estimation (EKF) |
| Thermal state (cold/operating temperature/overheating) | Anomaly threshold (a cold engine gives different vibration/sound) | Temperature sensor | Measurement |
| Tire pressure / wear | Rolling resistance, vibration signature, cornering grip | TPMS or indirect estimation | Measurement/estimation |
| Chain/mechanical tension | Vibration signature reference | Maintenance record + vibration | Measurement |
| Battery/power state | System reliability, transition to low-power mode | INA226 | Measurement |

**B) Driver state**

| Conditioner | What it affects | Source | Model or measurement |
|---|---|---|---|
| Driver identity | The definition of "normal" becomes person-specific (aggressive/cautious have different references) | Driving signature | **Model** (classification) |
| Fatigue / attention | Warning sensitivity, voice-assistant intervention frequency | Driving-irregularity pattern (IMU) | Model (already planned on K7) |
| Riding style (aggressive/calm) | Warning-threshold personalization, insurance/score | IMU + speed pattern | Model |

**C) Environment state**

| Conditioner | What it affects | Source | Model or measurement |
|---|---|---|---|
| Weather (dry/wet/cold) | Friction coefficient (µ), cornering limit, braking distance | Surface vibration + temperature + humidity | Lightweight model/measurement |
| Day/night | Dashboard brightness, LED sensitivity, camera mode | Light sensor | Measurement/threshold |
| Traffic density | Voice-assistant intervention frequency, warning prioritization | Speed variability, stop-and-go frequency | Statistics |
| Temporal (start/middle/end of ride) | Fatigue, engine warm-up phase, fuel depletion | Counter + sensor | Measurement |

**Only the ones that truly need a model:** road context (5b.0), driver identity, fatigue/attention, riding style, weather (µ estimation). The rest are measurement or physics estimation — not a separate ML model.

### 5b.0c Context Bus Architecture

Conditioners are not distributed one by one to individual models; they are collected on a common **context bus**, and each model reads what it needs from there. Adding a new conditioner does not change the existing models — it is simply added to the bus.

```
[Road context model] ──┐
[Driver identity model]─┤
[Fatigue/style model]───┤
[Mass/EKF estimation] ──┼→ [CONTEXT BUS] → read by the relevant models
[Thermal measurement] ──┤     (common shared state)
[Tire/mechanical] ──────┤
[Weather/µ] ────────────┤
[Day-night/traffic] ────┘
        │                          │
        ▼                          ▼
  [Anomaly detection]       [Cornering safety]
  (conditional normal)      (conditional threshold)
        │                          │
        ▼                          ▼
  [Voice assistant]           [Log frequency /
  (intervention frequency)     warning sensitivity]
```

**Thesis value:** "Context-aware driver assistance architecture" — an active research area in the literature, a holistic design that goes beyond isolated single-context approaches. Applying it to a motorcycle would be an original contribution.

---

### 5b.1 Blind Spot Monitoring System (BSM) — radar-based

Since it must work at reflex speed, deterministically, and independently, it is **MCU work** (not Raspi). Since the sensor and LED are at the rear/side, it is built as a separate I/O node — it doesn't burden the main unit and doesn't need long cables.

**Approved decisions:**
- **2 radars** (left + right, full side coverage)
- **24 GHz** mmWave radar (sufficient for blind spot; 60/77 GHz precision is unnecessary and more expensive)
- **LEDs must be readable even in morning sunlight** → high-brightness type, visible in direct sun; embedded inside the mirror
- **Not connected to the AI assistant** — reflex speed is required, LED is the correct interface, spoken words add latency/noise

**Processing node (D-072):** the **Cortex-M4 safety partition** of the STM32H755 reads the 2 radars on its own UARTs, runs the approach logic, drives the mirror LEDs and hands the status to the Cortex-M7, which broadcasts it on CAN. The decision is independent of the rt-core software, the Raspi and CAN, so the LED keeps working when rt-core crashes; a power or chip fault stops both (accepted, D-072 item 5). _(Original plan: the STM32F103 as a rear I/O node; retired.)_

**LED logic:**
- Green: side clear
- Solid red: a vehicle is present on that side
- Blinking red: a vehicle is approaching while signaling/changing lanes toward that side (signal info from CAN or a separate input)

**Sunlight readability:** High-brightness LED (high mcd), shaded/tunnel placement inside the mirror (so direct sun doesn't hit it), automatic brightness based on ambient light if needed.

**Communication:**
```
[24GHz Radar left] ─┐
                   ├→ [STM32F103 rear node] → [Mirror LED left/right]
[24GHz Radar right] ─┘         │ CAN (status broadcast)
                       ══════╪══════ PLATFORM CAN BUS (D-009)
                             │
                    [Main unit]   [HMI/Nextion]
```
- Radar → F103: analog/SPI/UART depending on module type
- F103 → LED: GPIO or WS2812 line
- F103 → CAN: blind-spot status (main unit logs it, HMI can display it)
- Signal info: from CAN or an input wired to the turn-signal lever

**Hardware:**

| Part | Role | Status | Estimate (TL) |
|---|---|---|---|
| STM32F103 | Rear I/O node | On hand | 0 |
| 24 GHz radar ×2 | Left+right side detection | To buy | 600-1600 |
| CAN transceiver | F103 → CAN | To buy | 80-150 |
| High-brightness LED (in-mirror) | Visual warning, readable in sunlight | To buy | 80-200 |
| Handlebar mirror (LED to be embedded) | — | Already to buy | — |
| Cable, connector, enclosure | Mounting | To buy | 150-300 |
| **Total** | | | **~910-2250** |

**Development direction:** (1) test/recognize radar standalone → (2) threshold + false-alarm logic (distinguishing a stationary object from an approaching vehicle — the heart of the system, thesis value) → (3) LED driving → (4) CAN integration → (5) signal integration → (6) road test and threshold tuning.

**Hardest part:** False-alarm filter — the radar also sees a guardrail, a parked vehicle, a pole. Telling apart a "genuinely approaching vehicle" requires speed+direction analysis.

---

### 5b.2 Cornering Safety Warning System — three-layer architecture (physics + EKF + ML)

A motorcycle-specific, safety-critical function. **The layers sit on different chips** — a deliberate isolation decision, not "software isolation" on a single chip.

**Three layers — which chip does which:**

```
Layer 1 — Deterministic decision (vehicle-safety-node, STM32 G4/F3, ISOLATED)
   Closed-form physics: in a steady turn tan(θ) = v²/(g·R) = F_y/N, so "no sliding" is tan θ ≤ µ (D-041).
   Speed and mass cancel; v_max = √(µ·g·R) is only a predictive (Layer 2/3) feature, not Layer 1.
   → Warning and LED triggering happen HERE. Works without the Raspi, phone, Wi-Fi, VSS and ML; without rt-core only in degraded mode (own-IMU fallback, D-042).
   → Its inputs are lean angle θ and µ_eff only, received from Layer 2 over CAN (D-041). Mass and vehicle speed are NOT safety-node inputs; the speed-age rules moved to rt-core.
   → Lateral only (Q-022): combined braking/acceleration in a curve is not checked yet.

Layer 2 — EKF estimation (vehicle-rt-core, STM32H7 — part of the context bus)
   µ (friction), mass, center-of-gravity height, lean angle — CLAMPED to physical ranges
   If out of range → falls back to a default safe value
   → Broadcast over CAN both to the safety-node and other consumers (dyno, display LED ring, lane tracking) — ONE computation, multiple uses

Layer 3 — ML adaptation (vehicle-rt-core, together with the context model, optional)
   Driver profile, road-surface context (from 5b.0) → tunes the threshold
   → Can NEVER loosen the safety CEILING, only fine-tunes on the conservative side
```

**Decision function (D-041).** Inputs: θ = `LEAN_ANGLE` (usable only with E2E status OK, `LEAN_ANGLE_STATE` ESTIMATED or CLAMPED, θ finite, |θ| ≤ 90°) and µ_eff = `FRICTION_COEFF` resolved by the D-029 rule (always finite, within [0.1, 1.2]). Two dimensionless thresholds k_yellow < k_red come from `limits/platform_limits.yaml`. The friction utilisation is u = tan|θ| / µ_eff: GREEN if u < k_yellow, YELLOW if k_yellow ≤ u < k_red, RED if u ≥ k_red, with level hysteresis/debounce. The implementation is division-free: GREEN only if sin|θ| < k_yellow·µ_eff·cos|θ|, YELLOW only if sin|θ| < k_red·µ_eff·cos|θ|, otherwise RED; any non-finite intermediate (NaN) gives RED. Threshold values are in the limits file, not in this document.

**Fallback IMU (D-042, resolves Q-002).** safety-node has its own minimal IMU (SPI). It uses its own speed-free lean estimate only when rt-core's lean is not usable (E2E status other than OK, state other than ESTIMATED/CLAMPED, or the rt-core heartbeat not OK / `NODE_MODE` ≠ NORMAL). In fallback, µ_eff = min(D-029 result, `friction_coeff_default`), the LED ring shows a distinct DEGRADED pattern and safety-node reports `NODE_MODE` = DEGRADED. If neither lean source is usable (boot, own-IMU fault) the ring shows UNAVAILABLE, never GREEN. Open details (cross-check against rt-core, whether the fallback may show GREEN before validation, IMU part, switching hysteresis, calibration): Q-023.

**Why closed-form + EKF, not PINN/heavy ML:** The cornering limit is solved in closed form (it has an analytical solution); training a neural network is unnecessary and **unexplainable** — "the network said so" is not defensible for a safety function. The grey box (parameter estimation with EKF) is both explainable and testable: when µ=0.62 comes out, it has physical meaning; a neural-network weight does not.

**Input data (Layer 2, in vehicle-rt-core):** IMU (lean angle, angular velocity), GPS (turn radius, speed), CAN (speed, acceleration). Lean angle is the EKF output, shared via the context bus (5b.0c) with the display LED ring (5b.4), lane-tracking correction (5b.5), and the safety-node alike.

**Lean estimator (D-065).** A 2-state EKF [roll, gyro bias] measuring roll from tan(roll) = v · yaw rate / g, in its own task above the comms task; wait-free triple buffers carry the speed (with its stamp) in and the lean out, and the comms pass sends 0x020. No usable speed (limits `vehicle_speed`) or no converged filter → INVALID (there is no default lean, D-029); the CLAMPED range is a defs limit. The EKF's alive supervision makes rt-core's heartbeat DEGRADED (D-064 item 4).

**Output — two channels:**
- **Round LED ring** (either side of the gauge, defined in 5b.4, driven by the Cortex-M4 safety partition, `vehicle-safety-node` (Q-026 resolved by D-072); never by rt-core, D-042): green→yellow→red, instantaneous lean state; DEGRADED / UNAVAILABLE patterns per D-042
- **Audio/HMI warning** (if the threshold is exceeded): on the main-screen profile (visible in the "sport" profile) + if needed, a fixed warning phrase from the voice command system (5b.6)

**Calibration and field testing:** T4-class tests from the vehicle work plan (section 7) — closed area, gradual speed increase, **aimed not at approaching the limit but at validating the model's consistency.** The actual tip-over/slide limit is never reached.

**HIL validation:** Tested on `vehicle-hil-bench` with fixed-radius+variable-speed scenarios — the expected warning point is computed and compared against the actual trigger point (see the vehicle work plan, section 8 test scenarios).

**Hardware:** `vehicle-safety-node` gets its own small IMU (SPI) as the fallback source (D-042; the part is chosen with the Group 7 hardware, Q-023). The rt-core IMU/GPS/CAN infrastructure feeds Layer 2 as before. _The earlier "no additional hardware" statement is outdated (D-042)._ Software effort: 60-100 hours, already in the scope list.

---

### 5b.3 I/O Node — Immobilizer + Park Mode/Tracking + Power Board (combined)

> **Superseded in part by D-072:** there is no separate I/O node. The immobilizer runs on the Cortex-M4 safety partition (rules below unchanged, invariant 6); park mode and the power-board logic run on the Cortex-M7 (rt-core).

_Superseded by D-072: the immobilizer and the blind-spot system run on the Cortex-M4 safety partition of the STM32H755 (`vehicle-safety-node`); `vehicle-io-node` is retired._ Originally: runs on the same physical node (`vehicle-io-node`, STM32 G0/F0) together with the blind-spot system — SDV zone-controller logic: few nodes, many modules.

**Immobilizer:**
- Intervention point: **starter relay coil circuit** (low current, non-functional while the engine runs — can never cut off a moving engine). The ignition/fuel-pump/ECU line is NEVER touched.
- **Bistable (latching) relay** — draws no power while parked, only pulls a short pulse when changing state
- **Fail-safe:** default position is open (a dead system lets the engine start) + a hidden mechanical bypass switch + revert to the open position after a 10 s decision timeout
- **Authorization:** NFC (PN532) primary (readable with gloves), PIN via the handlebar as backup. Fingerprint is not used (unreliable with gloves/moisture)

**Park mode / theft tracking:**
- IMU wake-on-motion deep sleep → wakes on detected movement (target sleep current < 1 mA)
- Notification: Wi-Fi preferred (in home range, free) — if this node has no Wi-Fi of its own, it notifies `vehicle-connectivity-node` (ESP32-S3) over CAN, which sends the notification
- Optional extension: a separate, hidden-mounted, self-powered GSM tracking module (works even if the line is cut) — separate sub-hardware, not integrated into this node
- False-alarm filter: threshold + duration + motion character (3-layer, same discipline as blind spot)

**Power board (separate physical board, subframe/tail-mounted, provides common supply to the units):**
- Input: fuse, reverse-polarity protection (P-MOSFET), TVS diode, LC filter
- Regulation: wide-input buck (6-40V→5V, 2-3A)
- **Supercapacitor buffer** — 3-10 s of energy when ignition is cut, enough to safely close the log file (matches the PWR-02 scenario in HIL)
- Monitoring: INA226 (voltage/current/power)
- Ignition switching: switch to a low-power mode at low voltage (<12.2V)

**Hardware (additional, on top of the blind-spot list):**

| Part | Role | Estimate (TL) |
|---|---|---|
| Bistable relay | Starter-circuit lockout | 80-200 |
| NFC reader (PN532) | Authorization | 100-250 |
| Supercapacitor set + balancing | Safe shutdown | 150-300 |
| Buck + protection (TVS, reverse polarity, fuse) | Power board | 300-550 |
| INA226 | Power monitoring | 100-300 |
| Hidden mechanical bypass switch | Fail-safe | 50-100 |
| **Total (additional)** | | **~780-1700** |

**References (verified through research):**
- **motogadget mo.lock NFC** — a commercial product, same principle as our design: contactless NFC, switching via relay (up to 40A), battery-free passive tag, can be hidden mounted behind a plastic panel. Common in the custom-motorcycle world — shows the design rests on a market-proven architecture.
- **Hackster.io "Start Your [ANYTHING] with NFC"** — open source, directly adaptable: bistable relay + 2-pin on/off control; the rationale for using a regulator so the MCU doesn't unexpectedly shut down during the starter's momentary voltage drop independently validates our power-board/supercapacitor decision.
- **Honda immobilizer patent (US7855470)** — a real manufacturer architecture: the power line and the "engine-stop relay" line are kept SEPARATE (no single-point cutoff), a passive transponder in the key. Consistent with our "coil circuit separate, non-functional while running" principle.
- **Forum discussion (ISO 26262 context)** — a warning aimed at someone adding their own immobilizer: risk of an added failure point, an emphasis that real immobilizers are tested to work even at low battery voltage (cold start) → the low-voltage scenario should be added to the HARA.
- **Megamos chip vulnerability (Wikipedia, immobiliser)** — a widely used immobilizer chip was proven cryptographically breakable; instead of a simple UID-reading NFC, a cryptographically authenticated tag (e.g. MIFARE DESFire) could be considered later (Phase 2, clone resistance).

**Process proposal:** (1) diagnose the starter relay coil circuit → (2) bench-test the bistable relay → (3) power board (regulator+supercapacitor) → (4) NFC read/authentication software → (5) fail-safe logic (default open + bypass + timeout) → (6) add low-voltage/sudden-cutoff/wrong-key scenarios to the HARA.

---

### 5b.4 Display and Visual Warning Architecture

**General principle — one info screen, multiple light indicators:** Placing two separate physical info screens (e.g. "engineer view" + "media view") side by side adds the burden of deciding which screen to look at while riding (cognitive load, increased scan time). Real racing dashboards (MoTeC, AIM) resolve this distinction as **pages/profiles on one screen**, switched with a physical button — not touch. This project follows the same pattern.

**Refresh-rate clarity (validated by research):** The "screen lag" complaints about real racing dashboards do not come from the screen's own refresh rate but from the **CAN data broadcast frequency** (at 100 Hz broadcast there is no perceptible lag; 20 Hz is enough for display; the problem shows up with low-frequency OBD2 polling). The Nextion's refresh rate is hundreds of Hz; the bottleneck is how often the firmware pushes data to the serial port. The existing Nextion hardware is sufficient on this front — the "doesn't meet the standard" worry is technically unfounded.

**Screen/display inventory:**

| Location | Hardware | Role | Connection | Note |
|---|---|---|---|---|
| Original Honda round gauge | — | Mandatory info (speed, fuel, fault lamp) | — | **Untouched** — legal/warranty |
| Between handlebar and tank | **1× Nextion** (existing hardware) | Main info screen — profile-based pages | UART → main MCU (H7) | Critical, works even if Linux/Raspi crashes |
| Left of the gauge | Round **LED ring** (WS2812, circular) | Left lean-angle indicator | M4 safety partition (D-072) | NOT a graphic display — see rationale |
| Right of the gauge | Round **LED ring** (WS2812, circular) | Right lean-angle indicator | M4 safety partition (D-072) | Same |
| Mirror ends (left/right) | LED (defined in 5b.1) | Blind-spot warning | M4 safety partition (D-072) | Not a screen; compensated by lean angle (see below) |
| Above/beside the main screen (optional) | RGB LED strip (WS2812) | Shift-light (green→red as RPM rises) | Main MCU | Same driver technology, low added cost |
| Phone | — | Remote interface (settings, history, reports) | BLE/WiFi → `vehicle-connectivity-node` | Not involved in critical work, loosely coupled |

**Profile-based page system:** Instead of separate "engineer view" and "media view" screens, the existing assistant-profile mechanism (section 9, vehicle-telemetri) is extended:

| Profile | Shown on the main screen |
|---|---|
| City | Speed, gear, fuel, fault lamp, blind-spot status |
| Touring | Range, consumption, gear recommendation, fuel warning |
| Sport ("engineer view") | RPM + shift-light, numeric lean angle, lap/segment time, driving score — raw/detailed data |
| Eco | Instant/average consumption, throttle coaching |
| Media | Spotify/Google Maps, voice-assistant feedback (song name, command confirmation, direction arrow) |

**Page/profile switching:** A physical button on the handlebar (racing standard — MoTeC/AIM 3 programmable pages, switched by button). NO touch/menu navigation — it would break riding comfort.

**Lean-angle indicator — why an LED ring, not a graphic display:**
- Commercial reference **KurvX** (X-Log): a handlebar-mounted device that measures lean with an accelerometer and gives a **LED flash** once a threshold is exceeded (no graphic display) — flash rate increases with lean, stays solid at an unsafe level.
- Patent reference: the lean-angle indicator is designed as **colored ring segments** (green→yellow→orange→dark orange→red) that light up according to safety level — matches the "oOo" visual concept one to one.
- **Human-factors rationale:** During cornering, peripheral vision instantly perceives a *color*; reading a *graph/number* requires fixating and interpreting with the eye. An LED ring is read faster than a fully graphic round display, is cheaper, draws less power, and needs simpler software (no graphics engine required).
- **Decision:** Position and function are kept (on either side of the gauge, "oOo" look), but the implementation is a **round WS2812 LED ring** — not a TFT/OLED round display.

**Lean-angle compensation of the blind-spot LED (point of originality):** Research shows that motorcycle blind-spot systems generally do not compensate for lean angle, and that this is a known shortcoming (the area visible in the mirror changes with lean). Since the system already produces lean angle from the EKF (context bus, 5b.0c), the blind-spot distance threshold can be slightly adjusted based on lean angle — a difference most competing systems lack, a point of originality for the thesis.

**Rule:** The Nextion is directly connected to the H7, works even if Linux/Raspi crashes. The LED rings and mirror LEDs are driven by the M4 safety partition, the shift-light by the M7 (D-072) — no heavy processing required. The helmet HUD (§5b.4a) only repeats warnings. The phone is never involved in any critical work.

**Phase 2 note (upgrade reference, not done now):** If switching from Nextion to LVGL+ESP32/round display is wanted, open-source references: `dev-ale/moto2000` (ESP32-S3 AMOLED round, BLE, phone-side logic, ~₺1250-1450 BOM, IP67 PG7 cable gland + silicone O-ring mounting), `emdzej/opencluster` (ESP32+LVGL, multi-screen over CAN, desktop simulator), `barcu00/DIY-dash-5` (ESP32-S3, table-based CAN decoder, UI-isolated architecture), `hpeyerl/evj55-dashboard` (large panel → Raspi/Linux framebuffer LVGL, the boundary where ESP32 falls short).

**IP67 mounting note:** An O-ring is more reliable for sealing than complex face-to-face gaskets; a low-hardness silicone gasket accommodates surface irregularities; the enclosure body must be rigid (a flexing body can bend the gasket and leak). Commercial motorcycle displays standardly use IP67 + 700-1000 nit brightness + glove-compatible capacitive touch — the Nextion enclosure should be 3D-printed to meet these three criteria.

---

### 5b.4a Helmet Unit — Visor HUD, Microphone and Voice (D-073, 2026-10-17)

**What it is:** a monocular head-up display at a fixed spot at the lower edge of the visor, fed over BLE by the bike ESP32. It is **not world-registered AR**: no head tracking, no overlay on the road scene. It repeats warnings and shows a few values so the rider does not look down. It replaces the "visor HUD PoC" line of the old Group 0 list.

**Hardware (helmet ESP32-S3, `vehicle-connectivity-node` helmet env):**

| Part | Role | Stage |
|---|---|---|
| ESP32-S3 N16R8 | HUD, BLE central, ESP-SR voice (PSRAM, Q-024) | H0 |
| 0.96" SSD1306 OLED | desk stand-in for the display | H0 |
| 0.39"/0.49" micro-OLED + combiner/beam-splitter prism + small lens | the visor image, focused far so the eye does not refocus | H1 |
| INMP441 I2S microphone | voice command (D-044, moved into the helmet) | H0 |
| MAX98357A I2S amplifier + small 8 Ω speaker (or the rider's intercom) | short voice prompts | H1 |
| Push-to-talk button | voice trigger (D-047); helmet or handlebar (Q-032) | H0 |
| LiPo 1000-2000 mAh with protection PCB + USB-C charger, slide switch | power | H1 |
| Clip-on housing (3D printed, PETG/ASA) | chin or side mount | H1 |

**Content (proposal; the final set and budget are Q-032):** in priority order: (1) cornering warning level as colour/blink, only YELLOW, RED, DEGRADED and UNAVAILABLE (GREEN and the mirror's "side clear" are never shown); (2) blind-spot side when a vehicle is present; (3) engine/anomaly warning icon; (4) speed, gear once known (Q-031), RPM bar; (5) link/health marker. The HUD never shows a "safe" state: on link loss or stale data it shows a distinct marker, and no warning on the HUD means nothing.

**Data path:** platform CAN → bike ESP32 → BLE notification → helmet ESP32 → display. The frame layout is defined in `vehicle-defs` `ble/` through `/signal-change` before any code; it carries only values that exist on the platform bus. Telemetry at most 10 Hz; warnings are sent on change and repeated while active.

**Rules:**
- **Informational only** (D-041 item 2, invariant 4). The wired LED ring and mirror LEDs driven by the M4 safety partition stay the safety output; BLE can drop.
- **Helmet integrity:** never drill, cut or glue the shell, the EPS liner or the visor (ECE 22.06 approval). The unit clips on and comes off without tools.
- **Glanceable:** few symbols, no text paragraphs, no animation, automatic brightness, short voice prompts.

**Stages (each ends with a measured result):**
1. **H0 desk:** helmet ESP32 + 0.96" OLED, BLE from the bike ESP32 → end-to-end latency (platform frame → pixel), packet loss.
2. **H1 helmet mock-up:** micro-OLED + prism on a clip-on housing → daylight readability, focus/eye strain, battery life, weight.
3. **H2 parked on the bike:** BLE range around the rider's body, interference with the bike ESP32's other links, rider check of the symbol set.
4. **H3 low-speed ride:** distraction check, warning latency in use.

**Risks:** daylight brightness of a micro-OLED through a combiner, visor fogging and tint, LiPo in cold or hot weather, helmet weight and balance, BLE shadowing by the rider's head, rider distraction. Open items: Q-032.


### 5b.5 Lane Tracking / Lane Departure Warning (LDW) System — camera + IMU based

Runs on the Raspi 5 (image processing is not MCU work). Motorcycle-specific critical difference: **lean angle rotates the camera image**, so a car LDW algorithm cannot be copied directly — IMU correction is required.

**Key finding from the literature:** For estimating the motorcycle's own heading, **direct lean-angle measurement** performs better than classifying the riding pattern. This is your advantage — you're already producing lean angle via EKF for the cornering safety module (context bus, 5b.0c); the same data is used here too, no separate computation needed.

**Classic open-source pipeline (OpenCV, no deep learning needed — runs comfortably on Raspi 5):**

1. Camera calibration — correcting lens distortion (with a checkerboard pattern)
2. Color + gradient thresholding — HLS color space (S channel, robust under varying lighting) + Sobel filter
3. Perspective transform — bird's-eye view (lane lines become parallel, reducing computation)
4. Lane-pixel tracking + curve fitting
5. Vehicle/lane center-position calculation

Reference (open source, directly inspectable): JunshengFu/driving-lane-departure-warning, RACRAMES/Lane-Departure-Warning-LDW-System (GitHub, OpenCV-based, implementing this pipeline step by step).

**Motorcycle-specific correction (logic of a patented method, adaptable open source):**

1. The distance between the camera's optical axis and the lane line is measured
2. The distance is **corrected based on yaw/lean angle** (compensating for image shift during turning/leaning)
3. The corrected distance is converted into the actual distance from the front wheel to the lane line
4. Warning if the threshold is exceeded (example in practice: a threshold of a few cm, automatic clear after a few seconds)

**Signal logic:** Consistent with the blind-spot system — the warning is suppressed while signaling (a deliberate lane change). Signal info is read from CAN, no separate integration needed.

**Wide-angle lens note:** A cheap/wide-angle camera magnifies the distortion problem (also separately addressed in the literature — requires vanishing-point estimation + correction based on lens characteristics). A standard-angle camera should be preferred where possible; if a wide-angle one is used, an extra distortion-correction step must be added.

**Motorcycle-specific threshold difference:** In natural riding, a motorcycle moves laterally more than a car does (balance/riding behavior) — the threshold should be looser than a car LDW's, otherwise the false-alarm rate will be high.

**Architecture:**
```
[Raspi 5 Camera] → distortion correction → color/gradient thresholding
                                              → bird's-eye transform
                                              → lane detection + curve fitting
                                                        │
[Context bus: EKF lean/yaw angle] ─────────────────────→ [Correction]
                                                        │
                                              [Lane-center distance]
                                                        │
                                    [Threshold + signal state] ← signal info from CAN
                                                        │
                                              [Warning: HMI/LED/audio]
```

Note: Lean angle is read from the context bus (5b.0c) — sharing the same source as the cornering safety module, not a separate island.

**Hardware:**

| Part | Role | Status | Note |
|---|---|---|---|
| Raspi 5 | Processing (OpenCV pipeline) | Already planned | No additional cost |
| Raspi Camera Module | Imaging | To buy | Standard angle preferred; if wide-angle, extra distortion-correction work |
| Camera mount (front, vibration-isolated) | Fixed angle | To buy | Vibration → risk of false lane detection |

**Development order:** (1) adapt the classic OpenCV pipeline from reference projects and run it on static images → (2) calibrate the bird's-eye view + curve fitting to the motorcycle's camera angle → (3) integrate IMU lean/yaw correction → (4) threshold + signal logic → (5) tune the motorcycle-specific false-alarm threshold with road testing.

**Reference/open-source list:** JunshengFu/driving-lane-departure-warning (GitHub), RACRAMES/Lane-Departure-Warning-LDW-System (GitHub), Bosch LDW technical description (reference for system behavior — ~60-100m detection, signal-suppression logic).

**Method decision — classic CV vs. deep learning (validated by research):**

| | Classic CV (SELECTED) | Deep learning (UFLD-style, Phase 2 note) |
|---|---|---|
| Training data | **Not needed** — algorithmic | Required (fine-tuning) |
| Speed | Comfortable on the Raspi 5 CPU | 3-6ms on GPU; borderline on the Raspi CPU without an accelerator |
| Robustness in hard scenes | Medium (struggles with shadow, faint lines, night) | High (CULane covers night/crowded/lineless scenarios) |
| Domain gap | None — it doesn't learn | Exists — TuSimple/CULane trained on car-hood-fixed-upright-angle data; doesn't transfer directly to a leaning motorcycle camera (the same category of problem as the domain gap in CWRU bearing data / engine-sound analysis) |

**Decision:** The classic CV method is used. Rationale: zero data-collection burden (the project's data budget is already shared among context classification, fault detection, voice command), runs on the Raspi 5 CPU without an accelerator, open-source references are directly adaptable. Deep learning (UFLD, Fast-CenLaneNet) can be evaluated in Phase 2 if higher robustness is desired — but it requires fine-tuning with the motorcycle's own data (~5-10 hours of varied road/weather/night data + labeling).

**Data collection requirement: NONE.** Unlike the project's other ML modules (context classification, fault detection, voice command), this subsystem needs no training data — the algorithm computes, it does not learn.

---

### 5b.6 Voice Command System (offline, rural-resilient)

**Decision:** Espressif's official **ESP-SR** framework is used — no custom model training is needed.

| Component | Technology | Note |
|---|---|---|
| Trigger | Push-to-talk (handlebar button), primary; ESP-SR wake word optional and configurable (D-047) | Push-to-talk eliminates false triggering in wind noise; the wake word's default and enabling conditions are open (Q-024) |
| Command recognition | **ESP-SR MultiNet** | Up to 300 words, **requires no retraining**, ready-made |
| Audio preprocessing | ESP-SR Audio Front-end (AEC, VAD, noise suppression) | First line of defense against wind/engine noise |
| Hardware | Helmet I2S microphone on the **helmet ESP32-S3** (`vehicle-connectivity-node` helmet env, D-044, D-073) | The engine sound uses a separate engine-facing microphone on linux-node (D-044, see 5b.9). After the trigger (button or wake word, D-047), speech for the LLM path goes to the Raspi; transport open, Q-024 (also whether the ESP32-S3 module has the PSRAM ESP-SR expects) |
| Location | **helmet ESP32-S3** (`vehicle-connectivity-node`, D-073) | Vector accelerator lives here; moving it to the Raspi adds unnecessary bridge latency |
| Reference | ESP-SR (espressif/esp-sr, GitHub) — WakeNet (~80ms, <2% false positive), MultiNet | Official Espressif framework |

**Latency:** ~100-200ms, fully offline, no connectivity required — works in rural areas.

**Note (TinyML claim):** Using ready-made ESP-SR is technically TinyML, but the model isn't trained, it's integrated. The project's "own trained model" TinyML claim is fulfilled by the context classification model (5b.0); here speed/reliability is the priority.

---

### 5b.7 Vehicle-MCP — Context-Grounded In-Ride LLM Assistant

**Architecture — two layers, two latency profiles:**

```
WHILE RIDING (connectivity AVAILABLE)
  Helmet microphone (connectivity-node, ESP-SR) → speech after the trigger (D-047) → Raspi 5 (VAD; transport open, Q-024, D-044) → ~internet (phone hotspot)
      → Cloud Realtime API (streaming STT+LLM+TTS) → ~2 s → helmet speaker
  While generating the answer, the LLM calls vehicle-mcp tools (tool call)

WHILE RIDING (connectivity UNAVAILABLE — rural fallback)
  → the 5b.6 closed-vocabulary system takes over (offline, ~100-200ms)

AT HOME/AFTERWARDS (demo, bonus)
  Claude Desktop / any MCP client → vehicle-mcp (remote)
      → queries like "how was my ride yesterday"
```

**Core principle (validated by the OVMS project's warning):** The LLM does not do its own math — it only translates an **already-computed result** into natural language. Having it interpret a raw numeric series is unreliable, and the LLM can produce a wrong result without telling the user (OVMS project: "current AI tools produce confident-but-wrong results without disclosing their limitations").

**Tool list — the natural API of existing subsystems:**

| Tool | Returns | Source |
|---|---|---|
| `get_live_snapshot()` | Instant speed, RPM, engine temperature, lean angle, tire temperature, voltage | Context bus (5b.0c) |
| `get_recent_stats(window_s)` | Max/avg/trend over the last N seconds | Ring buffer |
| `get_event_log(count)` | Recent events (anomaly, hard lean/braking, blind spot, mode change) | Event log |
| `get_anomaly_status()` | Anomaly score/classification | Anomaly-model output (not a separate model — a consumer of the existing output) |
| `get_maintenance_status()` | Engine-hour-based maintenance status | Maintenance-tracking module |
| `query_ride_history(date_range)` | Historical ride summaries | `vehicle-server` (tool call, extra latency) |

**Wiring:** In the MVP, a local bridge — `vehicle-linux-node` on the Raspi calls `vehicle-mcp` locally (localhost), adds the result as context to the cloud LLM; the cloud never connects directly to the vehicle. In home-demo mode, `vehicle-mcp` can be exposed externally as a real (authenticated) MCP server — clients like Claude Desktop can then query things like "tell me about my ride yesterday."

**Privacy and encryption (updated — result of discussion):**

- **General context packet:** Raw GPS coordinates are never sent to the cloud LLM/context packet; instead, a locally computed, irreversible summary goes out (e.g. "rural area," "12 km from home," "known route") — a natural extension of the offline map cache (5b.8). Such summaries need a position, which in Phase 0 only conn has (D-060 item 3); where they could be computed is open (Q-028).
- **Special calls requiring coordinates (navigation, etc.):** superseded by invariant 7 and D-060 item 3: latitude and longitude never leave conn, so no tool call carries coordinates. For location-independent questions like "how did I ride today," GPS never goes to the LLM at all.
- **Encryption — used in the right place, not in general context transmission:** HTTPS/TLS already exists on every cloud API call (nothing extra needed). Encryption's real added value is in two places: (1) `vehicle-mcp`'s "home demo" externally-exposed mode — TLS + authentication (API key/token) mandatory, protects all telemetry (not just GPS); (2) historical GPS data stored on `vehicle-server` — storage-level encryption (disk/DB level), preventing easy reading of location history on physical access.
- **Note:** This decision may change later (once the real usage/threat model is clearer) — this is the default for now. The assistant type (templates, a local LLM or this cloud path) and what may reach a cloud LLM are open as Q-028.

**Additional sensors (added to the core for this subsystem + the anomaly model):**

| Sensor | Purpose | Cost |
|---|---|---|
| IR tire/brake temperature sensor | Real measurement (no need to estimate) | 150-350 TL |
| EGT (exhaust gas temperature) | Engine health, combustion quality | 300-600 TL |

**Repo:** `vehicle-mcp` — **an independent open-source repo** (see section 8, exception rationale). Even though it runs on the same Raspi 5, it is kept separate for sharing/showcase purposes.

**References (verified through research):**
- **Mater** (Vasu1712/mater) — a separation of Redis "hot path" (live) and TimescaleDB "cold path" (history), a single MCP tool layer, two LLM agents (driver voice / owner chat). A direct reference for this project's live/historical data separation.
- **car-ai** (iqureshi123/car-ai) — shows that under the Raspi 5 (no GPU) constraint, the smallest model supporting tool-calling is llama3.2:3b (Q4_K_M, ~2GB); the "telemetry = location data, must not leave the vehicle" privacy rationale.
- **OVMS** (openvehicles/Open-Vehicle-Monitoring-System-3) — the warning that LLMs learn patterns rather than reasoning, and that current AI tools produce confidently-wrong results without disclosing their limitations → the rationale for the "the LLM must not do its own math" rule.
- **Connected-Car-AI-Support-Agent** — the operator-approval-gate pattern (ISO 26262 compliance) before actuator/OTA operations — not applied for now since this project is read-only, a reference for if actuators are added later.

**Phase 2 — Actuator-LLM Connection (write capability, approval-gated):** Currently, all Vehicle-MCP tools are read-only. In Phase 2, the LLM could be given the authority to trigger **only the peripheral actuators we ourselves added** (lights, heated-grip control, camera trigger — F17 class, not touching engine control). It will never be extended to engine/ECU control. Every write call passes through an **operator approval gate**, as in the Connected-Car-AI-Support-Agent pattern (no actuator triggers without voice/HMI confirmation) — the LLM directly changing something is a categorically different risk class from it performing a read, and that distinction is preserved. Pending Q-027: until it is decided, vehicle-mcp stays read-only (ARCHITECTURE).

---

### 5b.8 Linux Node — SDV Layer and Extended Roles

**Purpose:** Move `vehicle-linux-node` from a self-invented architecture to the standard structure of the Eclipse SDV ecosystem (a joint Bosch/BMW/Microsoft development).

**Layered architecture:**

| Layer | Technology | Role |
|---|---|---|
| Signal broker | **Kuksa Databroker** (Docker container) | Single source of truth, VSS semantic model — no application touches CAN directly |
| CAN bridge | **Eclipse kuksa-can-provider** (D-004; `vehicle-linux-node` `docker-compose.yml`) | CAN → VSS translation from `platform.dbc` + the generated `gen/vss/vss_dbc.json` (`dbc2vss` keys of the VSS overlay); receive-only, nothing self-written |
| Application framework | Velocitas SDK (Phase 2) | Each function (lane tracking, vehicle-mcp, HMI) is a "Vehicle App" |
| Communication | gRPC (local) + MQTT (cloud/`vehicle-server`) | Standard protocols |
| Container/OTA management | Eclipse Kanto (Phase 2) | Simple process in the MVP, moves to containers with maturity |

**Reference hardware:** Eclipse Kuksa CANOpi — a Raspi CM4-based, dual CAN-FD interface, OBD-powered official SDV prototyping board. The professional/automotive-grade counterpart of your MCP2515/CAN HAT setup.

**Fleet Management reference:** Eclipse's official end-to-end demo — Databroker → Zenoh → InfluxDB+Grafana in the cloud. `vehicle-server` follows this pattern.

**Capacity note (Raspi 5 8GB, rough budget):** Lane tracking (medium), Kuksa+CAN bridge (low), rich acoustic anomaly analysis (**the biggest new load** — should be run with periodic window analysis, not continuously at full rate), video encode (hardware-accelerated, low), HMI (low-medium), Kanto (medium extra load — **deferred in the MVP**). With these settings the total load stays within the Raspi 5's capacity.

**Extended role list:**

| Role | Description | Priority |
|---|---|---|
| Offline map cache | OSM extract local, navigation works without internet in rural areas | High — consistent with rural priority |
| Ride video + telemetry overlay | Combining camera + telemetry into clips of anomaly/blind-spot moments | High — high thesis/portfolio value, low added cost |
| Multi-ride summary report | Weekly/monthly km, consumption, score — from existing data, zero new data | High |
| MCU firmware distribution center | Download from `vehicle-server` and distribute to MCUs via CAN/UDS bootloader | Medium — natural Linux-side counterpart of the bootloader work |
| Node health panel | Heartbeat/status of all MCUs on one screen | Medium — the on-vehicle live counterpart of the HIL test report |
| Data preprocessing pipeline | Windowing raw data in the vehicle and extracting features, reducing server load | Medium |
| Event-based "black box" recorder | Storing a few seconds before/after an anomaly/crash at full resolution across all modalities, in separate storage | Medium — strong for the thesis, small footprint |
| Lightweight local time-series DB (SQLite/DuckDB) | Last few days of data locally, instead of a full InfluxDB | Medium |
| XCP/A2L host tool | Simple host/log viewer for the calibration interface (F18) | Low — if F18 is implemented |
| NTP time server | Distributes GPS time to the other MCUs | Low — resolves the open time-synchronization decision |
| Edge analytics buffer | Send summaries when connectivity is weak, complete the full data later | Low — a partial/conditional solution |
| Remote development access | Log/status checks over SSH | Low — developer convenience |
| DoIP gateway | Carrying UDS over Ethernet (next-gen diagnostic protocol) | **Phase 2** — not directly related to the rural priority, a CV/interview note |

**CI/CD vs. OTA separation (clarification):** CI/CD itself (build, automated test, HIL regression) runs on **the i7 desktop** (HIL host, section 9b) — it is not moved to the Raspi. OTA **distribution** (downloading new firmware and writing it to MCUs via the UDS bootloader) stays on the Raspi, but without Kanto — via a simple Linux service — light work, no container orchestration needed.

**Hardware inventory (corrected):** The user has a **Raspi 5 8GB** (in the vehicle, main Linux node) and a **Raspi 3B+** (1GB RAM, weak — the Pi 4 8GB from the for-sale listing will not be bought, that was an earlier mix-up). The 3B+ is not given the role of a second full Linux node in the vehicle (insufficient for CV/ML, the HIL host is already the i7). No role is forced onto it; two light options: (a) the display/UI end of the HIL control panel (the i7 does the heavy lifting, the 3B+ just shows the panel), (b) an unassigned spare for now — deployed later if a simple need arises (second NTP source, log collector).

**Raspi 5 power, heat, and placement (must be handled separately from the MCUs):**

- **A separate power line is mandatory.** The Raspi 5 draws 3-5W idle, 8-15W under load (camera+CV+voice model) — far above the MCU power budget (5b.3, 2-3A). The Raspi gets its own regulator and line, **isolated** from the rail shared by the MCUs (H7, safety, I/O). Rationale: a sudden load spike on the Raspi could cause a voltage dip on a shared rail, which could reset the safety MCU — a safety-critical node must not be affected by the Raspi's power fluctuations.
- **Mechanical/electrical power source:** From the vehicle battery/alternator, with its own regulator (not a separate mechanical generator) — same source as the MCUs, separate circuit. Whether the alternator's capacity covers the added load (a few watts) should be verified (from the service manual, see section 5b.3).
- **Thermal management — an overlooked risk in an IP67 enclosure:** A sealed enclosure also traps heat; under load (camera+CV+voice at the same time) the Raspi 5 can heat up and throttle in hot weather. Solution: a passive heatsink + a waterproof but breathable membrane (a pressure-equalization valve, common in IP67 electronics enclosures) or a large-surface passive cooling block. Should be considered together with the power-board design — hard to add afterward.
- **Chassis placement:** The MCU needs more volume than the power board. Suggestions: under the seat (if there's enough clearance, away from heat sources) or a side-panel/fairing cavity (may be limited in the CL250's scrambler body, needs checking). Must be kept away from the engine block and the exhaust.
- **New PCB difficulty (accepted risk):** A separate power/carrier board for the Raspi 5 (isolated regulator, protection, thermal management) is a real design-build-test cycle. Kept simple with perfboard/off-the-shelf power modules in the first round, printed once the design settles (see section 6, module/chip staging).

---

### 5b.9 Anomaly Detection Model — Unified Model Architecture (Raspi) + rt-core Safety Net

**Data schema:**

| Modality | Signal | Sampling | Captures |
|---|---|---|---|
| CAN | RPM, TPS, engine temperature, MAP, fuel trim, battery voltage, wheel speed (if available) | 1-20 Hz | Slow faults (filter, leak, sensor drift) |
| Engine-block accelerometer (vibration) | 3-axis acceleration on rt-core (SPI + DMA), high frequency; features → platform CAN at ≤ 10 Hz → Raspi / VSS; raw → rt-core log only (D-044; feature set, part and rate: Q-025) | 1000+ Hz | Mechanical: imbalance, looseness, misfire |
| Acoustic | Engine-facing microphone on linux-node (separate from the helmet microphone) → MFCC/spectral features, local (D-044) | Per audio frame | General engine health, combustion quality |
| Thermal | Engine temperature, EGT, ambient | 0.1-1 Hz | Combustion quality, overheating |
| Context (conditioning) | From the context bus: load, weather, riding mode | Event-based | "What's normal under this condition" |

**Fusion decision — one unified model (on Raspi) + a rule-based safety net on rt-core (H7, D-008):**

**Decision changed (result of discussion):** Our first decision was late fusion (separate scores, in separate places). After discussion, we moved to **early fusion** — rationale: Kuksa/VSS carries CAN signals, lean and vibration/acoustic features to the Raspi, not raw high-rate data (D-044 item 2), so evaluating this data in one unified model while it's already there can capture **cross-modality correlation** (cases where "two signals together are meaningful but neither alone crosses the threshold," which separate scores could miss), and it is also simpler from a development/synchronization standpoint.

```
Raspi 5 (single unified anomaly model):
   [CAN + Vibration + Acoustic + Thermal + Context] → unified model (early fusion)
   → single anomaly score/classification

rt-core (STM32H7) — minimal safety net, NOT ML, a handful of fixed rules (D-008):
   Engine-temperature threshold, illogical RPM jump, battery-voltage threshold, etc.
   → minimum control that never drops to ZERO even if the Raspi crashes/reboots
```

This gives both "ease of development in one model + correlation capture" (Raspi) and "never going completely silent" (rt-core rule-based fallback, not a separate ML model — no extra development load).

**Labeling:** During the fault-injection sessions in the vehicle work plan (spark plug, air filter, chain, tire pressure), CAN+IMU+audio are recorded simultaneously — three modalities labeled in a single session, no extra recording pass needed.

**Data adequacy — additional sensor suggestions:**

| Gap/improvement point | Suggestion | Cost | Priority |
|---|---|---|---|
| Vibration sensor location | The existing IMU (under the seat) is for lean/EKF; the engine vibration signature (piston, valve, bearing) is cleanest measured near the engine block. **A separate, small, engine-block-mounted accelerometer** should be added (independent of the existing IMU, for anomaly only) | 150-250 TL | **High — a concrete improvement** |
| Oil pressure/temperature | Probably absent on CAN (simple engine); a real signal for lubrication-related faults | 300-600 TL, mounting may be difficult | Optional |
| CAN, battery/power, thermal, context | Already sufficient | — | — |

**Methodological limits and validation protocol (decided):**

- **Goal:** Both (A) binary anomaly detection ("is there a deviation from normal") and (B) fault-type classification are targeted together. (B) requires balanced, sufficient data per class; the current 30-40 min/fault-session plan is strong for (A), limited for (B), and (B)'s accuracy may come out lower — this distinction must be clearly reported in the thesis.
- **Modality blind-spot risk:** Most of the planned fault scenarios (spark plug, vacuum leak, air filter, chain, tire pressure, idle) already leave a clear trace in CAN signals (fuel trim, RPM instability, MAP). This creates a risk that the vibration/acoustic layer (engine-block accelerometer, microphone) appears highly accurate without ever being truly validated (the accuracy could be coming from CAN while the expensive sensor infrastructure goes untested). **Solution:** at least one or two fault scenarios should primarily be of the type **visible in vibration, leaving a weak trace in CAN** (e.g. a controlled, loosened mounting bolt — reversible). Which modality catches which fault must be reported separately.
- **Validation:** The train/test split must be done **per session** (data from the same ride must not be in both training and test) — otherwise the model memorizes, producing misleadingly high accuracy.
- **Open datasets (CWRU, MaFaulDa, MIMII):** Useless for direct use (domain gap — different machine/vibration character). Their value is limited to a **methodology reference** (feature-extraction method); transfer learning for lower-layer transfer can be tried, but it's unproven — to be reported as an experiment with an actual outcome, not assumed.
- **Realistic accuracy expectation:** A ~80-90% detection rate can be expected for the specific faults tested (under the right conditions). Generalization to real/organic faults never tested (bearing wear, valve issues) **has not been tested and is unknown** — this must be explicitly stated as a limitation in the thesis; no false/exaggerated general-accuracy claim should be made (against the OVMS project's warning about "confident-but-wrong results without disclosing limitations").

---

### 5b.10 Virtual Dynamometer (moved from the feature pool — added to the core)

A module that computes the motorcycle's wheel power/torque without an external dynamometer. Wheel force/power is computed from longitudinal acceleration (IMU) + speed (CAN/GPS) + known vehicle parameters (mass, gear ratios, wheel radius); rolling/aerodynamic drag coefficients are calibrated with a coast-down test. Validation: repeatability + sensitivity (comparison against a known change — gear ratio) + an external dynamometer reference where possible.

**Hardware:** No additional hardware needed — existing IMU/CAN/GPS infrastructure suffices. Software only (60-90 hours).

### 5b.11 Comfort, Energy, and Driver Assistance Functions (moved from the feature pool)

Complementary functions built on top of the context bus, with low-medium added cost (from feature pool §9c, full list there):

**Comfort (K1-K10):** Adaptive display brightness, heated-grip control, automatic turn-signal cancellation, emergency brake signal, hill-start assist, wind/weather warning, fatigue/attention detection, ride log, social/group ride tracking, voice navigation integration.

**Energy (E1-E5):** Energy flow monitoring, battery charge status/health estimation, low-voltage protection, regenerative braking analysis (conceptual, for a future EV), sleep/wake power budget management.

**Driver Assistance (DR1-DR5):** Driver identity/personal profile, riding-skill progression tracking, **automatic post-crash notification (eCall-like — F7 fall detection + location + GSM, a concrete need in motorcycle safety)**, geofence/zone warnings, map-based speed-limit warning.

**Scope note:** All 20 of these sub-functions are considered Phase 2/extended scope; none is part of the core delivery commitment — listed here for full scope transparency in the advisor report.

---

## 6. Module or Chip

Depends on stage and chip type:

| Stage | What's used |
|---|---|
| Stage 1 — prototype (now) | Ready-made dev board (Nucleo, Discovery, ESP32 dev kit, Raspi board) |
| Stage 2 — integration | Own carrier PCB; module or chip depending on chip type |
| Stage 3 — product (Phase 2+) | Chips on their own PCB |

Rule by chip type:
- **ESP32-S3 (RF chip):** buy a module (WROOM/WROVER) — RF/antenna/certification work, don't place a bare chip
- **STM32 (pure MCU):** a bare chip is fine (with a reference circuit) — instructive, standard in automotive
- **Raspi 5 (computer):** board or Compute Module (CM5)

**Order:** Get the software running on a Nucleo/dev board first, then move to a bare chip. Debugging hardware and software errors at the same time on a bare chip in the first round should be avoided.

---

## 7. Staged Rollout

The target is 5 units, but not all are set up today. They are added as the corresponding function arrives.

| Stage | Unit | Trigger |
|---|---|---|
| Now | ESP32-S3 (temporary, sole unit — existing telemetry code) | Existing code, not yet moved to H7 |
| + | Main MCU migration to STM32H7 | Core work (telemetry, UDS, fusion, logging) moves here; the ESP32-S3's role narrows (connectivity+voice) |
| + | Safety MCU | Once the cornering safety module is built |
| + | I/O MCU | Once the combined blind-spot/immobilizer/power-management node is built (5b.1, 5b.3) |
| + | Raspi 5 | Once lane tracking/camera/HMI arrives |
| Separate | HIL simulator MCU | Bench (not in the vehicle) |

**Rule:** No unit is added until the function it will be used for arrives. An unused unit = maintenance burden.

---

## 8. Repository Structure (multi-repo)

Repo boundary = runtime boundary (things running in a different place/language/hardware are separate repos). Code-module boundaries within a repo are resolved with folders.

| # | Repo | Runtime | Language |
|---|---|---|---|
| 1 | `vehicle-rt-core` | **STM32H7** (main domain) | C/C++ |
| 2 | `vehicle-connectivity-node` | **ESP32-S3** (connectivity+voice) | C/C++ |
| 3 | `vehicle-safety-node` | STM32 G4/F3 (cornering safety) | C/C++ |
| 4 | ~~`vehicle-io-node`~~ | retired by D-072 (blind spot + immobilizer → safety-node, power → rt-core) | — |
| 5 | `vehicle-linux-node` | Raspi 5 (lane tracking, camera, HMI) | Python/C++ |
| 6 | `vehicle-hil-bench` | Simulator MCU (STM32F4) + host PC | C/C++ + Python |
| 7 | `vehicle-server` | Server | Python (FastAPI, D-010) |
| 8 | `vehicle-ml` | Offline training | Python |
| 9 | `vehicle-mobile` | Phone | Flutter (D-022) |
| 10 | `vehicle-defs` | Shared definitions | DBC/YAML/VSS |
| 11 | **`vehicle-mcp`** | Raspi 5 (same runtime, **separate repo — independent open-source project**) | Python |

**Why vehicle-mcp is a separate repo (exception rationale):** Its runtime is the same as `vehicle-linux-node`'s (Raspi 5), which would normally make it a single repo/module. But here **the sharing boundary** is a valid reason: it is intended to be published as an independent open-source project (so other DIY vehicle/motorcycle projects can use it too), to have its own star/contribution history on GitHub, to be a piece of the career showcase. `vehicle-linux-node` calls `vehicle-mcp` as an MCP client, treating it as a dependency/subprocess.

**Rationale for the split (1 and 2):** H7 and ESP32-S3 are different physical chips, differently compiled binaries, different flashes — a real runtime boundary. For the same reason, safety-node and io-node were also separate (different STM32 chip/flash); since D-072 safety-node is the Cortex-M4 image of the same STM32H755 (own flash bank and linker script) and io-node is retired. Functions on the main MCU (UDS, XCP, EKF, context, dynamometer, anomaly inference), however, are modules of a SINGLE repo — all compiled into the same H7 binary; a separate repo would be false isolation.

**vehicle-defs cornerstone:** Signal definitions, CAN message map, VSS model. The other ten repos take it as their source (submodule/package). Single source of truth → the "two units know the same signal differently" problem never occurs.

**Modules within a repo (NOT separate repos):** UDS/ISO-TP/bootloader, XCP, cornering EKF estimation, context classification, virtual dynamometer, anomaly safety net (D-008; the unified anomaly model runs on linux-node, §5b.9) → folders under `features/` inside `vehicle-rt-core` (H7). Voice command (ESP-SR, D-044) → a module inside `vehicle-connectivity-node` (ESP32-S3).

**ML split:** Training (Python, offline) → `vehicle-ml`. Inference (the model running in the vehicle) → the `features/` folder of the relevant node (context and the rule-based anomaly safety net → rt-core, the unified anomaly model → linux-node (§5b.9), voice command → connectivity-node, lane tracking → linux-node).

**Dependency direction (one-way):**
```
vehicle-defs → read by everyone
vehicle-rt-core → vehicle-defs
vehicle-connectivity-node → vehicle-defs, (via bridge) rt-core
vehicle-safety-node → vehicle-defs
~~vehicle-io-node → vehicle-defs~~ (retired, D-072)
vehicle-linux-node → vehicle-defs, (via bridge) rt-core, vehicle-mcp (called as subprocess/dependency)
vehicle-mcp → vehicle-defs (for vehicle schemas), local access to the context bus via the Raspi
vehicle-hil-bench → vehicle-defs
vehicle-server → vehicle-defs
vehicle-ml → vehicle-defs, vehicle-server
vehicle-mobile → vehicle-defs, vehicle-server
```

**Discipline:** `vehicle-defs` is versioned (v1.0, v1.1); the other repos are pinned to a specific version. When a signal changes, which repo needs updating becomes clear — none breaks silently.

---

## 9. Repository Setup Order

1. `vehicle-defs` — everyone depends on it, do it first (small but foundational)
2. `vehicle-hil-bench` — can be developed remotely (no hardware needed, host+simulator, even with Renode)
3. `vehicle-connectivity-node` (ESP32-S3) — existing code already runs here, easy transition
4. `vehicle-rt-core` (STM32H7) — main MCU migration, with hardware in the workshop
5. `vehicle-server` — data collection server
6. `vehicle-ml` — once data accumulates
7. `vehicle-safety-node` — once the cornering safety module is built
8. ~~`vehicle-io-node`~~ — retired by D-072; its functions are built in safety-node and rt-core
9. `vehicle-linux-node` — once Raspi/lane-tracking integration arrives
10. `vehicle-mobile` — last

---

## 9b. HIL Bench Hardware Architecture

The HIL bench is **separate** hardware that tests the vehicle system — it is not mixed in with the vehicle's 5-unit architecture. It has its own chip, power supply, and measurement layer. Its purpose: to simulate on the bench the electrical environment the DUT (device under test — the vehicle unit being tested) would see in a real vehicle.

### 9b.1 Core Principle — What's the Same, What's Different

- **The DUT and the interface the DUT sees must be THE SAME** (requirement): CAN transceiver, CAN speed/protocol, OBD2 connector, signal definitions, supply voltage profile. Otherwise the test is invalid.
- **The simulator's brain must be DIFFERENT** (independence principle): the simulator chip must not be the same as the vehicle's main chip — if it were, it would share the same blind spot/bug, and the test couldn't catch it. The balance: same manufacturer family (STM32 — one supply chain), different class and role, different library usage.

### 9b.2 Architecture — Restbus Simulation

**Restbus simulation** is used to simulate the vehicle as a whole: one powerful chip speaks as multiple virtual ECUs in software (engine ECU, ABS, dashboard) from different CAN IDs. A separate chip isn't needed for each ECU — CAN is a single bus, different IDs suffice. An industry-standard approach, consistent with the simplicity principle.

```
        HOST (i7 5th gen desktop + Linux/SocketCAN)
        scenario engine, logging, reporting — permanent test station / future CI runner
              │ USB/UART
        ┌─────┴──────┐
        │  STM32F4   │  ← SIMULATOR NODE
        │ · restbus (multiple virtual ECUs)
        │ · vehicle dynamic model (throttle→RPM→speed)
        │ · CAN message generation
        └──┬───────┬─┘
           │CAN    │control
      ═════╪═══    │
     device │   ┌───┴────────┐
      under │   │ STM32F103  │ ← fault injection + supply control
       test │   │ + prog.    │   (corrupted frame, line cut,
      (DUT)─┘   │ supply     │    programmable voltage)
               └────────────┘
```

### 9b.3 Components and Chip Selection

| Component | Chip/hardware | Status | Role |
|---|---|---|---|
| Simulator brain | **STM32F4** (F407/F429) | To buy | Restbus + vehicle model + CAN generation |
| Fault/supply control | **STM32F103** | On hand | Voltage manipulation, line cut, corrupted frames |
| Host (scenario engine) | **i7 5th gen desktop** + Linux | On hand | Python scenario engine, SocketCAN |
| CAN transceiver ×2 | SN65HVD230 etc. | To buy | Physical layer on the simulator + DUT side |
| Programmable supply | Buck + DAC/digital pot | To buy | Battery/starter/under-voltage scenarios |
| DUT connection | OBD2 connector, cable, termination | To buy | Connecting the DUT via a real socket |

**Chip rationale (STM32F4):** FPU (for the vehicle dynamic model), multiple CAN, very common in the industry (plenty of examples), reasonable price. openpilot's panda also uses STM32F4 (validation for vehicle-CAN hardware). Different class from the vehicle's main chip, H7/ESP32-S3 → ensures independence. H7 would be overkill for the simulator; the F103 (on hand) is weak as the main simulator node since it has only one CAN and no FPU — suited to an auxiliary role.

**Eliminated:** NXP S32K (a real automotive chip, would have been instructive, but the board costs ~10,000 TL — moved to Phase 2 for cost reasons).

### 9b.4 Host = Computer (not the simulator)

An important distinction: the computer (i7) is the **host**, it runs the scenario engine (commands like "drop the voltage, send a corrupted message"). The STM32F4 is the **simulator**, it converts those commands into real CAN signals. The computer has no CAN hardware, it cannot generate signals on its own — the F4 is required. The computer is the "brain/scenario," the F4 is the "hands/signal."

Installing Linux on the i7 desktop for the host is recommended: SocketCAN works natively, it can stay permanently on and evolve into test automation/a CI runner, and it frees up the Mac.

### 9b.5 Rough Cost

The only main part left to buy is the STM32F4 board; the rest is on hand or cheap. Total new spending ~800-1600 TL (STM32F4 300-600, transceiver 160-300, supply 200-400, connector/cable 150-300). The host and the F103 are already on hand.

**Approval status:** This HIL hardware list (STM32F4 simulator + STM32F103 fault/supply + i7 host + transceiver ×2 + programmable supply + OBD2 connection) has been approved by the user.

### 9b.6 Host-Side Visualization and Control Panel

Testing on the HIL host is monitored and directed via a monitor. Two layers are kept separate:

- **Control panel / visualization (on the host):** Start/stop scenario, parameter adjustment (voltage, RPM), live CAN traffic, latency graphs, pass/remaining test indicator. Tooling: web dashboard or Foxglove/PlotJuggler. **Core — to be done.** High demo and presentation value; the scaled-down equivalent of the control-desk logic in industrial HIL (dSPACE ControlDesk).
- **Vehicle dynamic model (in the simulator firmware):** Simple physics at first (throttle→RPM→speed); a detailed model (gears, torque curve, resistance) later. The counterpart of the Simulink model layer in industrial HIL.

**Boundary:** A 3D motorcycle model, realistic riding physics, an animated environment will NOT be built — these would shift the HIL from being a test tool into a riding simulator/game project. Panel + simple gauge + graph is enough.

---

## 10. Phase 2 / Next Stage (Consolidated List)

All items below are gathered into **a single "next stage" pool** — not split into sub-phases; prioritization/ordering will be done separately by the user. Not part of the core delivery commitment.

### 10.1 Permanently Eliminated (won't even be reconsidered in Phase 2)

| Item | Why permanently eliminated |
|---|---|
| NXP S32K / Infineon AURIX (a real ASIL-class safety MCU chip) | Cost (~10,000 TL) disproportionate to the project budget — permanent, not "revisit later" |
| NXP S32K (HIL simulator chip) | Same cost rationale — STM32F4 is the permanent decision |
| Full integration of the immobilizer with the ECU (OEM class) | Would require breaking Honda's closed protocol (seed-key) — a separate reverse-engineering project, out of scope. The current relay-based design is accepted as **deterrent class**; no OEM-level security is claimed — a limitation to be explicitly stated in the thesis |

### 10.2 Approved Phase 2 Roadmap (to be done, timing is next-stage)

| Item | What it brings | Dependency/note |
|---|---|---|
| Velocitas SDK | Moves Linux-node modules to the standard "Vehicle App" pattern | Builds on top of the Kuksa Databroker (core) |
| Eclipse Kanto | Container-based OTA/application management (Linux side) | Once Raspi capacity budget allows |
| SOME/IP | Moves the H7↔ESP32 bridge to the automotive middleware standard | Replaces the current simple messaging |
| DoIP | Carrying UDS over Ethernet (next-gen diagnostic protocol) | Via the Raspi's native Ethernet interface |
| Deep-learning LDW upgrade (UFLD/Fast-CenLaneNet) | Robustness in hard scenes (night, faint lines) | Low priority — the user won't prioritize lane tracking heavily, classic CV seems sufficient |
| Vehicle-MCP actuator-write capability (approval-gated) | The LLM being able to trigger its own added peripheral actuators (lights, heating, camera) | Never extended to engine/ECU control; operator approval gate mandatory. Pending Q-027 (read-only until then) |
| NFC cryptographic upgrade (MIFARE DESFire) | Clone resistance | PN532 hardware supports it, needs an additional library (software) |
| Nextion → LVGL+ESP32/round display | Enrichment of the main screen | References: moto2000, opencluster, DIY-dash-5, evj55-dashboard |
| Raspi 5 dedicated carrier/power PCB | **Not a function, a standardization step** — production maturation | Last on the list, done once the design settles |

### 10.3 Other Open Notes

- How the safety MCU will supervise the main MCU (watchdog/heartbeat) — to be designed once the safety MCU hardware is finalized
- ~~The HIL simulator's realism level~~ (both modes, D-035); the first target test function is still open (Q-009)
- ~~Whether the vehicle bus is classic CAN or CAN-FD~~ classic 500 kbps, verified (D-019)
- Suspension potentiometers — in Group 11 (hardware procurement list), the decision to add them is not yet final

### 10.4 Moved to the Core (no longer Phase 2 — reminder)

Items that were previously marked "optional/Phase 2" and were later moved into the core (to avoid confusion):

- Oil pressure/temperature sensor — added to the hardware list
- GSM module (park mode/theft tracking) — now core, together with the WhatsApp notification channel
- Brake-line pressure sensor — added to the hardware list
- ECU behavior analysis — planned as offline analysis on the home server (on the Raspi 3B+). **Method (legitimate, WITHOUT writing to ECU flash):** characterizing ECU behavior from runtime CAN/OBD data — throttle-map response, fuel trim, temperature compensation, RPM limit, load calculation ("black-box characterization"); the extracted behavior can feed the HIL vehicle model. Difference from chiptuning: reading/analysis is legitimate and planned, extracting the map from flash is technically very hard (Honda's protection, seed-key) and a separate reverse-engineering job; WRITING to the ECU (changing the map) is permanently out of scope for legal/warranty/safety reasons (see 10.1).
- Virtual dynamometer, comfort/energy/driver-assistance functions (20 sub-functions) — added to sections 5b.10-5b.11
