Status: idea note, not a decision

# Parked (Key-Off) Current Budget and Power-Down Options (T73)

Idea note (Gemini, 2026-11-27), **not a decision**. Nothing in this document takes effect without a recorded `D-xxx` decision in `DECISIONS.md`.

**Known conflicts with recorded decisions:** none. This note aligns with:
- **Invariant 3 & D-118:** `vehicle-safety-node` (`STM32G474RE`) remains isolated from `vehicle-rt-core` (`STM32H743ZI`) and `vehicle-linux-node` (Raspberry Pi 5) with its own supply branch and reset/clock domain.
- **Invariant 6 & D-082 item 6 / D-097:** the immobilizer uses a bistable (latching) relay in the starter-relay coil circuit only; it holds its state with zero coil holding current when parked and never cuts a running engine.
- **`vehicle-work-plan.md` §4.3 & `hardware-integration.md` §3.2:** current baseline taps an ignition-switched line (`KL15`) and sets a **< 1 mA** key-off sleep current target (otherwise the supply must be switched with the ignition).
- **D-033 & D-125:** English only; no personal data, no real ride data, and no copyrighted manual pages quoted.

---

## 1. Per-Node Low-Power Current (Datasheet Chip Figures)

Every numeric value below is a **bare-chip or documented board-level figure** from the cited datasheet or official documentation. Development-board extras (regulators, ST-LINK debuggers, USB-UART bridges, power LEDs, pull-ups, buck converters) are listed separately in Section 1.2 as **unknown until measured** and are never guessed.

### 1.1 Silicon and Subsystem Low-Power Modes

