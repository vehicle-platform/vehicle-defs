# vehicle-platform — Architecture (authoritative summary)

**Version:** 1.2 — 2026-10-18 (two servers D-077, position D-076, scope D-078; 1.1: units and topology per D-072/D-073) · Source: `hardware-architecture.md` v1.0 + `DECISIONS.md`
If this file conflicts with the raw document, **this file + DECISIONS.md** govern.

---

## 1. Principles

1. **SDV:** a few powerful units + an isolated safety monitor + as many edge nodes as needed. A new function means a new software module, not a new box.
2. **Real-time and rich workloads on separate chips:** deterministic → MCU (bare-metal/RTOS), rich → Linux.
3. **Loose coupling:** if the Raspi, phone, or server crashes, the critical function keeps running. They add richness, they are not required.
4. **Single source of truth:** all signal/message/DID definitions live in `vehicle-defs`; code is **generated** from them.
5. **Standards as concepts, not as a stack:** DBC (Vector de-facto), COVESA VSS, ISO 15765-2/14229 (ISO-TP/UDS), ASAM XCP, AUTOSAR E2E, and layering concepts. The Classic/Adaptive AUTOSAR stack is NOT USED (D-006).

---

## 2. Units

| Unit | Chip | Memory (RAM / flash) | CAN peripheral | Repo | Role |
|---|---|---|---|---|---|
| Domain controller | STM32H745/H755, **Cortex-M7** core (prototype board NUCLEO-H745ZI-Q, D-072, D-094) | ~1 MB / 2 MB, shared with the M4 (M4: flash bank 2 + D2 SRAM) | FDCAN x2 (both on the M7) | `vehicle-rt-core` | CAN gateway, single vehicle-bus tester, logging, fusion, UDS/ISO-TP, bootloader, XCP, EKF (Layer 2), context, dyno, anomaly safety net, derived signals (D-070), power management and park mode (from io-node, D-072) |
| Safety partition | same STM32H755, **Cortex-M4** core (D-072) | D2 SRAM / flash bank 2 | none (mailbox to the M7, E2E) | `vehicle-safety-node` | Lean-angle safety decision (Layer 1, closed form, D-041), own fallback IMU (D-042), blind-spot decision with 2 radars, immobilizer, LED ring and mirror LEDs (Q-026 resolved) |
| ~~Zone/I/O~~ | ~~STM32G0~~ — retired by D-072 | — | — | `vehicle-io-node` (no code; archive pending) | functions moved to the M4 (blind spot, immobilizer) and the M7 (power, park mode) |
| Connectivity, bike | ESP32-S3 (WROOM module) | 512 KB (+PSRAM) | TWAI x1 (classic) | `vehicle-connectivity-node` | Temporary vehicle-bus tester until rt-core (D-023); then platform bus ↔ BLE bridge to the phone and the helmet, Wi-Fi |
| Connectivity, helmet | ESP32-S3 N16R8 (D-073) | 512 KB + 8 MB PSRAM | none | `vehicle-connectivity-node` (helmet env) | Visor HUD (informational), helmet microphone, push-to-talk, ESP-SR voice command, voice prompts |
| HPC | Raspberry Pi 5 8 GB | 8 GB | 2-channel CAN HAT (SocketCAN) | `vehicle-linux-node`, `vehicle-mcp` | Kuksa, CAN→VSS, lane tracking, anomaly model, HMI, OTA distribution, MCP |
| HIL simulator | STM32F4 (F407/F429) | 192 KB / 1 MB | bxCAN x2 | `vehicle-hil-bench/simulator` | Restbus (CL250 + platform nodes), vehicle dynamics model |
| HIL fault/power | STM32F103 | 20 KB / 64 KB | bxCAN x1 | `vehicle-hil-bench` | Fault injection, programmable power supply |
| HIL host / CI runner | i7 desktop, Linux | — | SocketCAN (USB-CAN) | `vehicle-hil-bench/host` | Scenario engine, evaluator, dashboard, self-hosted CI |

Incremental rollout: a unit is not added until its function arrives (see hardware-architecture.md §7).

---

