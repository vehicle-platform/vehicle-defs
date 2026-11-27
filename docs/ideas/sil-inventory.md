# Software-in-the-Loop (SIL) Host Inventory (G4-6, T69 Input)

Status: idea note, not a decision (facts inventory for T69 SIL design)

Facts-only inventory (Gemini, 2026-11-27) of what builds and runs on host today across the platform repositories, which `dbc/platform.dbc` frames each host build transmits or receives, and the concrete gaps for running `vehicle-rt-core` + `vehicle-safety-node` + `vehicle-server` on one virtual bus. Claude writes the multi-node SIL design from this inventory; any options noted at the end are marked **proposed**.

**Host environment measured:** Apple Silicon macOS (`arm64`, local workspace checkout on `main`, 2026-11-27).

---

## 1. Per-Repository Host Build & Simulation Inventory

Every command below was executed once on this macOS host from its repository root; pass/fail and wall-clock duration are measured.

| Repo | Exact command run | Platform | Measured result & duration | What it simulates (bus, sensors, time) | Inputs & outputs |
|---|---|---|---|---|---|
| **`vehicle-rt-core`** (host tests) | `cmake --preset host-tests && cmake --build --preset host-tests && ctest --preset host-tests --output-on-failure` | macOS & Linux (ASan + UBSan) | **PASS** (55/55 tests, **53.64 s** total; ctest 50.67 s) | In-process `vbus_t` virtual CAN (`src/hal/host/vbus.c`), `sim_ecu` CL250 UDS responder, `sim_safety` `0x082` stub, `sim_tester` platform UDS client, `sim_listener` E2E/gap checker, `imu_host` sample ring (`src/hal/host/imu_host.c`), manual stepped or `CLOCK_MONOTONIC` time (`src/hal/host/hal_time_host.c`) | Inputs: Unity test cases, golden derived vectors (`tests/host/vectors/`). Outputs: ctest pass/fail + `build/host-tests/src/vehicle_rtcore_host` binary |
| **`vehicle-rt-core`** (SIL binary, 2 s smoke) | `./build/host-tests/src/vehicle_rtcore_host --duration-ms 2000 --quiet` | macOS & Linux (`--vcan` Linux-only) | **PASS** (`rc=0`, **2.18 s**; 89 UDS reads, 0 timeouts, 100× `0x020`, 40× `0x021`, 40× `0x110`, 20× `0x081`, 20× `0x082` rx) | Two in-process `vbus_t` buses (`bus` = vehicle, `platform_bus` = platform), `sim_ecu`, `sim_safety`, 800 Hz straight-riding `imu_host` feed (`main.c:217-226`), wall `CLOCK_MONOTONIC` with 1 ms `nanosleep` (`main.c:388`) | Inputs: CLI flags (`--vcan`, `--duration-ms`, `--min-responses`, `--dtcs`, `--uds-scenario`, `--quiet`). Outputs: stdout summary + exit code (`0` = pass, `1` = fail, `2` = arg/guard error) |
| **`vehicle-rt-core`** (SIL binary, UDS scenario) | `./build/host-tests/src/vehicle_rtcore_host --uds-scenario --quiet` | macOS & Linux | **PASS** (`rc=0`, **5.83 s**; 15/15 UDS server steps, worst first-frame latency 2 ms vs 50 ms P2) | Same as above plus `sim_tester` running a 15-step UDS diagnostic session on the in-process `platform_bus` | Inputs: `--uds-scenario` scripted steps (`src/app/host/sim_tester.c`). Outputs: stdout summary + exit code |
| **`vehicle-safety-node`** (host tests) | `cmake --preset host-tests && cmake --build --preset host-tests && ctest --preset host-tests --output-on-failure` | macOS & Linux | **PASS** (9/9 tests, **0.56 s** total; ctest 0.44 s) | In-memory dual-class RX/TX FIFO stub `can_host` (`src/hal/host/can_host.c`), GPIO stub `indicator_gpio_host` (`src/hal/host/indicator_gpio_host.c`), explicit caller-supplied `uint32_t now_ms` (no OS clock) | Inputs: unit tests calling `can_host_inject()` and `safety_app_step(now_ms, ...)`. Outputs: ctest pass/fail + frames popped via `can_host_tx_pop()`. **No standalone host executable (`main()`) exists** |
| **`vehicle-connectivity-node`** (native host tests) | `bash scripts/native_tests.sh` (CI uses `pio test -e native`) | macOS & Linux (g++ + Unity) | **PASS** (`rc=0`, **11.89 s**; 8 suites: `test_native`, `test_can_protocol`, `test_can_capture`, `test_gps`, `test_discovery_probe`, `test_dtc_snapshot`, `test_twai_can_bus`, `test_rider_input`) | Stubbed TWAI CAN (`test/native_stubs/`), UDS/ISO-TP vehicle-bus tester, BLE GATT packet builders, NMEA GPS parser, button input tracker; deterministic test clock | Inputs: Unity test suites. Outputs: stdout pass/fail + `.cache/native/*.log`. **No standalone SIL binary and no platform-bus simulation** (`src/main.cpp:15`) |
| **`vehicle-hil-bench`** | None (no build/test files yet) | — | **NOT BUILT** (skeleton repo only: `README.md`, `CLAUDE.md`, `LICENSE`) | None yet (`README.md:11`: planned STM32F4 restbus simulator + Python scenario host) | None |
| **`vehicle-server`** (mock live stack) | `uv run pytest tests/test_mock_stream.py -q` (runtime: `VEHICLE_LIVE_SOURCE=mock VEHICLE_LIVE_MOCK_SCENARIO=<normal\|overheat\|weak-charging\|dropout> uv run vehicle-server serve`) | macOS & Linux | **PASS** (15/15 tests, **1.05 s** total; pytest 0.15 s) | Synthetic 50 Hz (20 ms step) `MockCanStreamer` (`src/vehicle_server/mock_stream.py:67-243`) generating platform CAN frames + decoded signals + synthetic vehicle UDS responses, or replaying recorded `telemetry.csv` fixtures; feeds `LiveHub` → `/ws/live` and in-ride `alerts/service.py` SSE (`/alerts/stream`) | Inputs: scenario name (`normal`, `overheat`, `weak-charging`, `dropout`) or fixture dir; optional MQTT VSS live source (`mqtt_live.py`, D-109). Outputs: WebSocket `StreamBatchDto` (`/ws/live`), SSE alerts (`/alerts/stream`), stored notifications |
| **`vehicle-linux-node`** (host tests & replay generator) | `uv run pytest -q` (CLI: `uv run vehicle-linux-node-replay`) | macOS & Linux (Kuksa Docker `vcan0` bridge requires Linux SocketCAN) | **PASS** (153 passed, 3 skipped, **3.01 s** total; pytest 2.64 s) | `replay.py` generates synthetic `candump` (`platform_replay.log`, `CHANNEL="vcan0"`, 20 cycles × 0.1 s) and `expected.json` from `platform.dbc` + `gen/vss/vss_dbc.json`; unit tests cover `defs`, `replay`, `canif`, `ldw`, `blackbox`, `nodehealth`, `live` MQTT publisher (mocked) | Inputs: pinned `platform.dbc` + `vss_dbc.json` (and Docker Kuksa Databroker + `kuksa-can-provider` on Linux). Outputs: `platform_replay.log`, `expected.json`, VSS over gRPC (Linux Docker), MQTT `vehicle/<device_id>/live/<VSS path>` |

