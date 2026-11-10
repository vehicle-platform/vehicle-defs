# Phase 0 Implementation Plan — Data Collection Infrastructure and ML Readiness

> Translated from the Turkish original (`archive/tr/faz0-veri-toplama-plani.md`). Where this document conflicts with `ARCHITECTURE.md` or `DECISIONS.md`, those take precedence.

> **Superseded in part (D-032, D-045):** where this plan puts the microSD recording or the Wi-Fi sync on the ESP32 (WP-4, WP-7), it is superseded. The ESP32-S3 called "main unit" here is connectivity-node, the temporary sole tester and BLE bridge until rt-core exists (D-023); the main MCU is the STM32H7 (D-001). The data path is BLE → phone → upload (D-032); connectivity-node keeps no local copy and data lost while the phone is disconnected is accepted, with seq/tick gap accounting shown in vehicle-server's validation report (D-045). Persistent on-vehicle logging (microSD session files, buffered writes, safe shutdown) belongs to rt-core's logging function. The signal list and the WP structure stay valid.

**Project:** Motorcycle embedded diagnostics, telemetry, and driver assistance platform
**Scope of this plan:** First priority — ML research, open-source review, and a working data collection system
**Version:** 1.0 — September 2026

---

## 0. Rationale for This Plan

Before anything else, the **data collection system** must be set up. Rationale:

- Past rides cannot be collected retroactively — the earlier logging starts, the richer the accumulated data
- All ML models (fault detection, context classification, voice command) depend on this data
- If the data format and metadata schema are set up wrong from the start, the collected data becomes useless later

So the first task is not to **build** the ML model, but to **prepare the ground** for ML. The model is built in Phase 2; the data and infrastructure start now.

**Order:** research → format decision → recording system → validation → continuous collection begins.

---

## 1. Work Package Sequence

| Order | Work package | Output |
|---|---|---|
| WP-1 | ML and open-source research | Reference notes, format/method decisions |
| WP-2 | Data schema design | Signal list + metadata schema + recording format |
| WP-3 | Physical connection (jumper → perfboard) | Vibration-resistant connection |
| WP-4 | Recording system (microSD + binary) | Working on-vehicle recording software |
| WP-5 | Power and safe shutdown | Supercapacitor buffer, data-loss protection |
| WP-6 | Validation and calibration | IMU alignment, speed validation, format testing |
| WP-7 | Continuous collection + server sync | Automatic recording every ride, upload to server |

---

## 2. WP-1: ML and Open-Source Research

### 2.1 Open-Source Projects to Review

| Project | What to look for |
|---|---|
| **Freematics** | ESP32 + OBD telemetry hardware/software reference — closest to your platform |
| **WICAN** | ESP32 OBD-WiFi/BLE dongle, open circuit schematic and recording architecture |
| **RaceCapture (AutosportLabs)** | Racing telemetry recording format, channel structure, synchronization |
| **openpilot / panda** | Safe access to vehicle CAN, data recording architecture, code quality |
| **can-utils (candump/canplayer)** | Record/playback format logic |
| **asammdf** | MDF4 format — archive/sharing target |
| **Edge Impulse example projects** | IMU-based classification, data collection flow |

### 2.2 Datasets (preliminary research for fault detection)

| Dataset | Content | Note |
|---|---|---|
| CWRU Bearing | Bearing fault, vibration | Domain mismatch but useful for transfer-learning pretraining |
| MaFaulDa | 6 conditions, multi-sensor machine fault | Methodology reference |
| MIMII | Industrial machine sound anomaly | For sound-based approach |
| (CAN fault dataset) | None — missing in the literature | This is your area of contribution |

### 2.3 Research Outputs (decisions to be made)

- Anomaly detection approach: one-class learning or transfer learning
- Feature extraction: raw signal, frequency domain, or statistical features
- Sampling frequencies (for each signal)
- Labeling strategy (how fault conditions will be tagged)
- Recording format decision (binary schema)

**Effort:** 20-40 hours (reading, experimentation, notes)

---

## 3. WP-2: Data Schema Design

