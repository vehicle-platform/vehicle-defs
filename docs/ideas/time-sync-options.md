# Time Synchronisation Options (Q-008 — Proposed)

> **Status:** **Proposed** options paper only. Open question **Q-008** (`docs/DECISIONS.md` line 1135: *"Time synchronization: how is GPS PPS/NTP distributed to the MCUs?"*) remains **open**. Every architecture option, accuracy requirement, and trade-off below is **proposed**; no recommendation is final and no decision is recorded here.

---

## 1. Current Clocks and Timestamp Sources per Node

All facts below reflect the code and documentation on `main` (2026-11-27).

| Node | Hardware / OS Clock Today | Current Software Timebase & Timestamps (Cited) | Wall-Clock UTC Today? |
|---|---|---|---|
| **`vehicle-rt-core`** (STM32H743ZI, D-118) | Provisional clock tree (D-134, unverified on hardware until T26): HSE 8 MHz bypass (ST-LINK MCO) → PLL1 → SYSCLK 400 MHz, FDCAN kernel 80 MHz. | 32-bit monotonic millisecond counter via `hal_time_ms()` (`vehicle-rt-core/src/hal/hal_time.h:24`), wrapped by `timebase_now_ms()` / `timebase_elapsed_ms()` / `timebase_expired()` (`src/services/timebase.h:21-27`, wraps after ~49.7 days). Host port uses `CLOCK_MONOTONIC` or a manual stepped clock (`src/hal/host/hal_time_host.c:23-52`). Publishes 16-bit `RT_CORE_UPTIME` (seconds since boot, saturating at 65535 s) in `HeartbeatRtCore` (`dbc/platform.dbc:59`). | None. |
| **`vehicle-safety-node`** (STM32G474RE, D-118) | Provisional clock tree (D-134, unverified on hardware until T26): on-board HSE crystal → PLL → SYSCLK 170 MHz. | No `hal_time*` module in repo yet; board `main()` supplies a 32-bit monotonic `now_ms` into `safety_app_init(now_ms)` and `safety_app_step(now_ms)` (`vehicle-safety-node/src/app/safety_app.h:21-22,59-62`, `src/app/safety_app.c:36-55`), which drives `SAFETY_APP_PASS_MAX_MS` (5 ms), E2E freshness in `src/services/platform_link.c`, and wrap-safe `uptime_s` in `src/app/node_health_core.c:42-65` → `SAFETY_UPTIME` in `HeartbeatSafety` (`dbc/platform.dbc:66`). | None (and must never require one; see §4). |
| **`vehicle-connectivity-node`** (ESP32-S3) | ESP32-S3 crystal / Arduino-ESP-IDF millisecond tick (`millis()`). Also attached via UART to a u-blox NEO-M8N GNSS receiver (`src/GpsCore.h:20`). | `millis()` stamps `deviceTimeMs` into `BLETelemetryPacketV4` (`src/BLETelemetryPacket.h:103`, `src/BLEServerModule.cpp:245`), IMU blocks, vehicle-signal blocks, and `GpsFix::rxTimeMs` (`src/GpsFix.h:15`, `src/GpsBlockPacket.h:78`). `GpsFix::iTowMs` (`src/GpsFix.h:16`) holds GPS time-of-week strictly internally for epoch de-duplication; UTC calendar fields from UBX NAV-PVT are not exported today. `CanCaptureCore` accepts caller-supplied microsecond timestamps (`src/CanCaptureCore.h:14,148`). | None exported (GNSS NAV-PVT `iTowMs` stays internal). |
| **`vehicle-linux-node`** (Raspberry Pi 5) | Linux kernel `CLOCK_MONOTONIC` and `CLOCK_REALTIME` (systemd/OS clock; Pi 5 has an on-board RTC header, battery **CONFIRM**). | `blackbox/service.py:91` defaults to `int(time.monotonic() * 1000)` (or Kuksa timestamps, `blackbox/core.py:4-5`); `blackbox/store.py:35,65` stamps `written_utc` and event directory names with `datetime.now(UTC)`; `replay.py:92` uses synthetic `cycle * CYCLE_S`; `llmbench.py:247` uses `time.perf_counter()`. `docs/hardware-architecture.md` §5b.8 (line 606) lists *"NTP time server — Distributes GPS time to the other MCUs — Low — resolves the open time-synchronization decision"* as a proposed extended role, not yet implemented. | OS wall clock (no configured offline GNSS/NTP discipline yet). |
| **`vehicle-mobile`** (Android / Web companion) | Phone OS wall clock (network/NITZ/NTP synced when online) + Dart `Stopwatch` monotonic clock. | `SessionRecorder` (`vehicle-mobile/lib/services/session_recorder.dart`) stamps `created_utc` (`DateTime.now().toUtc()`, line 436), `first_packet_utc` / `last_packet_utc` (lines 100-101), per-row `rx_utc_iso` (lines 168-282, 523) and monotonic `rx_mono_ms` (`Stopwatch`, lines 169, 498), while preserving the node's `device_time_ms` from BLE packets (lines 192, 686, 751, 829). Rider marks carry phone UTC epoch ms `t_utc` (`lib/models/ride_mark.dart:59,78`). | Yes (OS UTC; can drift offline or step when cellular/NTP reconnects). |
| **`vehicle-server`** (FastAPI on Pi 5 edge or remote VPS, D-077) | Host OS `CLOCK_REALTIME` (`time.time`, `datetime.now(UTC)`) and `CLOCK_MONOTONIC` (`time.monotonic`). | **Live alerts:** `src/vehicle_server/alerts/service.py:4-6,61,115,118` deliberately evaluates sustain/cooldown timers on **server receive time** (`clock=time.time`) so a wrong or jumping device clock cannot stretch a debounce. **Stored series & alert replay:** `src/vehicle_server/series.py:11-13`, `decode.py:23,47`, and `alerts/replay.py:6` use the node's unwrapped `device_time_ms` relative to session `t0` (first sample across all session series) for a deterministic relative axis. **Ride marks matching:** `src/vehicle_server/marks.py:173-188` (`ride_window_ms`) matches a mark's `t_utc` against `[created_utc, created_utc + duration_ms]`, combining phone/server `created_utc` with `report.json` duration derived from `device_time_ms`. | Yes (host OS UTC; split across Pi edge and remote VPS). |

