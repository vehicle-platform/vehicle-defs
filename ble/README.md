# ble/: BLE packet schema (D-061)

`ble_schema.json` is the single source for the BLE notifications that vehicle-connectivity-node sends to vehicle-mobile: the telemetry packet (versions 2, 3 and 4), the IMU block, the GPS block (D-060), the vehicle-signal block (D-066), the rider-input block (D-121 item 5) and the GATT service and characteristic UUIDs. It moved here from vehicle-connectivity-node's `docs/` (Q-017 resolved by D-061), so the three parties that touch the bytes read one definition instead of keeping verbatim copies with drift tests:

| Consumer | Uses | Generated file |
|---|---|---|
| vehicle-connectivity-node (C/C++) | offset/size macros, UUID strings, flag bits; its packed structs `static_assert` against them (gen/c stays MISRA-clean, so no packed structs are generated) | `gen/c/conn/ble_schema.h` |
| vehicle-server (Python) | `SCHEMA` (the whole JSON) plus `CURRENT_VERSION`, `ACCEPTED_VERSIONS`, `TOTAL_BYTES_BY_VERSION`, `telemetry_fields(version)` | `gen/python/vehicle_defs/ble.py` |
| vehicle-mobile (Dart) | `const` ints and strings in `abstract final class`es (`BleTelemetryV4Offsets`, `BleImuFlagBits`, ...) | `gen/dart/vehicle_defs/` (package `vehicle_defs`, used by path from the submodule) |

## Layout rules

- Telemetry `fields` hold the current version (4). A field without `sinceVersion` exists since version 3; `sinceVersion: 4` marks the fields appended in D-058. Fields only ever get appended, so every older version is a prefix of the next: `totalBytesByVersion` gives the size of each (3: 37, 4: 57). Version 2 is the low-MTU fallback (`lowMtuFallback`), a separate layout.
- All multi-byte fields are little-endian. Offsets and sizes are explicit; `vehicle-codegen check` refuses a file whose fields overlap, leave a gap, disagree with their type size, or with `totalBytes`, `totalBytesByVersion`, the IMU `headerBytes`/`sampleBytes`/`totalBytesMax`, or that reuses a flag bit or a UUID.
- The GPS block (D-060, characteristic `gps`, 26 bytes, one block per UBX-NAV-PVT) carries ground speed, heading of motion, their accuracies, fix type, satellite count and the node time. Latitude, longitude and height never leave conn (invariant 7): `vehicle-codegen check` refuses a GPS field whose name looks like a position.
- The vehicle-signal block (D-066 item 4, characteristic `vehicleSignals`) carries one 9-byte record per DID of the tester's table, keyed by DID: state, age and the raw data bytes; receivers decode the value through the vehicle catalog (`vehicle_catalog.py`, `vehicle_signals.dart`). A promoted DID therefore flows without a layout change. Records page through the table (`firstRecord`, `totalRecords`); one record still fits the default MTU, so the block is never suspended. vehicle-server decodes it with `decode_vehicle_signal_block()` in `gen/python/vehicle_defs/ble.py`. Its own `vehicleSignalBlock.version` changes only with the header or record layout or the state values.
- The rider-input block (D-121 item 5, characteristic `riderInput`, 8 bytes) carries the handlebar push-to-talk button (D-047) from conn to vehicle-mobile: `version`, rolling `seq` (duplicates dropped, loss counted), `deviceTimeMs`, `event` (1 press, 2 release, 3 longPress) and `flags.buttonDown` (the debounced state after the event, so the phone can resynchronise after a lost block). It is notified once per button edge, never periodically, and is informational only: no safety path reads it (D-047 item 3, invariant 3), it is not a CAN signal and nothing goes on the vehicle bus. Its own `riderInputBlock.version` changes only with the layout or the event values.
- Version 4's tester fields (step gap, one rotating per-DID ECU round-trip record) are TEMPORARY, like the lean fields (D-023): rt-core's health DID 0xFD02 (D-055) replaces them.

## Changing a layout

1. Edit `ble_schema.json`. Any change to field order, size or meaning bumps `version` (and `versioning.currentVersion`, `acceptedVersions`, `history`, `totalBytes`, `totalBytesByVersion`); the IMU block has its own `imuBlock.version`.
2. `make check` and `make gen`; commit the schema and `gen/` together. `make drift` (CI) fails if they differ.
3. Add a `CHANGELOG.md` entry and tag a defs release (MINOR while defs is `v0.x`; say in the entry which consumers must change).
4. conn, vehicle-mobile and vehicle-server bump their `external/vehicle-defs` pin **together**; none of them may keep its own copy of the layout.

Not part of this schema: the phone telematics text written to `telematicsRx`.