| Node / Component | BOM Role | Low-Power Mode | Stated Current / Power | Conditions & Notes | Source (Document + Section / Table) |
|---|---|---|---|---|---|
| **Raspberry Pi 5 (8 GB)** | `vehicle-linux-node` (`hardware-procurement-list.md` On hand, Part 5A) | Halted, default (`POWER_OFF_ON_HALT=0`) | ~1.2–1.6 W (~240–320 mA at 5 V) (**CONFIRM** on our unit) | PMIC keeps primary 3.3 V / SoC rails in standby for HAT compatibility; community/bench range, not an official min/max spec | Official behaviour: Raspberry Pi Documentation, *Raspberry Pi Bootloader Configuration* (`POWER_OFF_ON_HALT`). Numeric power range: community bench measurements (**CONFIRM** on our Pi 5 8 GB) |
| **Raspberry Pi 5 (8 GB)** | `vehicle-linux-node` | Halted, `POWER_OFF_ON_HALT=1` + `WAKE_ON_GPIO=0` | PMIC outputs off; ~10–50 mW (~2–10 mA, up to ~10–40 mA depending on revision/peripherals at 5 V) (**CONFIRM** on our unit) | PMIC turns off all internal regulator outputs, **but the external 5 V input rail stays live** on the 40-pin header/HATs; wake requires onboard power button or pulling `GLOBAL_EN` low | Official behaviour: Raspberry Pi Documentation, *Raspberry Pi Bootloader Configuration* (`POWER_OFF_ON_HALT`, `WAKE_ON_GPIO`). Numeric current: bench measurements (**CONFIRM** on our Pi 5 8 GB) |
| **ESP32-S3 (bare chip)** | `vehicle-connectivity-node` (`ESP32-S3 DevKitC-1`, On hand, Part 4) | Light-sleep | **240 µA** (typ) | `VDD_SPI` and Wi-Fi/BT digital baseband powered down, digital peripherals paused, GPIOs high-Z | Espressif *ESP32-S3 Series Datasheet*, *Electrical Characteristics — Current Consumption in Low-Power Modes* |
| **ESP32-S3 (bare chip)** | `vehicle-connectivity-node` | Deep-sleep (RTC memory + RTC peripherals ON) | **8 µA** (typ) | RTC timer and RTC memory retained; radio off | Espressif *ESP32-S3 Series Datasheet*, *Electrical Characteristics — Current Consumption in Low-Power Modes* |
| **ESP32-S3 (bare chip)** | `vehicle-connectivity-node` | Deep-sleep (RTC memory ON, RTC peripherals OFF) | **7 µA** (typ) | Minimum state-retaining deep sleep; radio off | Espressif *ESP32-S3 Series Datasheet*, *Electrical Characteristics — Current Consumption in Low-Power Modes* |
| **ESP32-S3 (bare chip)** | `vehicle-connectivity-node` | Deep-sleep with ULP coprocessor active | **~22–190 µA** (typ, depends on ULP-FSM vs ULP-RISC-V duty cycle; **CONFIRM** exact table row) | Used only if ULP polls sensors/wake lines | Espressif *ESP32-S3 Series Datasheet*, *Electrical Characteristics — Current Consumption in Low-Power Modes* |
| **ESP32-S3 (bare chip)** | `vehicle-connectivity-node` | Power-off (`CHIP_PU` = low) | **1 µA** (typ) | Chip disabled | Espressif *ESP32-S3 Series Datasheet*, *Electrical Characteristics — Current Consumption in Low-Power Modes* |
| **ESP32-S3 (bare chip)** | `vehicle-connectivity-node` | BLE advertising / maintained connection | **Unknown until measured** for our advertising interval; datasheet Modem-sleep baseline ~10–30 mA (CPU clock dependent), Light-sleep baseline 240 µA + periodic radio TX/RX bursts | Deep-sleep powers off the BLE radio/link controller, so BLE advertising cannot run continuously in Deep-sleep | Espressif *ESP32-S3 Series Datasheet*, *Current Consumption in Active / Modem-sleep / Low-Power Modes* |
| **STM32H743xI** | `vehicle-rt-core` (`NUCLEO-H743ZI2`, Part 1, D-118) | Stop (`D1Stop / D2Stop / D3Stop`, Flash low-power) | **1.4 mA** typ (SVOS5), **1.95 mA** typ (SVOS4), **2.85 mA** typ (SVOS3) at 25 °C | All domains in Stop; increases sharply at 85–125 °C (max ~7.2 mA at 85 °C SVOS5). Selective `D1Standby/D2Standby/D3Stop` (SVOS5): typ **0.17–0.57 mA** at 25 °C | STMicroelectronics **DS12110** (*STM32H743xI/G Datasheet*), *Electrical Characteristics*, Table 26 (*Typical and maximum current consumption in Stop mode, regulator ON*) |
| **STM32H743xI** | `vehicle-rt-core` | Standby (Backup SRAM OFF, RTC/LSE ON) | **2.95 µA** (typ) at 25 °C | 1.2 V core domain off; higher with Backup SRAM ON or elevated junction temperature (tens of µA at 85–125 °C) | STMicroelectronics **DS12110**, *Features* (p. 1–2) & *Electrical Characteristics*, Table 27 (*Typical and maximum current consumption in Standby mode*) |
| **STM32G474xE** | `vehicle-safety-node` (`NUCLEO-G474RE`, Part 1 & 3A, D-118) | Stop 0 (main regulator ON) | **~100–120 µA** (typ, 3 V, 25 °C; **CONFIRM** exact DS12288 rev 6 row) | Fast wakeup (~3 µs from SRAM), SRAM/registers retained | STMicroelectronics **DS12288** (*STM32G474xB/xC/xE Datasheet*), *Electrical Characteristics*, Table 31 (*Current consumption in Stop 0 mode*) |
| **STM32G474xE** | `vehicle-safety-node` | Stop 1 (low-power regulator ON, RTC OFF) | **~11–15 µA** (typ, 3 V, 25 °C; **CONFIRM** exact DS12288 rev 6 row) | Low-power regulator active, SRAM/registers retained | STMicroelectronics **DS12288**, *Electrical Characteristics*, Table 30 (*Current consumption in Stop 1 mode*) |
| **STM32G474xE** | `vehicle-safety-node` | Standby (3 V, 25 °C) | **~300–400 nA** typ without RTC; **~0.5–1+ µA** with RTC/SRAM2 (**CONFIRM** exact DS12288 rev 6 row) | 1.2 V domain off; note fallback `NUCLEO-G431RB` (D-118) requires checking **DS12589** | STMicroelectronics **DS12288**, *Electrical Characteristics*, Table 32 (*Current consumption in Standby mode*) |
| **STM32G474xE** | `vehicle-safety-node` | Shutdown (3 V, 25 °C) | **~130 nA** typ without RTC; **~300–500 nA** with RTC (**CONFIRM** exact DS12288 rev 6 row) | Internal regulator and BOR off; wake via WKUP pins or NRST | STMicroelectronics **DS12288**, *Electrical Characteristics*, Table 33 (*Current consumption in Shutdown mode*) |
| **SN65HVD230** | CAN transceiver ×4 on bike (H743 FDCAN1/2, G474 FDCAN1, ESP32 TWAI; Part 1 & On hand) | Standby (`V_RS = V_CC`) | **370 µA** (typ), **600 µA** (max) **per transceiver** | Driver off, receiver stays active for bus wake. **Module caveat:** many breakout boards tie pin 8 (`Rs`) to GND through a fixed resistor, locking high-speed mode and preventing standby unless modified (**CONFIRM** on received boards). Four transceivers in standby draw ~1.48 mA typ (2.4 mA max) at 3.3 V | Texas Instruments **SLOS346** (*SN65HVD230, SN65HVD231, SN65HVD232 3.3-V CAN Transceivers*), *Electrical Characteristics* (`I_CC`, Standby) |
| **TJA1050 + MCP2515** | Pi 5 SPI CAN module alternative (Part 5A) | `TJA1050` Silent mode (no standby mode exists); `MCP2515` Sleep mode | `TJA1050`: **no standby mode** (Silent draws full recessive supply current, several mA — **CONFIRM** exact NXP table row); `MCP2515`: **1 µA** (typ) | `TJA1050` dominates the module whenever 5 V stays applied; `MCP2515` sleep does not cut `TJA1050` quiescent draw | NXP *TJA1050 High-speed CAN Transceiver* datasheet (Silent mode / Supply current); Microchip **DS21801** (*MCP2515 Stand-Alone CAN Controller*), *Electrical Characteristics* (Sleep mode) |
| **Waveshare 2-CH isolated CAN HAT** | Pi 5 CAN HAT alternative (Part 5A) | Standby / halted Pi | **Unknown until datasheet/board check (CONFIRM)** | Isolated DC-DC converters typically have significant no-load quiescent draw if the Pi 5 5 V rail stays live | `hardware-procurement-list.md` Part 5A (exact transceiver/isolator BOM not yet verified on board) |
| **MPU-6500** | Board `C1-IMU` (G474 safety IMU, Part 3A) | Full-chip Sleep mode | **6 µA** (typ) at `V_DD = 1.8 V`, 25 °C | Gyro, accel, and internal clocks off; serial interface responsive | InvenSense **PS-MPU-6500A** (*MPU-6500 Product Specification*), Section 3 (*Electrical Characteristics — D.C. Characteristics*) |
| **MPU-6500** | Board `C1-IMU` (also candidate for park-mode WoM) | Low-Power Accelerometer / Wake-on-Motion | **7.27 µA** typ (0.98 Hz ODR) to **18.65 µA** typ (31.25 Hz ODR) at `V_DD = 1.8 V`, 25 °C | Formula in datasheet: `I_DD ≈ 6.9 + 0.376 × ODR_Hz` µA (gyro off) | InvenSense **PS-MPU-6500A**, Section 3 (*Electrical Characteristics — D.C. Characteristics*) |
| **On-hand IMU ("MPU-6590")** | Board `C2` (H743 chassis IMU, On hand) | Sleep | **Unknown until chip identified** | Must read `WHO_AM_I` (`0x75`) first (`0x70` MPU-6500, `0x71` MPU-9250, `0x73` MPU-9255, `0x68` MPU-6050) | `hardware-procurement-list.md` On hand |
| **Bistable (latching) relay** | Immobilizer (Part 3A, Invariant 6) | Parked (locked or unlocked) | **0 mA** | Mechanical latch; coil pulsed only on state transitions | `hardware-architecture.md` §5b.3, `hardware-procurement-list.md` Part 3A |