### Check of `dbc/platform.dbc` for an Existing Time Message

Inspected `dbc/platform.dbc` (all messages, lines 21–193): **no platform-bus time-synchronisation message exists today.**

The only time-related signals in `dbc/platform.dbc` are per-node 16-bit uptime counters (1 s resolution, saturating at `65535` s) carried inside the four existing heartbeat messages:
- `BO_ 129 HeartbeatRtCore: 8 RT_CORE` → `SG_ RT_CORE_UPTIME : 24|16@1+ (1,0) [0|65535] "s" SAFETY,CONN,LINUX` (line 59)
- `BO_ 130 HeartbeatSafety: 8 SAFETY` → `SG_ SAFETY_UPTIME : 24|16@1+ (1,0) [0|65535] "s" RT_CORE,LINUX` (line 66)
- `BO_ 132 HeartbeatConn: 8 CONN` → `SG_ CONN_UPTIME : 24|16@1+ (1,0) [0|65535] "s" RT_CORE,LINUX` (line 73)
- `BO_ 133 HeartbeatLinux: 8 LINUX` → `SG_ LINUX_UPTIME : 24|16@1+ (1,0) [0|65535] "s" RT_CORE` (line 80)

Because those uptime counters have 1 s granularity, no epoch reference, and no common master, any option that transmits shared time over the platform CAN bus requires a new message added through `/signal-change` (not invented here).

---

## 2. Proposed Time Synchronisation Options

All four options below are **proposed**; none is selected.

