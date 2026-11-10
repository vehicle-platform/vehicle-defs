# CLAUDE.md — vehicle-defs

@.claude/PLATFORM-RULES.md

## What this repo is

The **single source of truth for signals** in the motorcycle platform. The CAN message map, the VSS (COVESA Vehicle Signal Specification) semantic model, and the diagnostic (UDS) service definitions live here. **The other 10 repos read this repo; none of them invent their own signal definitions.**

## What this repo is NOT

- Executable code (firmware, services) does not live here — only schema/definitions. Exception: `tools/codegen` (a development tool) and the `gen/` output it produces (pack/unpack/E2E code derived from the definitions).
- There is no business logic. It defines *what* a signal *is*, not *how* it is used.

## File structure (D-003, D-004 — `docs/ARCHITECTURE.md` §5)

```
/uds/vehicle_cl250.yaml → CL250 ECU DIDs polled by rt-core (addressing, formulas, poll rates, poll priority D-043; verified, D-019)
/dbc/cl250.dbc        → vehicle-bus broadcast frames, only if passive traffic is found (Q-001); skeleton
/dbc/platform.dbc     → platform bus (our nodes; ID plan in ARCHITECTURE §4; E2E attributes)
/vss/overlay.vspec    → Vehicle.Motorcycle.* extensions + dbc2vss mappings (kuksa-can-provider format)
/uds/obd_catalog.yaml → vehicle-independent OBD/UDS catalog (J1979 PIDs, multi-value fields, ISO 14229 identification DIDs), NOT polled; host-only (D-066, D-078)
/uds/dids.yaml        → per-node UDS servers: IDs, timing, services, DIDs, DTCs
/uds/iso14229.yaml    → generic ISO 14229-1 codes (names for numbers only)
/ble/ble_schema.json  → BLE packet schema of conn: telemetry v2/v3/v4, IMU block, GATT UUIDs; single source for conn, vehicle-mobile, vehicle-server (D-061)
/limits/platform_limits.yaml → k_yellow/k_red, µ/mass fallbacks, rt-core speed rules, per-node scope (provisional, D-029, D-048)
/vehicle/cl250_constants.yaml → CL250 constants for the derived signals, status + source per value (D-070)
/derived/cl250_derived.yaml → derived signal definitions + non-DID sensor inputs + ride-summary DIDs 0xFD40–0xFD5F; no formulas (D-070)
/faults/catalog.yaml → vehicle-independent fault catalog, FMEA style, sourced entries (D-084); no source = CONFIRM, not displayable
/vehicle/cl250_faults.yaml → catalog entries that apply to the CL250; their signals must exist in defs (D-084, D-078)
/mailbox/h755_mailbox.yaml → STM32H755 M7↔M4 mailbox: region, slot order, HSEM IDs; frame IDs/lengths come from platform.dbc (D-072 item 4c, D-093)
/tools/codegen/       → Python: cantools + vss-tools; generates node-filtered C, Python, Dart, VSS JSON
/gen/                 → GENERATED output (no manual edits; `make gen` + commit before tagging): `c/<node>`, `python/vehicle_defs`, `dart/vehicle_defs` (BLE schema), `vss`
/misra/               → MISRA C:2012 deviation register for gen/c + cppcheck suppressions (D-046)
/docs/                → all platform documentation (index: docs/README.md)
/CHANGELOG.md         → what changed in each release
```

Signal add/change flow: the `/signal-change` skill. CI must fail red if `gen/` is out of sync with the source.

## Versioning rule — THE MOST IMPORTANT RULE

This repo is **semantically versioned**: `v0.x` now (v0.1.0 … v0.9.0), `v1.0.0` once `platform.dbc` is stable (D-013, D-036). Other repos pin to a specific version (git submodule + tag, or package version). Adding/changing/removing a signal:

1. Is done here first, a line is added to `CHANGELOG.md`
2. A new version is tagged
3. **Only after that** are dependent repos (`vehicle-rt-core`, `vehicle-linux-node`, etc.) updated to the new version — not automatic, a deliberate step

When Claude Code works in this repo: after changing a signal schema, **check which repos depend on this version and remind the user** — do not break them silently.

## Build and checks

Tooling is a uv project in `tools/codegen` (Python 3.11+, cantools, vss-tools 6.0). From the repo root:

```bash
make check   # strict DBC parse + vehicle-codegen check + ruff + pytest (needs gcc for C tests)
make gen     # regenerate gen/ (first run downloads the pinned COVESA VSS 6.0 release)
make drift   # make gen, then fail if gen/ changed — CI runs this
make misra   # cppcheck style + MISRA C:2012 on every gen/c node, blocking in CI (D-046)
```

MISRA findings in `gen/c` are fixed in the codegen, never in `gen/`; a deviation needs a `DEV-xxx` row in `misra/README.md` and a line in `misra/suppressions.txt`.

C targets and the ID plan: `tools/codegen/src/vehicle_codegen/config.py`. E2E spec: `docs/e2e-profile.md`. Approved `Vehicle.Motorcycle.*` paths go into `APPROVED_EXTENSIONS` in `gen_vss.py` (only after the user says yes).

## Signal naming

Follow the VSS taxonomy (e.g. `Vehicle.Powertrain.CombustionEngine.Speed`). Do not invent your own arbitrary naming — check COVESA's VSS specification; if there is no VSS equivalent for a motorcycle-specific signal, propose a consistent extension under `Vehicle.Motorcycle.*` and **ask the user first**, do not add it silently.

## Context — project architecture

For the full hardware/repo architecture: `docs/ARCHITECTURE.md` (summary) and `docs/DECISIONS.md` · detail: `docs/hardware-architecture.md` §8-9 (section index in `docs/README.md`). You don't need to read this file every time — only check it when a signal/repo dependency is unclear.

## Vehicle: CL250 (first application)

Motorcycle: Honda CL250. Verified (D-019): classic CAN 500 kbps on the DLC, data by UDS `0x22` polling on 29-bit `0x18DA10F1`→`0x18DAF110`. The platform bus is independent of it: classic CAN 500 kbps (D-009). `/dbc/cl250.dbc` is this vehicle's concrete definition; the schema under `/vss/` is vehicle-independent.