### 1.2 Board-Level Extras (Unknown Until Measured — Not Guessed)

On prototype builds using off-the-shelf development boards and breakout modules, **board-level parasitic draw usually exceeds bare-chip sleep currents by 1–3 orders of magnitude**. Every item below is **unknown until measured** on our actual boards:

1. **12 V → 5 V buck converters (Board A and Pi 5 mezzanine):** `HW-788` (6–100 V, 2 A) or `LM2596HVS` (4.5–53 V, 3 A) on Board A; `HCW-P715` / `SY8205` (5 V, 5 A) on the Pi 5 stack. No-load input quiescent current $I_Q$ at 12.6 V and light-load switching losses are not guaranteed on generic module boards and must be measured.
2. **On-board LDOs:** Linear regulators on `ESP32-S3 DevKitC-1`, `NUCLEO-H743ZI2`, `NUCLEO-G474RE`, `C1-IMU` local LDO, and the optional Board A external-sensor `AMS1117-3.3` class LDO.
3. **Embedded debuggers and USB-UART bridges:** On-board **ST-LINK** circuits on `NUCLEO-H743ZI2` and `NUCLEO-G474RE` (plus SWD pull-ups/leakage if left connected) and **FT232R** (or CP2102N/CH343) on `ESP32-S3 DevKitC-1`.
4. **Indicator LEDs:** Always-on power LEDs on both Nucleos, the DevKitC, buck modules, CAN breakouts, `INA226` breakouts, `microSD` module, and IMU breakouts.
5. **Peripheral modules and passive bias networks (if powered during key-off):**
   - `WS2812B` LED rings (×2, 24 LEDs total): addressable LED controller ICs draw idle quiescent current even when commanded off (dark) if their 5 V rail stays live.
   - `HLK-LD2451` 24 GHz radars (×2), `PN532` NFC reader, `NEO-M8N` GPS receiver, `INA226` current monitors (×2), `74HC123` dead-man / `74AHCT125` buffer, `PC817` optocoupler pull-ups.
   - **Board A 1 kHz battery-voltage ADC divider:** if wired directly to `KL30` (unswitched battery) instead of behind `KL15` or a switched FET, the resistor divider draws a continuous quiescent current $V_{\text{bat}} / (R_{\text{top}} + R_{\text{bot}})$.