## 3. Bus topology — two separate CAN buses (D-009)

```
 VEHICLE CAN (CL250 DLC, rt-core polls) ═╤══════════════════════════════════════════╤═══
   500 kbps classic (verified, D-019)    │ FDCAN1 (only tester, D-021)              │ can0 optional,
           ┌─────────────────────────────┴───────────────────────┐           ┌──────┴─────┐ listen-only
           │ STM32H755 (one board, D-072)                        │           │  Raspi 5   │
           │ ┌────────────┐  mailbox (HSEM, E2E)  ┌────────────┐ │           │ linux-node │
           │ │ Cortex-M7  │◄─────────────────────►│ Cortex-M4  │─┼─ own pins └──────┬─────┘
           │ │ rt-core    │                       │ safety     │ │  only: SPI IMU,  │ can1
           │ └─────┬──────┘                       │ partition  │ │  2 radars (UART),│
           └───────┼──────────────────────────────┴────────────┴─┘  LED ring, mirror│
                   │ FDCAN2                                         LEDs, starter-  │
                   │                                                relay coil      │
 ══════════════════╧═════════════════════════════╤══════════════════════════════════╧═══  PLATFORM CAN (ours, dedicated)
   500 kbps classic, 11-bit IDs, 120Ω at both ends
                                          ┌──────┴─────┐   BLE    ┌──────────────┐
                                          │ ESP32-S3   │◄────────►│ ESP32-S3     │
                                          │ bike conn  │          │ helmet (HUD, │
                                          └─────┬──────┘          │ mic, voice)  │
                                                │ BLE             └──────────────┘
                                              phone
 Until rt-core runs on the bike, the bike ESP32 is the temporary vehicle-bus tester over TWAI (D-023).
```

- **Vehicle bus:** OEM network reached through the diagnostic connector (DLC). CL250 data is **poll-based** (UDS `0x22`, 29-bit `0x18DA10F1` → `0x18DAF110`, D-019), so there must be exactly **one tester: rt-core** (D-021), and it has to transmit: listen-only cannot collect this data (D-037). It sends only the session and read requests listed in `uds/vehicle_cl250.yaml` → `tester_policy` (D-020, the single source; the generated gates enforce it), never anything that changes ECU state. No other node transmits here. The Raspi may tap it strictly listen-only for raw logging. No additional termination resistor is added to the vehicle bus.
- **Platform bus:** the dedicated bus our own nodes talk on. No risk of ID collisions, confusing the OEM ECU, or added OEM bus load. Classic CAN was chosen because F103 and ESP32-S3 TWAI don't support FD (an FD frame produces an error frame on a classic node). Migration will be reconsidered once all nodes support FD.
- **One chip, two partitions (D-072).** The Cortex-M7 (rt-core) owns both FDCANs; the Cortex-M4 safety partition has no CAN and gets 0x020/0x022/0x081 through an HSEM-guarded shared-SRAM mailbox that keeps the platform payloads and their E2E checks. The M7 forwards the M4 heartbeat 0x082 and its warning/status bytes verbatim (never re-signs them) and stops when a slot is not updated. Peripherals, memory, GPIO ports and watchdogs are fixed per core, the clock tree is set once at boot, the M4 boots on its own from flash bank 2; power, clock, reset and silicon are shared, and IWDG/system resets restart both cores (accepted, D-072 items 4-5). The OTA A/B scheme stays inside bank 1 (D-072 item 4f).
- **rt-core republishes vehicle signals** (speed, RPM, coolant, TPS, battery) on the platform bus (state range 0x100-0x3FF; vehicle speed keeps its E2E protection for its other consumers, but safety-node does not read 0x021, D-041). Everyone else, including the Raspi's kuksa-can-provider (`platform.dbc`), reads them there (D-021). safety-node takes only lean and µ from rt-core (D-041), now through the mailbox (D-072); when they are not usable it falls back to its own IMU (D-042, Q-002 resolved).
- ~~The safety node also listens to the vehicle bus~~ and ~~rt-core does not forward vehicle signals~~ (D-009 bullets superseded by D-021).
- rt-core (M7) ↔ bike ESP32-S3: SPI/UART simple framed messaging (format to be co-designed, Q-004) or the platform bus. Bike ESP32 ↔ helmet ESP32: BLE, layout defined in `ble/` (D-073). Phase 2: SOME/IP.