---

## 2. Platform-Bus Frame Matrix (`dbc/platform.dbc`)

All ten message names below are taken verbatim from `vehicle-defs/dbc/platform.dbc` (classic CAN 11-bit, 500 kbps).

| Message (DBC name) | Frame ID | DBC TX → RX | E2E | `vehicle-rt-core` (`vehicle_rtcore_host`) | `vehicle-safety-node` (`platform_link` + `safety_app`) | `vehicle-connectivity-node` (host tests) | `vehicle-server` (`mock_stream.py`) | `vehicle-linux-node` (`replay.py` / Kuksa) |
|---|---|---|---|---|---|---|---|---|
| `EkfLean` | `0x020` (32) | `RT_CORE` → `SAFETY, LINUX` | Yes (20 ms) | **TX** (`lean_tx`, `main.c:334,380`) | **RX** (`HAL_CAN_RX_SAFETY`, E2E checked, `platform_link.c:33`) | None | **Synthesized TX** (E2E, `mock_stream.py:156`) | **Replay encode** (if `dbc2vss`-mapped, **no E2E** `replay.py:62-64`) / **RX** via `kuksa-can-provider` |
| `VehicleSpeed` | `0x021` (33) | `RT_CORE` → `CONN, LINUX` | Yes (50 ms) | **TX** (`vehicle_republish`, `main.c:315,380`); in-process `sim_listener` RX-checks E2E | None (rejected by filter, D-041/D-048) | None (`src/main.cpp:15`) | **Synthesized TX** (E2E, `mock_stream.py:163`) | **Replay encode** (**no E2E**) / **RX** via `kuksa-can-provider` |
| `EkfFrictionMass` | `0x022` (34) | `RT_CORE` → `SAFETY, LINUX` | Yes (100 ms) | **None** (not wired in `main.c`) | **RX** (`HAL_CAN_RX_SAFETY`, E2E checked, `platform_link.c:35`) | None | None | **Replay encode** (if mapped, **no E2E**) / **RX** via `kuksa-can-provider` |
| `SafetyWarningStatus` | `0x023` (35) | `SAFETY` → `RT_CORE, CONN, LINUX` | Yes (20 ms) | **None** (not decoded in `main.c`) | **TX** (E2E protected, `safety_app.c:77-105`, `platform_link.c:231`) | None | None | **Replay encode** (if mapped, **no E2E**) / **RX** via `kuksa-can-provider` |
| `HeartbeatRtCore` | `0x081` (129) | `RT_CORE` → `SAFETY, CONN, LINUX` | Yes (100 ms) | **TX** (`heartbeat`, `main.c:320,380`); in-process `sim_listener` RX-checks E2E | **RX** (`HAL_CAN_RX_SAFETY`, E2E checked, `platform_link.c:38`) | None | **Synthesized TX** (E2E, `mock_stream.py:187`) | **Replay encode** (if mapped, **no E2E**) / **RX** via `kuksa-can-provider` (`nodehealth`) |
| `HeartbeatSafety` | `0x082` (130) | `SAFETY` → `RT_CORE, LINUX` | Yes (100 ms) | **RX** (`safety_hb`, E2E checked, `main.c:324,380`); in-process `sim_safety` stub sends `0x082` (`sim_safety.c:26`) | **TX** (E2E protected, `safety_app.c`, `platform_link.c:233`) | None | None | **Replay encode** (if mapped, **no E2E**) / **RX** via `kuksa-can-provider` (`nodehealth`) |
| `HeartbeatConn` | `0x084` (132) | `CONN` → `RT_CORE, LINUX` | Yes (100 ms) | None | None | None | None | **Replay encode** (if mapped, **no E2E**) / **RX** via `kuksa-can-provider` (`nodehealth`) |
| `HeartbeatLinux` | `0x085` (133) | `LINUX` → `RT_CORE` | Yes (100 ms) | None | None | None | None | None (not sent by `replay.py` unless mapped) |
| `VehicleEngine` | `0x110` (272) | `RT_CORE` → `CONN, LINUX` | No (50 ms) | **TX** (`vehicle_republish`, `main.c:315,380`); in-process `sim_listener` RX-checks gaps | None (rejected by filter) | None (`src/main.cpp:15`) | **Synthesized TX** (`mock_stream.py:171`) | **Replay encode** / **RX** via `kuksa-can-provider` |
| `SafetyRequest` | `0x120` (288) | `RT_CORE` → `SAFETY` | Yes (100 ms) | **None** (not wired in `main.c`) | **RX** (`HAL_CAN_RX_QM`, E2E checked, `platform_link.c:41`) | None | None | None |