---

## 2. CL250 Battery Capacity and Days-Parked Arithmetic

### 2.1 Battery Specification (Primary Source)

- **Source:** Local reference manual `CL250_2023_owners_manual_JP.pdf` (*Main Specifications*, printed p. 86 / PDF p. 88; kept outside public git per D-033).
- **OEM battery type:** `YTZ8V` or `FTZ8V` (12 V VRLA/AGM).
- **Rated nominal capacity ($C_{\text{nom}}$):** **12 V, 7 Ah (10HR)** (`7.0 Ah`).
- **Vehicle OEM key-off quiescent draw ($I_{\text{oem}}$):** **Unknown until measured** on the user's CL250. (`docs/ideas/cl250-technical-baseline.md` §2.5 lists `< 0.5 mA` marked **CONFIRM**; it is not printed in the owner's manual.)

### 2.2 Days-Parked Formula

Let all currents be measured **at the 12 V battery terminal** (in mA):

$$t_{\text{days}} = \frac{f_{\text{usable}} \cdot C_{\text{nom}} \cdot 1000}{24 \cdot \left(I_{\text{oem}} + I_{\text{plat,12V}} + I_{\text{self}}\right)}$$

Where:
- $C_{\text{nom}} = 7.0\text{ Ah}$ — rated 10-hour capacity (`spec`, `CL250_2023_owners_manual_JP.pdf`, printed p. 86 / PDF p. 88).
- $f_{\text{usable}}$ — fraction of nominal capacity allowed to be discharged while preserving reliable cold-cranking reserve and avoiding AGM sulfation (**estimate**, not a Honda spec; two illustrative levels shown below: `0.30` [2.1 Ah usable, conservative] and `0.50` [3.5 Ah usable, upper bound before starting reliability degrades]).
- $I_{\text{oem}}$ (mA) — stock motorcycle key-off draw (**unknown until measured**; `0.5 mA` used below as an illustrative **estimate**).
- $I_{\text{self}}$ (mA) — equivalent average AGM self-discharge current (**estimate**, temperature-dependent; ignored/folded into $I_{\text{oem}}$ in the illustrative table below for short-to-medium parks, becomes significant over multi-month storage).
- $I_{\text{plat,12V}}$ (mA) — total platform key-off current drawn from the 12 V battery terminal, including converter quiescent draw and light-load efficiency loss:

$$I_{\text{plat,12V}} = \sum_{k} \left( I_{Q,\text{conv},k} + \frac{V_{\text{rail},k} \cdot I_{\text{rail},k}}{\eta_k(I_{\text{rail},k}) \cdot V_{\text{bat}}} \right) + I_{\text{direct,12V}}$$

where $I_{Q,\text{conv},k}$ is converter $k$'s no-load 12 V input current, $\eta_k(I_{\text{rail},k})$ is its efficiency at microamp/milliamp load (often far below datasheet peak efficiency), $V_{\text{bat}} \approx 12.6\text{ V}$ resting, and $I_{\text{direct,12V}}$ covers any always-on 12 V dividers, TVS leakage, or load-switch leakage.

