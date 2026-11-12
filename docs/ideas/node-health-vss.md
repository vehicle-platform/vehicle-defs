# Node health on VSS (Q-016, D-004): proposal for the user's approval

**Status:** proposal, 2026-11-11. Nothing here is decided; D-004 says the user approves every new `Vehicle.Motorcycle.*` path. Written so the L2 node-health panel on linux-node can be built once the choice is made.

## Why it is blocked today

The four heartbeat messages (`HeartbeatRtCore` 0x081, `HeartbeatSafety` 0x082, `HeartbeatConn` 0x084, `HeartbeatLinux` 0x085) carry the **same signal names** `NODE_MODE`, `ERROR_COUNT`, `UPTIME` (plus the E2E bytes). kuksa-can-provider resolves a `dbc2vss` entry by **signal name** (`dbcfeederlib/dbcparser.py` warns "Signal name %s is being used in multiple CAN messages" and then picks one), so a mapping `"signal": "NODE_MODE"` cannot say which node it means. D-028 already noted this ("they need unique names first"). linux-node applications never read SocketCAN directly (CLAUDE.md), so without VSS paths there is no panel.

## Option A (recommended): per-node signal names + one VSS branch

**DBC (`platform.dbc`, MAJOR per the CHANGELOG rule "changed signal name"):** rename the three payload signals per message with the node prefix already used for the sender: `RT_CORE_NODE_MODE`, `RT_CORE_ERROR_COUNT`, `RT_CORE_UPTIME`; `SAFETY_*`; `CONN_*`; `LINUX_*`. Bit positions, scales, value tables and E2E stay identical, so **no frame on the bus changes**. The E2E bytes keep their shared names (they are not mapped).

**VSS overlay (`vss/overlay.vspec`, whitelisted in `gen_vss.APPROVED_EXTENSIONS`):**

```
Vehicle.Motorcycle.Nodes                      branch
Vehicle.Motorcycle.Nodes.RtCore               branch   (also Safety, Conn, Linux)
Vehicle.Motorcycle.Nodes.RtCore.Mode          sensor, string, allowed: INIT NORMAL DEGRADED SAFE_STATE BOOTLOADER DIAGNOSTIC
Vehicle.Motorcycle.Nodes.RtCore.ErrorCount    sensor, uint8   ("faults since boot, saturates at 255")
Vehicle.Motorcycle.Nodes.RtCore.UptimeSeconds sensor, uint16, unit s ("a decrease means the node restarted")
```

`dbc2vss` per leaf: `signal: RT_CORE_NODE_MODE`, `interval_ms: 100` (heartbeat period; the panel needs no faster), string transform `INIT→INIT …` like `LeanAngleState`. 12 leaves in all.

**Consumers that regenerate (gen/c):** vehicle-rt-core (`platform_can.h` names of its own heartbeat and of the three it monitors), vehicle-safety-node (its own 0x082 and the 0x081 it monitors, **safety-reviewer**: the heartbeat is an invariant-8 module), vehicle-connectivity-node, vehicle-hil-bench. Mechanical renames, no logic change; a defs MAJOR bump (0.29.0 → **1.0.0?** or stay 0.x: the project is pre-1.0, so **0.29.0 with a MAJOR note** per the existing CHANGELOG practice).

**What linux-node then builds (L2):** a `node_health` service subscribing to the 12 leaves, deriving per node `present` (a value younger than N heartbeat periods), `restarted` (uptime decreased) and the mode; served to the HMI and the server as a small JSON; the existing black-box recorder picks the leaves up automatically (it subscribes to every `dbc2vss` leaf).

## Option B: keep the DBC, map by message in the provider

kuksa-can-provider has no "message.signal" syntax in 0.5.1, so this would need an upstream change or a fork. Not recommended: a fork is a maintenance cost for one feature, and the rename in A is mechanical.

## Option C: linux-node reads the heartbeats itself

Breaks the CLAUDE.md rule that only kuksa-can-provider and the OTA client touch SocketCAN, and duplicates decoding outside the defs pipeline. Not recommended.

## Also in Q-016: the `*_VALID` bits

`VehicleEngine` carries `ENGINE_SPEED_VALID` etc. The provider cannot combine two DBC signals into one VSS value, so the honest mapping is one boolean leaf per bit, e.g. `Vehicle.Motorcycle.Validity.EngineSpeed` (bool). Four leaves; consumers that care read both. Propose to decide together with A so the overlay changes once.

## Decision needed from the user

1. Option A yes/no (rename + `Vehicle.Motorcycle.Nodes.<Node>.{Mode,ErrorCount,UptimeSeconds}`).
2. Node branch names: `RtCore`, `Safety`, `Conn`, `Linux` (matching the DBC node ids) or the repo names.
3. Include the four `*_VALID` leaves now or later.

Once answered: `/signal-change` in defs (overlay + DBC rename + CHANGELOG), consumer repins with safety-reviewer on safety-node and rt-core, then linux-node L2.