### 3.1 Signals to Record

| Source | Signal | Frequency (Hz) |
|---|---|---|
| CAN | Engine RPM | 10-20 |
| CAN | Vehicle speed | 10 |
| CAN | Throttle position | 10-20 |
| CAN | Engine temperature | 1 |
| CAN | Intake pressure / air flow | 10 |
| CAN | Fuel trim (if available) | 1 |
| CAN | Battery voltage | 1 |
| CAN | Wheel speeds (from ABS, if available) | 20-50 |
| CAN | Fault codes | Event-based |
| IMU | 3-axis acceleration | 100-200 |
| IMU | 3-axis angular rate | 100-200 |
| Derived | Lean angle | 100 |
| GPS | Position, ground speed, heading | 5-10 |
| Unit | Supply voltage, current | 10 |
| Unit | Internal temperature | 0.1 |
| Unit | Stack/task status | 1 |

### 3.2 Metadata Schema (at the start of each session)

- Session ID, date, time
- Ambient temperature, weather (dry/wet)
- Tire pressure (front/rear)
- Fuel level
- Rider weight, additional load
- Vehicle configuration (gearing, exhaust, filter — for modification experiments)
- **Condition label: healthy / fault type** (critical for fault sessions)
- Route type (urban/rural/highway/closed course)
- Free-text note

### 3.3 Recording Format Decision

| Layer | Format | Rationale |
|---|---|---|
| On-vehicle write | Simple binary | Fast, compact, ESP32-friendly |
| Archive/sharing | MDF4 (converted later) | Industry compatibility, Hugging Face |
| Model training | Parquet / NumPy | Libraries read this natively |

**Binary schema design:** fixed-size record block, timestamp + signal fields + CRC. Per-block CRC, partial recovery on sudden interruption.

**Effort:** 10-15 hours

---

## 4. WP-3: Physical Connection

Jumper wires are unreliable under vibration. Intermediate step: **solder onto perfboard** (without waiting for the PCB).

| Task | Detail |
|---|---|
| Perfboard assembly | Modules (ESP32-S3, IMU, GPS, SD, power) soldered |
| Connectors | Locking connectors (JST/Molex) at detachable points, no jumpers |
| CAN connection | Y-cable, parallel to the DLC, no cutting |
| Enclosure | IP54 box, connector opening facing down |
| Vibration | Board on silicone mount; IMU rigid (no mount) |

**Effort:** 15-25 hours
**Note:** PCB design is not part of this phase — it comes after the design settles (Phase 1).

---

## 5. WP-4: Recording System

_Superseded in part (D-045): microSD session files are rt-core's logging function, not the ESP32's._

| Component | Task |
|---|---|
| microSD driver | SPI or SDMMC, high write speed |
| Binary writer | Block writing per schema, buffered |
| Time base | Monotonic counter + GPS synchronization |
| File management | One file per session, split at 100 MB |
| Integrity | Block CRC, partial recovery |
| Metadata | Write JSON at session start |

**Effort:** 30-50 hours

---

## 6. WP-5: Power and Safe Shutdown

| Component | Task |
|---|---|
| Input protection | Fuse, reverse polarity, TVS, LC filter |
| Regulation | Wide-input buck (6-40V → 5V) |
| Supercapacitor buffer | Enough energy to safely close the file when ignition is cut |
| Shutdown detection | Ignition line monitored via GPIO, shutdown begins on drop |
| Power monitoring | INA226 (voltage, current) |

**Effort:** 20-35 hours
**Note:** Can be designed as a separate power board; subframe/tail placement.

---

## 7. WP-6: Validation and Calibration

| Test | Purpose |
|---|---|
| IMU alignment | Static reference + validation at a known angle |
| Speed validation | CAN speed vs. GPS vs. calculation (from gear ratio) |
| CAN signal map | Which ID/byte maps to which signal — definition file |
| Recording integrity | Ignition-cut test, file recoverability |
| Noise test | Engine on/off signal comparison |
| Sleep current | < 1 mA verification |

**Effort:** 20-30 hours

---