### 2.3 Illustrative Sensitivity Table (All Rows Marked **Estimate**)

Inputs used strictly for illustration: $C_{\text{nom}} = 7.0\text{ Ah}$ (`spec`), $I_{\text{oem}} + I_{\text{self}} = 0.5\text{ mA}$ (**estimate**), $V_{\text{bat}} = 12.6\text{ V}$ (**estimate**).

| Scenario (Illustrative) | $I_{\text{plat,12V}}$ (**estimate**) | Total $I_{\text{12V}}$ (**estimate**) | Days at $f_{\text{usable}} = 0.30$ (2.1 Ah) (**estimate**) | Days at $f_{\text{usable}} = 0.50$ (3.5 Ah) (**estimate**) |
|---|---:|---:|---:|---:|
| Ignition-switched (`KL15`) — platform disconnected | 0.0 mA | 0.5 mA | 175.0 days | 291.7 days |
| Platform at `vehicle-work-plan.md` §4.3 target (`1.0 mA`) | 1.0 mA | 1.5 mA | 58.3 days | 97.2 days |
| One unswitched low-$I_Q$ buck + sleeping MCU (`5 mA`) | 5.0 mA | 5.5 mA | 15.9 days | 26.5 days |
| Unmodified DevKit / generic buck idle (`15 mA`) | 15.0 mA | 15.5 mA | 5.6 days | 9.4 days |
| Unswitched Pi 5 (`POWER_OFF_ON_HALT=1`) + buck overhead (`50 mA`) | 50.0 mA | 50.5 mA | 1.7 days | 2.9 days |
| Unswitched Pi 5 halted with default `POWER_OFF_ON_HALT=0` (~1.2–1.6 W via buck → ~120–160 mA at 12.6 V) | 140.0 mA | 140.5 mA | **0.62 days (~15 h)** | **1.04 days (~25 h)** |

**Key arithmetic takeaway (conditional on the estimates above):**
- Leaving a Raspberry Pi 5 powered on `KL30` with its factory default `POWER_OFF_ON_HALT=0` can deplete 30 % of a 7 Ah battery in under a day.
- Even at 15 mA (typical of an unmodified dev board + generic buck on `KL30`), usable cranking margin drops below a week.
- Meeting a multi-week parked duration on a 7 Ah motorcycle battery requires $I_{\text{plat,12V}}$ to stay near or below the **1 mA** target in `vehicle-work-plan.md` §4.3 (or 0 mA via `KL15` cut-off).

---

## 3. Power-Down and Wake Architecture Options (All **Proposed**)

No option is decided here. Claude records any `D-xxx` decision after user review.

### 3.1 Candidate Options (**Proposed**)