### Option (a) — `rt-core` as Platform-Bus Time Master (Proposed)

`rt-core` broadcasts a periodic platform-bus time-reference frame (e.g., at 1 Hz or 0.5 Hz, carrying `rt-core`'s 64-bit monotonic ms counter or epoch time + validity/epoch-source flags; exact DBC frame name and ID to be assigned via `/signal-change` if chosen).

- **What it needs per node:**
  - `vehicle-defs`: new platform-bus message in `dbc/platform.dbc` (and codegen update via `/signal-change`), optionally two-phase (sync + follow-up, AUTOSAR Global Time / StbM style) if TX-completion timestamping is needed.
  - `rt-core`: periodic TX of its monotonic/epoch timestamp (ideally latching hardware FDCAN TX timestamp or timer capture at frame transmission).
  - `connectivity-node` / `linux-node`: RX listener computing a filtered offset (`local_ms - master_ms`) for log and Kuksa alignment; `linux-node` can map `master_ms` against Linux UTC on ingest.
  - `safety-node`: **optional receive-only** (for diagnostic log correlation only, never an input to cornering, BSM, or immobilizer).
  - `phone` / `server`: unchanged on-bike; receives `rt-core` master timestamps (or monotonic + epoch validity flag) in uploaded sessions.
- **Accuracy class (proposed estimate):** ~1–5 ms with software RX stamping on 500 kbps classic CAN (jitter dominated by bus arbitration and ISR latency); sub-millisecond (~0.1–0.5 ms) only if FDCAN hardware timestamps + two-step follow-up messages are used. **Relative alignment across nodes is strong, but absolute UTC still drifts at crystal tolerance (~20–50 ppm → ~1.7–4.3 s/day) unless `rt-core` is disciplined by an external UTC source (see Options b and c).**
- **Failure behaviour when time source is missing:** If `rt-core` is absent or stops sending the time frame, each node continues on its own free-running monotonic clock (`hal_time_ms()`, `millis()`, `CLOCK_MONOTONIC`) and marks synced time invalid. Safety and telemetry loops keep running uninterrupted.
- **Cost & complexity:** Zero extra hardware cost; low–medium firmware complexity (one new non-safety platform CAN frame, negligible bus load < 0.1% at 1 Hz); requires defining epoch anchoring separately if UTC is needed.

### Option (b) — GNSS Time + 1PPS Directly into `rt-core` (Proposed)

The GNSS receiver (currently u-blox NEO-M8N on `connectivity-node`, `src/GpsCore.h:20`; moving or splitting UART/PPS to `rt-core` requires verifying hardware wiring — **CONFIRM**) feeds a 1PPS hardware pulse into an STM32H743 timer input-capture pin and UTC time-of-second (`NAV-PVT` / `NAV-TIMEUTC` time fields only, stripping lat/lon/height per invariant 7 / D-076) into `rt-core`, which then distributes time to the platform bus (as in Option a) or to `linux-node`.

- **What it needs per node:**
  - Hardware: 1PPS signal line from GNSS module to an `rt-core` STM32H743 timer input-capture pin (**CONFIRM** pinout on NUCLEO-H743ZI2 and whether the specific NEO-M8N breakout exposes TIMEPULSE/1PPS); GNSS UART time messages (either GNSS moves to `rt-core`, or `conn` forwards UTC second only while 1PPS wires to `rt-core`).
  - `rt-core`: TIM input-capture ISR latching `hal_time` / microsecond timer on each 1PPS rising edge, disciplining a software PLL/offset to UTC, and publishing the resulting UTC-anchored time on the platform bus (Option a).
  - `linux-node`: optional PPS tap or CAN-derived time sync (`chrony` refclock) if Pi 5 needs offline UTC without cellular/Wi-Fi.
  - `safety-node`: unaffected (continues on local monotonic HSE clock; invariant 3).
  - `phone` / `server`: receives UTC-anchored timestamps directly in ride logs (eliminating phone-clock vs. node-clock skew when matching `t_utc`).
- **Accuracy class (proposed estimate):** ~1–50 µs on `rt-core` itself (limited by NEO-M8N 1PPS jitter, typically tens of ns, plus H743 timer capture resolution); ~0.5–5 ms on other nodes via platform CAN distribution (Option a). True absolute UTC even with zero internet/cellular coverage (rural riding).
- **Failure behaviour when time source is missing (tunnels, garages, cold start before fix):** Before first GNSS time lock or during signal loss, `rt-core` holds over on its HSE crystal (~20–50 ppm, < 5 ms drift over a 100 s tunnel) and sets a `time_synced = false` / holdover flag. Cold-boot rides before any GNSS fix fall back to monotonic time until lock is acquired (note: `rt-core` must never step its monotonic `hal_time_ms()` backwards; UTC is kept as an additive offset, never mutating the monotonic tick).
- **Cost & complexity:** Low hardware cost if the existing NEO-M8N breakout already exposes 1PPS (**CONFIRM**); medium–high integration complexity (new physical wire to Main Box, timer input-capture + holdover logic in `rt-core`, plus enforcing invariant 7 / D-076 so GNSS position never crosses into `rt-core` logs or public paths).

### Option (c) — NTP / `chrony` on the Pi 5 with MCUs Following `rt-core` (Proposed)

Matches the extended-role sketch in `docs/hardware-architecture.md` §5b.8 (line 606: *"NTP time server — Distributes GPS time to the other MCUs"*), refined so that MCUs never depend on Linux availability or IP networking. `linux-node` runs `chrony` (disciplined by internet NTP when parked on Wi-Fi/hotspot, a Pi 5 RTC battery backup **CONFIRM**, and/or GNSS/NMEA/PPS if attached to the Pi), serves NTP over local Wi-Fi to `connectivity-node` and the phone/server, and periodically hands coarse UTC wall-clock anchors to `rt-core` over the platform bus (or `rt-core` remains monotonic master for fast MCU alignment while `linux-node` binds `rt-core` monotonic time to UTC).

- **What it needs per node:**
  - `linux-node`: `chrony` configured with upstream NTP + local RTC / optional GNSS refclock; optional local NTP server for `connectivity-node` (if Wi-Fi is up) and a low-rate platform-bus UTC anchor message (new DBC frame via `/signal-change` if sent to `rt-core`).
  - `rt-core`: remains monotonic timebase (`hal_time_ms()`) for all real-time control and EKF loops; optionally stores a `(master_ms, utc_ms)` anchor pair from `linux-node` for log headers without ever stepping `hal_time_ms()`.
  - `connectivity-node`: optional SNTP client against Pi 5 over Wi-Fi, or follows `rt-core` monotonic frame on platform bus.
  - `safety-node`: unaffected (invariant 3: never depends on Raspi or Wi-Fi).
  - `phone` / `server`: Pi 5 edge `vehicle-server` shares the same `chrony`-disciplined UTC clock; phone aligns to NTP when online or via session start offset.
- **Accuracy class (proposed estimate):** ~1–20 ms UTC on Pi 5 when internet NTP is reachable (or ~0.1–10 ms with GNSS/PPS refclock on Pi); degrades to Pi RTC/crystal drift (~20–50 ppm) when riding offline without GNSS. Cross-MCU alignment still depends on Option (a) (~1–5 ms) unless `rt-core` and Pi align over CAN.
- **Failure behaviour when time source is missing (Pi powered off, booting (~20 s, estimate, **CONFIRM**) after ignition, or offline in rural areas):** Because the Pi 5 boots much slower than MCUs and is QM-only (invariant 3/4), MCUs MUST start and log immediately on local monotonic time. If the Pi is absent or offline without an RTC battery (**CONFIRM**), UTC is unavailable or stale until Wi-Fi/NTP returns, and logs fall back to monotonic time + phone `created_utc`.
- **Cost & complexity:** Zero extra hardware if using Wi-Fi NTP only (small coin-cell battery cost if using Pi 5 RTC — **CONFIRM**); low Linux config complexity (`chrony`), but introduces a dependency on the Pi being booted and online for UTC accuracy, which is weakest in rural offline rides (`hardware-architecture.md` §5b.8 line 597).

### Option (d) — No Common Clock: Per-Node Monotonic Time + Post-Ride Offset Estimation (Proposed)

Keep every node on its own independent monotonic clock (essentially today's architecture, extended to `rt-core` + `linux-node` logs), and estimate linear clock offset and drift `(offset_ms, skew_ppm)` offline after the ride during `vehicle-server` ingest using shared observable events (e.g., `HeartbeatRtCore` / `VehicleSpeed` / `VehicleEngine` arrival times on `linux-node`, BLE packet `device_time_ms` vs. phone `rx_mono_ms`/`rx_utc_iso`, or correlated speed/RPM/IMU peaks).

- **What it needs per node:**
  - `rt-core`, `safety-node`, `connectivity-node`, `linux-node`, `phone`: zero new protocols, zero new wires, zero new DBC frames; each node logs its own monotonic timestamp (and phone/Pi log UTC receipt time where available, as `vehicle-mobile/lib/services/session_recorder.dart` already does with `(rx_utc_iso, rx_mono_ms, device_time_ms)`).
  - `vehicle-server`: offline alignment pass (e.g., robust linear regression / minimum-delay envelope on `(rx_mono_ms, device_time_ms)` pairs, handling `device_time_ms` 32-bit wrap and resets already flagged by `bringup.py:269`) to compute per-session UTC mapping and cross-stream offsets.
- **Accuracy class (proposed estimate):**
  - Between `rt-core` CAN logs and `linux-node` CAN/Kuksa logs (same physical bus, known frame sequence): ~1–5 ms post-ride.
  - Between BLE `device_time_ms` and phone `rx_utc_iso`: ~15–100 ms (limited by BLE connection interval, OS buffering, and phone UTC skew).
  - Between independent non-CAN sensors without shared bus events (e.g., Pi acoustic mic vs. `rt-core` raw vibration log): ~5–50 ms depending on correlation anchors; cannot provide real-time sub-ms UTC on the bike.
- **Failure behaviour when time source is missing:** Trivially resilient — there is no external time master to fail. Phone UTC jumps or offline clock skew still affect absolute UTC anchoring (`created_utc` vs. `t_utc`), and mid-ride MCU resets break a single linear offset segment (must be segmented per reset, detectable via `device_time_ms` resets / uptime decreases).
- **Cost & complexity:** Zero hardware cost, zero firmware complexity, zero new DBC frames; pushes alignment complexity into `vehicle-server` ingest and leaves real-time on-vehicle multi-node timestamps unaligned.

### Side-by-Side Comparison (Proposed)

| Option (Proposed) | Hardware Added | New DBC / Protocol | On-Bike Cross-Node Accuracy | Absolute UTC Offline (Rural) | Failure Impact | Firmware Complexity |
|---|---|---|---|---|---|---|
| **(a) `rt-core` CAN master** | None | 1 platform CAN frame | ~1–5 ms (SW) / < 1 ms (HW TS) | No (crystal drift without UTC anchor) | Nodes hold monotonic; zero safety impact | Low–Medium |
| **(b) GNSS + 1PPS → `rt-core`** | 1PPS wire (**CONFIRM** pinout) | 1 platform CAN frame (to share) | ~1–50 µs on `rt-core`; ~1–5 ms on bus | **Yes** (once GNSS locks) | Crystal holdover + `synced=false` flag | Medium–High |
| **(c) Pi `chrony`/NTP + `rt-core`** | Optional Pi 5 RTC battery (**CONFIRM**) | Optional Pi → `rt-core` anchor frame | ~1–20 ms (Pi↔MCUs via Option a) | Only with RTC or Pi GNSS | Delayed until Pi boots (~20 s, estimate, **CONFIRM**) / stale offline | Low (Pi) + Low (MCU) |
| **(d) No common clock + post-ride** | None | None | None live (~1–100 ms post-ride) | Phone/Pi OS clock only | None (no master); MCU resets need re-segmentation | Zero (MCU) / Medium (server) |

*(Note: Options can be combined in phases — e.g. starting with (d) for Phase 0 bring-up, adding (a) once platform-bus logging starts, and anchoring `rt-core` via (b) or (c) if offline UTC accuracy is needed. Any combination is **proposed**.)*

---

## 3. Consumer Accuracy Requirements Table (Proposed)

All target tolerances below are **proposed** engineering bounds derived from each consumer's sampling period and data model; none is a final requirement.

| Consumer | Where It Runs / Code Reference | Needs Absolute UTC or Relative Time? | Proposed Accuracy Need | Notes & Sensitivity |
|---|---|---|---|---|
| **Cornering & BSM safety path** | `vehicle-safety-node` (`safety_app.c`, `platform_link.c`) | **Local monotonic only** (never shared/UTC) | Local `now_ms` within `SAFETY_APP_PASS_MAX_MS` (5 ms); E2E freshness on 20 ms `EkfLean` | **Hard invariant (invariant 3, D-042):** must operate with zero external time source. Uses local HSE crystal (D-134) and E2E counters/timeouts only. |
| **EKF sensor fusion (lean, friction, mass)** | `vehicle-rt-core` (`features/cornering/`, `services/imu_core.h`) | **Single-node monotonic** (`timebase_now_ms()`) | ≤ 1 ms internal IMU sample spacing; ≤ 10–20 ms alignment with the vehicle speed sample (polled every 110 ms, `uds/vehicle_cl250.yaml`) | IMU and EKF run on `rt-core` itself; speed arrives on `rt-core`'s own UDS poller (110 ms period, 300 ms stale limit). Does not need cross-node UTC. |
| **Multi-modal logging alignment (CAN + IMU + vibration + Pi audio/video)** | `rt-core` SD log + `vehicle-linux-node` (`blackbox/core.py`, `blackbox/store.py`) + `vehicle-server` (`series.py`) | **Common relative axis** across `rt-core` and Pi (UTC nice-to-have for file naming) | **~5–20 ms** for CAN/IMU/video overlay and early-fusion anomaly windows (`hardware-architecture.md` §5b.9, ≤ 10 Hz features); **~1–5 ms** if aligning raw vibration bursts to acoustic frames | `rt-core` logs raw 1 kHz vibration locally while Pi extracts acoustic MFCCs (D-044). Cross-node drift > 50–100 ms smears window alignment across 10 Hz feature frames. |
| **Early-fusion anomaly detection & ML windows** | `vehicle-linux-node` (Kuksa/VSS) & `vehicle-ml` (sliding windows) | **Relative time** within a ride | **~20–50 ms** (window lengths are seconds; CAN/feature rates are 1–20 Hz) | Robust to small offsets as long as clock is monotonic and free of backwards jumps. |
| **Live in-ride alerts (D-129)** | `vehicle-server/src/vehicle_server/alerts/service.py:4-6,61` | **Server receive time** (monotonic/wall delta) | **~100–500 ms** (sustain windows in `faults/alert_rules.yaml` are 5–60 s) | Intentionally uses server receive clock (`alerts/service.py:4-6`) so bad device clocks cannot manipulate debounce timers; replay (`alerts/replay.py:6`) uses relative `device_time_ms`. |
| **Ride marks matching `t_utc` (D-133)** | `vehicle-mobile` (`ride_mark.dart:59`) → `vehicle-server` (`marks.py:173-188`, `marks_export.py`) → `vehicle-ml` | **Absolute UTC** (phone `t_utc` matched against session `[created_utc, created_utc + duration_ms]`) | **~0.5–2 s** (human tap reaction time is ~1–3 s; ML weak-label windows are several seconds around `offset_s`) | Currently vulnerable if phone UTC and recording node/server `created_utc` disagree by > a few seconds (e.g., offline phone clock skew or delayed session start vs. first packet). |
| **Multi-node SIL (T69)** | Host PC / CI (`docs/ideas/multi-node-sil.md` §5) | **Stepped virtual clock** or host `CLOCK_MONOTONIC` | **1 ms tick** (`hal_time_host_advance`, `safety_app_step(now_ms)`) for deterministic runs; real-time wall-clock suffers OS jitter (14–20 ms observed on macOS in `docs/ideas/sil-inventory.md` §3.3) | Separate from on-vehicle hardware time sync, though a stepped virtual clock can test Option (a) time-frame loss and holdover deterministically. |

---

## 4. Non-Negotiable Constraints

Any decision closing **Q-008** must preserve all platform invariants:

1. **Safety-node independence (Invariant 3, D-042):** `vehicle-safety-node` (STM32G474) MUST run cornering, blind-spot, and immobilizer logic using only its own HSE-backed monotonic clock (`now_ms`) and E2E freshness checks. It must never wait for, block on, or degrade when GNSS, NTP, Pi 5, Wi-Fi, or a platform-bus time frame is absent, corrupt, or jumping.
2. **Read-only ECU bus (Invariant 1, D-020, D-037):** Time synchronisation traffic is strictly confined to the platform CAN bus (or local Pi/Wi-Fi links). Nothing related to time sync is ever transmitted on the CL250 vehicle bus.
3. **No position leakage via GNSS time (Invariant 7, D-076):** If Option (b) or a GNSS refclock on the Pi uses UBX `NAV-PVT` / `NAV-TIMEUTC`, only time/validity fields (`year..sec`, `nano`, `valid`, `tAcc`, `iTOW`) may cross into time-sync paths; latitude, longitude, and height must never appear in platform CAN frames, MCU logs, or public artifacts (continuing the `GpsFix` design in `vehicle-connectivity-node/src/GpsFix.h:8-11`).
4. **Monotonicity of MCU control loops:** `hal_time_ms()` (`vehicle-rt-core/src/hal/hal_time.h`) and `safety_app_step(now_ms)` must stay strictly monotonic. Any external UTC or master-time correction MUST be tracked as a separate offset (`utc_offset_ms` + validity flag), never by stepping the 32-bit monotonic tick backwards or forwards.
5. **No dynamic allocation on MCUs (Invariant 5):** Any MCU time-sync receiver/transmitter uses fixed-size static structs only.

---

## 5. Open Questions for Claude and the User (Q-008 Stays Open)

1. **Do Phase 0 / first-ride logs need sub-second cross-node alignment, or is Option (d) enough until the Pi 5 and `rt-core` run together?**
2. **Where will the u-blox NEO-M8N live after Phase 0?** Today it is wired to `connectivity-node` (`src/GpsCore.h`). Does its breakout expose a 1PPS pin (**CONFIRM**), and should GNSS stay on `connectivity-node` or move to `rt-core` / Pi 5?
3. **Is a Pi 5 RTC backup battery installed (**CONFIRM**)?** Without one, Option (c) has no valid UTC on cold offline starts in rural areas.
4. **If Option (a) is chosen, should the platform-bus time frame carry monotonic ms only, or UTC epoch ms + validity flags (requiring an external anchor from Option b or c)?** Adding any platform CAN message requires a `/signal-change` PR in `vehicle-defs`.
5. **How should `ride_window_ms` (`vehicle-server/src/vehicle_server/marks.py:173-188`) handle phone-vs-node clock skew?** Recording `first_packet_utc` alongside `device_time_ms` (already present in `SessionRecorder`) allows computing an anchor even without on-bike UTC sync.
