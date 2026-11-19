# Platform E2E profile (D-005, D-026)

Protects every platform-bus message in `0x010-0x08F` (mandatory) and any other message marked `E2E_Protected = Yes` in `dbc/platform.dbc`. AUTOSAR E2E Profile 1/2-like; the code is generated (`gen/c/<node>/vehicle_e2e.*`, `platform_e2e.*`; Python reference `gen/python/vehicle_defs/e2e.py`). Never hand-write it in a consumer.

## Frame layout

| Byte / bits | Content |
|---|---|
| byte 0 | `E2E_CRC`: CRC-8/SAE-J1850 |
| byte 1 bits 0-3 | `E2E_COUNTER`: alive counter 0..15, +1 per transmission, wraps 15 → 0 |
| byte 1 bits 4-7, bytes 2.. | payload signals |

**CRC:** poly `0x1D`, init `0xFF`, final XOR `0xFF`, no reflection (catalogue check value `0x4B` for `"123456789"`). Input, in order: `DataID & 0xFF`, `DataID >> 8`, then frame bytes `1..DLC-1`. The 16-bit `E2E_DataID` is never transmitted; a frame with the right layout but another message's DataID fails the CRC (masquerade detection). DataIDs must be unique on the bus (checked by codegen); the convention is `0x1000 + CAN ID`.

## Sender

Pack the payload, then call `platform_<msg>_e2e_protect(data, size, &tx_state)` right before transmitting. It writes the counter, then the CRC.

## Receiver

Call `platform_<msg>_e2e_check(data, size, &rx_state, now_ms)` for each received frame and `platform_<msg>_e2e_check_timeout(&rx_state, now_ms)` at least once per cycle. The check itself also enforces the timeout: a frame arriving more than the timeout after the last valid one resynchronises (`INITIAL`), so a stalled sender never resumes as `OK` and 16 lost frames cannot alias to a counter step of 1.

| Status | Meaning | Payload usable? |
|---|---|---|
| `OK` | counter +1 | yes |
| `OK_SOME_LOST` | counter jump ≤ max delta (unused while max delta = 1) | yes |
| `INITIAL` | first valid frame after start or timeout; resynchronises | **no** |
| `REPEATED` | same counter again (frozen/duplicated sender) | no |
| `WRONG_SEQUENCE` | counter jump > max delta; resynchronises the counter | no |
| `WRONG_CRC` | corrupted frame or wrong DataID | no |
| `NO_NEW_DATA` | timeout expired (or never received); forces a resync | no |
| `WRONG_LENGTH` | (generated C wrappers only, v0.30.0; the Python `vehicle_defs.e2e` has no per-message length guard yet) frame size is not the message's DBC DLC (`PLATFORM_<MSG>_E2E_LENGTH`); the state and the buffer are left untouched | no |

Only `OK`/`OK_SOME_LOST` (`vehicle_e2e_is_valid()`) allow use. `OK`, `OK_SOME_LOST` and `INITIAL` refresh the timeout; the others do not, so a frozen or corrupted stream ends in `NO_NEW_DATA`. Parameters: timeout = **3 × GenMsgCycleTime** (`PLATFORM_<MSG>_E2E_TIMEOUT_MS`), max delta counter = **1** (`..._E2E_MAX_DELTA_COUNTER`), so a single lost frame makes that cycle invalid. After an invalid status the consumer uses its own safe state; safety-node then uses its own-IMU fallback (DEGRADED or UNAVAILABLE, D-042, which resolved Q-002).

## Consumer order (v0.30.0)

For each received frame: (1) the generated `platform_<msg>_e2e_check()` (length, CRC, counter, timeout); only on `OK`/`OK_SOME_LOST` (2) `platform_<msg>_unpack_checked()` (exact DLC, every signal in range, `dst` untouched on failure); then (3) the enum fallback (an undefined enum value in range is read as the documented fallback, e.g. INVALID). Senders: `<signal>_encode_checked()` per float signal, `<msg>_pack_checked()`, then `platform_<msg>_e2e_protect()`.

## Sender restart

A restarted sender begins again at counter 0: the receiver sees `WRONG_SEQUENCE`, then `OK` on the next frame. E2E therefore cannot tell fresh-but-unconverged data from good data. Senders of estimates (rt-core EKF) must transmit `*_STATE = INVALID` and `QUALITY = 0` until converged; a falling heartbeat `UPTIME` also reveals the restart. With max delta 1, one CAN error invalidates one cycle, so consumers need debouncing (D-042; details in Q-023).

## Not covered

E2E detects late, frozen, corrupted and masqueraded data. It does not authenticate the sender (no MAC/keys) and does not make the application value plausible; range and plausibility checks stay in the consumer.
