# Feature Pool, Hardware Architecture, and Open Source Reference

> Translated from the Turkish original (`archive/tr/ozellik-havuzu.md`). Where this document conflicts with `ARCHITECTURE.md` or `DECISIONS.md`, those take precedence.

**Project:** Motorcycle embedded diagnostics, telemetry, and driver assistance platform
**Purpose:** Long-term development pool (candidate items + prioritization), hardware architecture analysis, and open source/hardware reference — in a single file
**Version:** 2.0 — September 2026

**Contents:** Sections 1-13 function/technology categories · 14 highlights · 15 out of pool · 16 prioritization framework · 17 hardware architecture analysis · 18 open source ecosystem and hardware costs

---

## How To Use

This document is not a commitment list — it is a **candidate pool**. For each item:

- **Effort:** rough hour estimate (prioritization input)
- **Dependency:** which item needs to be finished first
- **Value:** K = career/interview value, T = thesis/academic value, U = usage value
- **Open source:** the relevant project or standard

Prioritization suggestion: high value + low effort + few dependencies goes first.

---

## 1. Core Protocol Layer

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| P1 | CAN driver + error state machine | 25-35 | — | K,T | ESP-IDF TWAI, SocketCAN |
| P2 | ISO-TP transport layer | 40-60 | P1 | K,T | ISO 15765-2, `isotp-c`, `can-isotp` |
| P3 | UDS diagnostic server | 60-90 | P2 | K,T | ISO 14229, `udsoncan` (reference) |
| P4 | UDS diagnostic client (scan tool) | 25-40 | P2 | K,U | `python-OBD`, `udsoncan` |
| P5 | Full OBD2 mode support (01-0A) | 15-25 | P1 | U | SAE J1979 |
| P6 | CAN FD support | 20-30 | P1 | K | ISO 11898-1 |
| P7 | DoIP (Diagnostics over IP) | 40-60 | P3 | K | ISO 13400 |
| P8 | CANopen support | 30-50 | P1 | — | CiA 301, `CANopenNode` |
| P9 | J1939 support (commercial vehicle) | 30-50 | P1 | K | SAE J1939, `python-j1939` |

**Note P7:** DoIP is replacing CAN-based diagnostics in next-generation vehicles. Ethernet-based. High industry visibility.

---

## 2. Software Architecture and Platform

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| A1 | Layered modular architecture (HAL/service/function) | 40-60 | — | K,T | AUTOSAR SWC/RTE logic |
| A2 | **COVESA VSS signal model** | 25-40 | A1 | K,T | Vehicle Signal Specification |
| A3 | Migration/port to Zephyr RTOS | 60-100 | A1 | K | Zephyr Project |
| A4 | SOME/IP service communication | 50-80 | A1 | K | `vsomeip` (COVESA) |
| A5 | DDS / Zenoh pub-sub layer | 40-70 | A1 | K | Cyclone DDS, Eclipse Zenoh |
| A6 | micro-ROS integration | 40-60 | A1 | — | micro-ROS, ROS 2 |
| A7 | Eclipse Kuksa data broker | 30-50 | A2 | K,T | Eclipse Kuksa (SDV) |
| A8 | Eclipse Velocitas application framework | 40-60 | A7 | K | Eclipse Velocitas |
| A9 | Embedded module in Rust (one module as example) | 40-70 | A1 | K | `embassy`, `embedded-hal` |
| A10 | Containerized vehicle applications | 50-80 | Linux unit | K | Docker, Eclipse Leda |
| A11 | Hypervisor / virtualization experiment | 60-100 | Linux unit | K | Xen, Jailhouse |

**A2 especially recommended:** VSS is the standard definition model for vehicle signals. The concept of a "vehicle-independent signal definition file" is exactly this in industry terms. Using VSS instead of inventing your own schema carries weight in both the thesis and interviews. Low effort, high value.

**A7/A8:** Projects of the Eclipse SDV working group. Backed by Bosch, Microsoft, Red Hat. The open source reference implementation of the software-defined vehicle architecture.

---

## 3. Functional Safety

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| S1 | HARA (hazard analysis and risk assessment) | 25-40 | — | K,T | ISO 26262-3 |
| S2 | FMEA / FTA (fault tree analysis) | 20-35 | S1 | K,T | ISO 26262, IEC 61025 |
| S3 | Requirement-test traceability matrix | 20-30 | S1 | K,T | ASPICE |
| S4 | Watchdog and transition to safe state | 15-25 | A1 | K,T | ISO 26262-5 |
| S5 | Freedom from interference | 25-40 | A1 | K,T | ISO 26262-6 |
| S6 | MISRA C compliance and static analysis | 20-35 | — | K | MISRA C:2012, `cppcheck`, `clang-tidy` |
| S7 | SOTIF analysis (safety of the intended functionality) | 25-40 | S1 | T | ISO 21448 |
| S8 | Safety state machine and fault management | 30-50 | S4 | K,T | — |

---