## 8. WP-7: Continuous Collection and Server Sync

_Superseded in part (D-032, D-045): upload is BLE → phone → server, not Wi-Fi sync from the ESP32; no local copy on connectivity-node._

| Component | Task |
|---|---|
| Automatic recording | Session starts on every ignition-on |
| Wi-Fi sync | Automatic upload to server within home range |
| Server side | File storage + time-series DB (InfluxDB/TimescaleDB) or simple files + Python |
| MDF4 conversion | Archive format on the server via `asammdf` |
| Backup | Two copies (local + cloud) |

**Note:** Learning is **offline and versioned** — periodic retraining on the server, human approval, model deployment via OTA. Not continuous/online learning.

**Effort:** 40-60 hours (basic sync + simple DB)

---

## 9. Hardware Requirements

### 9.1 Already on Hand

- ESP32-S3 (connectivity-node: the Phase 0 data collector and temporary sole tester, D-023; the main MCU is the STM32H7, D-001/D-094)
- OBD2/CAN connection
- Nextion display

### 9.2 Required for This Phase — Mandatory

| Hardware | Purpose | On hand? | Estimate (TL) |
|---|---|---|---|
| CAN transceiver (SN65HVD230) | Physical layer | Check | 80-150 |
| IMU (6/9-axis, MPU6050/9250 or LSM6DSO) | Motion data | ? | 150-300 |
| microSD card module + card (industrial/high-endurance) | Recording | No | 150-300 |
| GPS module (NEO-M8N) + antenna | Position, speed | ? | 250-450 |
| Perfboard, locking connectors, cable | Assembly | Partially | 200-350 |
| Power: buck + protection + INA226 | Supply, monitoring | Partially | 300-500 |
| Supercapacitor + balancing + current limiter | Safe shutdown | No | 150-300 |
| Enclosure (IP54) | Protection | No | 150-300 |
| **Subtotal** | | | **1430-2650** |

### 9.3 For This Phase — Optional / Next Phase

| Hardware | Purpose | When |
|---|---|---|
| STM32 (Nucleo F303RE / F103) | HIL simulator, second node | HIL phase — can be bought from the for-sale list |
| Raspberry Pi 4/5 | Linux unit, camera, ML | Distributed architecture phase |
| Pi camera | Image processing | Camera phase |
| Microphone + button | Voice command | Voice command phase |
| LoRa module | Long-range telemetry | Optional |

### 9.4 Recommended Purchases from the For-Sale List

Not directly needed for this phase, but valuable for later phases and worth buying if the price is right:

- **STM32 Nucleo F303RE** — HIL simulator and second node
- **STM32F103C8T6 (x2)** — ideal for HIL simulator (ECU emulation)
- **Raspberry Pi 4 8GB** — distributed architecture (if the price is right; a Pi 5 alternative can be considered)
- **Pi camera** — image processing phase
- **LoRa + antenna** — long-range telemetry experiment

**Not worth buying:** Arduino UNO (a step backward), OV7670 (low quality), motor/stepper drivers (no actuator drive in this project).

---

## 10. Phase 0 Total Effort

| Work package | Effort (hours) |
|---|---|
| WP-1 ML/open-source research | 20-40 |
| WP-2 Data schema | 10-15 |
| WP-3 Physical connection | 15-25 |
| WP-4 Recording system | 30-50 |
| WP-5 Power and safe shutdown | 20-35 |
| WP-6 Validation | 20-30 |
| WP-7 Continuous collection + sync | 40-60 |
| **Total** | **155-255** |

At the end of Phase 0 you will have: a vibration-resistant, interruption-resistant system that automatically collects data on every ride and syncs to the server — plus a clean, labeled, continuously growing dataset for every ML model to build on.

---

## 11. After This Phase

Once Phase 0 is complete, next up:
- The protocol stack (CAN/ISO-TP/UDS) and the HIL bench, while data continues to accumulate
- The first ML model once enough data has accumulated (context classification — the easiest to label)
- Fault injection sessions (data enrichment)
- Model training and validation

Progress follows the buckets in the priority pool (separate document).
