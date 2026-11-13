# Hardware integration — Phase 0 data-collection build (CL250)

**Status:** working guide, started 2026-10-03; parts on hand and the phone-only display recorded 2026-10-11 (user); figures and the connector/cable plan added 2026-11-12 (Claude). **Scope:** the first on-vehicle build that collects data with the code that exists today, plus the H755 target build it grows into (§3.4, §4.1, §4.2, §11). It does not change any decision. Authority: `DECISIONS.md` > `ARCHITECTURE.md` > `vehicle-work-plan.md` / `phase0-data-collection-plan.md` > this file. Items marked **CONFIRM** are not documented anywhere yet. Fill them in from the bike or the parts on the desk; never guess them.

## 0. Figures (`docs/img/hardware/`)

Every figure draws only what the text and the decisions already say; a value that has no source is marked CONFIRM or TBD in the drawing too. Open them on GitHub or in the editor; they are plain SVG with no external resources.

| Fig. | File | Shows | Used in |
|---|---|---|---|
| 1 | [`01-system-overview.svg`](img/hardware/01-system-overview.svg) | Nodes, the two CAN buses, mailbox, BLE/Wi-Fi paths of the target build | §1, §11, ARCHITECTURE §3 |
| 2 | [`02-power-chain.svg`](img/hardware/02-power-chain.svg) | Board A power chain, the C1/C2/Pi branches, battery divider, ground rules, gate B1 | §3.2 |
| 3 | [`03-main-box-layout.svg`](img/hardware/03-main-box-layout.svg) | 170×120×55 Main Box: Nucleo layer 1, Boards A/B mezzanine, C1-IO, six glands, stack heights | §4.2 |
| 4 | [`04-h755-pin-map.svg`](img/hardware/04-h755-pin-map.svg) | Pin plan v0.1 per core (proposal, `h755-pin-plan.md`) | §10 item 10 |
| 5 | [`05-can-topology.svg`](img/hardware/05-can-topology.svg) | Vehicle-bus stub vs. terminated platform bus, where the 120 Ω are | §3.1 |
| 6 | [`06-cl250-placement.svg`](img/hardware/06-cl250-placement.svg) | Side view with the candidates (a)–(h), heat zone, IMU zone, DLC, wheel-travel line | §4.1, Q-034 |
| 7 | [`07-imu-boxes.svg`](img/hardware/07-imu-boxes.svg) | C1-IMU and C2 frame boxes, cables, axis convention to record | §3.4, §4.1, §9 |
| 8 | [`08-phase0-wiring.svg`](img/hardware/08-phase0-wiring.svg) | Today's ESP32-S3 unit, pin by pin | §1, §3.3, §5 |
| 9 | [`09-immobilizer.svg`](img/hardware/09-immobilizer.svg) | Latching contact in the starter-relay coil line, bypass, C1-IO drivers, fail state | §3.4 (D-097) |
| 10 | [`10-led-ring-deadman.svg`](img/hardware/10-led-ring-deadman.svg) | Ring data/buffer/330 Ω chain, 74HC123 dead-man on the ring supply, mirror LEDs, IND_L/R inputs | §3.4, §4.1 |
| 11 | [`11-pi5-box.svg`](img/hardware/11-pi5-box.svg) | Pi 5 box stack, S5 connections, open items before the Pi rides | §4.1 option 2 |
| 12 | [`12-bringup-gates.svg`](img/hardware/12-bringup-gates.svg) | B0 → B2 → §7.1 capture → V0 → V3 → T2/T3 with pass criteria | §6 |
| 13 | [`13-harness.svg`](img/hardware/13-harness.svg) | Harness rules by signal class and the anatomy of one shielded run | §3.4, §4 |

## 1. What this build is

- **Node:** `vehicle-connectivity-node` on an ESP32-S3 DevKitC-1. Until rt-core runs on the bike, it is the **temporary sole vehicle-bus tester** (D-021, D-023, D-037).
- **Path:** CL250 ECU → DLC Y-cable → CAN transceiver → ESP32-S3 TWAI → BLE → phone (`vehicle-mobile`) → session zip → `vehicle-server` (D-032).
- **No on-vehicle storage:** conn keeps no local copy. Data lost while the phone is disconnected is accepted, and the server report shows the gaps (D-045). Persistent logging (microSD, safe shutdown) is rt-core's job later, so the Phase 0 plan's microSD and supercapacitor items are not part of this build.
- **IMU:** an MPU-6050-class IMU on the same ESP32 at 100 Hz, streamed over BLE. It is for offline analysis only: it is not a vehicle signal, not a safety input, and no lean is estimated from it (D-032, D-044).
- **Display:** the phone (`vehicle-mobile`) is the only live telemetry view in this build. The Nextion stays unconnected for now (user, 2026-10-11) and comes back in a later prototype; `NextionModule` with nothing on UART2 is harmless.
- **Not in this build:** rt-core (STM32H755 M7, D-072), the platform bus, the M4 safety partition (io-node retired, D-072), Raspi, the Nextion (for now). GPS joins it per D-060 (see §9).

```
 CL250 DLC ──Y-cable (CANH, CANL, GND; < 50 cm, twisted)──┐
                                                          │
 12 V ignition-switched ─ fuse 2 A ─ reverse-polarity ─ TVS ─ LC ─ buck 6-40 V → 5 V
                                                          │            │
                                              ┌───────────┴────────────┴───────────┐
                                              │ SN65HVD230 ── GPIO4 TX / GPIO5 RX  │
                                              │ ESP32-S3 DevKitC-1 (conn firmware) │
                                              │ MPU-6500 ── I2C GPIO7 SDA / GPIO6 SCL (0x68, 400 kHz)
                                              │ NEO-M8N ── UART1: module TX → GPIO15 / module RX ← GPIO16 (pins CONFIRM, §7.3)
                                              │ Nextion (later, unconnected now) ── UART2 GPIO17 TX / GPIO18 RX
                                              └──────────────┬─────────────────────┘
                                                             │ BLE "Honda-CL250-Telemetry"
                                                    phone: vehicle-mobile ── session zip ──► vehicle-server (laptop)
```

## 2. Parts list for this build

Sources: `phase0-data-collection-plan.md` §9, `hardware-procurement-list.md` (groups 1-3, 10, "Already On Hand"), `vehicle-work-plan.md` §3. On hand as of 2026-10-11 (user): ESP32-S3, MPU-6050, SN65HVD230, NEO-M8N; everything else is still to be bought or confirmed. Desk bring-up 2026-10-15: the board and the working IMU are recorded in the rows below.

| Part | Spec | Role | On hand |
|---|---|---|---|
| ESP32-S3 DevKitC-1 | WROOM module | conn firmware | **on hand**: ESP32-S3 rev v0.2, 16 MB flash, 8 MB embedded PSRAM, FTDI FT232R USB-UART (shows as `/dev/cu.usbserial-*`), flashes and boots with the DevKitC-1 envs (2026-10-15). GPIOs used: 4, 5, 6, 7, 8, 15, 16 |
| CAN transceiver | SN65HVD230 (3.3 V) | TWAI ↔ vehicle CAN | **on hand**; **CONFIRM** whether the breakout carries a 120 Ω termination resistor: it must be removed or left open, since the vehicle line is already terminated (§3.1) |
| IMU | MPU-6050 class, must deliver ±8 g / ±500 dps at 100 Hz (D-032) | raw motion data | **on hand**: the working part is an MPU-6500 (WHO_AM_I 0x70, accepted by conn; ±8 g / ±500 dps meet D-032; the part stays provisional). The first module (MPU-6050 class) gave no I2C answer on the desk. The user also has one IMU board marked "MPU-6590" (2026-10-23; not a known InvenSense part number): **CONFIRM** the chip by `WHO_AM_I` register `0x75` (`0x70` MPU-6500, `0x71` MPU-9250, `0x73` MPU-9255, `0x68` MPU-6050) and whether it is the working part above. It serves this build now and becomes the M7 chassis IMU (Board C2) in the H755 build |
| GPS | u-blox NEO-M8N, 3.3 V logic on its UART, own antenna (D-060) | ground speed, heading | **on hand** |
| DLC Y-cable | Parallel to the OEM connector, no cut | bus access | **CONFIRM** connector type |
| Fuse + holder | 2 A, blade or glass | input protection | **CONFIRM** |
| Reverse-polarity protection | Series Schottky or P-MOSFET | input protection | **CONFIRM** |
| TVS diode | Bidirectional, 24-30 V clamp | load-dump / transients | **CONFIRM** |
| Buck converter | Wide input 6-40 V → 5 V, 2-3 A | supply | **CONFIRM** |
| Input filter | Electrolytic + ceramic, LC | EMC | **CONFIRM** |
| INA226 (optional) | Current/voltage monitor | sleep-current check (§7) | **CONFIRM**, or use a multimeter |
| Enclosure | ABS or aluminium, ≥ IP54, < 100 × 70 × 30 mm target | protection | **CONFIRM** |
| Connectors, glands, wrap | Locking connector (one detachable plug), PG7 glands, spiral wrap | assembly | **CONFIRM** |
| Nextion display | UART2 | local display | on hand, **not used in this build** (later prototype) |
| Phone | Android with the `vehicle-mobile` APK | BLE receiver, session files | **CONFIRM** |
| Laptop | `vehicle-server` (uv or Docker) | ingest + report | on hand (i7 desktop or laptop) |