## 4. Cybersecurity

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| C1 | TARA (threat analysis and risk assessment) | 25-40 | — | K,T | ISO/SAE 21434 |
| C2 | Secure boot | 40-60 | B1 | K | ESP32 Secure Boot, TF-M |
| C3 | Flash encryption | 15-25 | C2 | K | ESP32 Flash Encryption |
| C4 | CAN intrusion detection (IDS) | 50-80 | P1 | K,T | `CaringCaribou`, ROAD dataset |
| C5 | Message authentication (SecOC-like) | 40-60 | P1 | K | AUTOSAR SecOC |
| C6 | Secure OTA (signature verification, rollback protection) | 40-70 | B1 | K,T | **Uptane** standard |
| C7 | SBOM generation and dependency tracking | 10-20 | — | K | CycloneDX, SPDX |
| C8 | Penetration testing scenarios (against own system) | 30-50 | C4 | T | `CaringCaribou`, `SavvyCAN` |
| C9 | UN R155/R156 compliance documentation | 20-30 | C1 | K,T | UNECE regulations |

**C6 (Uptane):** The de facto standard for automotive OTA security. A topic expected to be known in automotive cybersecurity.

---

## 5. Bootloader and Update

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| B1 | Bootloader over UDS (0x34/36/37) | 80-120 | P3 | K,T | ISO 14229 |
| B2 | A/B bank + atomic switchover | 30-50 | B1 | K | MCUboot logic |
| B3 | Rollback on power loss | 25-40 | B2 | K,T | — |
| B4 | Delta update (diff-based) | 30-50 | B1 | K | `bsdiff`, `detools` |
| B5 | Campaign management (server side) | 40-70 | B1 | K | Eclipse hawkBit |
| B6 | Linux-side OTA (if a second unit exists) | 40-60 | Linux unit | K | RAUC, SWUpdate, Mender |

---

## 6. Test, Verification, and HIL

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| H1 | HIL bench hardware | 40-60 | — | K,T | — |
| H2 | Scenario engine + automated evaluation | 50-70 | H1 | K,T | — |
| H3 | Vehicle-independent definition layer | 25-40 | H2, A2 | K,T | VSS, DBC (`cantools`) |
| H4 | Measurement layer (timestamping, latency, bus load) | 30-50 | H2 | K,T | — |
| H5 | Fault injection (electrical + protocol) | 30-50 | H1 | K,T | ISO 7637-2 (partial) |
| H6 | Record / replay mode | 20-30 | H1 | K,U | `candump`/`canplayer` logic |
| H7 | CI/CD on hardware (self-hosted runner) | 30-50 | H2 | K,T | GitHub Actions, Jenkins |
| H8 | Unit test infrastructure (embedded C) | 25-40 | A1 | K | Unity, Ceedling, CMock |
| H9 | Code coverage measurement | 10-20 | H8 | K | gcov, lcov |
| H10 | **Virtual hardware simulation with Renode** | 30-50 | — | K,T | Renode (Antmicro) |
| H11 | ASAM XIL API-compatible interface | 40-60 | H2 | K | ASAM XIL |
| H12 | Simulink plant model + MIL/SIL/PIL chain | 80-120 | H2 | K,T | MATLAB/Simulink |
| H13 | Scenario definition with OpenSCENARIO | 30-50 | H2 | K | ASAM OpenSCENARIO |

**H10 (Renode):** An open source tool that simulates the MCU without hardware. Lets you run tests in CI without hardware — complements the physical bench. A lesser-known but impressive item.

---

## 7. Data, Logging, and Platform

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| D1 | Telemetry collection and logging infrastructure | 50-80 | P1, A1 | T,U | — |
| D2 | **Logging in MDF4 format** | 25-40 | D1 | K,T | ASAM MDF, `asammdf` |
| D3 | **MCAP format support** | 20-30 | D1 | K | MCAP (Foxglove) |
| D4 | Time synchronization (GPS/PTP) | 25-40 | D1 | K,T | IEEE 1588 PTP |
| D5 | Client-server synchronization | 50-80 | D1 | U | MQTT, Mosquitto |
| D6 | Time series database + dashboard | 30-50 | D5 | U | InfluxDB/TimescaleDB + Grafana |
| D7 | **Data visualization with Foxglove Studio** | 15-25 | D3 | K,U | Foxglove |
| D8 | PlotJuggler integration | 10-20 | D1 | U | PlotJuggler |
| D9 | Hugging Face dataset publication | 20-35 | D1 | T | HF Datasets, dataset card |
| D10 | Data anonymization (GPS clipping, identity) | 10-20 | D9 | T | — |
| D11 | End-of-ride report generation | 25-40 | D1 | U | — |
| D12 | Map overlay visualization (speed/lean/brake layer) | 30-50 | D11 | U | Leaflet, MapLibre |

**D2 (MDF4):** The standard format for automotive measurement data. Using MDF4 instead of inventing your own binary format makes the data openable in tools like CANape/CANoe. A concrete detail in an interview.

**D7 (Foxglove):** An open source data visualization tool becoming widespread in robotics and automotive. Professional-looking analysis without writing your own UI.

---

## 8. Edge AI / TinyML

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| M1 | Voice command recognition (keyword spotting) | 60-90 | A1 | K,T | TFLite Micro, ESP-NN |
| M2 | Driving context classification (IMU) | 40-60 | D1 | T | TFLite Micro, Edge Impulse |
| M3 | Road surface classification | 40-60 | M2 | T | — |
| M4 | Anomaly detection (one-class learning) | 60-100 | D1 | T | scikit-learn, TFLite |
| M5 | Fault prediction model (using controlled fault data) | 100-200 | D1, D9 | T | — |
| M6 | Driver identification (driving signature) | 30-50 | M2 | T | — |
| M7 | Model regression testing (size/latency/accuracy) | 20-35 | H7, M1 | K,T | — |
| M8 | Quantization and pruning optimization | 25-40 | M1 | K | TFLite, ONNX Runtime |
| M9 | Sound-based engine health analysis | 60-100 | M4 | T | MIMII/MaFaulDa pretraining |