---

## 4. Platform CAN ID plan and reliability

11-bit ID, lower ID = higher priority:

| Range | Class | E2E | Example |
|---|---|---|---|
| 0x000-0x00F | Reserved (emergency/network management) | — | — |
| 0x010-0x07F | **Safety critical** | Mandatory | lean angle/µ (rt-core→safety, D-041; 0x022 also carries total mass, which is not a safety-node input, D-029/D-041), 0x023 safety partition status (cornering level and source, blind spot, immobilizer; D-072) |
| 0x080-0x08F | Heartbeat (`0x080 + node_id`), 100 ms | Mandatory | node status, operating mode, error counter |
| 0x100-0x3FF | Status/control, context data bus | Optional | context classes, riding profile, 0x120 QM requests rt-core → safety partition (ignition, park mode, lock request; never a safety input, D-072) |
| 0x400-0x5FF | Telemetry (low priority) | — | statistics, power measurement |
| 0x600-0x6FF | Bridge/log/development | — | — |
| 0x700-0x7FF | UDS diagnostics (platform nodes) | — | physical `0x7N0`/`0x7N8`, functional `0x7DF` |

**Node ID:** 1 RT_CORE · 2 SAFETY (the M4 partition, D-072) · (3 unused: IO retired by D-072, removed in defs v0.15.0) · 4 CONN · 5 LINUX · 0xE HIL_SIM · 0xF TESTER

**E2E (AUTOSAR E2E Profile 1/2-like, D-005):** protected messages carry a 4-bit alive counter + CRC8 (SAE J1850, poly 0x1D). The message's `E2E_DataID` is included in the CRC calculation but not transmitted. The receiver checks three things: **timeout** (3 × cycle), **counter jump/freeze**, **CRC**. If any of these fails, the signal is considered `INVALID` and the consumer transitions to its own safe state. For the safety node, an invalid lean/µ switches to its own-IMU fallback (DEGRADED, or UNAVAILABLE if no source is usable; D-042, Q-002 resolved, details in Q-023). Cost is 1-2 bytes per message plus a few lines of generated code.

**Heartbeat:** every node publishes one. The safety node monitors rt-core's heartbeat (through the mailbox, D-072), rt-core monitors the other nodes. The Raspi health dashboard displays this.

---

## 5. Signal definition pipeline (D-003, D-004)

```
vehicle-defs/
  uds/vehicle_cl250.yaml  vehicle ECU DIDs polled by rt-core (addressing, DID, formula, poll rate; verified per D-019)
  dbc/cl250.dbc         vehicle-bus broadcast frames — only if passive traffic is ever found (Q-001); skeleton for now
  dbc/platform.dbc      platform bus (ours; GenMsgCycleTime, E2E_DataID, E2E_Protected attributes), incl. rt-core's republished vehicle signals
  vss/overlay.vspec     motorcycle extensions (Vehicle.Motorcycle.*) + dbc2vss mappings (from platform.dbc)
  uds/dids.yaml         our platform nodes' UDS servers (IDs, timing, DIDs, DTCs)
  uds/iso14229.yaml     generic ISO 14229-1 codes
  ble/ble_schema.json   BLE packet schema of conn (telemetry v2/v3/v4, IMU, GPS and vehicle-signal blocks, GATT; D-061)
  tools/codegen/        python: cantools + vss-tools wrapper
        │ make gen  (run before tagging, output is committed)
        ▼
  gen/c/<node>/         per-node filtered: pack/unpack + E2E protect/check + ID constants + DID table (const, no malloc)
  gen/python/           signal constants for host/server/hil (+ BLE schema for vehicle-server)
  gen/dart/             BLE layout constants for vehicle-mobile (Dart package vehicle_defs)
  gen/vss/              VSS JSON for Kuksa (+ dbc2vss mapping)
```