## 3. Electrical integration

Rules from `vehicle-work-plan.md` §3.2, §3.3 and §4; vehicle bus facts from D-019.

### 3.1 Vehicle CAN

| Item | Value | Source |
|---|---|---|
| Access point | Diagnostic connector (DLC), Y-cable parallel to the OEM plug, harness never cut | VWP §3.2, §4.1 |
| Lines | CANH, CANL, GND | VWP §3.2 |
| DLC location and pinout on the CL250 | **CONFIRM** (not documented; the legacy build used it, D-019) | — |
| Bus | Classic CAN, 500 kbps | D-019 |
| Addressing | 29-bit, request `0x18DA10F1` → response `0x18DAF110` | D-019, `uds/vehicle_cl250.yaml` |
| Termination | **None added.** The vehicle line is already terminated at both ends | VWP §3.2 |
| Cable | Twisted pair, shielded if possible, < 50 cm, away from the ignition coil and plug lead | VWP §3.2, §4.2 |
| ESP32 pins | TWAI TX `GPIO4`, RX `GPIO5` (`src/main.cpp`) | `legacy-telemetry-notes.md` §5 |

### 3.2 Power

| Item | Value |
|---|---|
| Tap | Ignition-switched line, not the always-on battery line (no drain when parked). Exact tap point: **CONFIRM** |
| Chain | 2 A fuse at the unit input → reverse-polarity (Schottky or P-MOSFET) → bidirectional TVS (24-30 V) → LC filter → buck 5 V → DevKitC 5 V pin |
| Ground | Directly to the battery negative, not the chassis |
| Sleep current | Target < 1 mA with the ignition off, verified by measurement (§7, T0); above that, switch the supply with the ignition |

### 3.3 IMU, display and GPS wiring