---

## 9. Vehicle Functions

| # | Item | Effort | Dependency | Value | Open source |
|---|---|---|---|---|---|
| F1 | Cornering safety warning (physics + EKF + ML) | 60-100 | D1 | T,U | — |
| F2 | State/parameter estimation with EKF | 50-80 | D1 | K,T | `Eigen`, `kalman` |
| F3 | Virtual dyno | 60-90 | F2 | T,U | — |
| F4 | Gear detection and gear-shift coaching | 10-20 | D1 | U | — |
| F5 | Fuel consumption and range estimation | 10-20 | D1 | U | — |
| F6 | Battery health indicator | 15-25 | D1 | T,U | — |
| F7 | Fall / crash detection | 15-25 | D1 | U | — |
| F8 | Maintenance tracking (load-based) | 10-20 | D1 | U | — |
| F9 | Driving aggressiveness score | 10-15 | D1 | U | — |
| F10 | Brake performance analysis | 10-20 | D1 | U | — |
| F11 | Segment / lap comparison | 25-40 | D12 | U | — |
| F12 | Assistant profiles (city/touring/sport/eco) | 30-50 | A1 | U | — |
| F13 | Park mode + wake-on-motion + movement alarm | 45-70 | D1 | K,U | — |
| F14 | GPS tracking + GSM notification | 50-70 | F13 | U | — |
| F15 | Immobilizer (NFC + PIN, starter circuit) | 20-35 | A1 | T,U | — |
| F16 | Digital key (BLE proximity) | 30-50 | F15 | K | CCC Digital Key (reference) |
| F17 | Actuator control (lights, heating, camera trigger) | 25-40 | P3 | U | UDS 0x31 |
| F18 | XCP calibration interface + A2L | 40-60 | P2 | K,T | ASAM XCP, `pyXCP` |
| F19 | Calibration panel (live parameters) | 30-50 | F18 | U | — |

---

## 9b. Racing / Motorsport Telemetry

Achievable with mostly existing hardware (IMU + GPS + CAN); fills out the content of the "sport profile".

| # | Item | Effort | Dependency | Value | Open source / note |
|---|---|---|---|---|---|
| R1 | Lap detection (GPS geofence / beacon) | 15-25 | D1 | U | Automatic lap start/end |
| R2 | Delta time display | 20-30 | R1 | T,U | Instantaneous difference against a reference lap |
| R3 | Segment (sector) analysis | 20-35 | R1 | T,U | Splitting the lap to find where time is lost |
| R4 | Brake point consistency analysis | 15-25 | D1 | T,U | Distribution of brake onset points |
| R5 | Lean rate and lean angle histogram | 15-25 | F2 | T,U | Lean-in aggressiveness, unused lean margin |
| R6 | Throttle-to-brake transition time analysis | 10-20 | D1 | T,U | Riding technique metric |
| R7 | Driving consistency score | 10-15 | R1 | U | Standard deviation of lap times |
| R8 | Slip ratio estimation | 20-35 | D1 | K,T | If wheel speed is on CAN |
| R9 | Suspension stroke histogram + bottoming out | 25-40 | Potentiometer | T,U | Baseline data for setup |
| R10 | Tire/brake surface temperature tracking | 20-35 | IR sensor | U | Warm-up lap indicator |
| R11 | Chassis vibration signature (resonance/looseness) | 25-40 | Existing IMU | T | Mechanical anomaly |
| R12 | Racing line analysis | 30-50 | D12, D4 | T,U | Requires high-resolution GPS/fusion |
| R13 | Road grade estimation | 15-25 | F2 | K,T | Also a virtual dyno input |
| R14 | Brake pad wear prediction | 15-25 | D1 | U | Brake energy integration |
| R15 | Engine load factor / maintenance interval | 10-20 | D1 | U | RPM-torque weighted usage |

---

## 9c. Comfort, Energy, and Driver Functions

Function proposals not previously in the pool. Most achievable with existing hardware or a small addition.

| # | Item | Effort | Dependency | Value | Note |
|---|---|---|---|---|---|
| K1 | Adaptive display brightness | 5-10 | Ambient light sensor | U | Automatic day/night |
| K2 | Heated grip control | 15-25 | F17 | U | Automatic adjustment by temperature |
| K3 | Automatic turn signal cancellation | 10-20 | D1 | U | Cancel from IMU once the turn is complete |
| K4 | Emergency brake signal (rapid flashing) | 10-15 | D1, F17 | U | Stop lamp flasher on hard braking |
| K5 | Hill-start assist notification | 15-25 | F2 | U | Grade + stop detection |
| K6 | Wind/weather warning | 10-20 | N1 | U | Road condition info if connectivity available |
| K7 | Fatigue/attention detection | 30-50 | M2 | T | From riding irregularity pattern |
| K8 | Ride log and statistics | 15-25 | D1 | U | Km, duration, average, route history |
| K9 | Social/group ride tracking | 40-70 | N1 | U | Location of multiple vehicles |
| K10 | Voice navigation integration | 40-70 | M1, N4 | U | Phone navigation + voice guidance |
| E1 | Energy flow monitoring (generation/consumption) | 15-25 | D1 | T | Alternator output vs. load |
| E2 | Battery state of charge and health estimation | 20-35 | F6 | T,U | SoC/SoH estimation |
| E3 | Low voltage protection and load shedding | 15-25 | Power board | K,U | Disconnecting non-critical loads |
| E4 | Regenerative braking analysis (for future EV) | 20-30 | D1 | T | Conceptual, for a future vehicle |
| E5 | Sleep/wake power budget management | 20-35 | F13 | K,T | Consumption optimization by mode |
| DR1 | Driver identity and personal profile | 30-50 | M6 | K | Load settings based on who is riding |
| DR2 | Riding skill progression tracking | 25-40 | R7 | U | Consistency/speed trend over time |
| DR3 | Automatic post-crash notification (eCall-like) | 30-50 | F7, N2 | K,U | Fall detection + location + emergency notification |
| DR4 | Geofence / zone alerts | 15-25 | D1 | U | Entering/leaving a specific zone |
| DR5 | Speed limit warning (map-based) | 25-40 | N1 | U | Limit information based on location |

