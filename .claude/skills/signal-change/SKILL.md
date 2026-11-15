---
name: signal-change
description: Add, modify or remove a CAN message/signal, VSS mapping or UDS DID in vehicle-defs, then regenerate code and bump the version. Use for any change to dbc/cl250.dbc, dbc/platform.dbc, vss/overlay.vspec or uds/dids.yaml, or when a consumer repo needs a signal that does not exist yet. Supersedes the older user-level can-dbc-conventions skill.
---

<!-- Synced from vehicle-workspace/.claude/skills/signal-change/SKILL.md by scripts/sync_claude.py. Do not edit here; edit the source and re-run the sync. -->

# Signal change workflow (vehicle-defs)

Background: `ARCHITECTURE.md` §3-5, decisions D-003/D-004/D-005/D-009. Signals are **only** defined here; consumers never hand-write them.

## 1. Decide which bus

- **Vehicle ECU data** (`uds/vehicle_cl250.yaml`): CL250 data is poll-based (D-019). Each entry: DID, name, request/response addressing, response byte layout, J1979-style formula, unit, range, poll period, `verified: true|false` + evidence. rt-core is the only poller (D-021); a signal that others need is **also** added to `platform.dbc` as rt-core's republish. `dbc/cl250.dbc` is only for passive broadcast frames, if ever found (Q-001); mark unverified ones `CM_ ... "UNVERIFIED - <evidence>"`.
- **Platform bus** (`dbc/platform.dbc`): messages between our nodes. Nodes: `RT_CORE SAFETY CONN LINUX HIL_SIM TESTER` (IO retired by D-072; SAFETY is the separate G474 safety MCU on the platform bus, D-118). Pick the ID from the class range (ARCHITECTURE §4):
  `0x010-0x07F` safety-critical (E2E mandatory) · `0x080+node_id` heartbeat (E2E) · `0x100-0x3FF` state/context · `0x400-0x5FF` telemetry · `0x600-0x6FF` bridge/dev · `0x700-0x7FF` UDS. Check that the ID is free.

## 2. Edit the DBC (cantools-compatible)

- Message names `PascalCase`, signal names `SNAKE_CASE`, units in SI or the conventional unit (`km/h`, `rpm`, `deg`, `degC`, `V`, `A`).
- Pick factor/offset/min/max so the physical range fits with margin. Prefer little-endian (`@1`) for platform messages.
- Required message attributes on `platform.dbc` (define once with `BA_DEF_` if missing):
  ```
  BA_DEF_ BO_ "GenMsgCycleTime" INT 0 10000;
  BA_DEF_ BO_ "E2E_Protected" ENUM "No","Yes";
  BA_DEF_ BO_ "E2E_DataID" INT 0 65535;
  BA_ "GenMsgCycleTime" BO_ <id_dec> 20;
  ```
- E2E-protected messages reserve **byte 0 = `E2E_CRC` (8 bit)** and **byte 1 bits 0-3 = `E2E_COUNTER` (4 bit)**, declared as real signals. `E2E_DataID` must be unique across the platform bus.
- Example:
  ```
  BO_ 32 LeanEstimate: 8 RT_CORE
   SG_ E2E_CRC : 0|8@1+ (1,0) [0|255] "" SAFETY
   SG_ E2E_COUNTER : 8|4@1+ (1,0) [0|15] "" SAFETY
   SG_ LEAN_ANGLE : 16|16@1- (0.01,0) [-90|90] "deg" SAFETY,LINUX
   SG_ LEAN_ANGLE_QUALITY : 32|8@1+ (1,0) [0|100] "%" SAFETY
  ```

## 3. VSS mapping (only if the signal is consumed on the Raspi side)

- Use a standard COVESA VSS path if one exists. Otherwise propose a `Vehicle.Motorcycle.*` extension and **ask the user before adding it**.
- Map in `vss/overlay.vspec` using the kuksa-can-provider `dbc2vss` format:
  ```yaml
  Vehicle.Motorcycle.LeanAngle:
    type: sensor
    datatype: float
    unit: degrees
    description: Roll angle estimated by rt-core EKF; positive = right.
    dbc2vss:
      signal: LEAN_ANGLE
      interval_ms: 50
  ```
- Safety-path signals may be mirrored to VSS for display/logging, but no safety decision may read them from VSS.

## 4. UDS DIDs (if applicable)

Add to `uds/dids.yaml` under the owning node: DID (0xF1xx identification, 0xFDxx platform-specific), name, length, encoding, access (read-only unless the user approves). The vehicle ECU is never written to.

## 5. Generate, validate, version

1. `make gen`: regenerates `gen/c/<node>/`, `gen/python/`, `gen/vss/`. Never hand-edit `gen/`.
2. Validate: `python -c "import cantools; cantools.database.load_file('dbc/platform.dbc', strict=True)"` (same for cl250.dbc), and the codegen's own checks (ID ranges, unique DataIDs, E2E layout).
3. `CHANGELOG.md`: add a line under `Unreleased`. Semver: new message/signal = MINOR; changing or removing an existing one (ID, layout, scale, name) = MAJOR; comment-only = PATCH.
4. Tag only when the user asks (`vX.Y.Z`), then update the root `manifest.yaml`.

## 6. Tell the user about consumers

List the repos that include the affected node's `gen/c/<node>/` or the VSS path (grep in `../vehicle-*/`), and remind the user that each needs a deliberate submodule bump. Nothing updates automatically. Afterwards, run `vss-schema-guardian` on the changed consumer repos.