| Aspect | **Option A (Proposed): Pure `KL15` Ignition-Switched** | **Option B (Proposed): `KL15` Wake + Timed `KL30` Self-Hold for Clean Shutdown** | **Option C (Proposed): Always-On Low-Power Park Monitor (`KL30`) + Switched Heavy Loads** |
|---|---|---|---|
| **What stays powered key-off** | Nothing in the platform (`0 mA` on `KL30`); immobilizer latching relay holds its state passively (`0 mA`) | Only a high-side `KL30` load switch / P-MOSFET gate pull-up and `KL15` sense network once the shutdown timer expires (target: tens of µA, to be measured) | Dedicated ultra-low-$I_Q$ standby rail powering a stripped-down wake controller (e.g. STM32 Standby + MPU-6500 WoM) only; Pi 5, ESP32, radars, LEDs, and transceivers stay switched off |
| **Who wakes whom on key-on** | `KL15` energizes the protected 12 V rails directly; `H743`, `G474`, `ESP32-S3`, and `Pi 5` cold-boot independently on their own branches | `KL15` rising edge turns on the high-side `KL30` switch (hardware diode-OR with MCU `HOLD` pin); `H743` asserts `HOLD` during boot; `G474` stays on its own independent fused `KL15` branch (Invariant 3) | `KL15` wakes all main rails (as in Option B); park-mode tilt interrupt from `MPU-6500` wakes only the QM park-mode path on `H743` (and conditionally powers `ESP32-S3` / future GSM for notification) |
| **Key-off / shutdown sequence** | Immediate power loss on `KL15` off; `H743` uses supercapacitor buffer (3–10 s, `hardware-architecture.md` §5b.3) to close microSD logs; `Pi 5` requires either read-only/overlay rootfs or its own UPS/supercap | `KL15` drops → `H743` detects key-off, sends clean-shutdown signal to `Pi 5` (GPIO or CAN) and closes microSD logs → waits up to bounded timeout (proposed: 20–30 s) → `Pi 5` halts with `POWER_OFF_ON_HALT=1` → `H743` releases `HOLD`, cutting `KL30` to all bucks | Same clean-shutdown cut-off for heavy loads (`Pi 5`, radars, LEDs, bucks), then `H743` enters Standby with `MPU-6500` in Low-Power WoM mode |
| **Safety-node isolation (Invariant 3, D-118)** | Preserved: `G474` has its own fused `KL15` branch | Preserved: `G474` must **not** depend on `H743`'s `HOLD` circuit; `G474` powers directly from its own fused `KL15` branch | Preserved: `G474` remains strictly on its own fused `KL15` branch; park-mode alarm stays QM on `H743` |
| **Prototype feasibility on dev boards (Wave 1–5)** | **High** — works immediately with `NUCLEO-H743ZI2`, `NUCLEO-G474RE`, `ESP32-S3 DevKitC-1`, and off-the-shelf bucks | **High** — adds one automotive high-side switch (or P-MOSFET + NPN latch) on Board A and one on the Pi 5 power rail; eliminates buck $I_Q$ and Pi 5 halted draw completely | **Low on Nucleo/DevKitC dev boards** — ST-LINK, FT232R, LDOs, power LEDs, and generic bucks make `< 1 mA` difficult without hardware modifications or a custom PCB |
| **Park-mode tilt/theft alarm** | Not supported | Not supported | Supported (matches `hardware-architecture.md` §5b.3 future goal) |

### 3.2 Additional Proposed Safeguards

- **Pi 5 EEPROM setting (Proposed):** Regardless of whether Option A, B, or C is chosen, configure `POWER_OFF_ON_HALT=1` and `WAKE_ON_GPIO=0` in the Pi 5 EEPROM so that if `5 V` ever remains present during bench testing or a stuck hold-off, halted draw is minimized rather than pulling ~1.2–1.6 W.
- **Battery-voltage sense divider (Proposed):** If `KL30` direct sensing is not required during sleep, place the `1 kHz` battery-voltage divider downstream of `KL15` (or behind a high-side switch) so it adds `0 µA` key-off.
- **Hardware low-voltage cut-off (Proposed):** In Options B and C, enforce a hardware or firmware cut-off if resting battery voltage drops below `12.2 V` (`hardware-architecture.md` §5b.3) so a software hang cannot drain the battery.

---

## 4. Measurement Procedure When Boards Arrive (Proposed, T73)

Run these measurements on the bench **before** connecting any always-on rail to the CL250 battery, and record the measured values in `docs/test-results/` with tool models, firmware commit SHAs, and supply voltages.

### 4.1 Required Equipment

- Regulated bench DC supply set to **12.6 V** (simulating resting charged AGM battery) with current limit set to 500 mA during sleep checks.
- Digital multimeter with **µA** and **mA** ranges (note shunt burden voltage on the µA range; verify the board does not brown out when switching ranges, or use a shorting jumper across the ammeter during boot before opening it in sleep).
- `INA226` breakout (Part 1 / Part 5A) for continuous logging of active-to-sleep transitions (note `INA226` resolution depends on shunt resistor; verify against the multimeter at sub-mA currents).
- Oscilloscope (optional, recommended) to observe key-off shutdown timing and key-on inrush spikes.

### 4.2 Stage 1 — Individual Component and Board Bench Measurements

Measure each item alone at ambient room temperature (~20–25 °C) and record `V_in`, `I_avg`, and board modifications (if any):

1. **Buck modules at no-load (`12.6 V` input, output open):**
   - Measure `HW-788` / `LM2596HVS` (Board A) and `HCW-P715` / `SY8205` (Pi 5).
   - Repeat with a dummy load approximating MCU sleep (e.g. `10 kΩ` on 5 V → `0.5 mA`) to measure real light-load 12 V input current.
2. **Raspberry Pi 5 8 GB (`5.0 V` input, no USB peripherals):**
   - Run `sudo poweroff` with default EEPROM (`POWER_OFF_ON_HALT=0`), wait 30 s, record 5 V current.
   - Set `POWER_OFF_ON_HALT=1` and `WAKE_ON_GPIO=0` via `sudo rpi-eeprom-config --edit`, reboot, run `sudo poweroff`, wait 30 s, record 5 V current.
   - Repeat both measurements through the Pi 5 `12 V → 5 V` buck at `12.6 V` input.