**DR3 (eCall-like):** The motorcycle version of the automatic emergency call system mandatory for real vehicles in the EU. Fall detection (F7) + location + GSM to send a "crash occurred, here's my location" notification. A genuine need in motorcycle safety, and a strong social-impact argument in the thesis.

---

## 10. Computer Vision and Advanced Perception

> STM32G0 dependencies in this table predate D-072: io-node is retired, so these items would run on the STM32H743 (rt-core) or the STM32G474 safety MCU (D-118; formerly the H755 M7/M4 split).

| # | Item | Effort | Dependency | Value | Open source |
|---|---|---|---|---|---|
| V1 | Camera integration and recording | 40-70 | Linux unit | U | OpenCV, GStreamer |
| V2 | Lane detection | 60-100 | V1 | T | OpenCV, LaneNet |
| V3 | Vehicle/obstacle detection | 80-150 | V1 | T | YOLO, OpenVINO |
| V4 | Blind spot / rear approach warning | 60-100 | V3 | U | — |
| V5 | Ride recording (dashcam + event-triggered) | 30-50 | V1 | U | — |
| V6 | Data collection and labeling pipeline | 60-120 | V1 | T | CVAT, Label Studio |
| V7 | Camera-IMU-CAN synchronization | 30-50 | V1, D4 | K,T | — |
| V8 | Traffic sign recognition | 60-100 | V3 | T | GTSRB dataset |
| V9 | Rear-End Collision Warning (RCW) & tail strobe | 40-70 | V4, STM32G0 | K,T,U | TTC engine, 4Hz brake pulse |
| V10 | Crowdsourced pothole & road quality map | 60-90 | V1, D4 | K,T,U | OpenCV + IMU $a_z$ + PostGIS |
| V11 | Multi-source speed limit assurance & voice query | 50-80 | V8, GPS | U | YOLO-Nano + OSM + CAN 0xF40D |
| V12 | AR cornering apex guide & anti-target-fixation dot | 60-90 | V2, EKF | K,T,U | Lean kinematics + Visor AR |
| V13 | Automated telemetry video overlay & highlight reels | 30-50 | V7 | U | FFmpeg/Cairo + 40° lean trigger |
| V14 | Low-light night vision (Sony Starvis IMX462) | 40-60 | V1 | T,U | NIR 850nm + YOLO pedestrian |
| V15 | Dual cockpit HMI (Nextion UART + low-latency RTSP) | 35-50 | V1 | U | Nextion serial + WebRTC/DSI |
| V16 | SMIDSY conspicuity light modulator (4 Hz high-beam) | 30-45 | V3, STM32G0 | K,T,U | DOT 49 CFR 571.108 S7.9.4 (US; in the EU and Turkey UN R53 applies) |
| V17 | Kamm friction circle curve-braking envelope & haptics | 50-80 | EKF, IMU | K,T,U | Kamm circle, grip margin reserve |
| V18 | Tank-slapper (speed wobble) 6-9 Hz resonance detector | 40-60 | IMU-1, Gyro | K,T,U | 2nd-order IIR bandpass, audio SOS |
| V19 | Rapid tire blowout early warning (UN ECE R141) | 25-40 | BLE TPMS | K,T,U | $dP/dt < -0.15\text{ bar/s}$, hazard pulse |
| V20 | Urban lane-filtering "dooring" optical flow predictor | 50-80 | V1 | T,U | Optical flow lateral delta ($>10\text{ cm}$) |
| V21 | Telemetry-driven cognitive fatigue & hypothermia index | 40-70 | CAN, DIDs | T,U | Throttle micro-jitter + wind-chill |
| V22 | Post-crash fuel/ignition isolation & cellular eCall SOS | 35-50 | STM32G0, 4G | K,T,U | $70^\circ$ lean + 3g shock; the fuel relay is out of pool (§15, invariant 6) |
| V23 | Sentry guard mode (parked IMU wake + 4G video push) | 30-50 | V1, 4G | U | Ultra-low-power IMU + 1080p clip |
| V24 | Remote cloud immobilizer & starter circuit inhibit | 20-35 | STM32G0, 4G | U | Zero-speed check + starter relay |

---

## 11. Linux / High-Level Unit

