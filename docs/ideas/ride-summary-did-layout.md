# Ride-summary DID layout (C3 part 2b) — proposal, awaiting the user

Status: **approved 2026-11-03 as D-098** (with the review fixes of checks 3, 4 and 8); D-098 is authoritative where this note differs. 2026-10-26, Claude. Decisions it builds on: D-070 item 4 (class-B ride summaries are rt-core UDS DIDs 0xFD40-0xFD5F), D-087 item 2 (a ride = one D-075 stop epoch), D-055/D-067 (the existing `record` DID encoding). On approval it becomes a decision (D-0xx) and a `/signal-change`.

## Problem

`derived/cl250_derived.yaml` reserves one DID per ride-summary record (0xFD40-0xFD49 summaries, 0xFD4A-0xFD4E health windows) and gives every class-B signal its record, `range` and `resolution`, but no byte layout. rt-core computes 12 of these signals since rt-core#54 and cannot serve them without a layout, and a hand-written layout would break invariant 2.

## Proposal

1. **Generated, not hand-written.** Codegen builds each record's layout from `cl250_derived.yaml` (the class-B signals of that `record`, in YAML order) and emits it into the rt-core `platform_uds` tables as an ordinary `record` DID (the same encoding as 0xFD02/0xFD03: big-endian unsigned fields of 1, 2 or 4 bytes that saturate, never wrap). No layout is typed into `uds/dids.yaml` by hand.
2. **Field encoding.** `raw = round((value - range.min) / resolution)`, unsigned, big-endian. Width = the smallest of 1, 2 or 4 bytes whose all-ones value is above the largest raw value: the all-ones value is reserved as **NOT_AVAILABLE** (not computed on rt-core yet, not valid, or no ride closed). A value outside the range is NOT_AVAILABLE too (D-070: never clamped). Offsetting by `range.min` makes signed signals unsigned, so the existing encoder needs no signed field type.
3. **Header (4 bytes, every record).** Byte 0: layout version (1). Bytes 1-2: the ride's stop-epoch counter (uint16, from `services/tester_epoch`; lets a reader match records of the same ride and see a new ride). Byte 3: flags — bit 0 `RIDE_CLOSED` (1 = the last closed ride, 0 = no ride closed since boot, all fields NOT_AVAILABLE); bits 1-7 reserved 0.
4. **Which ride.** The DIDs serve the **last closed ride** (the previous-ride record of rt-core#54). The running ride is not served in v1 (it changes during the read, and the log covers it); a "current ride" mirror at 0xFD50-0xFD5E stays possible later inside the reserved block.
5. **Multi-element signals are left out of v1.** `operating_point_time` (RPM × load histogram), `fuel_trim_map`, `ride_coolant_time_at_temp`, `ride_oil_time_at_temp` and the per-gear `ride_final_drive_ratio` get their own layout later (a histogram does not fit a small record; ISO-TP allows it, but the server buffer and the D-070 item 6 cost need a separate look). Their records carry only the scalar fields; `RIDE_OPERATING_POINTS` (only a histogram) is not served in v1.
6. **Serving.** The platform UDS server (comms task) answers 0x22 for these DIDs from a comms-side copy of the closed-ride record, which the derived task hands over through one `services/snapshot` (derived → comms, single producer and consumer, the 0xFD03 pattern: the server never reads the derived state itself). Read-only, platform bus only, never the vehicle bus.

## Resulting sizes (scalar fields + 4 B header, computed from the current YAML)

| DID | Record | Scalar fields | Bytes |
|---|---|---|---|
| 0xFD40 | RIDE_USAGE | distance 4 B, time 4 B, idle time 4 B, stop count 2 B | 18 |
| 0xFD41 | RIDE_FUELING | fuel used, consumption, LTFT mean, STFT std (2 B each) | 12 |
| 0xFD42 | RIDE_OPERATING_POINTS | — (histogram only) | not served in v1 |
| 0xFD43 | RIDE_THERMAL | 8 fields (1-2 B) | 14 |
| 0xFD44 | RIDE_ELECTRICAL | cranking dip, rest voltage | 8 |
| 0xFD45 | RIDE_ENGINE_STRESS | 6 fields | 22 |
| 0xFD46 | RIDE_DRIVETRAIN | 4 fields | 12 |
| 0xFD47 | RIDE_CALIBRATION | 4 fields | 14 |
| 0xFD48 | RIDE_RIDER_STYLE | 2 fields | 8 |
| 0xFD49 | RIDE_ECU_HEALTH | 7 fields | 21 |
| 0xFD4A-0xFD4E | health windows W1-W5 | 4-8 fields | 12-20 |

Today rt-core computes 12 of the scalar fields; the others read NOT_AVAILABLE until their formula exists, so the layout is stable while signals are added.

## Open points for the user

- Approve the encoding (offset by `range.min`, all-ones = NOT_AVAILABLE, 4-byte header with the epoch counter) and "last closed ride only" for v1.
- Approve leaving the histogram / per-gear signals for a later layout.
- A defs MINOR release follows (new generated DIDs), then rt-core serves them (QM, D-070 item 5).

## Compatibility review (DeepSeek, 2026-11-02)

Reviewed against defs `v0.19.1` (`14eaae6`). The proposal text above is unchanged. The size rows were recomputed from `derived/cl250_derived.yaml` with the throwaway script pasted in `external-ai/log/2026-11-02-opencode-long-run-8.md`; the script reads the record entries, class-B scalar signals, `range`, `resolution`, `bins` and `per_gear` at run time.

| Check | Evidence (file:line) | Result | Note |
|---|---|---|---|
| 1. DID range | `derived/cl250_derived.yaml:212-258`; `uds/dids.yaml:14-18`; `uds/obd_catalog.yaml` (no `0xFDxx`) | OK | The 15 records are `0xFD40-0xFD4E`, inside the reserved `0xFD40-0xFD5F` block and clear of every explicit DID and the OBD candidate catalog. `0xFD42` exists but is not served in v1. |
| 2. Sizes table | `derived/cl250_derived.yaml:1166-1985`; throwaway script (log) | OK | No row differs from the table above. 70 scalar fields; the largest record is 22 B (`RIDE_ENGINE_STRESS`); no raw maximum needs more than 4 B; no raw maximum is an exact `.5` rounding tie. `RIDE_OPERATING_POINTS` is the only scalar-empty record. |
| 3. Record encoding | `tools/codegen/src/vehicle_codegen/gen_uds.py:285-317`; `uds/dids.yaml:19-21`; `vehicle-rt-core/src/features/uds/uds_server.c:50-62`; `vehicle-rt-core/src/services/lean_health_core.c:104-108` | OPEN | Codegen already accepts 1/2/4-byte big-endian record fields and emits `*_MAX` (the all-ones value); no generated record uses a 4-byte field yet. The generated tables describe the layout, not the operation: saturation is done by the hand-written writer (0xFD02's `put_be` plus `clamp`), and 0xFD03 already uses a per-field all-ones sentinel (`UNLEARNED_S_UNKNOWN`) in its writer, but that use is hand-arranged, not a generic codegen feature. The proposal needs one: a field marker that emits e.g. `*_NA`, and a writer that uses it for missing/out-of-range values, distinct from `*_MAX` (which already means saturation, D-055). Do not reuse `*_MAX` as NOT_AVAILABLE. |
| 4. Header | `vehicle-rt-core/src/services/tester_epoch.h:28-45`; `vehicle-rt-core/src/features/derived/derived_ride.h:71-79`; `vehicle-rt-core/src/features/derived/derived_ride.c:304-317`; `vehicle-rt-core/src/features/uds/uds_client.c:68-71` | MISMATCH | The counter type matches: `tester_epoch_t.counter` is `uint16_t` and wraps; consumers compare with `!=`. But rt-core keeps the counter only for the **open** ride (`derived_ride_t.counter`); `prev[]` stores the closed values without the epoch counter, and `derived_ride_close()` does not save it. Once a new ride opens, the last-closed record's counter is gone, so header bytes 1-2 cannot be built from the current state. Add a `prev_counter` at close (or remove/derive the header counter) before implementation. After 65,535 epochs the counter wraps to 0; `uds_client_open()` also resets it to 0 and the first epoch repeats 1, so it is not a unique ride id across a re-open or wrap. If the proposal's all-ones = NOT_AVAILABLE rule is applied to the header counter itself, a valid counter of `0xFFFF` would also read as NOT_AVAILABLE; exempt the header field from that rule (or define it separately). |
| 5. Payload size | `vehicle-rt-core/src/features/uds/uds_server_core.h:60-66`; `vehicle-rt-core/src/features/uds/uds_server.c:348-350`; `vehicle-rt-core/src/features/uds/uds_server.c:396-412`; `vehicle-rt-core/src/features/uds/isotp_core.h:36-38`; `uds/dids.yaml:122-124` | OK | Largest response = 22 B record + `0x62` + 2 DID bytes = 25 B. `UDS_SERVER_RSP_MAX` is 101 B (`1 + 4 * (2 + 23)`), and both the response and ISO-TP TX buffers use it. 25 B fits one DID and the four-DID read (97 B). Classic CAN needs multi-frame for >7 B; the FF limit is 4095 B and the link buffer is 101 B, so no transport blocker. A 23 B record (0xFD02, 26 B response) is already served today, so 22 B is within proven size. |
| 6. Which ride / RIDE_CLOSED | `vehicle-rt-core/src/features/derived/derived_ride.h:71-78`; `vehicle-rt-core/src/features/derived/derived_core.c:1263-1272`; `vehicle-rt-core/src/features/derived/derived_ride.c:304-317` | OK | `prev[]` is the last closed ride and `have_prev` is false at boot; `derived_core_ride_out(PREVIOUS)` returns `NO_DATA` when none exists. `RIDE_CLOSED` is derivable from `have_prev` (0 with all fields NOT_AVAILABLE before the first close), and the 12 computed values can be copied from `prev[]`. The missing closed counter is the separate mismatch in check 4. |
| 7. NOT_AVAILABLE coverage | `vehicle-rt-core/src/features/derived/derived_ride.h:40,71-78`; `vehicle-rt-core/src/features/derived/derived_ride.c:23-30`; `vehicle-rt-core/src/features/derived/derived_core.c:1263-1272`; `derived/cl250_derived.yaml:1166-1985` | OK | rt-core computes exactly the expected 12 scalar fields: `RIDE_USAGE` 4/4, `RIDE_FUELING` 4/4, `RIDE_THERMAL` 4/8. The other 58 scalar fields would read NOT_AVAILABLE: thermal 4, electrical 2, engine stress 6, drivetrain 4, calibration 4, rider style 2, ECU health 7, windows 29. No valid raw maximum equals all-ones: the width rule chooses a wider field whenever the next all-ones value would be reached. |
| 8. Server parity | `vehicle-server/src/vehicle_server/derived/summary.py:449-452`; `vehicle-server/src/vehicle_server/derived/golden.py:163-171` | OPEN | The reference computes 16 of the 70 scalar fields as physical floats (the 12 above, `ride_distance_gps`, and `RIDE_ECU_HEALTH`'s `ride_bus_off_count`, `ride_tester_rtt_max`, `ride_tester_step_gap_max`); the other 54 have no reference value (`not_implemented` or `not_ready`). It has no raw encoding or NOT_AVAILABLE output: `_checked()` only range-checks and returns the float. A future encoder must match Python's half-even `round`; rt-core has no ride raw encoder. If it uses `lrintf`/`nearbyint` with `FE_TONEAREST` it matches, while `roundf`/`lroundf` (ties away from zero) does not. `golden.quantise()` uses Python `round` for DID input quantisation, not for ride-summary output, so it is not evidence for this rule. |
| 9. Histogram leftovers | `derived/cl250_derived.yaml` (`bins`, `per_gear`); throwaway script (log) | OK | Exactly the five listed signals are multi-element: `operating_point_time`, `fuel_trim_map`, `ride_coolant_time_at_temp`, `ride_oil_time_at_temp` and `ride_final_drive_ratio` (the last is `per_gear`). No other class-B signal in these records has `bins` or `per_gear`. `RIDE_OPERATING_POINTS` is the only record that becomes empty; every other record has scalar fields. |

**Verdict:** no size or transport blocker, and checks 1, 2, 5, 6, 7 and 9 are OK. Before approval, Claude must resolve **check 3** (add a per-field NOT_AVAILABLE codegen/writer feature), **check 4** (the last-closed epoch counter is not kept by rt-core, and the counter wraps/resets) and **check 8** (no server raw/NA encoder; Python/C rounding tie rule open). No code, defs, codegen or rt-core files were changed by this review.
