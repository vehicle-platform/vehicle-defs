# Documentation Index — where to look for what

**Rule (for Claude):** start with `ARCHITECTURE.md` + `DECISIONS.md`. The raw docs below are large (~2,800 lines in total), so read only the needed section with `Read offset/limit`, or ask the `docs-researcher` agent. Line numbers are as of 2026-09-29. If a doc changes, refresh them with `grep -n '^#' <file>`.

Authority order: `DECISIONS.md` > `ARCHITECTURE.md` > other English docs. For vehicle facts, `uds/vehicle_cl250.yaml` beats `legacy-telemetry-notes.md`. `archive/` is not read by Claude (D-038).

| File | Status | Use for |
|---|---|---|
| `ARCHITECTURE.md` | **Authoritative (summary)** | Units, buses, CAN ID plan, E2E, codegen pipeline, layers, data flows, CI pyramid |
| `DECISIONS.md` | **Authoritative** | Decisions (ADR D-xxx) + open questions (Q-xxx) |
| `hardware-architecture.md` | Detail (rationale); **bus topology superseded** by ARCHITECTURE §3 | Subsystem rationale, references, Phase 2 list |
| `vehicle-work-plan.md` | On-vehicle plan (bus access per D-037) | CL250 data, mounting, field test protocols T0-T4, virtual dyno |
| `phase0-data-collection-plan.md` | Authoritative (data), superseded in part (D-032, D-045) | Recording format, metadata schema, work packages WP-1..WP-7 |
| `feature-pool.md` | Pool | All feature candidates (IDs F1.., K1.., ...), open-source references |
| `hardware-procurement-list.md` | Current (v2.9, 2026-10-24, D-072/D-073, D-082) | Full parts list by purchase wave, with Turkish store links and prices, items on hand |
| `hardware-integration.md` | Working guide (2026-10-03) | Phase 0 on-vehicle build: parts, wiring, mounting, bring-up gates, first measurements, open items |
| `vehicle-data-catalog.md` | Working list (2026-10-15), **not a decision** | Every signal read today, pollable, discoverable or derivable; standard data outside the polled table; on-bike proprietary-DID discovery procedure; vehicle bus load; switch/ABS acquisition paths; per-repo code coverage |
| `ideas/*` | Idea notes (drafted with Gemini, 2026-10-05), **not decisions** | `can-data-expansion.md` (CAN/UDS expansion, tasks V-01..V-16), `mcp-scenarios.md` (vehicle-mcp scenarios), `vehicle-signal-taxonomy.md` (groups G/I beyond the CL250, scale tiers, anomaly-model direction; Antigravity, 2026-10-18), `can-analyzer-master-plan.md` (CAN analyzer benchmark and phased plan; Antigravity, 2026-10-19; the repo itself is D-081), `physics-informed-anomaly.md` (D-083 stage 0 physics models, D-084 fault-catalog schema and the deep-research brief), `cl250-technical-baseline.md` (CL250 electrical figures, mostly CONFIRM; Antigravity, 2026-10-20), `ride-summary-did-layout.md` (C3 part 2b proposal for the 0xFD40-0xFD4E ride-summary DID layouts; Claude, 2026-10-26, awaiting the user), `derived-thresholds-research.md` (research brief to replace the D-103 provisional derived-signal thresholds; Claude, 2026-11-05), `node-health-vss.md` (Q-016: per-node heartbeat signal names + `Vehicle.Motorcycle.Nodes.*` paths for the linux-node health panel; Claude, 2026-11-11, awaiting the user). Each lists its known conflicts with recorded decisions at the top; nothing applies without a D-xxx |
| `h755-pin-plan.md` | Proposal v0.1 (2026-11-10), **not a decision** | Roadmap S2: NUCLEO-H745ZI-Q pin and port plan per core (M7 ports A-D, M4 ports E-G), from ST's open pin data; to be checked in CubeMX + UM2408 by the user |
| `e2e-profile.md` | **Authoritative (spec, short)** | E2E frame layout, CRC, counter, receiver statuses, timeouts (D-005, D-026) |
| `legacy-telemetry-notes.md` | Reference (short) | Legacy HondaCl250_Telemetry facts per D-023: UDS state machine, NRC table, bus-off backoff, ISO-TP first-frame pitfall, ESP32-S3 pin map, discrepancies, accepted security risks, legacy test coverage |
| `archive/tr/*` | Turkish originals + the two advisor documents (D-038) | **Not read by Claude.** Ç1-Ç8 are in `ARCHITECTURE.md` §9 |