| # | Item | Effort | Dependency | Value | Open source |
|---|---|---|---|---|---|
| L1 | Linux unit integration (power, thermal, vibration, enclosure) | 40-60 | Power board | U | — |
| L2 | Custom image with Yocto/Buildroot | 50-80 | L1 | K | Yocto Project, Buildroot |
| L3 | Automotive Grade Linux experiment | 60-100 | L2 | K | AGL |
| L4 | Android Automotive OS experiment | 80-150 | L1 | K | AAOS |
| L5 | Read-only root filesystem + power-loss resilience | 25-40 | L2 | K | overlayfs |
| L6 | MCU-Linux communication bridge | 30-50 | L1, A4 | K | SOME/IP, UART/SPI |
| L7 | Display/HMI application | 50-90 | L1 | U | Qt, Flutter, LVGL |

---

## 12. Communication and Connectivity

| # | Item | Effort | Dependency | Value | Open source / standard |
|---|---|---|---|---|---|
| N1 | Cloud connectivity via MQTT | 25-40 | D5 | U | Mosquitto, `paho-mqtt` |
| N2 | GSM/LTE module integration | 40-60 | — | U | — |
| N3 | Phone connection via BLE | 30-50 | A1 | U | NimBLE |
| N4 | Mobile app (simple dashboard) | 60-100 | N3 | U | Flutter, React Native |
| N5 | Long-range telemetry via LoRa | 30-50 | — | U | LoRaWAN |
| N6 | Automotive Ethernet experiment | 50-80 | — | K | 100BASE-T1 |
| N7 | TSN (time-sensitive networking) experiment | 60-100 | N6 | K | IEEE 802.1 TSN |
| N8 | V2X experiment (vehicle-to-vehicle) | 80-150 | N6 | K | C-V2X, `OpenC2X` |

---

## 13. Process and Development Infrastructure

| # | Item | Effort | Dependency | Value | Open source |
|---|---|---|---|---|---|
| G1 | Requirements management | 20-35 | — | K,T | Doorstop, StrictDoc |
| G2 | V-model process documentation | 25-40 | G1 | K,T | ASPICE |
| G3 | Release management and branching strategy | 10-20 | — | K | Git Flow, semantic versioning |
| G4 | Automatic documentation generation | 15-25 | — | U | Doxygen, Sphinx |
| G5 | Build system and dependency management | 15-30 | — | K | CMake, PlatformIO, west |
| G6 | Code review and quality gates | 10-20 | H7 | K | SonarQube |
| G7 | Open source release (license, contribution guide) | 15-30 | — | T,U | — |

---

## 14. Top Ten Highlights

Since the pool is large, I am also flagging the ten items with the highest value/effort ratio:

| Item | Why |
|---|---|
| **A2 — COVESA VSS** | Low effort, high industry visibility, standardizes the foundation of the architecture |
| **D2 — MDF4 logging format** | Makes your data compatible with industry tools, low effort |
| **D7 — Foxglove** | Professional visualization, nearly free |
| **H10 — Renode** | Hardware-free CI testing, lesser-known but impressive |
| **C6 — Uptane** | The standard for OTA security, a natural continuation if building a bootloader |
| **S6 — MISRA C + static analysis** | Low effort, substantiates the "industry standard" claim |
| **H8/H9 — Unit test + coverage** | Proof of software engineering rigor |
| **F6 — Battery health indicator** | Small effort, real diagnostic technique, testable on HIL |
| **A7 — Eclipse Kuksa** | The open source reference for SDV architecture |
| **F18 — XCP + A2L** | The language of the calibration world, distinctive |
| **R2/R3 — Delta time + segment** | The heart of race telemetry, achievable with existing hardware, measurable output |

---

## 15. Deliberately Out Of Pool

| Item | Rationale |
|---|---|
| ECU flash writing / stage mapping | Legal (off-registration modification), warranty, safety concerns; gain of only 3-5% |
| Piggyback / fuel map intervention | Risk of engine damage without wideband lambda and EGT |
| Cutting the engine while running (fuel/ignition) | Riding safety — only the starter circuit is to be intervened on |
| Applying voltage to the handlebar/frame | Harm to third parties, legal liability, ineffective |
| Autonomous driving stack (Autoware/Apollo) | Orders of magnitude beyond this platform's scale |
| Real load dump test (ISO 7637-2 pulse 5) | Requires special equipment, destroys the DUT |

---

## 16. Suggested Framework for Prioritization

I recommend sorting items into four buckets:

**Bucket 1 — Backbone.** The infrastructure everything else rests on. Without these, nothing else can be done: P1, P2, A1, D1, F2, H1, H2.

**Bucket 2 — Thesis deliverable.** The cross-section to be shown to the committee. Backbone + a few visible functions + process documentation.

**Bucket 3 — Career showcase.** What will be discussed in interviews. Items with clear industry relevance such as P3, B1, C6, F18, H7, A2, S6.

**Bucket 4 — Long-term.** Computer vision, Linux unit, V2X, autonomous functions. Sequential, without a time constraint.

Every new idea goes into the pool, not into a bucket. For something to enter a bucket, something else must come out — this rule is the only thing that keeps the pool functional.

---

## 17. Hardware Architecture Analysis and Standardization

The current system is single-node (ESP32-S3 + OBD2/CAN + Nextion). As the platform grows, this structure becomes limiting. The problem is not the ESP32-S3, but piling every task onto a single chip. Standard automotive architecture is distributed: each node handles one job, and they communicate over CAN.

### 17.1 Three-Stage Evolution