*(Note: `vehicle-hil-bench` has no code yet and sends/receives no frames.)*

---

## 3. Concrete Gaps for One Virtual Bus (`rt-core` + `safety-node` + `server`)

Every gap below is recorded as a fact with source file and line references. Options are explicitly marked **proposed**.

### 3.1 Missing Host Ports and Cross-Process Bus Transport

1. **No cross-process virtual CAN backend on macOS:**
   - `vehicle-rt-core/src/hal/host/can_port_host.c:5-17` sets `HAVE_SOCKETCAN = 0` on non-Linux hosts; `can_port_host_bind_socketcan()` unconditionally returns `false` (`can_port_host.c:151-156`).
   - Even on Linux, `vehicle-rt-core/src/app/host/main.c:292-301` hard-wires `CAN_PORT_PLATFORM` to an in-process `vbus_t platform_bus`; only `CAN_PORT_VEHICLE` accepts `--vcan` (`main.c:281`).
2. **`vehicle-safety-node` has no host executable and no bus transport:**
   - `vehicle-safety-node/src/CMakeLists.txt` builds only a library and Unity test executables; there is no `src/app/host/main.c` runner.
   - `vehicle-safety-node/src/hal/host/can_host.c:11-167` provides only in-memory unit-test ring buffers (`can_host_inject` / `can_host_tx_pop`) and cannot attach to SocketCAN, UDP/Unix-socket virtual CAN, or `vehicle-rt-core`'s `vbus_t`.
3. **No CAN-to-`vehicle-server` host bridge without Linux Kuksa + MQTT:**
   - `vehicle-server/src/vehicle_server/mock_stream.py:67-243` synthesizes frames internally rather than subscribing to an external virtual bus.
   - `vehicle-server`'s real live ingest path (`src/vehicle_server/mqtt_live.py`, D-109) consumes MQTT VSS topics (`vehicle/<device_id>/live/<VSS path>`), not raw CAN frames, which today requires `vehicle-linux-node` (`kuksa-can-provider` on Linux `vcan0` → Kuksa Databroker → `live/service.py` MQTT publisher).

### 3.2 Missing Frame, E2E, and Heartbeat Wiring on Host