- MCUs only include `gen/c/<their own node>/`. The only place that parses DBC/VSS files at runtime is the Linux/host side.
- VSS **lives only on the Raspi and above** (Kuksa, vehicle-mcp, server, mobile, ML). Raspi applications don't touch SocketCAN directly — they read from Kuksa.
- The safety path (cornering, blind spot) never enters VSS.
- Consumers pin the `external/vehicle-defs` submodule to a **tag**. The schema-change process lives in the `/signal-change` skill.

---

## 6. Software layers (MCUs) — AUTOSAR concept mapping

```
src/features/<module>/  ≈ SWC      independent function; modules do NOT include each other
src/services/           ≈ BSW      signal pool, time base, logging, com (pack/unpack+E2E), diag, NVM
src/hal/                ≈ MCAL     thin wrapper over CubeMX HAL (can, imu, gps, gpio)
cubemx/                 generated code (Core/Drivers) — not hand-edited, except USER CODE blocks
external/vehicle-defs  submodule (tagged)
tests/host/             host-native unit tests with Unity (pure logic: EKF, ISO-TP, E2E, decision)
```

- features → services → hal (one direction). If a feature is removed, the others still build and run.
- Safety-critical tasks run at the highest priority. A delay in a low-priority module doesn't affect them (freedom from interference).
- RTOS: FreeRTOS for rt-core on the Cortex-M7 (CubeMX CMSIS-RTOS2). The safety partition on the Cortex-M4 uses a bare-metal super loop + timer interrupt (determinism, simplicity; D-012, D-072). If this changes, write it into DECISIONS.

---

## 7. Data flows