**Stage 1 — rationalizing the current structure (recommended for the thesis).**
The ESP32-S3 remains the main node, but the separation of duties becomes clear (fusion/function/logging layers). The HIL simulator is a separate chip. Hardware stays the same, only the software architecture changes (layered structure).

**Stage 2 — standard automotive MCU (extended scope).**
Keep the main unit on the ESP32-S3 (Wi-Fi/BLE is valuable), add a second node using STM32. Deterministic work (CAN timing, safety-critical loop, control) moves to the STM32. Adds an "STM32 + automotive MCU" line to the CV.

**Stage 3 — domain controller (Phase 2).**
A real-time domain (STM32/S32K) + a high-level domain (Raspi/Linux), bridged by SOME/IP. This is the modern SDV architecture itself.

### 17.2 Automotive MCU Families

| Chip family | Position | Note |
|---|---|---|
| STM32 F/G/H | General embedded | The most common learning path |
| STM32H7 | High performance + DSP | ML + control together |
| NXP S32K | AUTOSAR compliant, ASIL-B/D | Widespread in industry, ideal for Phase 2 |
| Infineon AURIX (TriCore) | Safety-critical ECU | Expensive, difficult to learn |
| Renesas RH850 | Automotive ECU | Common among Japanese OEMs |

### 17.3 Intermediate Module Standardization

| Area | Current | Standard approach |
|---|---|---|
| CAN transceiver | Generic module | TJA1051/TJA1441 (automotive), SN65HVD230 (3.3V) |
| Power regulation | Buck module | Automotive-grade DC-DC (load-dump rated) |
| Connector | Various | Deutsch DT series (waterproof, automotive standard) |
| Protection | Scattered | TVS + reverse polarity + PTC standard input stage |
| Timing | MCU internal | External RTC or GPS-disciplined clock |
| Storage | microSD | Industrial SD or eMMC |

**Deutsch DT connector** in particular: cheap (a few hundred TL) but takes the system from a "prototype" to "field hardware" look. Makes a difference with the committee and in interviews.

### 17.4 Recommendation

Stay at Stage 1 for the thesis. Take Stage 2 (STM32 second node) into the extended scope. Leave Stage 3 for Phase 2. Do not move the main unit off the ESP32-S3 — there's no good reason to lose Wi-Fi/BLE.

---

## 18. Open Source Ecosystem and Hardware Costs

> **Legal and ethical framework:** The security/reverse-engineering tools below are intended for learning and defensive use **on your own vehicle, on your own network**. Unauthorized interference with someone else's vehicle or network is both illegal and destroys the project's legitimacy. These tools are valuable in the thesis in the context of "I applied attack scenarios to my own system and developed defenses" — not as attack tools, but as security verification tools.

### 18.1 CAN / Automotive Network Tools (General)

| Project | What it does | License | Note |
|---|---|---|---|
| **SocketCAN** | Linux kernel's CAN infrastructure | GPL | The foundation of all Linux CAN work |
| **can-utils** | candump, cansend, canplayer, cangen | GPL | Record/replay, traffic generation — perfect for HIL |
| **python-can** | CAN access in Python | LGPL | Ideal for your scenario engine |
| **cantools** | DBC/ARXML parsing, signal encoding | MIT | The core of the vehicle-independent signal layer |
| **SavvyCAN** | Graphical CAN analysis/reverse engineering | MIT | Visual tool for decoding unknown messages |
| **Wireshark + CAN** | Protocol analysis | GPL | Traffic inspection |
| **udsoncan** | Python UDS client implementation | MIT | Reference for verifying your own UDS |
| **isotp (Python/C)** | ISO-TP transport layer | MIT | For comparing against your own ISO-TP |
| **CANopenNode** | CANopen protocol stack | Apache 2.0 | Industrial/robotics CAN |

---

### 18.2 Security Research and Reverse Engineering Tools

This section addresses your "hacking side" interest. Automotive security research is a serious and growing field; these tools were developed for academic and defensive purposes.

| Project | What it does | Origin / community | Note |
|---|---|---|---|
| **CaringCaribou** | "nmap for vehicles" — CAN discovery, UDS scanning, fuzzing | Sweden (HEAVENS project) | The best-known open tool for automotive penetration testing |
| **CANToolz** | CAN analysis, MITM, fuzzing framework | **Russian security community** (Alexey Sintsov) | Modular, building attack scenarios |
| **c0f** | CAN fingerprinting | Security community | Identifying ECUs from traffic |
| **Metasploit HWBridge** | CAN attack modules via a hardware bridge | Rapid7 | CAN plugin for a penetration testing framework |
| **UDS fuzzers** | Abnormal input to UDS services | Various | Testing the robustness of your own UDS server |
| **gallia** | Automotive diagnostics fuzzing/scanning framework | Germany (Fraunhofer) | UDS/DoIP focused, modern |
| **scapy-automotive** | Scapy's CAN/ISO-TP/UDS/DoIP layer | France/community | Packet generation and analysis, very powerful |
| **OpenGarages / UDSim** | ECU simulator, learning environment | OpenGarages | The "Car Hacker's Handbook" ecosystem |

**On the Russian/former-Soviet scene:** This region has a strong tradition of reverse engineering and low-level systems programming — CANToolz is the most visible open source example of it. There is also extensive forum and community knowledge on immobilizer/key system and ECU read-write (chiptuning) and alarm system reverse engineering (drive2, various RU-language forums). Some of this knowledge sits in a gray area (it can intertwine with vehicle theft), so when selecting sources stay on the defense/research side — avoid content that drifts toward chiptuning and vehicle-theft techniques. The academic and CTF (capture-the-flag) side is clean and instructive.