4. **In-process `sim_safety` stub collides with a real `safety-node` on `0x082`:**
   - `vehicle-rt-core/src/app/host/main.c:297,366` always initializes and steps `sim_safety` (`src/app/host/sim_safety.c:16-39`), which transmits `HeartbeatSafety` (`0x082`) every 100 ms. Running a real `safety-node` on the same platform bus requires disabling `sim_safety` (and `sim_listener` if external peers replace it).
5. **Missing `rt-core` host TX for `EkfFrictionMass` (`0x022`) and `SafetyRequest` (`0x120`) and RX for `SafetyWarningStatus` (`0x023`):**
   - `vehicle-rt-core/src/app/host/main.c:315-380` transmits `EkfLean` (`0x020`), `VehicleSpeed` (`0x021`), `HeartbeatRtCore` (`0x081`), and `VehicleEngine` (`0x110`), but has no transmitter for `EkfFrictionMass` (`0x022`) or `SafetyRequest` (`0x120`), and no receiver for `SafetyWarningStatus` (`0x023`).
   - Consequently, `vehicle-safety-node` (`src/services/platform_link.c:35-43`) will always see `EkfFrictionMass` absent/timed out (falling back to default friction/mass per D-029/D-042) until `rt-core` publishes `0x022`.
6. **`vehicle-linux-node/src/vehicle_linux_node/replay.py` omits E2E protection:**
   - `replay.py:14-15,62-64` fills unmapped signals (including `E2E_CRC` and `E2E_COUNTER`) with minimum raw values (`0`), so frames generated by `vehicle-linux-node-replay` cannot pass E2E checks in `vehicle-safety-node` (`platform_link.c:134`) or `vehicle-rt-core` (`safety_hb`).

### 3.3 Time-Source and Scheduling Differences

7. **Mismatched time models across the three nodes:**
   - `vehicle-rt-core/src/hal/host/hal_time_host.c:12-64` supports both manual stepped time (`hal_time_host_use_manual` / `hal_time_host_advance`) and wall `CLOCK_MONOTONIC`; `vehicle_rtcore_host` uses wall `CLOCK_MONOTONIC` with `nanosleep(1 ms)` (`main.c:388`). On macOS, OS scheduling jitter already caused `14 ms` (2 s run) and `20 ms` (5.8 s UDS run) step gaps exceeding `VEHICLE_CL250_CLIENT_STEP_MAX_MS` (10 ms, D-053).
   - `vehicle-safety-node/src/app/safety_app.c:36` and `safety_app.h:35` take `uint32_t now_ms` explicitly from the caller and enforce `SAFETY_APP_PASS_MAX_MS` (`5 ms`, `safety_app.c:19`: 4 passes per 20 ms `EkfLean` cycle) plus E2E timeout checks. Free-running wall-clock threads on macOS risk spurious `SAFETY_APP_PASS_MAX_MS` overruns and E2E timeouts.
   - `vehicle-server/src/vehicle_server/mock_stream.py:86-89` steps synthetic dynamics on a fixed 20 ms counter (`_step * 20 / 1000.0`) stamped with host wall/monotonic `timestamp_us`.
8. **Uncoupled synthetic sensor / dynamics sources:**
   - `vehicle-rt-core/src/app/host/main.c:217-226` feeds a hard-coded stationary/straight-riding IMU signal (`feed_imu`), and `sim_ecu` returns fixed/synthetic DID values; `vehicle-safety-node` expects its own independent fallback IMU samples (`cornering` module) and indicator GPIOs (`indicator_gpio_host`). No shared synthetic ride dynamics generator feeds synchronized vehicle ECU DIDs + H743 IMU + G474 fallback IMU simultaneously.

### 3.4 Obvious Integration Options (**Proposed** — Claude Decides in T69)

- **Option 1 (Proposed — Deterministic in-process or lockstep C/Python harness, macOS + Linux):** Link `rt-core` and `safety-node` host libraries against a shared stepped virtual clock (`now_ms` incremented in deterministic 1 ms or 5 ms ticks) and a shared in-process bus (or Unix-domain socket bus with explicit tick barriers), feeding decoded `platform.dbc` frames into `vehicle-server` via a lightweight host bridge (`LiveHub` / MQTT). Eliminates macOS timer jitter (`SAFETY_APP_PASS_MAX_MS` and D-053 step overruns) and works identically in CI on Linux and macOS.
- **Option 2 (Proposed — Linux `vcan0` multi-process stack):** Add `--platform-vcan <if>` to `vehicle_rtcore_host` (plus `--no-sim-safety`), add a Linux SocketCAN host runner to `vehicle-safety-node`, and reuse `vehicle-linux-node`'s Docker Kuksa + `kuksa-can-provider` → MQTT → `vehicle-server` chain. Runs closer to production topology on Linux/CI, but requires Linux `vcan` (not native macOS) and careful pacing to avoid host jitter tripping the 5 ms / 10 ms bounds.
