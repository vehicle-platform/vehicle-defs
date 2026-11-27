# Read-Only UDS Polling and Platform-Bus Republish

**Caption:** Sequence showing how `vehicle-rt-core` enforces the single-tester and read-only allow-list gates on the CL250 vehicle CAN bus before storing decoded samples and republishing them on the dedicated platform CAN bus (`0x021` with E2E, `0x110` engine state).

```mermaid
sequenceDiagram
  autonumber
  participant Poller as rt-core UDS Client<br/>(features/uds/uds_client.c)
  participant Gate as Generated Policy Gates<br/>(gen/c/rt_core/vehicle_cl250.h)
  participant CanIf as CAN Interface & Foreign-Tester Watch<br/>(services/can_if.c)
  participant ECU as CL250 OEM ECU<br/>(Vehicle CAN 500 kbps)
  participant Store as Vehicle Signal Store<br/>(services/vehicle_signals.c)
  participant Repub as Vehicle Republish<br/>(features/vehicle_republish/)
  participant PlatBus as Platform CAN Bus<br/>(FDCAN2, 11-bit, 500 kbps)

  Note over CanIf,ECU: Foreign-tester watch listens on 0x18DA10F1 & fallback ID.<br/>Any external request frame latches the poller off (D-021).

  Poller->>Gate: vehicle_cl250_request_allowed(0x22, DID)
  Gate-->>Poller: allowed (D-020 read-only allow-list)
  Poller->>Gate: vehicle_cl250_frame_allowed(SF / FC.CTS)
  Gate-->>Poller: allowed (Single Frame or fixed FC.CTS only)
  Poller->>CanIf: transmit ISO-TP frame (CAN_PORT_VEHICLE, 0x18DA10F1)
  CanIf->>ECU: 29-bit CAN frame (0x10 01/03, 0x3E, 0x22, 0x19)
  ECU-->>CanIf: 29-bit response (0x18DAF110, SID 0x62 + DID + payload)
  CanIf-->>Poller: RX callback + ISO-TP reassembly
  Poller->>Gate: vehicle_cl250_parse_response(SID 0x62, DID echo)
  Gate-->>Poller: decoded engineering value
  Poller->>Store: vehicle_signals_set(idx, value, now_ms)

  loop Cyclic republish (com_cycle_due)
    Repub->>Store: vehicle_signals_get(idx, now_ms)
    Store-->>Repub: sample (or VEHICLE_SIGNAL_NONE if stale)
    Repub->>Repub: pack + E2E protect (4-bit counter + CRC8 + DataID)
    Repub->>PlatBus: 0x021 VehicleSpeed (50 ms, E2E, dedicated TX buffer)
    Repub->>PlatBus: 0x110 VehicleEngine (RPM, coolant, TPS, battery)
  end
```

## Sources
- `vehicle-defs/docs/DECISIONS.md`: D-019 (CL250 29-bit `0x18DA10F1` -> `0x18DAF110`), D-020 (vehicle-bus service allow-list), D-021 (sole tester + platform-bus republish), D-027 (generated `vehicle_cl250_request_allowed`, `vehicle_cl250_frame_allowed`, `vehicle_cl250_parse_response`), D-037 (single read-only tester), D-059 (FC.CTS multi-frame receive cap)
- `vehicle-defs/docs/ARCHITECTURE.md` §3, §4
- `vehicle-rt-core/src/features/uds/uds_client.c` (lines 34-80: `on_foreign_request`, `latch`, `uds_client_open`)
- `vehicle-rt-core/src/features/vehicle_republish/vehicle_republish.c` (`send_speed`, `send_engine`, `vehicle_republish_open`, `vehicle_republish_step`)