- IMU on I2C: SDA `GPIO7`, SCL `GPIO6`, address `0x68` (AD0 to GND), 400 kHz (conn#19; the legacy port used GPIO1/2). GPIO4/5 stay with CAN. Keep the I2C wires short, inside the enclosure, and solder the module's header: a header only pushed into the jumpers lost contact on the desk (2026-10-15).
- Nextion (later, unconnected in this build): UART2 TX `GPIO17`, RX `GPIO18`, 115200 8N1.
- `GPIO8` pulses high for each `loop()` pass (scope probe for the step time, §6).
- GPS (D-060): NEO-M8N on UART1, module TX → `GPIO15` (conn RX), module RX → `GPIO16` (conn TX), common GND. **CONFIRM**: candidate pins of the `esp32-s3-devkitc-1-gps` env, confirmed by the procedure in §7.3. The module's UART must be 3.3 V logic.

### 3.4 Chassis sensor harness: twisted-pair rules, shield grounding, insulation & split perfboard layout

To suppress magnetic induction (EMF = -dΦ/dt, from the ignition coil/HT lead, regulator/rectifier, and starter cable) and capacitive cross-talk on every sensor run between the motorcycle frame and the `NUCLEO-H755ZI-Q` box:

| Signal Class | Examples on Bike | Twisting Rule (`~30–40 twists/m`) | Shielding & Termination Rule |
|---|---|---|---|
| **Differential Bus** | Vehicle CAN (`CAN_H / CAN_L`), Platform CAN | Twist `CAN_H + CAN_L` tightly together (`120 Ω` only at Platform CAN physical ends; **never** on the `< 50 cm` DLC stub) | Unshielded automotive twisted pair (`FLRY-B 0.35–0.50 mm²`) is sufficient |
| **Single-Ended High-Speed Digital (`SPI / I2C / UART / WS2812B`)** | `ADXL345 ×2` (SPI/I2C), `MAX31856` (SPI), `MLX90614 / VL53L1X / AS5600 / BME280` (I2C), `INMP441` (I2S), `HLK-LD2451 ×2` (UART), `WS2812B` (800 kHz) | **NEVER twist `SCL + SDA`, `SCK + MOSI`, or `TX + RX` with each other** (causes capacitive cross-talk). Instead, twist **`Signal + GND` as Pair 1** and **`VCC + GND` as Pair 2** | Use **`LiYCY 4×0.22 mm²` tinned-copper braided shielded cable**; the M4 IMU `SPI` link to C1 (SCK, MOSI, MISO, CS + supply/GND) needs a **6- or 8-core** `LiYCY` (D-082 item 2). Connect the braid shield to **`GND` at the `H755` enclosure side ONLY (single-ended drain)** and leave the sensor-side shield floating/insulated (prevents chassis ground loops). For I2C sensors (`MLX90614`, `VL53L1X`, `AS5600`, and any I2C sensor more than ~30 cm from the box): keep the I2C run short (≤ ~30 cm) or use a differential I2C extender (PCA9615 class); **CONFIRM** in the schematic. Stronger `2.2–4.7 kΩ` pull-ups to `3.3V` at the controller end are a proposal (placement **CONFIRM**; `10 kΩ` on-board pull-ups are weak for long cable capacitance) |
| **Low-Level Analog / Differential (`mV` / Thermocouple / NTC / Hall)** | `K-type EGT` (`µV/°C`), `M12×1.5 Sump NTC`, `10K Radiator NTC`, `ACS758` (`Analog Out`) | Twist `Signal + Signal_Return (AGND)` tightly; keep the `MAX31856` cold-junction amplifier close to the K-type stainless braid exit | Keep **`> 15 cm` away from the ignition coil and spark-plug HT lead**; clamp **`5–7 mm` snap-on ferrite cores** on the engine-bay `ADXL345`, `EGT`, and `Inductive Spark Clip` cables right before the `PG7` enclosure entry |

- **Flexible Harness Insulation (Never Full-Length Heat-Shrink):** Do **not** encase long chassis cable runs in full-length heat-shrink tubing ; cured heat-shrink becomes stiff, transfers frame vibration directly into solder joints, and traps condensation. Instead:
  1. Use **`3–4 cm` adhesive-lined heat-shrink (`3:1`) ONLY at connector backs, solder splices, shield terminations, and `PG7` gland entries** as strain relief.
  2. Wrap the twisted pairs along their length with **`Tesa 51608` automotive fleece/cloth harness tape** (`50%` overlap), which stays flexible, damps rattle, and resists `105–150 °C`.
  3. Add **PE spiral wrap** or split corrugated loom (`6–8 mm`) only over high-abrasion pinch zones (headstock steering pivot, swingarm pivot, frame pass-throughs).
- **Split perfboard architecture (D-082):** Never solder all subsystems onto a single monolithic `9×15 cm` perfboard (it mixes `12V` power transient return currents with analog `AGND` and precludes `Scale 1A` vs. `Scale 1B` hardware separation). Build the 2nd story (`M3 × 18–20 mm` hex standoffs over the `NUCLEO-H755ZI-Q`, inside the `170 × 120 × 55 mm` H755 box) as **two independent, side-by-side double-sided epoxy perfboards**, and keep the two IMU boards out of the stack in their own frame-mounted boxes:
  1. **Board A (`5 × 7 cm` — core power, dual CAN & `Scale 1A` base):** `1N5822` reverse-polarity Schottky + `SMBJ30CA` TVS + LC stage + `12V → 5V` buck + `SN65HVD230 ×2` (`FDCAN1 / FDCAN2`) + `1 kHz` battery-voltage ADC divider + `INA226 #1` + `MicroSD SPI`. Required by all tiers (`Scale 1A`).
  2. **Board B (`7 × 9 cm` — `Scale 1B` QM conditioners, detachable):** `PC817` 4-ch optocoupler (`Clutch / Brake / Fan 12V`, the M7 `TAP_*` channels), `MAX31856` EGT, `NTC` RC dividers (`10 kΩ 0.1% + 100 nF`), spark-pickup input (`1N4148` + 3.3 V Zener + `74HC14`; **CONFIRM** (proposal)), `LJ12A3` level shifter, and the single detachable `Scale 1B Expansion Port` headers. Unplugging Board B cleanly reverts the hardware to `Scale 1A`. **Board B holds no safety input.**
  3. **Board C1 = C1-IO + C1-IMU (`M4` safety boards; split decided 2026-10-24, D-082 item 2).** **C1-IO (`4 × 6 cm`, in the H755 box, never on Board B):** `74AHCT125` 5 V LED buffer + `HLK-LD2451 ×2` radar UART headers + immobilizer driver (latching-relay coil drivers only; gate pull-downs, pulse-only drive) + the ring-supply dead-man `74HC123` (D-072 item 5, not part of the immobilizer driver; required unless the moving alive pixel is used; retriggered by a GPIO edge from the M4 main loop after each completed decision step, never a timer/PWM/DMA; trigger input pulled down) + the Q-033 indicator inputs (two opto-isolated `PC817` inputs, the M4's own input, D-075 item 4; a broken wire, dead opto or stuck input reads as "not signalling" and may only escalate a warning, never suppress it; series R sized for >= 16 V, reverse diode, pull-up sized for the minimum CTR). **C1-IMU (`3×7 cm` cut to ~`30×40 mm`, own small frame box):** the M4's own `MPU-6500` (SPI; D-042, D-075 item 6), its LDO and the SPI series resistors. C1-IO has its own fused branch from the protected 12 V (not shared with C2) and its own connector to the M4 pins; its 5 V (LED buffer, radars, ring) comes from the Board A buck; whether it fits beside A and B on the 2nd story is **CONFIRM**. C1-IMU's LDO is fed from the C1-IO branch through the C1-IMU cable (6–8-core shielded `LiYCY`). The M4 `MPU-6500` runs on that LDO but talks SPI to Nucleo-powered pins: 33-100 ohm series resistors on the SPI lines against back-powering; a C1-IMU LDO or cable loss shows as a WHO_AM_I/self-test fault -> UNAVAILABLE.
  - **Immobilizer fail state (D-082 item 6, confirmed by D-097; bypass = passive switch across the relay contact):** the latching relay keeps its position when C1 or the M4 loses power; an M4 boot never pulses SET; a dead M4 while locked or AUTH_PENDING needs the hidden bypass (the 10 s unlock timer cannot run without the M4). The relay sits only in the starter-relay coil line, so it can never stop a running engine (invariant 6).
  4. **Board C2 (`3×7 cm` cut to ~`30×40 mm` — `M7` chassis IMU carrier):** the M7 chassis IMU only (the on-hand board marked "MPU-6590", chip **CONFIRM**, §2). Separate cable, separate supply branch.
- **Why C1 and C2 are separate (D-082):** separate supply branches, connectors and cables (D-042, invariant 3; prototype, no dependent-failure analysis). A fault on C2 or its cable cannot remove an M4 function. A fault on C1-IMU or its cable removes only the M4's own IMU (cornering UNAVAILABLE, shown on the ring); a fault on C1-IO removes its functions together and must show as a dark ring / UNAVAILABLE (D-042 item 4, D-072 item 5). Remaining common causes: the protected 12 V chain and buck on Board A (which also feeds C1's 5 V), the star ground, the H755 supply/clock/reset, the mounting point and loom route, and two IMUs of the same family (no diversity). Both IMUs sit rigidly on the main frame near the centre of mass (§4.1). Boxes: the `DT-0508` / `DT-0505` named so far are `126×136×54` / `126×136×48 mm` ABS boxes with no IP rating stated (store pages, 2026-10-24; corrected in `hardware-procurement-list.md` v2.8). They are far too large for the ~`30×40 mm` IMU boards; C1-IMU and C2 use the same small IP65/IP67 box, product and position **CONFIRM** with Q-034. C1-IO sits in the H755 box.

### 3.5 Connector and cable plan (H755 build; every type is a proposal until bought)

One row per cable that leaves a board or a box. Pin orders are fixed in the Fusion sheets (SCHEMATIC §8); this table fixes what each cable carries, so the gland count, the cable stock and the Deutsch kit can be ordered. Lengths are "measure on the bike" (§4.1) except where a rule caps them. Fig. 3 numbers the Main Box glands G1–G6; Fig. 13 gives the harness rules.

| # | From → to | Cores (signal list) | Cable | Connector | Length rule | Shield / notes |
|---|---|---|---|---|---|---|
| G1 | Bike harness → Board A | 2: `+12V_IGN`, `GND` (to battery negative) | 22 AWG silicone, twisted | waterproof blade-fuse holder in line; 5.0 mm screw terminal on Board A | fuse within ~15 cm of the tap (**CONFIRM** practice) | fuse 2 A at the unit input; GND never via chassis |
| G2 | DLC Y-cable → Board A (`SN65HVD230 #1`) | 3: `VCAN_H`, `VCAN_L`, `GND` | FLRY-B 0.35–0.50 twisted pair + GND | Honda DLC adapter (4- or 6-pin, **CONFIRM**) → 3.81 mm pluggable terminal | **< 50 cm** total stub, non-negotiable | no termination ever; this stub decides the box position (§4.1) |
| G3 | Board A (`SN65HVD230 #2`) → platform bus | 2 (+ GND optional): `PCAN_H`, `PCAN_L` | FLRY-B twisted pair | 3.81 mm pluggable terminal; Deutsch DT 2-pin at the box wall (proposal) | no stub limit (terminated bus); keep drops short | 120 Ω on Board A (end 1); the far node carries end 2 |
| G4 | C1-IO → C1-IMU box (M4 SPI4) | 8: `SPI_M4_SCK`, `MOSI`, `MISO`, `CS_IMU_M4`, `IMU_INT_M4`, `+12V_PROT` (C1 fuse), `GND`, spare | LiYCY 8×0.22 shielded | Deutsch DT 8-pin (proposal; type **CONFIRM**) | **≤ ~30 cm** (check longer on the desk with the logic analyzer) | shield → GND at the Main Box only; 33–100 Ω series on the four SPI lines (C1-IMU side) |
| G5 | Board A → Board C2 box (M7 I2C1) | 4: `I2C_M7_SDA`, `GND`, `+12V_PROT` (C2 fuse) or `+3V3_C2`, `GND`; SCL as 5th if the pairs stay (**CONFIRM** 4 vs 6 cores) | LiYCY 4×0.22 or 6×0.22 shielded | Deutsch DT 4/6-pin (proposal) | **≤ ~30 cm**; longer → PCA9615 pair | SDA+GND, SCL+GND, VCC+GND pairs; never SDA with SCL |
| G6 | Board B / C1-IO → Scale 1B harness and front/rear lines | per sub-harness below | mixed | Board B "Scale 1B expansion port" header (JST-XH) + Deutsch DT at the wall | — | unplugging Board B reverts to Scale 1A |
| G6a | C1-IO → LED ring L / R (front) | 3 each: `LED_RING_x_DIN`, `+5V_RING`, `GND` | LiYCY 4×0.22 (Data+GND pair, 5V+GND pair) | Deutsch DT 3-pin each | long (gauge); slack at the head stock | 330 Ω at the buffer; dead-man-switched 5 V; desk test at full length |
| G6b | C1-IO → mirror LEDs L / R | 2 each: `MIRROR_LED_x`, `+V` (per MOSFET stage, TBD) | 22 AWG twisted | DT 2-pin each | long (mirrors) | low-side N-MOSFET on C1-IO |
| G6c | C1-IO → radar L / R boxes (rear) | 4 each: `UART_RAD_x_TX`, `RX`, `+5V`, `GND` | LiYCY 4×0.22 | DT 4-pin each | short (rear box) | UART level and supply **CONFIRM** (datasheet) |
| G6d | rear indicator feeds → C1-IO | 2 each: `IND_L` / `IND_R` 12 V signal, return | 22 AWG | harness tap connector, not a cut (**CONFIRM** tap) | short (rear) | PC817 input with series R ≥ 16 V and reverse diode |
| G6e | C1-IO → immobilizer relay box (near the starter relay) | 4: `IMMO_SET`, `IMMO_RESET` coil drives (+12V side per driver topology), `GND`; plus 2 power contacts of the relay in the starter-relay coil line | 22 AWG for the coils; harness-gauge for the contact | DT 4-pin + the two contact leads | relay box as close to the starter relay as the harness allows (**CONFIRM** location) | contact only in the coil line (invariant 6); bypass switch wired across the contact |
| G6f | Board B → chassis sensors (Scale 1B) | `ADXL345` ×2 (SPI: 6 cores each), `MAX31856` probe (2 + CJ amp local), NTC ×3–5 (2 each, Signal+AGND), `ACS758` (3: VOUT, 5V, GND), `LJ12A3` ×2 (3 each), spark clip (2) | LiYCY 4/6×0.22 for digital; twisted pairs for analog | DT per sensor box | engine-bay runs: ferrite before the gland; ≥ 15 cm from coil/HT lead | shields float at the sensor; AGND meets GND once |
| P1 | Board A → Pi 5 box | 2: `+12V_PROT` (own fuse), `GND` | 22 AWG twisted | DT 2-pin | any (not a CAN stub) | HCW-P715 inside the Pi box |
| P2 | Pi 5 box ↔ platform bus | 2: `PCAN_H`, `PCAN_L` | FLRY-B twisted pair | DT 2-pin | any; J1 120 Ω only if the Pi is the far end | MCP2515 SO/INT level-shifted |
| P3 | Pi 5 box → camera (front) | 22-pin CSI flex | Pi 15→22 pin cable | — | as short as the mount allows | shielded sleeve if it passes the engine (**proposal**) |
| E1 | ESP32 conn box ↔ platform bus | 2: `PCAN_H`, `PCAN_L` | FLRY-B twisted pair | DT 2-pin | mid-bus node: no 120 Ω | the on-board 120 Ω of its SN65HVD230 removed/open |

Counts this table implies for Wave 1 (check against the procurement list before ordering): Main Box glands 6 (G1–G6) plus up to 4 more if G6a–G6e enter through their own PG7 instead of one multi-core harness (**decide at the box**), Pi box 4, ESP32 box 2, each sensor/IMU/radar/relay box 1–2. Deutsch DT: 13 pairs for Wave 1 (6× 2-pin: G3, G6b ×2, P1, P2, E1; 2× 3-pin: G6a; 4× 4-pin: G5, G6c ×2, G6e, with G5 6-pin if its six cores are confirmed; 1× 8-pin: G4); the G6f Scale 1B sensor runs add 12 in Wave 2 (7× 2-pin with five NTCs, 3× 3-pin, 2× 6-pin), 25 in all. The procurement list v3.0 carries these counts and adds 20 % spare to the cable metres. LiYCY: 5 m 4-core, 2 m 8-core, 5 m 2-core; FLRY-B pair 3 m.

**Cable metres per run (estimate, CONFIRM with M1-M16).** Basis: Honda CL250 (2023) overall length 2175 mm, width 830 mm, height 1135 mm, wheelbase 1485 mm, seat height 790 mm ([Webike Japan spec page](https://japan.webike.net/HONDA/CL250/14769/m-spec/), [Webike launch article](https://japan.webike.net/moto_news/latest-news/20230314-cl250-will-be-released-on-5-18-specifications-also-revealed-motorcycle-show-2023/); some figures there are pre-release, so M-sheet values win) and the Q-034 placement of §4.1 (Main Box on the rear-subframe tray, option (c); battery, starter relay, indicator feeds, radars within about 0.5-1 m of it). Routed lengths follow the frame, not the straight line: tray to gauge / head stock is about 1.3 m along the frame plus about 0.5 m for the rise to the bars and steering slack, so about 2 m. "Base" is the one-way routed length, "Buy" is base + 30 % slack, rounded up to the next 0.5 m (G2 is capped, see its note). Every number below is an **estimate, CONFIRM with M1-M16**. No connector, pin or decision changes.

| Run | Cable | Cores | Base (m) | Buy (m) | Basis | Measure |
|---|---|---|---|---|---|---|
| G1 | 22 AWG | 1 red + 1 black | 0.8 | 1.5 each | tray to fuse box / tap, GND to battery negative (both under the seat region) | M11, M14 |
| G2 | FLRY-B pair (+ GND on 22 AWG black) | 2 + 1 | 0.45 | 1.0 pair, 1.0 black | stub **< 50 cm is a cap, not a minimum**; the 1.0 m is spare for a failed crimp, cut to <= 0.5 m | M1, M2 |
| G3 | FLRY-B pair | 2 | 2.0 | 3.0 | platform bus trunk, tray to front hub | M10 |
| P2 | FLRY-B pair | 2 | 0.5 | 1.0 | Pi box drop (1.5 m if the Pi sits on the front crash bar, option 2) | M3, M4 |
| E1 | FLRY-B pair | 2 | 0.5 | 1.0 | ESP32 box drop at the front end of the trunk | |
| G4 | LiYCY 8x0.22 | 8 | 0.3 | 0.5 | C1-IO to C1-IMU, <= ~30 cm rule | M10 |
| G5 | LiYCY 6x0.22 (4x0.22 if 4 cores are confirmed) | 6 | 0.3 | 0.5 | Board A to C2 box, <= ~30 cm rule | M10 |
| G6a | LiYCY 4x0.22, two runs | 4 | 2.0 | 3.0 each (6.0) | tray to the gauge area, includes head-stock slack | M15 |
| G6b | 22 AWG twisted, two runs | 1 red + 1 black | 2.3 | 3.0 each | tray to the mirror stems, along the ring route plus the bar width | M16 |
| G6c | LiYCY 4x0.22, two runs | 4 | 0.6 | 1.0 each (2.0) | tray to the rear radar boxes at the tail | M5 |
| G6d | 22 AWG, two runs | 1 red + 1 black | 0.6 | 1.0 each | tray to the rear indicator feed taps | M13 |
| G6e | 22 AWG | 3 red + 1 black | 0.8 | 1.5 each | tray to the immobilizer relay box at the starter relay; the 2 relay contact leads are harness gauge and not counted here | M12 |
| P1 | 22 AWG twisted | 1 red + 1 black | 1.5 | 2.0 each | Board A to the Pi box (0.8 m if the Pi box shares the tray or plate) | M3, M4 |
| G6f-a | LiYCY 6x0.22, two runs | 6 | 1.2 | 2.0 each (4.0) | `ADXL345` x2 (Wave 2), tray to the engine area | M8 |
| G6f-b | LiYCY 2x0.22, five NTC + spark clip | 2 | 1.0 / 1.2 | 1.5 each (7.5), 2.0 | five NTC runs at the upper bound, one spark clip run (Wave 2) | M8 |
| G6f-c | LiYCY 4x0.22 | 3 used | 0.6 / 1.0 | 1.0 (`ACS758`), 1.5 x2 (`LJ12A3`) | battery current sensor and the two inductive sensors (Wave 2) | M11, M14 |

Not counted (not stock cable): the `MAX31856` thermocouple probe lead, the two relay contact leads, the Pi CSI flex (P3), internal board-to-board wiring.

**Totals and purchase suggestion (estimate, CONFIRM with M1-M16):**

| Cable | Wave 1 (m) | Wave 2 (m) | Total (m) | Suggested purchase | Row now in the procurement list |
|---|---|---|---|---|---|
| 22 AWG silicone, red | 16.0 | 0 | 16.0 | 20 m (2 x 10 m) | 5 m |
| 22 AWG silicone, black | 14.0 | 0 | 14.0 | 15 m (10 m + 5 m) | 5 m |
| LiYCY 2x0.22 | 0 | 9.5 | 9.5 | 10 m (2 x 5 m) | 6 m |
| LiYCY 4x0.22 | 8.0 | 4.0 | 12.0 | 15 m (3 x 5 m) | 6 m |
| LiYCY 6x0.22 | 0.5 | 4.0 | 4.5 | 5 m | 0 m (not counted) |
| LiYCY 8x0.22 | 0.5 | 0 | 0.5 | 2 m (cut once, keep a retry) | 2.4 m |
| FLRY-B pair | 6.0 | 0 | 6.0 | 10 m (5 m + 5 m) | 3.6 m |

Totals already contain the 30 % slack; the 20 % spare of procurement list v3.0 is not added on top. 22 AWG split by colour: red carries supply and signal-hot cores, black carries GND/return (G6e: 3 red + 1 black, assumed). Wave 1 totals are the bike-side runs of the Main Box build; Wave 2 is the G6f Scale 1B sensors.

## 4. Mechanical integration

| Item | Rule | Source |
|---|---|---|
| Location | Under the seat (preferred) or inside a side panel; never near the engine block | VWP §3.1 |
| Heat | ≥ 15 cm from exhaust, cylinder, radiator, or a heat shield | VWP §4.1 |
| Unit mount | Silicone mount or vibration-damping tape | VWP §3.1 |
| IMU mount | **Rigid, never on the damped mount** (a damper adds its own resonance); aligned with the bike's longitudinal axis, offset measured and corrected in software | VWP §3.4 |
| IMU vs unit | If the unit sits on a damped mount, the IMU goes on its own rigid bracket on the frame. Exact spot and axis directions: **CONFIRM** and record them in the session metadata | VWP §3.4 |
| Removal | One detachable connector takes the whole unit off the bike | VWP §3.1, §4.1 |
| Cables | Spiral wrap or conduit, clear of steering, suspension and chain, every end labelled, wiring diagram kept with this file | VWP §4.1 |
| Rain | Glands on every cable entry; the enclosure must not collect water at the cable side | VWP §3.1 |

### 4.1 Placement on the CL250 for the H755 + Pi 5 build (Q-034 open; Claude recommends (c))

The under-seat rule above came from the ESP32-only build. The user found no free space under the seat above the battery (2026-10-18), and the Wave 1/Wave 5 enclosures (`170 × 120 × 55 mm` for the `NUCLEO-H755ZI-Q` and for the `Raspberry Pi 5`) need dedicated frame-mounted or exterior volumes. Candidates and analysis (Q-034 until the user decides; items marked **CONFIRM** are unverified):

**IMU boards apart from the controller boxes (D-082).** C1-IMU (M4 IMU) and Board C2 (M7 IMU) are separate from the big boxes, each in its own small IP65/IP67 box (product open, see §3.4); C1-IO stays in the H755 box. Bolted rigidly on short `6 mm` brass standoffs to the main steel frame near the centre of mass (a point between the rear of the fuel tank and the front of the seat is the idea; **CONFIRM** the frame point on the bike), each with its own `LiYCY` shielded run to the main box (`≤ ~30 cm`), they free the large `H755` and `Pi 5` boxes to sit on soft silicone dampers in any cool, accessible spot. That separate mounting is common practice on production motorcycles and race loggers (**CONFIRM**, no source cited).

| Candidate | Heat (≥ 15 cm rule) | Vibration & clearance | Noise & cable routing | Verdict |
|---|---|---|---|---|
| **(a) Around the engine block** | Fails: cylinder, head and exhaust header | Strongest on the bike (combustion, crank) | Next to the ignition coil and plug lead | **Rejected for boxes.** Only the D-044 engine `ADXL345` (`DT-0505` / `1590A`) belongs here |
| **(b) E-Clutch unit's place (right clutch cover)** | Fails: on the engine's clutch side (Honda mounts the E-Clutch actuator there, **CONFIRM** for the CL250); without E-Clutch the spot is the clutch cover itself, a hot crankcase cover near the upswept exhaust | Engine primary vibration | Near ignition and stator leads | **Rejected** for the same reasons as (a) |
| **(c) Rear subframe: tray under the fender** | Good on the left; the CL250's upswept muffler is on the right (**CONFIRM** the distance) | Moderate; verify the rear wheel travel (`~150 mm`, **CONFIRM**) at full bottoming | Farthest from the ignition; DLC run: measure, the `< 50 cm` stub limit decides | **Recommended (Claude), Q-034 open**, with the tyre-clearance check and the rules below |
| **(d) Left-side pannier carrier plate** (`SW-Motech` / `Longride` carrier bosses, `~127 mm` pitch: **CONFIRM** the bosses, the pitch and their load rating) | Likely good: opposite side from the right-hand exhaust (distance **CONFIRM**), open airflow | Rigid bosses if they exist; less bottoming and spray exposure than (c) (**CONFIRM**) | DLC run: measure, the `< 50 cm` stub limit decides; side access to `ST-LINK` / microSD | **Candidate.** Pros: cool side, rigid mounting, access. Cons: depends on unverified bosses; adds a plate |
| **(e) Pillion seat / rear luggage rack plate** (`~23 × 23 cm`, **CONFIRM**) | Excellent in principle: away from the engine and exhaust, full airflow | Plate or tail-bag base on dampers; check the lever arm of a cantilevered rack | DLC run: measure; clear sky for `GPS`, `BLE` and `Wi-Fi` | **Candidate.** Pros: easy prototype mount, airflow. Cons: rack stiffness and run length unverified |
| **(f) Left crash bar / front left frame downtube** | Good on the left: cold frontal airflow (the exhaust header curves right; verify `≥ 15 cm`) | Higher frame vibration than the rear (rubber bobbin isolators needed) | DLC run likely `> 50 cm` (measure): unsuitable for the `H755` box on the vehicle CAN stub; suits the `Pi 5` (platform CAN is terminated, no `50 cm` limit) or a front sensor hub | **Candidate** for the `Pi 5` or a front hub |
| **(g) Behind the headlight / number-plate cowl** | Excellent: isolated from engine and exhaust heat | Steering-head inertia (keep the load `< 400 g`; unsuitable for the big boxes) | `DT-0508` front hub (`126×136×54 mm`: check the cowl space; `ESP32-S3`, camera, `PN532` NFC, `BME280`, cornering LEDs) | **Candidate** for front satellite modules (Part 3B) |
| **(h) Behind the left side cover** (document-pouch cavity, size **CONFIRM**) | Good: plastic side panel on the cool left side | Inside the main frame triangle next to battery and DLC | Too shallow (`< 45 mm`, **CONFIRM**) for the `170×120×55 mm` box; could take a C1 or C2 box, the `ACS758LCB-200B` box or the immobilizer relay box | **Candidate** for the small boxes |

Rules across the candidates:
- **Layouts to compare (none decided).** *Option 1:* a `3–4 mm` aluminium plate on the left-side carrier bosses (d) carrying both `170 × 120 × 55 mm` boxes (H755 and Pi 5) on silicone dampers, glands down; the DLC run must be measured. *Option 2:* the `H755` box on the subframe tray (c) or the plate (d), and the `Pi 5` box on the left crash bar (f) or the rear rack (e), connected over the terminated platform CAN (`FDCAN2`), which shortens the camera lead to the front.
- **Rules for (c).** A rigid tray inside the subframe outline (under the rear fender/tail, between or on the subframe rails, left of centre), bolted at two or more points; a half-circle extension behind the tail only if the tray does not fit, then triangulated so it does not ring. The box sits on silicone mounts on the tray; glands point down and the box must not collect road spray.
- **IMUs (C1, C2) never on a damped tray, pannier plate, rack or extension.** The chassis IMU (M7, Board C2) and the M4's own IMU (D-042, Q-023, C1-IMU) each sit in their own box, bolted rigidly to the main frame near the centre of mass and aligned with the bike's axes. Reason: a gyro sees the same angular rate anywhere on a rigid body, but an accelerometer at an offset r also sees ω × (ω × r) + α × r, and a bracket that flexes adds its own resonance. Record the offset r and the axis directions in the session metadata (§9). The shielded run to the main box stays short (`≤ ~30 cm`); if the frame point is farther from the box, check the run length on the desk with the logic analyzer before the build. For the I2C chassis IMU keep the run short or use a differential I2C extender (§3.4).
- **Vehicle CAN stub.** The DLC Y-cable is an unterminated stub on the vehicle bus; its `< 50 cm` limit (§3.1) stays. The DLC is reported to be under the seat near the battery (**CONFIRM**, §10 item 1); every run from the DLC to a candidate box is **measure; the `< 50 cm` stub limit decides**. Never add termination to extend it. CAN itself is differential and twisted: a longer run adds little noise pickup, and the CAN error counters and `can_bus_off_count` in telemetry show if it does.
- **Platform CAN** (`H755 FDCAN2` ↔ bike `ESP32-S3` and `Raspberry Pi 5`): a proper bus with `120 Ω` at both physical ends, so its length is not the limit.
- **Power.** The ignition-switched tap, fuse, reverse protection, TVS and LC filter sit at the box input (§3.2, Board A). The ground goes on its own wire straight to the battery negative (star point, no chassis return, no second ground path for the same unit). At well under 1 A the voltage drop of a longer run does not matter. C1 and C2 each get their own fused branch (§3.4).
- **Front-end lines get longer** (LED rings beside the gauge, mirror LEDs): the `WS2812B` data line is the sensitive one (single-ended, `800 kHz`). Drive it through a 5 V buffer (`74AHCT125` class, also the 3.3 → 5 V level shift, on C1-IO) with a `~330 Ω` series resistor, run it twisted with its ground (`Data + GND`), and leave steering slack through the head stock. Test it at full length on the desk first.
- **Rear-end lines get shorter:** both `HLK-LD2451` blind-spot radars (`DT-0508` boxes facing rear-left and rear-right, mounting angle from the radar datasheet), the Q-033 indicator inputs (D-075 item 4, opto-isolated on C1-IO) and the GPS antenna (on top under plastic, never under metal, clear of the ESP32 antenna) are close to a rear box. The immobilizer relay (`DT-0508`) goes next to the starter relay wherever that is (**CONFIRM**), coil circuit only (invariant 6).
- **Noise sources to keep the boxes and cables away from:** ignition coil and plug lead (`≥ 15 cm`), regulator/rectifier, starter motor cable (high cranking current; the `ACS758LCB-200B` is a series element in it, with its own mounting and fuse/cable plan, **CONFIRM** on the bike), fuel pump and injector wiring. Magnetic near-field coupling falls off steeply with distance, so a rear box is quieter than one near the engine.

**Measure on the bike before Q-034 is decided** (photos + dimensions; never commit photos showing the plate or the location): free volume under the tail/rear fender and between the subframe rails (c); whether the left-side carrier bosses exist, their spacing and thread depth (d); cavity dimensions behind the left side cover (h); muffler distance on both sides; DLC position and its cable path to each candidate (run lengths); battery, starter relay, fuse box and regulator/rectifier positions; the indicator feed wires at the rear; a rigid steel frame point near the centre of mass for the C1 and C2 boxes. Fig. 6 is the sketch to annotate with the numbers; Fig. 7 the IMU boxes.

**Measurement sheet (fill in on the bike, keep the photos out of the repos):**

| # | Measure | Unit | Needed by | Value |
|---|---|---|---|---|
| M1 | DLC position (which side, under the seat?), connector pin count and type | — | §3.1, G2 | |
| M2 | DLC → candidate (c) tray: shortest cable path | cm | the < 50 cm stub rule | |
| M3 | DLC → candidate (d) plate | cm | same | |
| M4 | DLC → candidate (e) rack | cm | same | |
| M5 | Free volume under the tail between the subframe rails: L × W × H | mm | (c), 170×120×55 box + dampers | |
| M6 | Rear wheel at full bottoming: lowest point of the free volume above the tyre | mm | (c) clearance (travel ~150 mm) | |
| M7 | Left carrier bosses: present? pitch, thread, depth | mm | (d) | |
| M8 | Muffler/header distance from (c), (d), (e) | cm | ≥ 15 cm rule | |
| M9 | Cavity behind the left side cover: L × W × depth | mm | (h) small boxes | |
| M10 | Frame point for the IMU boxes: location, flat area, bolt option; distance to the Main Box candidate | mm / cm | Fig. 7, ≤ ~30 cm runs | |
| M11 | Ignition-switched tap point and the fuse-box location | — | §3.2, G1 | |
| M12 | Starter relay location; coil-wire access without cutting | — | Fig. 9, G6e | |
| M13 | Rear indicator feed wires: colour, connector, access | — | G6d | |
| M14 | Battery negative terminal access for the star ground | — | §3.2 | |
| M15 | Gauge area for the LED rings: free arc, cable path to the rear | cm | G6a | |
| M16 | Mirror stem: LED fixing option, cable path | — | G6b | |

### 4.2 Main Box internal layout (H755 build; Fig. 3)

Proposal derived from the procurement list v2.9 design rule and the board sizes; nothing here is bought yet, so measure the real box before drilling.

- **Layer 1 (box floor):** the `NUCLEO-H745ZI-Q` (133.3×70 mm) on M3 6–8 mm standoffs, ST-LINK USB end toward a box side that stays reachable when mounted. Beside the Nucleo a free strip of roughly 170×43 mm takes **C1-IO** (60×40 mm laid flat, its own fused branch and its own connector to the M4 pins), the screw terminals and the Deutsch tails. Whether C1-IO really fits there with the gland bodies is **CONFIRM** (§10 item 11).
- **Layer 2 (mezzanine, M3 18–20 mm hex columns over the Nucleo):** **Board A** (50×70) and **Board B** (70×90) side by side on long-pin stacking headers from CN7–CN10. Together they are 160×70 mm over a 133×70 board, so Board B overhangs the Nucleo end opposite the ST-LINK; support that end with its own columns to the floor. A ↔ B by JST-XH; Board B's Scale 1B port is a separate connector. Unplugging Board B reverts the hardware to Scale 1A.
- **Height check:** 8 (standoff) + 1.6 (Nucleo) + 20 (column) + 1.6 (mezzanine) ≈ 31 mm of structure in a 55 mm box, so mezzanine parts may stand at most ~12–13 mm under the lid gasket (the procurement list's "~42 mm total stack" leaves ~13 mm). Lay the 470 µF capacitor flat and keep the buck module's inductor low; measure before committing.
- **Glands:** six PG7 on the edge that points down when mounted (Fig. 3 G1–G6, listed in §3.5); a ferrite clamp outside each. The box must not collect spray on the cable side; the lid gasket faces up.
- **Mounting:** the box sits on silicone dampers (bobbins) on the tray/plate chosen by Q-034. The IMUs are **not** in it (§4.1, Fig. 7).
- **Keep out:** 12 V return currents never share a trace or wire with `AGND`; the immobilizer latching relay is in its own box near the starter relay (only its coil drivers are on C1-IO, Fig. 9).

## 5. Firmware and software setup

| Step | Command / action | Repo |
|---|---|---|
| Build + flash (real CAN) | `pio run -e esp32-s3-devkitc-1 -t upload` (needs `platformio_local.ini` with `AP_PASSWORD`) | vehicle-connectivity-node |
| GPS bring-up (until the pins are confirmed) | `pio run -e esp32-s3-devkitc-1-gps -t upload`, procedure in §7.3 | vehicle-connectivity-node |
| Desk test without the bike | `pio run -e esp32-s3-devkitc-1-mock -t upload` (synthetic telemetry) | vehicle-connectivity-node |
| Host tests before every flash | `scripts/native_tests.sh` (or `pio test -e native`) | vehicle-connectivity-node |
| Phone | Install the `vehicle-mobile` APK, pair with `Honda-CL250-Telemetry` | vehicle-mobile |
| Server | `export VEHICLE_API_TOKEN=…; uv run vehicle-server serve`, or `uv run vehicle-server import <zip>` offline | vehicle-server |
| Check a session | `uv run vehicle-server report <session_id>` (gaps, MTU, CAN health) | vehicle-server |

What the tester does on its own, with no setting to change (conn README, Q-018, D-030):
- After boot it **listens only** until it has 2 s of clean traffic (no lost frames, no other tester, no unsolicited ECU answer). Only then does it send its first request.
- It sends only what `tester_policy` allows, through `vehicle_cl250_frame_allowed()` (D-020).
- It latches off when it sees another tester or repeated bus-offs. The latch survives resets until the next power cycle.

## 6. Bring-up sequence (each gate passes before the next; Fig. 12)

| Gate | Where | Do | Pass when |
|---|---|---|---|
| B0 | Desk | Native tests; mock firmware; phone receives v3 telemetry + IMU blocks; record a session; `vehicle-server import` it | Report `ok`, IMU gap count 0 at rest |
| B1 | Desk, bench supply 12-14 V | Power chain only: fuse, TVS, buck; check 5 V under load; reverse the input once (must not conduct) | 5 V stable, no heat on the buck |
| B2 | Desk | Real firmware, transceiver connected, no bus | Stays in its listen window, sends nothing |
| V0 | Bike, ignition on, engine **off** | Plug the Y-cable, power the unit, phone connected | ECU present, all 5 DIDs valid, no latch flags, no bus-off |
| V1 | Bike, engine idling, **closed area** | First polling session with the engine running (VWP §3.2) | RPM changes with a throttle blip; CAN health clean for ≥ 5 min |
| V2 | T0 static set | VWP §7 (sleep current, cranking, idle, warm-up from cold) | §7 checks below |
| V3 | T1 low speed, closed lot, 0-30 km/h (VWP §7.3) | CAN speed against the gear-ratio formula (VWP §2.3); ignition cut mid-session | Deviation explained (speedometer error, VWP §2.3); after the cut the phone keeps the session and the report shows the gap |

Gates B0, V0 and V1 can be checked from a recorded session: `uv run vehicle-server bringup <session_id> --gate V0` (or `GET /sessions/{id}/bringup?gate=V0`, also shown in vehicle-analyzer's Recorded sessions view) prints one line per "Pass when" criterion. "At rest" (B0) and the throttle blip (V1) stay `manual`: the command shows the values, you judge them.

Recommended first contact with the bike: the §7.1 listen-only capture, before V0. Its image never transmits, so it is the lowest-risk first connection and it answers Q-001 before the tester polls.

Road tests (T2, T3) come only after V3 passes, and the rules in §8 apply. T4 is out of scope for this build.

## 7. What to measure in the first sessions

| Measurement | Why | How with this build |
|---|---|---|
| Tester step gap | D-053 assumes `client_step_max_ms` = 10 ms; conn's step is unbounded (conn README) | D-058 item 2: the poller's step-gap max and over-10-ms count in BLE telemetry v4 (server report, §7.2); the G0.1 serial report still gives the per-module `loop()` durations; scope on `GPIO8` |
| ECU round trip | D-029, A-4 polling budget (assumed 20 ms) | D-058 item 1: per DID min/max/sum/count and 0x78 count, one rotating record per BLE telemetry v4 packet (server report, §7.2) |
| Passive broadcast traffic | Q-001 (VWP §5.5 step 1: 5 min listen-only) | D-058 item 4: flash the `esp32-s3-devkitc-1-listen-only` env (no TX at all), log USB serial for 5 min with the ignition on, then flash the tester env again (§7.1). Record the result on Q-001 |
| PID support, vehicle info, DTCs | A-4: MAP, fuel trim, wheel speed | D-059: flash the `esp32-s3-devkitc-1-probe` env once (0x01 bitmaps, 0x09, 0x19, 0x22 0xF4xx support DIDs, segmented answers with one FC.CTS); the serial output goes into defs with `/signal-change`, `verified: false`. Never commit the VIN |
| Sleep current | VWP §4.3, < 1 mA | Multimeter or INA226 in series, ignition off |
| Engine-on noise | VWP §4.2 | The same idle recording with the engine stopped and running; compare CAN error counters and IMU noise |
| IMU zero and axis offset | VWP §3.4, §5.4 | Upright on flat ground, then a known tilt (side stand) |
| BLE loss | D-045 | Server report: seq and tick gaps per session |
| GPS rate, BLE path and the step gap with GPS notify | D-060 item 2 (10 Hz; step gap measured with the GPS running), D-062, D-063 | §7.3: serial `[GPS]` report at the desk, a bonded phone session uploaded to the laptop, then the step gap on the bike |

### 7.1 Listen-only capture (Q-001, D-058 item 4)

Nothing else on the DLC (no scan tool, no tester build). From `vehicle-connectivity-node`, with `platformio_local.ini` in place:

```bash
pio run -e esp32-s3-devkitc-1-listen-only -t upload
# 921600 baud. Write the log outside every repo (D-033); stop it after the FINAL lines (300 s).
mkdir -p "$VEHICLE_DATA_DIR/captures"
pio device monitor -e esp32-s3-devkitc-1-listen-only | tee "$VEHICLE_DATA_DIR/captures/q001-$(date +%Y%m%d-%H%M).csv"
# afterwards, back to the tester:
pio run -e esp32-s3-devkitc-1 -t upload
```

Run it once with the ignition on and the engine off, and once idling. Line format (conn `src/CanCaptureCore.h`): `F,<t_us>,<id>,<S|X>,<dlc>,<data>` per frame; `S,…` per-ID rows (count, min/max period in ms, `W` = an OBD functional request ID, D-040) every 10 s; `S,END,…,frames=,ids=,overflow=,lost=,dropped=`; the same once as `FINAL,…` after 300 s.

| FINAL shows | Means | Record on Q-001 |
|---|---|---|
| `frames=0` | No passive broadcast on the DLC | "none found", with the date and ignition/engine state |
| Rows with a steady period | Broadcast frames: ID, DLC, period | IDs and periods; they go into `dbc/cl250.dbc` only through `/signal-change` |
| One frame repeated back to back | Its sender gets no ACK (conn never ACKs in listen-only): the ECU broadcasts with nobody else on the bus | The ID; a finding too (D-058 item 4) |
| A `W` row | Another tester is on the bus | Stop: remove it before any tester session (§8) |
| `lost` or `dropped` > 0 | The capture missed frames or serial lines | Repeat; note the counts |

The capture never transmits: no `twai_transmit` in its image, and the listen-only errata workaround keeps the controller error passive so it sends no error flag either (CI checks both). Still to verify on the bench: a CRC-corrupted frame from the HIL with a scope on the bus, and a 10-minute run without a watchdog reset.

### 7.2 Tester statistics (BLE telemetry v4, D-058 items 1-2)

Record a normal session with the tester env (V0/V1), upload or import it, then:

```bash
uv run vehicle-server report <session_id>
```

`tester_stats` in the report:
- `step_gap_max_ms`, `step_gap_over_count`: since-boot maximum gap between two poller steps and the count of gaps above `client_step_max_ms` (10 ms). A count above 0 means the D-053 assumption does not hold for conn; compare with the G0.1 serial report to find the slow module.
- `rtt["0xXXXX"]`: per DID `min_ms`, `max_ms`, `avg_ms`, `count`, `nrc78_count`, from the last record seen for that DID. One step is included in every sample. Requests answered after 0x78, and requests sent within `response_timeout_max_ms` (2 s) after a timeout, give no sample. Compare `max_ms` with `assumed_round_trip_ms` (20 ms); a larger value changes the D-029 budget (A-4).

`vehicle-server bringup <session_id> --gate V0` (or `V1`) shows both items as warnings next to the gate checks.

### 7.3 GPS bring-up and the step gap with GPS notify (D-060, D-062, D-063)

Steps 1-4 run at the desk (no bike). Step 5 turns the result into the pin confirmation, and step 6 runs on the bike with the build CI checks.

**1. Wiring.** As in §3.3: module TX → `GPIO15`, module RX → `GPIO16`, common GND, the module powered as its breakout board specifies (3.3 V logic on its UART). The antenna needs a clear sky view (outdoors or at a window); a cold start can take minutes to the first fix.

**2. Serial report.** With `CONN_GPS_PINS_CONFIRMED=0` the firmware never installs the UART, so set it to `1` in the `esp32-s3-devkitc-1-gps` env **in your local copy only**, then from `vehicle-connectivity-node`:

```bash
pio run -e esp32-s3-devkitc-1-gps -t upload
pio device monitor -e esp32-s3-devkitc-1-gps
# afterwards: git checkout platformio.ini   (the confirmed pins arrive through a PR, step 5)
```

conn first tries 38400 baud, then the factory 9600 with a CFG-PRT that moves the receiver to 38400, and configures UBX only with NAV-PVT at 10 Hz (RAM only; conn sends no CFG-GNSS, so the receiver's default GNSS set applies). Every 10 s it prints one line with the rate, fix and error counters only, never speed, heading or position:

`[GPS] link=<state> pvt/s=<rate> fix=<type> sv=<count> ck_err=<n> len_err=<n> ovf=<n> lost=<n>`

| Field | Pass | If not |
|---|---|---|
| `link` | `OK` | `PENDING`: not configured yet, wait. `NO_RECEIVER`: no valid UBX at 38400 or 9600; check TX/RX crossed, GND, supply. `(UART install failed)`: the driver did not install on these pins |
| `pvt/s` | `10.0` on every line for ≥ 5 min with `fix=3` | Record the value and `sv`: the receiver does not hold 10 Hz with its default GNSS set (D-060 item 2 asks for 10 Hz; VWP §3.5 needs ≥ 5 Hz). A decision, not a code fix |
| `fix` | `3` (3D) after the first fix | Stays `0`-`2`: sky view or antenna |
| `sv` | Record it | — |
| `ck_err`, `len_err` | `0` and not rising | Noise or a baud mismatch on the wires |
| `ovf` | `0` | The UART driver's buffer overflowed: the GPS task was starved |
| `lost` | `0` | The receiver went silent for 3 s; check power and the connector |

**3. Phone, bonding and the `gps` subscription (Android).** Install the vehicle-mobile APK (v0.2.0 or later) and connect to `Honda-CL250-Telemetry`. The app starts pairing on connect (Just Works, no passkey); telemetry and IMU work without it, the `gps` characteristic does not (D-062). Record a session of ≥ 5 min and check:
- the session has a non-empty `gps.csv` next to `telemetry.csv` and `imu.csv`;
- after a disconnect and reconnect, GPS rows arrive again: conn clears the subscription on every connect, so the app must subscribe again (D-062 item 1).

iOS: vehicle-mobile has no iOS project yet (§10 item 8).

**4. Upload to the laptop and the report.** On the laptop:

```bash
export VEHICLE_API_TOKEN=…        # same token in the app's Settings
uv run vehicle-server serve       # listens on 0.0.0.0:8000
ipconfig getifaddr en0         # the laptop's LAN IP (macOS, Wi-Fi)
scutil --get LocalHostName     # its mDNS name, add ".local"
```

In the app's Settings set the server URL to `http://<LAN IP>:8000` (or `http://<name>.local:8000` if the phone resolves it), phone and laptop on the same Wi-Fi; allow incoming connections if the macOS firewall asks. Then:
- upload the session; it must succeed (D-063 allows a private address or a `.local` name);
- set a non-local URL (for example `https://example.com`) and upload again: the app must refuse before any network call, naming D-063; set the local URL back;
- `uv run vehicle-server report <session_id>`. The GPS lines read `GPS: N block(s), L lost or MTU-skipped (p%), effective rate R Hz, usable for the speed check U%` and the fix types.

Pass: the effective rate matches the serial `pvt/s`; lost or MTU-skipped near 0 with the phone next to the unit; no decode error, parse error, UART overflow or app/server mismatch. Many lost or skipped blocks with a good serial rate mean radio loss or an MTU too small for the GPS block (the node advances `seq` for a block it skips, D-062 item 2).

**5. Confirm the pins.** Once steps 2-4 pass, the pins go into §3.3 without **CONFIRM**, conn sets `CONN_GPS_PINS_CONFIRMED=1`, GPS moves into the main tester env and the `-gps` env is removed (conn `platformio.ini` comment), each through a PR.

**6. Step gap with GPS notify on (bike).** D-060 item 2 measures the step gap of D-058 with the GPS running. With the main tester env from step 5 and the phone bonded and subscribed to `gps` for the whole session, record ≥ 5 min at V0 (ignition on, engine off) and at V1 (idling, closed area, §8). The baseline is a V0/V1 session under the same conditions with the tester env before step 5 (no GPS). Read `step_gap_max_ms` and `step_gap_over_count` in each report (§7.2): the difference is the cost of the GPS task and its notify. An over count above 0 is a measurement for D-053 and rt-core, recorded with the session conditions, not a reason to change the tester.

**What to record.** The pins used; `pvt/s`, `sv` and the fix time from step 2; the phone model and Android version, whether pairing, the reconnect and the D-063 refusal behaved as described; the report's GPS line; the step-gap pairs of step 6. Numbers only: `gps.csv`, sessions and screenshots never go into a repo or an issue (D-033, D-060 item 5).

## 8. Safety rules on the bike

- **One tester only, and it only reads** (D-037). Never connect a scan tool, another dongle or a second build while conn is on the DLC. conn latches off if it sees one, but the rule is to not let it happen.
- Nothing that writes, clears, resets, unlocks, controls or reprograms the ECU, ever (D-020). The gate enforces it; do not flash a firmware that bypasses it.
- First engine-on session in a closed area, engine idling (VWP §3.2).
- Check that recording works **before** riding, never while riding. Full protective gear; T4 limit tests only on a closed area with a second person (VWP §7, §12).
- The unit must not change how the bike behaves: power from the ignition-switched line, a 2 A fuse, the harness never cut, one plug to remove it.

## 9. Data handling

- **Session = one ride.** Files per `vehicle-mobile/docs/session-format.md`: `meta.json`, `telemetry.csv`, `events.csv`, `summary.json`, `imu.csv`, and `gps.csv` when the GPS block is subscribed.
- Fill the metadata of the Phase 0 plan §3.2 / VWP §6.2: ambient temperature and weather, tyre pressures, fuel level, rider weight and load, vehicle configuration, condition label (healthy / fault type), route type, notes. Add the unit and IMU mounting (§4).
- **Never commit ride data to any repo** (all repos are public, D-033). Sessions live under `$VEHICLE_DATA_DIR` on the server machine, with a second copy off the laptop.
- **GPS (D-060):** a u-blox NEO-M8N on a conn UART (UBX-NAV-PVT, 10 Hz; pins **CONFIRM**, §7.3). Only ground speed, heading, their accuracies, fix type and satellite count leave conn, on the BLE GPS block; latitude, longitude and height never do. The phone writes them to `gps.csv`, which goes to the server with the session. A speed + heading series can rebuild the route's shape, so sessions stay on your own machine and never in a repo; vehicle-mobile uploads a session with `gps.csv` only to a local server (D-063). _(D-076, provisional: latitude, longitude and height may later go to the user's own servers and to the LLM through vehicle-mcp; until its `/signal-change` and the D-063 guard change are implemented, the behaviour above is what the code does.)_

## 10. Open items (fill in, then move facts into the sections above)

| # | Item | Blocks |
|---|---|---|
| 1 | CL250 DLC location, connector type and pinout | §3.1, Y-cable |
| 2 | Parts actually on hand: ESP32-S3, MPU-6050, SN65HVD230 and NEO-M8N recorded (2026-10-11); board and IMU (MPU-6500) confirmed on the desk (2026-10-15); the board marked "MPU-6590" (2026-10-23) still needs its `WHO_AM_I` check; the transceiver's termination resistor, the Y-cable, the power chain, the enclosure and the phone are still **CONFIRM** (§2) | Build start |
| 3 | Ignition-switched tap point on the CL250 harness | §3.2 |
| 4 | C1-IMU and C2 box locations (rigid frame point near the centre of mass) and axis directions | §4, §4.1, metadata |
| 5 | ~~GPS source and privacy handling~~ decided in D-060; UART pins still **CONFIRM** (procedure §7.3) | T1 speed check, §9 |
| 6 | ~~Listen-only capture tool for Q-001~~ decided in D-058 item 4 (conn `-listen-only` env) | §7 |
| 7 | ~~ECU round-trip instrumentation~~ decided in D-058 items 1-3 (BLE telemetry v4) | D-029, A-4 |
| 8 | vehicle-mobile has no iOS project yet (Android only), so the D-062 bonding check on iOS waits for one | §7.3 step 3 on iOS |
| 9 | Main enclosure placement for the H755 build (Q-034): the measurements of §4.1 | §4.1, Wave 1 on-bike build |
| 10 | Schematic CONFIRM/TBD items (vehicle-workspace `models/fusion-lib/SCHEMATIC-README.md`, D-082): `L1` value; `+3V3` source for off-box sensors; Nucleo `AGND` tie (UM2408); `ACS758LCB-200B` mounting and fuse/cable plan; `LJ12A3` unloaded output voltage; `HLK-LD2451` supply and UART level; `IND_L/IND_R` tap point on the harness; H755 pin map (CubeMX) | S1-S3 schematics, Wave 1/2 build |
| 11 | C1-IMU and C2 boxes: one small IP65/IP67 box type for both (the `DT-0505`/`DT-0508` are `126×136` mm, no IP rating stated, §3.4), product **CONFIRM** with Q-034; C1-IO fit beside the Nucleo (§4.2) **CONFIRM**; ~~D-082 item 6 (immobilizer fail state)~~ confirmed by D-097 | C1/C2 build, §4.1 |
| 12 | Connector and cable plan (§3.5): Deutsch DT as the box-wall connector (type), G5 core count (4 vs 6), whether G6a–G6e share one harness gland or get their own, the relay-box location, the measurement sheet M1–M16 (§4.1) | Wave 1 order, S1–S4 |

## 11. Later: moving to rt-core

When the NUCLEO-H755ZI-Q exists (D-072, Q-019 resolved), rt-core on its Cortex-M7 becomes the tester (D-021). conn is then built with `-e esp32-s3-devkitc-1-no-tester` (no TWAI driver at all), so there are never two testers. rt-core needs two transceivers (vehicle FDCAN1, platform FDCAN2, A-5), takes over microSD logging (D-045) and republishes the vehicle signals on the platform bus (D-056).