## hardware-architecture.md (     902 lines)

| Lines | Section |
|---|---|
| 13-99 | §1-5 philosophy, units (superseded in part by D-072/D-073), chip choices, CAN rules, latency (bus topology: see ARCHITECTURE §3) |
| 100-195 | §5b.0-0c context classification, conditioning factors, context bus |
| 196-246 | §5b.1 blind spot monitoring (BSM) |
| 247-292 | §5b.2 cornering safety (3 layers) |
| 293-340 | §5b.3 immobilizer, park mode, power board (former io-node, D-072) |
| 341-386 | §5b.4 display / LED ring / profile pages |
| 387-421 | §5b.4a helmet unit: visor HUD, microphone, voice (D-073) |
| 422-494 | §5b.5 lane departure warning (LDW) |
| 495-513 | §5b.6 voice commands (ESP-SR) |
| 514-572 | §5b.7 vehicle-mcp, privacy |
| 573-624 | §5b.8 linux-node SDV layer, Raspi power/thermal |
| 625-672 | §5b.9 anomaly model + validation protocol |
| 673-692 | §5b.10-11 virtual dyno, comfort/energy/driver assistance |
| 693-728 | §6-7 module vs chip, staged rollout |
| 729-790 | §8-9 repo structure, dependency direction, setup order |
| 791-860 | §9b HIL bench |
| 861-     902 | §10 Phase 2, eliminated items, open notes |

## vehicle-work-plan.md (673 lines)

| Lines | Section |
|---|---|
| 19-92 | §2 CL250 data, ratios, wheel radius, speed formula |
| 93-202 | §3 on-vehicle hardware (DUT, CAN + bus safety note 3.2, power, IMU, GPS, microphone) |
| 203-231 | §4 wiring, EMC, sleep current |
| 232-291 | §5 parameter measurement, **5.5 CAN signal map extraction (274)** |
| 292-349 | §6 data collection: signals, metadata, storage |
| 350-422 | §7 field test classes T0-T4 |
| 423-475 | §8 virtual dynamometer protocol |
| 476-548 | §9-11 assistant profiles, modification experiments, real dyno |
| 549-587 | §12 legal/safety framework |
| 588-673 | §13-16 BOM, schedule, risks, deliverables |

## phase0-data-collection-plan.md (278 lines)

Superseded-in-part note (D-032, D-045) at the top, line 5 · §1 work packages 27-40 · §3 data schema 76-124 (format decision 111) · §4-8 WP-3..WP-7 125-206 · §9 hardware 207-252 · §10-11 effort, next 253-278

## feature-pool.md (624 lines)

§1-13 categories 26-311 (vehicle functions §9 173, comfort/energy §9c 223, vision §10 254) · §14 top ten 312 · §15 out of pool 332 · §16 prioritization 345 · §17 hardware analysis 361-404 · §18 open-source ecosystem 405-624 (SDV §18.3 446, test/sim §18.5 479, data/ML §18.6 495, reference projects §18.7 510, costs §18.9 545)

## hardware-procurement-list.md (299 lines)

On hand 15 · Part 1 core, power chain, boards A/B/C1/C2, boxes 31 · Part 2 anomaly sensors 96 (2A 100, 2B 110, 2C 128, 2D boxes 140) · Part 3 safety 160 (3A M4 partition 164, 3B camera 184, 3C boxes 191) · Part 4 helmet 208 · Part 5 Pi 5 + HIL 233 (5A 235, 5B 248) · board/box master reference 262 · budget 284 · removed from v1.0 294

## archive/tr/ (for the user; not read by Claude, D-038)

- `bitirme-projesi-kapsam.md`: thesis scope (§5 Ç1-Ç8 / G1-G5), validation, 14-week schedule, risks
- `bitirme-raporu-hoca-sunumu.md`: advisor report (methodology, MCU adequacy, HIL, scalability)
- the Turkish originals of the English docs (not maintained)