**How to use this legitimately:** Scan your own motorcycle's CAN bus with CaringCaribou or gallia → learn which services are open and which IDs exist → use this information both to derive your signal map (the P items) and to test the robustness of your own UDS server/client through fuzzing (C4, C8 in the pool). In the thesis, this becomes the "I performed an attack surface analysis on my own system" section.

---

### 18.3 Software-Defined Vehicle (SDV) — Open Source

| Project | What | Backer | Pool counterpart |
|---|---|---|---|
| **COVESA VSS** | Vehicle signal data model standard | COVESA (BMW, Bosch, Ford...) | A2 |
| **Eclipse Kuksa** | VSS-based data broker | Eclipse SDV | A7 |
| **Eclipse Velocitas** | Vehicle application development framework | Eclipse SDV | A8 |
| **Eclipse Leda / Chariott** | SDV runtime environment | Eclipse SDV | A10 |
| **Eclipse hawkBit** | OTA campaign management | Eclipse | B5 |
| **vsomeip** | SOME/IP implementation | COVESA | A4 |
| **Eclipse Cyclone DDS** | DDS pub-sub | Eclipse | A5 |
| **Eclipse Zenoh** | Lightweight pub-sub/data streaming | Eclipse | A5 |
| **Eclipse ThreadX** | Real-time operating system (formerly Azure RTOS) | Eclipse | A3 alternative |

This ecosystem is the concrete open source form of what you mean by "next-generation automotive philosophy." Players like Bosch, Microsoft, Red Hat, and BMW are contributing code to these projects.

---

### 18.4 Operating System and Runtime

| Project | What | Pool counterpart |
|---|---|---|
| **Zephyr RTOS** | Modern embedded RTOS, broad hardware support | A3 |
| **FreeRTOS** | Widely used lightweight RTOS (already used by ESP-IDF) | Existing |
| **Automotive Grade Linux (AGL)** | Linux distribution for automotive | L3 |
| **Android Automotive OS** | Google's in-vehicle OS | L4 |
| **Yocto Project** | Custom embedded Linux image generation | L2 |
| **RAUC / SWUpdate / Mender** | Linux OTA solutions | B6 |
| **MCUboot** | Secure bootloader (A/B, signing) | B1/B2 reference |
| **TF-M (Trusted Firmware-M)** | Secure world / secure boot | C2 |

---

### 18.5 Test, Simulation, Verification

| Project | What | Pool counterpart |
|---|---|---|
| **Renode** | MCU/SoC software simulation (hardware-free testing) | H10 |
| **QEMU** | General system emulation | H10 alternative |
| **Unity / CMock / Ceedling** | Embedded C unit testing | H8 |
| **gcov / lcov** | Code coverage | H9 |
| **cppcheck / clang-tidy** | Static analysis | S6 |
| **PlotJuggler** | Time series data visualization | D8 |
| **Foxglove Studio** | Robotics/automotive data visualization | D7 |
| **CARLA** | Autonomous driving simulator (heavy) | For the V-series |
| **esmini** | OpenSCENARIO scenario player | H13 |

---

### 18.6 Data and ML

| Project | What | Pool counterpart |
|---|---|---|
| **asammdf** | MDF4 read/write (Python) | D2 |
| **MCAP** | Multi-channel logging format (Foxglove) | D3 |
| **TensorFlow Lite Micro** | ML inference on MCU | M-series |
| **Edge Impulse** | TinyML development platform (partially open) | M1/M2 |
| **ESP-DL / ESP-NN** | ML acceleration for ESP32 | M1 |
| **ONNX Runtime** | Model execution/conversion | M8 |
| **scikit-learn** | Classic ML (anomaly detection) | M4 |
| **Hugging Face Datasets** | Dataset publishing | D9 |

---

### 18.7 Reference / Custom Projects to Draw Inspiration From

Open source work done by individuals or small teams that is close to your project:

| Project | What | Why relevant |
|---|---|---|
| **comma.ai / openpilot** | Open source ADAS (lane keeping, adaptive cruise) | Best example of custom hardware + vehicle CAN integration; a reference for code quality and architecture |
| **openpilot panda** | Hardware for safe access to vehicle CAN | Design of a safety-locked CAN interface |
| **RetroPilot** | Community forks of openpilot | Small-team sustainability |
| **Freematics** | Arduino/ESP-based OBD telemetry hardware+software | The open hardware closest to your platform |
| **ESP32-OBD2 projects** | Various individual OBD scanners | ESP32 + CAN reference code |
| **WICAN** | ESP32-based open source OBD-WiFi/BLE dongle | Commercial-open hybrid, open circuit schematic |
| **O-Panel / TinyCAN dashboard projects** | Motorcycle/vehicle digital dashboard | Reference for Nextion/LVGL displays |
| **Speeduino** | Open source ECU (megasquirt-style) | For learning how an ECU works — not for use on your own engine |
| **rusEFI** | Open source ECU firmware | Speeduino alternative, strong community |
| **DIY race telemetry (RaceCapture)** | Open source race data logger | AutosportLabs — a direct reference for the R-series |

