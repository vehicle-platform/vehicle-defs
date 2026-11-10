"""Static platform configuration: repo paths, node table and CAN ID plan.

The ID plan and node IDs mirror docs/ARCHITECTURE.md section 4. The DBC is the
source of truth for messages; this module only holds the rules they must obey.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
PLATFORM_DBC = REPO_ROOT / "dbc" / "platform.dbc"
CL250_DBC = REPO_ROOT / "dbc" / "cl250.dbc"
VEHICLE_YAML = REPO_ROOT / "uds" / "vehicle_cl250.yaml"
OBD_CATALOG_YAML = REPO_ROOT / "uds" / "obd_catalog.yaml"  # D-066, D-078 item 2, host only
DIDS_YAML = REPO_ROOT / "uds" / "dids.yaml"
ISO14229_YAML = REPO_ROOT / "uds" / "iso14229.yaml"
LIMITS_YAML = REPO_ROOT / "limits" / "platform_limits.yaml"
VEHICLE_CONSTANTS_YAML = REPO_ROOT / "vehicle" / "cl250_constants.yaml"  # D-070 item 3
DERIVED_YAML = REPO_ROOT / "derived" / "cl250_derived.yaml"  # D-070 item 3
FAULT_CATALOG_YAML = REPO_ROOT / "faults" / "catalog.yaml"  # D-084
FAULTS_CL250_YAML = REPO_ROOT / "vehicle" / "cl250_faults.yaml"  # D-084 item 2, D-078
MAILBOX_YAML = REPO_ROOT / "mailbox" / "h755_mailbox.yaml"  # D-093
CATALOG_MD = REPO_ROOT / "docs" / "vehicle-data-catalog.md"  # derived `catalog` rows
OVERLAY_VSPEC = REPO_ROOT / "vss" / "overlay.vspec"
BLE_SCHEMA = REPO_ROOT / "ble" / "ble_schema.json"
GEN_DIR = REPO_ROOT / "gen"

# Node name -> node_id (ARCHITECTURE section 4).
NODE_IDS: dict[str, int] = {
    "RT_CORE": 1,
    "SAFETY": 2,
    # 3 was IO (retired by D-072; the ID stays unused)
    "CONN": 4,
    "LINUX": 5,
    "HIL_SIM": 0xE,
    "TESTER": 0xF,
}


@dataclass(frozen=True)
class CTarget:
    """A firmware node that gets generated C code under gen/c/<directory>/."""

    node: str
    directory: str
    all_messages: bool = False  # restbus simulator: every message, both directions
    vehicle_dids: bool = False  # gets the CL250 DID table (vehicle-bus tester or simulator)
    limits: bool = False  # gets platform_limits.h (producer/consumer of cornering values)
    # gets vehicle_cl250_constants.h and vehicle_cl250_derived.{h,c} (computes the derived
    # signals, D-070)
    vehicle_constants: bool = False
    # uds_iso14229.h: "full" (UDS server and/or client) or "client" (vehicle-bus tester
    # only: nothing outside the D-020 allow-list is named, D-040). None: no UDS.
    uds_iso: str | None = None
    # gets platform_mailbox.h: the two images of the STM32H755 share the M7<->M4 layout (D-093)
    mailbox: bool = False


# LINUX and TESTER parse the DBC/VSS at runtime (Python), so they get no C code.
C_TARGETS: tuple[CTarget, ...] = (
    CTarget(
        "RT_CORE",
        "rt_core",
        vehicle_dids=True,
        limits=True,
        uds_iso="full",
        vehicle_constants=True,
        mailbox=True,
    ),
    CTarget("SAFETY", "safety", limits=True, mailbox=True),
    # Temporary sole vehicle-bus tester until rt-core polls (D-023).
    CTarget("CONN", "conn", vehicle_dids=True, uds_iso="client"),
    # Simulates the CL250 ECU and impersonates platform nodes on the HIL bench.
    CTarget(
        "HIL_SIM", "hil_sim", all_messages=True, vehicle_dids=True, limits=True, uds_iso="full"
    ),
)


@dataclass(frozen=True)
class IdRange:
    first: int
    last: int
    name: str
    e2e_mandatory: bool
    allowed_in_dbc: bool = True

    def contains(self, frame_id: int) -> bool:
        return self.first <= frame_id <= self.last


ID_RANGES: tuple[IdRange, ...] = (
    IdRange(0x000, 0x00F, "reserved", e2e_mandatory=False, allowed_in_dbc=False),
    IdRange(0x010, 0x07F, "safety", e2e_mandatory=True),
    IdRange(0x080, 0x08F, "heartbeat", e2e_mandatory=True),
    IdRange(0x100, 0x3FF, "state", e2e_mandatory=False),
    IdRange(0x400, 0x5FF, "telemetry", e2e_mandatory=False),
    IdRange(0x600, 0x6FF, "bridge", e2e_mandatory=False),
    # UDS frames are defined by ISO 15765 addressing, not as DBC messages.
    IdRange(0x700, 0x7FF, "uds", e2e_mandatory=False, allowed_in_dbc=False),
)

HEARTBEAT_BASE_ID = 0x080
HEARTBEAT_CYCLE_MS = 100
E2E_TIMEOUT_CYCLES = 3  # receiver timeout = 3 x cycle (ARCHITECTURE section 4)
E2E_MAX_DELTA_COUNTER = 1  # conservative: any lost frame is reported as WRONG_SEQUENCE

# D-041/D-042: the only safety inputs of safety-node (lean, mu and the rt-core heartbeat
# for the fallback). Vehicle speed in particular is not a safety-node input.
SAFETY_RX_SAFETY_INPUTS = frozenset({"EkfLean", "EkfFrictionMass", "HeartbeatRtCore"})
# D-072 item 4c/7: QM requests used by the immobilizer alone. They never gate the
# cornering decision, the blind spot, the LEDs, the D-042 source selection or the M4
# power/clock state, and a missing frame never changes the immobilizer state.
SAFETY_RX_QM_IMMOBILIZER = frozenset({"SafetyRequest"})
# Everything safety-node may receive. Widening either list is a safety decision
# (safety-reviewer).
SAFETY_RX_ALLOWED = SAFETY_RX_SAFETY_INPUTS | SAFETY_RX_QM_IMMOBILIZER

# D-072 item 7 (safety-reviewer MAJOR-1): in an E2E message sent by or to SAFETY, raw 0
# of every value-table signal must mean "no information", so a zero-initialised,
# never-written or NaN-encoded field cannot read as GREEN, CLEAR or UNLOCKED.
NO_INFORMATION_NAMES = frozenset({"UNAVAILABLE", "NONE", "UNKNOWN", "INVALID", "INIT"})
# Stable frames released before the rule; their raw 0 is a valid estimate state.
NO_INFORMATION_EXEMPT = frozenset(
    {
        ("EkfLean", "LEAN_ANGLE_STATE"),
        ("EkfFrictionMass", "FRICTION_COEFF_STATE"),
        ("EkfFrictionMass", "TOTAL_MASS_STATE"),
    }
)

# D-020 forbidden vehicle-bus services, repeated here as a second line of defence:
# the checker rejects vehicle_cl250.yaml if its policy ever allows one of them.
FORBIDDEN_VEHICLE_SERVICES = frozenset({0x11, 0x14, 0x27, 0x2E, 0x2F, 0x31, 0x34, 0x36, 0x37})
FORBIDDEN_VEHICLE_SUBFUNCTIONS = {0x10: frozenset({0x02})}
# D-020 allow-list, golden copy: sid -> allowed sub-functions (bit 7 masked), None = any.
# The YAML policy may be narrower, never wider; widening it needs a new decision.
ALLOWED_VEHICLE_SERVICES: dict[int, frozenset[int] | None] = {
    0x10: frozenset({0x01, 0x03}),  # DiagnosticSessionControl: default / extended only
    0x3E: frozenset({0x00}),  # TesterPresent
    0x22: None,  # ReadDataByIdentifier
    0x19: frozenset({0x01, 0x02, 0x04, 0x06}),  # ReadDTCInformation: D-080 + scan (E-23)
    0x01: None,  # OBD show current data
    0x09: None,  # OBD request vehicle information
}


# D-059 (Q-020), golden copy: the only frame besides a Single Frame request that the
# vehicle-bus tester may send is one Flow Control frame, FC.ContinueToSend with BS 0
# (one FC per reception) and an STmin in the ms range. The YAML fixes the bytes within
# these bounds; widening them (WAIT, OVFLW, BS > 0, multi-frame requests) needs a new
# decision and safety-reviewer.
VEHICLE_FC_PCI = 0x30  # PCI type 3 = Flow Control
VEHICLE_FC_FLOW_STATUS = 0x0  # ContinueToSend
VEHICLE_FC_BLOCK_SIZE = 0
VEHICLE_FC_ST_MIN_MAX_MS = 0x7F  # 0x00-0x7F = 0-127 ms; the µs codes are not used
VEHICLE_FC_MAX_FF_DL = 0xFFF  # 12-bit FF_DL only (D-034: no 32-bit escape)


def flow_control_d059_errors(transport: dict) -> list[str]:
    """Errors if transport.flow_control is missing or outside the golden D-059 FC."""
    fc = transport.get("flow_control")
    if not isinstance(fc, dict):
        return ["transport.flow_control missing (D-059)"]
    errors = []

    def is_int(value: object) -> bool:
        return type(value) is int

    if transport.get("frame_dlc") != 8 or not is_int(transport.get("frame_dlc")):
        errors.append("transport.frame_dlc must be 8: the FC is a full classic CAN frame")
    if not is_int(fc.get("flow_status")) or fc["flow_status"] != VEHICLE_FC_FLOW_STATUS:
        errors.append("transport.flow_control.flow_status must be 0 (ContinueToSend, D-059)")
    if not is_int(fc.get("block_size")) or fc["block_size"] != VEHICLE_FC_BLOCK_SIZE:
        errors.append("transport.flow_control.block_size must be 0 (one FC per reception, D-059)")
    st_min = fc.get("st_min_ms")
    if type(st_min) is not int or not 0 <= st_min <= VEHICLE_FC_ST_MIN_MAX_MS:
        errors.append("transport.flow_control.st_min_ms must be an integer 0..127 (D-059)")
    pad = fc.get("padding_byte")
    if not is_int(pad) or not 0 <= pad <= 0xFF or pad != transport.get("padding_byte"):
        errors.append(
            "transport.flow_control.padding_byte must be a byte equal to transport.padding_byte"
        )
    max_ff_dl = fc.get("max_ff_dl")
    if type(max_ff_dl) is not int or not 8 <= max_ff_dl <= VEHICLE_FC_MAX_FF_DL:
        errors.append("transport.flow_control.max_ff_dl must be an integer 8..4095 (D-059)")
    return errors


def vehicle_fc_max_cf_burst(transport: dict) -> int:
    """CFs the ECU may send back to back after the FC: ceil((max_ff_dl - 6) / 7)."""
    return -(-(transport["flow_control"]["max_ff_dl"] - 6) // 7)


def vehicle_fc_frame(transport: dict) -> bytes:
    """The one FC.CTS frame (8 bytes) the gate passes; raises outside the golden copy."""
    errors = flow_control_d059_errors(transport)
    if errors:
        raise ValueError("; ".join(errors))
    fc = transport["flow_control"]
    pad = fc["padding_byte"]
    head = [VEHICLE_FC_PCI | fc["flow_status"], fc["block_size"], fc["st_min_ms"]]
    return bytes(head + [pad] * (transport["frame_dlc"] - len(head)))


def policy_d020_errors(policy: dict) -> list[str]:
    """Errors if the YAML tester policy allows anything outside the golden D-020 list."""
    errors = []
    for entry in policy.get("allowed", []):
        sid = entry.get("sid")
        if sid not in ALLOWED_VEHICLE_SERVICES:
            errors.append(f"tester_policy allows 0x{sid:02X}, not on the D-020 allow-list")
            continue
        golden = ALLOWED_VEHICLE_SERVICES[sid]
        subs = entry.get("subfunctions")
        if golden is not None and (subs is None or not set(subs) <= golden):
            errors.append(
                f"tester_policy 0x{sid:02X} sub-functions {subs} exceed D-020 {sorted(golden)}"
            )
    return errors


def assert_policy_within_d020(policy: dict) -> None:
    errors = policy_d020_errors(policy)
    if errors:
        raise ValueError("; ".join(errors))


def id_range_of(frame_id: int) -> IdRange | None:
    for r in ID_RANGES:
        if r.contains(frame_id):
            return r
    return None


def did_stale_after_ms(did: dict[str, Any]) -> int:
    """A vehicle DID's stale_after_ms: the one value the C table and the Python catalog share."""
    value = did["stale_after_ms"]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{did.get('name')}: stale_after_ms must be an integer, got {value!r}")
    return value