3. **ESP32-S3 DevKitC-1 (`5.0 V` pin and `3.3 V` pin):**
   - Flash minimal sleep firmware: measure in Deep-sleep (`esp_deep_sleep_start`) and Light-sleep (`esp_light_sleep_start`) with USB disconnected.
   - Measure again if BLE advertising is enabled at a candidate interval (e.g. 500 ms / 1000 ms), noting average current over ≥ 30 s.
4. **NUCLEO-H743ZI2 and NUCLEO-G474RE (when delivered):**
   - Measure MCU-only current via the Nucleo `IDD` current-measurement jumper (confirm jumper designator in `UM2407` / `UM2505`) in Run, Stop, Standby, and (G474) Shutdown.
   - Measure **whole-board** current on the external `5 V` / `VIN` pin with ST-LINK USB unplugged (and, separately, with ST-LINK isolated per the Nucleo user manual) to quantify on-board regulator/ST-LINK/LED overhead.
5. **SN65HVD230 CAN modules and IMUs:**
   - Check pin 8 (`Rs`) wiring on each received `SN65HVD230` breakout with a continuity tester; measure `3.3 V` current in normal recessive mode and (if `Rs` can be pulled to `3.3 V`) in Standby mode.
   - Read `WHO_AM_I` (`0x75`) on the on-hand "MPU-6590" board to confirm the silicon; measure `MPU-6500` sleep and WoM currents at `3.3 V`.
6. **High-overhead peripherals (sanity check):**
   - Measure `WS2812B` 12-LED ring at `5.0 V` with all pixels set to `(0, 0, 0)` (off).
   - Measure `Board A` battery-voltage divider current at `12.6 V`.

### 4.3 Stage 2 — Integrated Bench Harness Check (`12.6 V`)

1. Assemble the full Wave 1 / Wave 5 power tree on the bench at `12.6 V`.
2. Verify key-on boot current, normal steady-state current, and key-off transition:
   - Under **Option A:** confirm `KL30` draw is `0.00 mA` when `KL15` is opened, and confirm supercapacitor hold time (≥ 3 s) is sufficient to close microSD files cleanly.
   - Under **Option B:** time the full `KL15` off → Pi 5 halt → `HOLD` release sequence, confirm bounded timeout if the Pi hangs, and measure final resting `KL30` current 60 s after `KL15` opens.
   - Under **Option C:** measure resting `KL30` current in park mode and verify wake-on-motion triggers within the false-alarm filter window without waking `G474`.

### 4.4 Stage 3 — On-Bike Verification (CL250, `vehicle-work-plan.md` §4.3)

1. **Stock baseline first:** With the entire platform harness unplugged and ignition OFF (key removed, wait ≥ 5 minutes for OEM ECM sleep), measure the stock CL250 key-off current in series with the battery negative terminal. Record this as measured $I_{\text{oem}}$.
2. **Platform connected:** Plug in the platform harness, cycle ignition ON then OFF (key removed), wait for the shutdown timer + 60 s, and re-measure total battery negative current.
3. **Delta check:** Compute $I_{\text{plat,12V}} = I_{\text{total}} - I_{\text{oem}}$.
   - **Pass criterion (`vehicle-work-plan.md` §4.3):** $I_{\text{plat,12V}} < 1.0\text{ mA}$.
   - If $\ge 1.0\text{ mA}$, keep all platform supplies strictly behind `KL15` (Option A) or behind a verified self-hold cut-off switch (Option B) before leaving the motorcycle parked unattended.

---

## 5. Open Decisions for Claude / User

1. Choose between **Option A** (pure `KL15`), **Option B** (`KL15` + timed `KL30` self-hold for clean Pi 5 / microSD shutdown), and **Option C** (always-on park monitor) and record the choice as a `D-xxx` decision in `DECISIONS.md`.
2. Decide whether Pi 5 clean shutdown (Option B) is required from Wave 5 onward or whether an overlay/read-only rootfs on Option A is preferred for the prototype.
3. Confirm whether park-mode tilt/theft wake (`hardware-architecture.md` §5b.3) is deferred until a custom low-$I_Q$ PCB replaces the Nucleo/DevKitC dev boards.