**Note on Speeduino/rusEFI:** These are open source ECU projects. NOT for installing on your own CL250 (out of pool — legal/warranty concerns). But worth reading to learn how engine control works, as a reference when building the HIL plant model, and to be able to say "I understand the ECU side too."

**RaceCapture (AutosportLabs):** Open source race telemetry hardware and software. A direct inspiration for the R-series (race telemetry) — see how delta time, lap analysis, and dashboards are done.

---

### 18.8 Learning Resources

| Resource | What |
|---|---|
| **The Car Hacker's Handbook** (Craig Smith) | The foundational book on automotive security, free PDF available |
| **OpenGarages community** | Vehicle security learning ecosystem |
| **ISO standards on the CAN bus** | 11898 (CAN), 15765 (ISO-TP/OBD), 14229 (UDS), 13400 (DoIP) |
| **AUTOSAR specifications** | Publicly available, architecture reference |
| **CTF (capture-the-flag) vehicle security** | Practical, legal learning environment |

---

### 18.9 Additional Hardware Cost List

Hardware required by pool items that is NOT present in the current system. Prices are September 2026 Turkey estimates; confirm before ordering.

### 9.1 Sensors

| Hardware | For which item | Estimate (TL) |
|---|---|---|
| Linear potentiometer / pull-wire encoder ×2 | R9 suspension | 300-600 |
| IR temperature sensor (MLX90614 etc.) | R10 tire/brake temperature | 150-350 |
| Thermocouple + MAX31855 (EGT) | Engine health, fault detection | 300-600 |
| Wideband lambda sensor + controller | AFR / combustion quality | 2000-4000 |
| TPMS sensors (tire pressure) | Race pressure tracking | 800-1500 |
| Additional IMU (high quality, low drift) | F2/R-series precision | 400-1000 |
| RTK GPS module + antenna | R12 line analysis | 2000-4500 |
| Brake lever load cell + amplifier | Brake force analysis | 500-1200 |

### 9.2 Processing and Communication

| Hardware | For which item | Estimate (TL) |
|---|---|---|
| Raspberry Pi 5 (or CM5) | Linux unit, camera, heavy ML | 2500-4500 |
| Raspi power HAT / UPS module | L1 power-loss resilience | 400-900 |
| STM32 development board | HIL simulator alternate platform | 150-400 |
| CAN FD transceiver | P6 CAN FD | 100-250 |
| GSM/LTE module (A7670/SIM7600) | F14, N2 | 400-900 |
| LoRa module (SX1276/1262) | N5 long range | 200-450 |
| Automotive Ethernet PHY (100BASE-T1) | N6, DoIP | 500-1200 |
| BLE already on ESP32-S3 | N3, F16 | 0 |

### 9.3 Camera and Imaging

| Hardware | For which item | Estimate (TL) |
|---|---|---|
| Raspi camera module (v3 / HQ) | V1 | 500-1500 |
| Global shutter camera | V3 motion blur reduction | 1000-2500 |
| Waterproof camera enclosure | V1 external mounting | 200-500 |
| Coral USB TPU / accelerator (optional) | V3 heavy model | 1500-3000 |

### 9.4 Power and Protection

| Hardware | For which item | Estimate (TL) |
|---|---|---|
| Supercapacitor set + balancing | Controlled shutdown | 150-300 |
| Wide-input buck (2-3 A) | Separate power board | 100-250 |
| INA226/228 power monitoring | Power measurement, HIL | 100-300 |
| Protection (TVS, reverse polarity, fuse) | Power board | 100-250 |
| Small LiPo + charging circuit | Battery-powered hidden tracking module | 200-450 |
| Bistable relay | F15 immobilizer | 80-200 |
| NFC reader (PN532) | F15 authorization | 100-250 |

### 9.5 HIL Bench (separate system)

| Hardware | For which item | Estimate (TL) |
|---|---|---|
| Second ESP32/STM32 (simulator) | H1 | 150-450 |
| CAN transceiver ×1 | H1 | 80-150 |
| DAC-controlled adjustable power supply | H5 electrical fault | 150-300 |
| Relay/analog switch (fault injection) | H5 | 80-200 |
| OBD2 female connector + cable | H1 | 100-250 |

### 9.6 Rough Totals

| Package | Range (TL) |
|---|---|
| Current system plus basic additions only (power board, immobilizer, park mode) | +600-1400 |
| Additional race telemetry sensors (suspension, IR, EGT) | +750-1550 |
| HIL bench | +560-1350 |
| Linux + camera layer | +4000-9000 |
| Advanced sensors (lambda, RTK, TPMS, load cell) | +5300-11200 |

**Note:** The lower band comes from local Turkish sourcing, the upper band from imported/premium parts. Should be bought piece by piece in priority order — buying everything up front is neither necessary nor sensible. AliExpress prices are roughly half but carry 3-5 weeks of shipping and customs risk; buy locally if time is critical.

---

### 18.10 Note on Prioritization

Most of the open source tools in this document are **free** and require no hardware — meaning the marginal cost of the pool's software items is often zero. The real cost is in hardware, and that scales in stages. Almost all of the "top ten highlights" in Section 14 (feature pool) can be done with the free open source tools in this document: VSS, MDF4, Foxglove, Renode, MISRA tools, unit testing — none of these require additional hardware.

So when prioritizing in the next step, set the rule as follows: **sweep the zero-hardware, high-value items first** (these come with open source), and buy hardware-requiring items piece by piece only when you actually reach that function.