| Flow | Path | Channel | Criticality |
|---|---|---|---|
| Cornering warning | IMU/GPS/vehicle CAN → rt-core EKF (M7) → lean + µ [mailbox, E2E, D-072] → safety-partition decision (M4) (no speed, D-041; own-IMU fallback when rt-core data is unusable, D-042) → LED ring driven by the M4 (Q-026 resolved); helmet HUD copy informational (D-073) | mailbox | µs-ms, safety |
| Blind spot | radar x2 (UART, M4) → safety-partition decision → mirror LED; status → M7 → platform CAN; helmet HUD copy informational (D-073) | local + mailbox | reflex, safety |
| Context data bus | rt-core `context/` + EKF + measurements → platform CAN 0x100-0x3FF → consumers | CAN | ms |
| Derived signals (D-070) | vehicle DIDs + IMU + GPS speed → rt-core `features/derived` → microSD log (all); ride summaries → rt-core UDS DIDs; platform CAN 0x100-0x3FF only for a live consumer (Raspi anomaly model via VSS, D-004); cross-ride trends → vehicle-server. Never a safety-partition input | SD/CAN | latency-tolerant (QM) |
| Telemetry/logging | rt-core → microSD (binary, block CRC) → Wi-Fi (ESP/Raspi) → vehicle-server → MDF4/Parquet | SD/Wi-Fi | latency-tolerant |
| VSS | vehicle + platform CAN → kuksa-can-provider → Kuksa Databroker → Raspi applications (gRPC) | local | ms |
| Cloud (D-077) | Kuksa → local vehicle-server on the Raspi (every ride, offline) → live stream (MQTT/Zenoh or HTTP, open) + end-of-ride batch → remote vehicle-server (user's machine now, VPS-ready: containers, TLS proxy, per-device token) | Wi-Fi/LTE | latency-tolerant |
| LLM assistant | vehicle-mcp (read-only) on the Raspi (localhost, offline) and on the remote vehicle-server (TLS + auth, D-077) → LLM; position and windowed slices allowed provisionally (D-076, Q-035); the LLM does no math | local/HTTPS | none |
| OTA | vehicle-server → Raspi → UDS bootloader (platform CAN) → MCU A/B bank | CAN | controlled |
| Engineering analysis (D-081) | vehicle + platform CAN (USB adapter, listen-only), recorded logs or the vehicle-server live stream (`/ws/live`; only a mock source for now, the real source via the Raspi is open under D-077) → vehicle-analyzer (web host, later Tauri desktop); decodes only from the pinned defs, never transmits on a vehicle bus | USB/local/HTTPS | none |
| Rider layer (D-085) | own motorcycle (Raspi, remote vehicle-server) → rider front end (repo open, Q-037); explanations from the LLM through vehicle-mcp; high-severity catalog results shown directly, without the LLM | local/HTTPS | none (advice, QM) |

---

## 8. Verification pyramid and CI

| Level | What | Where | CI |
|---|---|---|---|
| L0 | Unit tests (Unity / pytest), static analysis (cppcheck MISRA addon, ruff) | host | GitHub-hosted, every push |
| L1 | SIL: firmware on Renode, virtual CAN | host | GitHub-hosted, every PR |
| L2 | HIL: real DUT + STM32F4 restbus + fault injection | i7 bench | self-hosted runner, nightly/labeled PR |
| L3 | On-vehicle T0-T4 | CL250 | manual, per protocol |

Requirement–test traceability (Ç8): requirement IDs (`REQ-<DOMAIN>-NNN`) appear in test names/comments. Where the HARA/FMEA and requirements files live is open in Q-006.

---

## 9. Repo setup order

1. `vehicle-defs` skeleton + codegen + `platform.dbc` draft → `v0.1.0`
2. `vehicle-hil-bench` host (Python, hardware-free) + Renode
3. `vehicle-connectivity-node` (migration of existing code)
4. `vehicle-rt-core` (once the NUCLEO-H745ZI-Q arrives, D-072, D-094)
5. `vehicle-server` → 6. `vehicle-ml` → 7. `vehicle-safety-node` (the M4 image, D-072) → ~~8. `vehicle-io-node`~~ (retired, D-072) → 9. `vehicle-linux-node` + `vehicle-mcp` → 10. `vehicle-mobile` → 11. `vehicle-analyzer` (D-081; started early by an external tool, 2026-10-20)

The thesis core (Ç1-Ç8) is covered by steps 1-4 above, plus HIL, in this order.

**Thesis work packages** ("Ç" = *çekirdek*, the committed core scope of the thesis; the Turkish advisor document `archive/tr/bitirme-projesi-kapsam.md` §5 predates D-001, this table is current):

| ID | Work package | Current target | Repo |
|---|---|---|---|
| Ç1 | CAN driver layer: error state machine, bus-off recovery | H755 (M7) FDCAN behind `hal/can_port` (D-001, D-072) | vehicle-rt-core |
| Ç2 | ISO-TP transport (ISO 15765-2) | `features/uds/isotp_*` (done, v0.2.0) | vehicle-rt-core |
| Ç3 | UDS (ISO 14229), two parts: **server** for our own nodes on the platform bus (built scope, D-040: 0x10 (01/03), 0x3E, 0x22, 0x19, 0x14 on *our* ECU), and the **vehicle client** (the poller) that only reads the CL250 (D-037). Not offered yet: 0x27, 0x2E, 0x31 and the bootloader services 0x11, 0x34-0x37; D-040 item 7 requires 0x27 (or an equivalent) before any of 0x10 02, 0x11, 0x2E, 0x31, 0x34-0x37 | `features/uds/`; client released in rt-core v0.3.0, server merged (rt-core#9), not yet tagged | vehicle-rt-core |
| Ç4 | HIL bench hardware: STM32F4 restbus simulator, transceivers, termination, OBD2 connector, programmable supply | D-001, D-035 | vehicle-hil-bench |
| Ç5 | HIL bench software: scenario engine, fault injection, automatic evaluation, report | log replay + live model (D-035) | vehicle-hil-bench |
| Ç6 | Test automation: self-hosted runner, build + static analysis + on-hardware regression per commit | needs the NUCLEO-H755ZI-Q (D-072) | all firmware repos |
| Ç7 | Data collection: signal logging, timestamps, metadata, storage schema | `phase0-data-collection-plan.md` | connectivity-node, mobile, server |
| Ç8 | Process documentation: HARA, requirement–test traceability, FMEA (ISO 26262 approach) | location open (Q-006) | vehicle-defs |

Extended scope G1-G5 (bootloader, XCP, riding modes, voice, client-server) is in the same Turkish document §5.2.
