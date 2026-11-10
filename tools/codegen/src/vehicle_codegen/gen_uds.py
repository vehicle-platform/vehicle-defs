"""UDS on our own nodes: ISO 14229 codes (uds/iso14229.yaml) and the platform-bus
servers (uds/dids.yaml), checks and C/Python generation (D-039, D-040).

The ISO file only names numbers of the standard. What the vehicle-bus tester may send
is decided by vehicle_cl250.yaml -> tester_policy and the golden D-020 copy in config;
a tester-only node (UdsIso.CLIENT) gets no name outside that allow-list.
"""

from __future__ import annotations

import re
from typing import Any

from . import config
from .c_e2e_templates import BANNER

ENCODINGS = ("uint", "ascii", "bitfield", "vehicle_sample", "record")
VEHICLE_SAMPLE_HEADER_LEN = 3  # [state][age_ms hi][age_ms lo]
VEHICLE_SAMPLE_STATES = {"NONE": 0, "VALID": 1, "STALE": 2}
VEHICLE_SAMPLE_AGE_MAX_MS = 0xFFFF
NO_VEHICLE_IDX = 0xFF
RIDE_RECORD_LAYOUT_VERSION = 1  # header byte 0 of every generated ride record (D-098)
FIELD_KEYS = {"byte", "mask", "length", "name", "description", "ride_signal"}  # see ride_records
_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
ISOTP_MAX_LEN = 4095  # 12-bit FF_DL, classic CAN
TRANSPORT_KEYS = ("frame_dlc", "padding_byte", "block_size", "st_min_ms", "n_bs_ms", "n_cr_ms")
SERVER_INT_KEYS = (
    "physical_request_id",
    "physical_response_id",
    "p2_server_max_ms",
    "p2_star_server_max_ms",
    "s3_server_ms",
    "max_read_dids",
    "rx_buffer",
    "dtc_status_availability_mask",
)
# ISO 14229-1:2013 Tables 274/276 (D-090). These are the standard's own values, so the
# check is a golden copy: a different value means a typo, not a vehicle variant.
DTC_RECORD_REPORTS = {
    "dtc_and_status_length": 4,
    "snapshot": {
        "subfunction": "REPORT_DTC_SNAPSHOT_RECORD_BY_DTC_NUMBER",
        "record_header_length": 2,
        "identifier_length": 2,
        "undefined_number_of_identifiers": 0x00,
        "legislated_record_number": 0x00,
    },
    "ext_data": {
        "subfunction": "REPORT_DTC_EXT_DATA_RECORD_BY_DTC_NUMBER",
        "record_header_length": 1,
        "manufacturer_records": [0x01, 0x8F],
        "obd_records": [0x90, 0xEF],
    },
}
_J2012_RE = re.compile(r"^([PCBU])([0-3])([0-9A-F])([0-9A-F])([0-9A-F])-([0-9A-F]{2})$")
_J2012_LETTER = {"P": 0, "C": 1, "B": 2, "U": 3}


def _hex(value: int, width: int) -> str:
    return f"0x{value:0{width}X}u"


def _c_float(value: float) -> str:
    """A C float literal (`f` suffix) that reads back as the same float32."""
    text = repr(float(value))
    return text + "f"


def j2012_to_dtc(code: str) -> int | None:
    """3-byte DTC of a SAE J2012 code with failure type byte, e.g. U0100-00 -> 0xC10000."""
    m = _J2012_RE.match(code)
    if m is None:
        return None
    letter, d1, d2, d3, d4, ftb = m.groups()
    high = (_J2012_LETTER[letter] << 14) | (int(d1) << 12) | (int(d2 + d3 + d4, 16))
    return (high << 8) | int(ftb, 16)


# --------------------------------------------------------------------------- ISO codes


def _by_name(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    return {i["name"]: i[key] for i in items}


def iso_tables(iso: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        "services": _by_name(iso["services"], "sid"),
        "sessions": _by_name(iso["sessions"], "id"),
        "tester_present_subfunctions": _by_name(iso["tester_present_subfunctions"], "id"),
        "read_dtc_subfunctions": _by_name(iso["read_dtc_subfunctions"], "id"),
        "dtc_status_bits": _by_name(iso["dtc_status_bits"], "mask"),
        "nrcs": _by_name(iso["nrcs"], "nrc"),
    }


# Which ISO table names the sub-functions of a service.
SUBFUNCTION_TABLES = {
    "DIAGNOSTIC_SESSION_CONTROL": "sessions",
    "TESTER_PRESENT": "tester_present_subfunctions",
    "READ_DTC_INFORMATION": "read_dtc_subfunctions",
}


def check_iso(iso: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    keys = ("schema_version", "services", "positive_response_offset", "negative_response_sid",
            "negative_response_length", "suppress_pos_rsp_bit", "sessions",
            "tester_present_subfunctions", "read_dtc_subfunctions", "dtc_format_identifier",
            "group_of_dtc_all", "dtc_status_bits", "nrcs", "functional_suppressed_nrcs",
            "p2_resolution_ms", "p2_star_resolution_ms", "dtc_record_reports")  # fmt: skip
    missing = [k for k in keys if k not in iso]
    if missing:
        return [f"iso14229: missing keys {missing}"]
    for table in ("services", "sessions", "tester_present_subfunctions", "read_dtc_subfunctions",
                  "dtc_status_bits", "nrcs"):  # fmt: skip
        items = iso[table]
        key = {"services": "sid", "dtc_status_bits": "mask", "nrcs": "nrc"}.get(table, "id")
        names = [i.get("name") for i in items]
        values = [i.get(key) for i in items]
        if len(set(names)) != len(names) or len(set(values)) != len(values):
            errors.append(f"iso14229: {table} has duplicate names or values")
        if not all(isinstance(v, int) and 0 <= v <= 0xFF for v in values):
            errors.append(f"iso14229: {table} values must be bytes")
        if not all(isinstance(n, str) and n.isupper() for n in names):
            errors.append(f"iso14229: {table} names must be UPPER_CASE")
    if errors:
        return errors
    offset = iso["positive_response_offset"]
    for s in iso["services"]:
        if s["sid"] >= offset or s["sid"] + offset == iso["negative_response_sid"]:
            errors.append(f"iso14229: service 0x{s['sid']:02X} is not a request SID")
    if sorted(b["mask"] for b in iso["dtc_status_bits"]) != [1 << i for i in range(8)]:
        errors.append("iso14229: dtc_status_bits must name the eight bits once")
    nrcs = set(_by_name(iso["nrcs"], "nrc").values())
    if not set(iso["functional_suppressed_nrcs"]) <= nrcs:
        errors.append("iso14229: functional_suppressed_nrcs must be listed nrcs")
    if iso["group_of_dtc_all"] != 0xFFFFFF:
        errors.append("iso14229: group_of_dtc_all must be 0xFFFFFF")
    if iso["dtc_record_reports"] != DTC_RECORD_REPORTS:
        errors.append("iso14229: dtc_record_reports differs from ISO 14229-1 Tables 274/276")
    subs = {s["name"] for s in iso["read_dtc_subfunctions"]}
    for report in ("snapshot", "ext_data"):
        if DTC_RECORD_REPORTS[report]["subfunction"] not in subs:
            errors.append(f"iso14229: dtc_record_reports.{report} sub-function is not listed")
    return errors


def client_subset(iso: dict[str, Any]) -> dict[str, Any]:
    """The codes a vehicle-bus tester may know: nothing outside the golden D-020 list."""
    golden = config.ALLOWED_VEHICLE_SERVICES
    sub = dict(iso)
    sub["services"] = [s for s in iso["services"] if s["sid"] in golden]
    sessions = golden.get(0x10) or frozenset()
    sub["sessions"] = [s for s in iso["sessions"] if s["id"] in sessions]
    tp = golden.get(0x3E) or frozenset()
    sub["tester_present_subfunctions"] = [
        s for s in iso["tester_present_subfunctions"] if s["id"] in tp
    ]
    if 0x19 not in golden:
        sub["read_dtc_subfunctions"] = []
    elif golden[0x19] is not None:  # E-23: only the report types the gate passes
        sub["read_dtc_subfunctions"] = [
            s for s in iso["read_dtc_subfunctions"] if s["id"] in golden[0x19]
        ]
    sub["nrcs"] = [n for n in iso["nrcs"] if n.get("client")]
    sub["group_of_dtc_all"] = None  # 0x14 only
    sub["functional_suppressed_nrcs"] = []  # server only
    return sub


def generate_iso_c(iso: dict[str, Any], client_only: bool) -> dict[str, str]:
    codes = client_subset(iso) if client_only else iso
    scope = (
        "Client subset: this node is a vehicle-bus tester only, so services and sessions\n"
        " * outside the D-020 allow-list (vehicle_cl250.yaml tester_policy) are not named."
        if client_only
        else "Full set (client and server)."
    )
    h = [BANNER.format(source="uds/iso14229.yaml"), "#ifndef VEHICLE_UDS_ISO14229_H",
         "#define VEHICLE_UDS_ISO14229_H", ""]  # fmt: skip
    h += [
        f"/* Generic {iso['standard']} codes (D-039, D-040). Names for numbers only: a",
        " * name here never allows sending anything. What the vehicle-bus tester may send",
        " * is decided by the generated D-020 gates in vehicle_cl250.h.",
        f" * {scope} */",
        "",
        "/* Request SIDs; positive response = SID + UDS_POSITIVE_RESPONSE_OFFSET. */",
    ]
    for s in codes["services"]:
        h.append(f"#define UDS_SID_{s['name']} ({_hex(s['sid'], 2)}) /* clause {s['clause']} */")
    h += [
        "",
        f"#define UDS_POSITIVE_RESPONSE_OFFSET ({_hex(iso['positive_response_offset'], 2)})",
        f"#define UDS_SID_NEGATIVE_RESPONSE ({_hex(iso['negative_response_sid'], 2)})",
        f"#define UDS_NEGATIVE_RESPONSE_LEN ({iso['negative_response_length']}u)",
        f"#define UDS_SUPPRESS_POS_RSP_BIT ({_hex(iso['suppress_pos_rsp_bit'], 2)})",
        "",
        "/* DiagnosticSessionControl sub-functions (sessions). */",
    ]
    h += [f"#define UDS_SESSION_{s['name']} ({_hex(s['id'], 2)})" for s in codes["sessions"]]
    h += ["", "/* TesterPresent sub-functions. */"]
    h += [
        f"#define UDS_TESTER_PRESENT_{s['name']} ({_hex(s['id'], 2)})"
        for s in codes["tester_present_subfunctions"]
    ]
    if codes["read_dtc_subfunctions"]:
        h += ["", "/* ReadDTCInformation sub-functions. */"]
        h += [
            f"#define UDS_READ_DTC_{s['name']} ({_hex(s['id'], 2)})"
            for s in codes["read_dtc_subfunctions"]
        ]
        fmt = iso["dtc_format_identifier"]
        h.append(f"#define UDS_DTC_FORMAT_{fmt['name']} ({_hex(fmt['id'], 2)})")
    h += ["", "/* DTCStatusMask bits. */"]
    h += [
        f"#define UDS_DTC_STATUS_{b['name']} ({_hex(b['mask'], 2)})" for b in iso["dtc_status_bits"]
    ]
    if codes["group_of_dtc_all"] is not None:
        h += ["", f"#define UDS_GROUP_OF_DTC_ALL ({_hex(iso['group_of_dtc_all'], 6)})"]
    h += ["", "/* Negative response codes. */"]
    h += [f"#define UDS_NRC_{n['name']} ({_hex(n['nrc'], 2)})" for n in codes["nrcs"]]
    h += [
        "",
        "/* sessionParameterRecord units of the 0x50 response. */",
        f"#define UDS_P2_RESOLUTION_MS ({iso['p2_resolution_ms']}u)",
        f"#define UDS_P2_STAR_RESOLUTION_MS ({iso['p2_star_resolution_ms']}u)",
        "",
        "#endif /* VEHICLE_UDS_ISO14229_H */",
        "",
    ]
    return {"uds_iso14229.h": "\n".join(h)}


# --------------------------------------------------------------------------- servers


def _vehicle_dids(vehicle: dict[str, Any]) -> dict[str, tuple[int, dict[str, Any]]]:
    return {d["name"]: (i, d) for i, d in enumerate(vehicle.get("dids", []))}


def did_length(item: dict[str, Any], vehicle: dict[str, Any]) -> int:
    if item.get("encoding") == "vehicle_sample":
        _, vd = _vehicle_dids(vehicle)[item["vehicle_did"]]
        return VEHICLE_SAMPLE_HEADER_LEN + int(vd["length"])
    return int(item["length"])


def _check_did(node: str, item: dict[str, Any], vehicle: dict[str, Any], has_vehicle: bool,
               seen: set[int], names: set[str]) -> list[str]:  # fmt: skip
    errors: list[str] = []
    did = item.get("did")
    label = f"dids: {node} DID {item.get('name', did)}"
    if not isinstance(did, int) or not (0xF100 <= did <= 0xF1FF or 0xFD00 <= did <= 0xFDFF):
        errors.append(f"dids: {node} DID {did} outside 0xF1xx/0xFDxx")
    elif did in seen:
        errors.append(f"dids: {node} duplicate DID 0x{did:04X}")
    else:
        seen.add(did)
    name = item.get("name")
    if not isinstance(name, str) or not name.isupper() or name in names:
        errors.append(f"{label}: name missing, not UPPER_CASE or duplicate")
    names.add(str(name))
    if item.get("access", "read") != "read":
        errors.append(f"{label}: only read access without user approval")
    if not item.get("description"):
        errors.append(f"{label}: description missing")
    enc = item.get("encoding")
    if enc not in ENCODINGS:
        return errors + [f"{label}: encoding must be one of {ENCODINGS}"]
    if enc == "vehicle_sample":
        if not has_vehicle:
            errors.append(f"{label}: vehicle_sample needs a node with the CL250 DID table")
        if item.get("vehicle_did") not in _vehicle_dids(vehicle):
            errors.append(f"{label}: vehicle_did {item.get('vehicle_did')} not in vehicle_cl250")
        elif "length" in item and item["length"] != did_length(item, vehicle):
            errors.append(f"{label}: length must be {did_length(item, vehicle)}")
        return errors
    length = item.get("length")
    if not isinstance(length, int) or not 1 <= length <= 255:
        return errors + [f"{label}: length must be 1..255"]
    max_age = item.get("max_age_ms")
    if max_age is not None and (not isinstance(max_age, int) or not 0 < max_age <= 0xFFFF):
        errors.append(f"{label}: max_age_ms must be 1..65535")
    if enc == "uint" and length > 4:
        errors.append(f"{label}: uint length must be 1..4")
    if enc in ("bitfield", "record"):
        errors += _check_fields(label, enc, item, length)
    return errors


def field_max(field: dict[str, Any]) -> int:
    """Largest value of a field: its mask, or the saturation value of a record uint."""
    if "mask" in field:
        return int(field["mask"])
    return (1 << (8 * int(field["length"]))) - 1


def _check_fields(label: str, enc: str, item: dict[str, Any], length: int) -> list[str]:
    """bitfield: `{byte, mask}` fields. record: also `{byte, length}` unsigned big-endian
    fields (1, 2 or 4 bytes, saturating), and every byte of the record belongs to a field."""
    errors: list[str] = []
    fields = item.get("fields") or []
    used: dict[int, int] = {}
    uint_bytes: set[int] = set()
    names: set[str] = set()
    for f in fields:
        name, byte, mask, size = f.get("name"), f.get("byte"), f.get("mask"), f.get("length")
        if not set(f) <= FIELD_KEYS:
            errors.append(f"{label}: field {name} has unknown keys {sorted(set(f) - FIELD_KEYS)}")
        if not isinstance(name, str) or not _NAME_RE.match(name) or name in names:
            errors.append(f"{label}: field {name} name missing, not UPPER_CASE or duplicate")
        if any(isinstance(f.get(k), bool) for k in ("byte", "mask", "length")):
            errors.append(f"{label}: field {name} byte/mask/length must be integers, not bool")
            continue
        names.add(str(name))
        if not f.get("description"):
            errors.append(f"{label}: field {name} description missing")
        if not isinstance(byte, int) or not 0 <= byte < length:
            errors.append(f"{label}: field {name} byte invalid")
            continue
        if enc == "record" and mask is None:
            if size not in (1, 2, 4) or byte + size > length:
                errors.append(f"{label}: field {name} length must be 1, 2 or 4 inside the record")
                continue
            span = set(range(byte, byte + size))
            if span & (uint_bytes | set(used)):
                errors.append(f"{label}: field {name} overlaps")
            uint_bytes |= span
            continue
        if size is not None or not isinstance(mask, int) or not 0 < mask <= 0xFF:
            errors.append(f"{label}: field {name} byte/mask invalid")
            continue
        if used.get(byte, 0) & mask or byte in uint_bytes:
            errors.append(f"{label}: field {name} overlaps")
        used[byte] = used.get(byte, 0) | mask
    if not fields:
        errors.append(f"{label}: {enc} needs fields")
    elif enc == "record" and not errors and uint_bytes | set(used) != set(range(length)):
        errors.append(f"{label}: record bytes not covered by a field")
    by_name = {f.get("name"): f for f in fields}
    for fname, values in (item.get("values") or {}).items():
        f = by_name.get(fname)
        valid = f is not None and (isinstance(f.get("mask"), int) or f.get("length") in (1, 2, 4))
        if (
            not valid
            or not values
            or not all(isinstance(n, str) and _NAME_RE.match(n) for n in values)
            or len(set(values.values())) != len(values)
            or not all(
                isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= field_max(f)
                for v in values.values()
            )
        ):
            errors.append(f"{label}: values.{fname} invalid")
    return errors


def _check_server(node: str, content: dict[str, Any], iso: dict[str, Any],
                  vehicle: dict[str, Any], functional_id: int) -> list[str]:  # fmt: skip
    errors: list[str] = []
    srv = content["server"]
    for key in SERVER_INT_KEYS:
        if not isinstance(srv.get(key), int) or srv[key] < 0:
            errors.append(f"dids: {node}.server.{key} must be a non-negative integer")
    if errors:
        return errors
    base = 0x700 + config.NODE_IDS[node] * 0x10
    if srv["physical_request_id"] != base:
        errors.append(f"dids: {node} physical_request_id must be 0x{base:03X} (0x7N0, NodeId)")
    if srv["physical_response_id"] != base + 8:
        errors.append(f"dids: {node} physical_response_id must be 0x{base + 8:03X} (0x7N8)")
    if not srv["physical_request_id"] <= 0x7FF or functional_id in (
        srv["physical_request_id"],
        srv["physical_response_id"],
    ):
        errors.append(f"dids: {node} physical IDs clash with the UDS range or functional ID")
    p2, p2s, s3 = srv["p2_server_max_ms"], srv["p2_star_server_max_ms"], srv["s3_server_ms"]
    res = iso["p2_star_resolution_ms"]
    if not 0 < p2 < p2s or p2 > 0xFFFF or p2s % res or p2s // res > 0xFFFF or s3 <= p2:
        errors.append(
            f"dids: {node} timing needs 0 < P2 < P2* (P2* a multiple of {res} ms, both fit "
            "16 bits in the 0x50 response) and S3 > P2"
        )
    if not 1 <= srv["max_read_dids"] or not 1 + 2 * srv["max_read_dids"] <= srv["rx_buffer"]:
        errors.append(f"dids: {node} rx_buffer must hold a 0x22 request with max_read_dids")
    if srv["rx_buffer"] > ISOTP_MAX_LEN or srv["dtc_status_availability_mask"] > 0xFF:
        errors.append(f"dids: {node} rx_buffer or dtc_status_availability_mask out of range")
    tables = iso_tables(iso)
    sessions = srv.get("sessions") or []
    if "DEFAULT" not in sessions or not set(sessions) <= set(tables["sessions"]):
        errors.append(f"dids: {node} sessions must include DEFAULT and name ISO sessions")
    seen_services: set[str] = set()
    for entry in srv.get("services") or []:
        name = entry.get("service")
        if name not in tables["services"] or name in seen_services:
            errors.append(f"dids: {node} service {name} unknown or duplicate")
            continue
        seen_services.add(name)
        if not entry.get("sessions") or not set(entry["sessions"]) <= set(sessions):
            errors.append(f"dids: {node} service {name} sessions must be served sessions")
        subs = entry.get("subfunctions")
        if subs is not None:
            table = SUBFUNCTION_TABLES.get(name)
            if table is None or table == "sessions" or not set(subs) <= set(tables[table]):
                errors.append(f"dids: {node} service {name} sub-functions invalid")
    for required in ("DIAGNOSTIC_SESSION_CONTROL", "TESTER_PRESENT"):
        if required not in seen_services:
            errors.append(f"dids: {node} server must offer {required}")
    return errors


def check_dids(data: dict[str, Any], iso: dict[str, Any], vehicle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        return ["dids: 'nodes' mapping missing"]
    transport = data.get("transport") or {}
    for key in (*TRANSPORT_KEYS, "functional_request_id"):
        if not isinstance(transport.get(key), int) or transport[key] < 0:
            errors.append(f"dids: transport.{key} must be a non-negative integer")
    if errors:
        return errors
    if transport["frame_dlc"] != 8 or transport["padding_byte"] > 0xFF:
        errors.append("dids: transport frame_dlc must be 8 (classic CAN), padding a byte")
    if transport["block_size"] > 0xFF or transport["st_min_ms"] > 127:
        errors.append("dids: transport block_size must be a byte, st_min_ms 0..127")
    if not 0 < transport["n_bs_ms"] <= 0xFFFF or not 0 < transport["n_cr_ms"] <= 0xFFFF:
        errors.append("dids: transport n_bs_ms / n_cr_ms must be 1..65535")
    functional = transport["functional_request_id"]
    if functional != 0x7DF:
        errors.append("dids: transport.functional_request_id must be 0x7DF (ARCHITECTURE 4)")
    targets = {t.node: t for t in config.C_TARGETS}
    for node, content in nodes.items():
        if node not in config.NODE_IDS:
            errors.append(f"dids: unknown node {node}")
            continue
        content = content or {}
        has_server = isinstance(content.get("server"), dict)
        if (content.get("dids") or content.get("dtcs")) and not has_server:
            errors.append(f"dids: {node} has DIDs/DTCs but no server section")
        if has_server:
            if node not in targets:
                errors.append(f"dids: {node} has no C target for a server")
                continue
            errors += _check_server(node, content, iso, vehicle, functional)
        seen: set[int] = set()
        names: set[str] = set()
        has_vehicle = node in targets and targets[node].vehicle_dids
        for item in content.get("dids") or []:
            errors += _check_did(node, item, vehicle, has_vehicle, seen, names)
        seen_dtc: set[int] = set()
        dtc_names: set[str] = set()
        for item in content.get("dtcs") or []:
            dtc, name, code = item.get("dtc"), item.get("name"), str(item.get("code"))
            label = f"dids: {node} DTC {name}"
            if not isinstance(dtc, int) or not 0 < dtc < 0xFFFFFF or dtc in seen_dtc:
                errors.append(f"{label}: dtc must be a unique 3-byte value, not 0 or 0xFFFFFF")
            elif j2012_to_dtc(code) != dtc:
                errors.append(f"{label}: code {code} does not encode 0x{dtc:06X} (SAE J2012)")
            seen_dtc.add(dtc if isinstance(dtc, int) else -1)
            if not isinstance(name, str) or not name.isupper() or name in dtc_names:
                errors.append(f"{label}: name missing, not UPPER_CASE or duplicate")
            dtc_names.add(str(name))
            if not item.get("description"):
                errors.append(f"{label}: description missing")
        if has_server and not errors:
            srv = content["server"]
            longest = 1 + sum(
                2 + did_length(i, vehicle)
                for i in sorted(
                    content.get("dids") or [], key=lambda i: did_length(i, vehicle), reverse=True
                )[: srv["max_read_dids"]]
            )
            if longest > ISOTP_MAX_LEN:
                errors.append(f"dids: {node} longest 0x22 response {longest} B > {ISOTP_MAX_LEN}")
    return errors


def servers(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Nodes that have a UDS server section."""
    return {
        node: content
        for node, content in (data.get("nodes") or {}).items()
        if isinstance((content or {}).get("server"), dict)
    }


def _session_list(iso: dict[str, Any], names: list[str]) -> list[int]:
    table = iso_tables(iso)["sessions"]
    return [table[n] for n in names]


def generate_server_c(node: str, content: dict[str, Any], data: dict[str, Any],
                      iso: dict[str, Any], vehicle: dict[str, Any]) -> dict[str, str]:  # fmt: skip
    """gen/c/<node>/platform_uds.{h,c}: the node's platform-bus UDS server contract."""
    p = "PLATFORM_UDS"
    srv = content["server"]
    tr = data["transport"]
    dids = content.get("dids") or []
    dtcs = content.get("dtcs") or []
    tables = iso_tables(iso)
    uses_vehicle = any(d["encoding"] == "vehicle_sample" for d in dids)
    ride_fields = [
        (d, f) for d in dids if d.get("ride_record")
        for f in d["fields"] if "ride_signal" in f
    ]  # fmt: skip

    def define(name: str, value: str, comment: str = "") -> str:
        tail = f" /* {comment} */" if comment else ""
        return f"#define {p}_{name} ({value}){tail}"

    h = [BANNER.format(source="uds/dids.yaml"), "#ifndef PLATFORM_UDS_H", "#define PLATFORM_UDS_H"]
    h += ["", "#include <stdbool.h>", "#include <stddef.h>", "#include <stdint.h>", ""]
    h += ["#ifdef __cplusplus", 'extern "C" {', "#endif", ""]
    h += [
        f"/* {node} UDS server on the platform bus (D-040). Nothing here is ever sent on the",
        " * vehicle bus (D-020, D-037). Codes: uds_iso14229.h. */",
        "",
        define("NODE_ID", f"{config.NODE_IDS[node]}u"),
        define("PHYS_REQUEST_ID", _hex(srv["physical_request_id"], 3), "11-bit, 0x7N0"),
        define("PHYS_RESPONSE_ID", _hex(srv["physical_response_id"], 3), "11-bit, 0x7N8"),
        define("FUNCTIONAL_REQUEST_ID", _hex(tr["functional_request_id"], 3), "Single Frame only"),
        "",
        "/* Platform-bus ISO-TP (ISO 15765-2). */",
        define("FRAME_DLC", f"{tr['frame_dlc']}u"),
        define("PADDING_BYTE", _hex(tr["padding_byte"], 2)),
        define("BLOCK_SIZE", f"{tr['block_size']}u"),
        define("ST_MIN_MS", f"{tr['st_min_ms']}u"),
        define("N_BS_MS", f"{tr['n_bs_ms']}u"),
        define("N_CR_MS", f"{tr['n_cr_ms']}u"),
        "",
        "/* Server timing (ISO 14229-2) and limits. */",
        define("P2_SERVER_MAX_MS", f"{srv['p2_server_max_ms']}u"),
        define("P2_STAR_SERVER_MAX_MS", f"{srv['p2_star_server_max_ms']}u"),
        define("S3_SERVER_MS", f"{srv['s3_server_ms']}u"),
        define("MAX_READ_DIDS", f"{srv['max_read_dids']}u"),
        define("RX_BUFFER", f"{srv['rx_buffer']}u", "longest request accepted"),
        define(
            "MAX_DID_LENGTH",
            f"{max((did_length(d, vehicle) for d in dids), default=0)}u",
            "longest data record",
        ),
        define("DTC_STATUS_AVAILABILITY_MASK", _hex(srv["dtc_status_availability_mask"], 2)),
        "",
        define("DID_COUNT", f"{len(dids)}u"),
    ]
    for d in dids:
        h.append(define(f"DID_{d['name']}", _hex(d["did"], 4), d["encoding"]))
        h.append(
            define(f"DID_{d['name']}_LENGTH", f"{did_length(d, vehicle)}u", "data record bytes")
        )
    h += ["", "/* Index into platform_uds_dids[]. */", "typedef enum {"]
    h += [f"    {p}_IDX_{d['name']} = {i}," for i, d in enumerate(dids)]
    h += ["} platform_uds_did_index_t;", ""]
    h += [
        "typedef enum {",
        f"    {p}_ENC_UINT = 0,           /* unsigned big-endian */",
        f"    {p}_ENC_ASCII = 1,          /* NUL-padded text */",
        f"    {p}_ENC_BITFIELD = 2,       /* see the *_MASK / *_BYTE defines */",
        f"    {p}_ENC_VEHICLE_SAMPLE = 3, /* [state][age_ms hi][age_ms lo][raw] */",
        f"    {p}_ENC_RECORD = 4          /* *_BYTE with *_MASK, or *_LENGTH bytes big-endian */",
        "} platform_uds_encoding_t;",
        "",
        define("NO_VEHICLE_IDX", _hex(NO_VEHICLE_IDX, 2)),
        "",
        "typedef struct {",
        "    uint16_t did;",
        "    uint8_t length;      /* data record bytes (fixed) */",
        "    uint8_t encoding;    /* platform_uds_encoding_t */",
        f"    uint8_t vehicle_idx; /* vehicle_cl250_did_index_t, or {p}_NO_VEHICLE_IDX */",
        "} platform_uds_did_t;",
        "",
        f"extern const platform_uds_did_t platform_uds_dids[{p}_DID_COUNT];",
        "",
    ]
    for d in dids:
        if "max_age_ms" in d:
            h.append(
                define(
                    f"{d['name']}_MAX_AGE_MS",
                    f"{d['max_age_ms']}u",
                    "older data is stale (D-040), see the DID",
                )
            )
        for f in d.get("fields") or []:
            base = f"{d['name']}_{f['name']}"
            h.append(define(f"{base}_BYTE", f"{f['byte']}u"))
            if "mask" in f:
                h.append(define(f"{base}_MASK", _hex(f["mask"], 2), f["description"].rstrip(".")))
            elif "ride_signal" in f:
                rs = f["ride_signal"]
                width = 2 * f["length"]
                h.append(define(f"{base}_LENGTH", f"{f['length']}u", f["description"].rstrip(".")))
                h.append(
                    define(f"{base}_MAX", _hex(rs["raw_max"], width), "largest valid raw value")
                )
                h.append(define(f"{base}_NA", _hex(field_max(f), width), "NOT_AVAILABLE (D-098)"))
                h.append(define(f"{base}_RANGE_MIN", _c_float(rs["range_min"]), rs["signal"]))
                h.append(define(f"{base}_RESOLUTION", _c_float(rs["resolution"])))
            else:
                h.append(define(f"{base}_LENGTH", f"{f['length']}u", f["description"].rstrip(".")))
                # An enum field (one with `values`) is a state, not a counter: no saturation note.
                is_enum = f["name"] in (d.get("values") or {})
                note = (
                    "header field, exempt from NOT_AVAILABLE (D-098)"
                    if d.get("ride_record")
                    else "counters saturate here"
                )
                h.append(
                    define(
                        f"{base}_MAX",
                        _hex(field_max(f), 2 * f["length"]),
                        "" if is_enum else note,
                    )
                )
        for fname, values in (d.get("values") or {}).items():
            for vname, v in values.items():
                h.append(define(f"{d['name']}_{fname}_{vname}", f"{v}u"))
        if d.get("fields"):
            h.append("")
    if uses_vehicle:
        h.append(define("VEHICLE_SAMPLE_HEADER_LEN", f"{VEHICLE_SAMPLE_HEADER_LEN}u"))
        for name, v in VEHICLE_SAMPLE_STATES.items():
            h.append(define(f"VEHICLE_SAMPLE_STATE_{name}", f"{v}u"))
        h.append(define("VEHICLE_SAMPLE_AGE_MAX_MS", _hex(VEHICLE_SAMPLE_AGE_MAX_MS, 4)))
        h.append("")
    if ride_fields:
        h += [
            "/* Ride-summary records (D-098), generated from derived/cl250_derived.yaml. A field is",
            " * raw = round-half-even((value - RANGE_MIN) / RESOLUTION), unsigned big-endian. *_MAX is",
            " * the largest VALID raw value, *_NA (all ones) means NOT_AVAILABLE: these fields never",
            " * saturate. The header (LAYOUT_VERSION, RIDE_COUNTER, flags) is exempt from *_NA. */",
            define("RIDE_RECORD_LAYOUT_VERSION", f"{RIDE_RECORD_LAYOUT_VERSION}u"),
            define("RIDE_FIELD_COUNT", f"{len(ride_fields)}u", "rows of platform_uds_ride_fields[]"),
            "",
            "typedef struct {",
            "    uint8_t did_idx;     /* platform_uds_did_index_t of the record */",
            "    uint8_t byte;        /* first byte of the field in the record */",
            "    uint8_t length;      /* 1, 2 or 4 bytes, big-endian */",
            "    uint16_t signal;     /* VEHICLE_CL250_DERIVED_<SIGNAL> index */",
            "    float range_min;",
            "    float resolution;",
            "    uint32_t raw_max;    /* largest valid raw value */",
            "    uint32_t na;         /* NOT_AVAILABLE: all ones of the width */",
            "} platform_uds_ride_field_t;",
            "",
            f"extern const platform_uds_ride_field_t platform_uds_ride_fields[{p}_RIDE_FIELD_COUNT];",
            "",
        ]  # fmt: skip
    h.append(define("DTC_COUNT", f"{len(dtcs)}u"))
    for t in dtcs:
        h.append(define(f"DTC_{t['name']}", _hex(t["dtc"], 6), t["code"]))
    h += ["", "/* Index into platform_uds_dtcs[]. */", "typedef enum {"]
    h += [f"    {p}_DTC_IDX_{t['name']} = {i}," for i, t in enumerate(dtcs)]
    h += ["} platform_uds_dtc_index_t;", ""]
    if dtcs:
        h += [f"extern const uint32_t platform_uds_dtcs[{p}_DTC_COUNT];", ""]
    h += [
        "/* Table entry for `did`, or NULL. */",
        "const platform_uds_did_t *platform_uds_find_did(uint16_t did);",
        "",
        "/* True if the server offers the service at all (else NRC 0x11). */",
        "bool platform_uds_service_supported(uint8_t sid);",
        "",
        "/* True if the service runs in `session` (else NRC 0x7F). */",
        "bool platform_uds_service_allowed_in_session(uint8_t sid, uint8_t session);",
        "",
        "/* True if the server switches to `session` with 0x10 (else NRC 0x12). */",
        "bool platform_uds_session_supported(uint8_t session);",
        "",
        "/* Sub-function check for 0x3E / 0x19 (bit 7 masked; else NRC 0x12). 0x10 uses",
        " * platform_uds_session_supported(). False for services without sub-functions. */",
        "bool platform_uds_subfunction_supported(uint8_t sid, uint8_t subfunction);",
        "",
        "/* True if the server stays silent instead of sending this NRC to a functionally",
        " * addressed request (ISO 14229-1 clause 7.5). */",
        "bool platform_uds_nrc_suppressed_functional(uint8_t nrc);",
        "",
        "#ifdef __cplusplus",
        "}",
        "#endif",
        "",
        "#endif /* PLATFORM_UDS_H */",
        "",
    ]

    c = [BANNER.format(source="uds/dids.yaml"), '#include "platform_uds.h"']
    if uses_vehicle:
        c.append('#include "vehicle_cl250.h"')
    if ride_fields:
        c.append('#include "vehicle_cl250_derived.h"')
    c += ["", f"const platform_uds_did_t platform_uds_dids[{p}_DID_COUNT] = {{"]
    for d in dids:
        enc = f"{p}_ENC_{d['encoding'].upper()}"
        vidx = (
            f"(uint8_t)VEHICLE_CL250_IDX_{d['vehicle_did']}"
            if d["encoding"] == "vehicle_sample"
            else f"{p}_NO_VEHICLE_IDX"
        )
        c.append(
            f"    {{ {p}_DID_{d['name']}, {did_length(d, vehicle)}u, (uint8_t){enc}, {vidx} }},"
        )
    c += ["};", ""]
    if ride_fields:
        c.append(
            f"const platform_uds_ride_field_t platform_uds_ride_fields[{p}_RIDE_FIELD_COUNT] = {{"
        )
        for d, f in ride_fields:
            base = f"{p}_{d['name']}_{f['name']}"
            sig = f["ride_signal"]["signal"].upper()
            c.append(
                f"    {{ (uint8_t){p}_IDX_{d['name']}, {base}_BYTE, {base}_LENGTH, "
                f"VEHICLE_CL250_DERIVED_{sig}, {base}_RANGE_MIN, {base}_RESOLUTION, "
                f"{base}_MAX, {base}_NA }},"
            )
        c += ["};", ""]
    if dtcs:
        c.append(f"const uint32_t platform_uds_dtcs[{p}_DTC_COUNT] = {{")
        c += [f"    {p}_DTC_{t['name']}," for t in dtcs]
        c += ["};", ""]
    c += [
        "const platform_uds_did_t *platform_uds_find_did(uint16_t did)",
        "{",
        "    size_t i;",
        "",
        f"    for (i = 0u; i < {p}_DID_COUNT; i++) {{",
        "        if (platform_uds_dids[i].did == did) {",
        "            return &platform_uds_dids[i];",
        "        }",
        "    }",
        "    return NULL;",
        "}",
        "",
    ]
    services = srv.get("services") or []

    # service_supported
    c += ["bool platform_uds_service_supported(uint8_t sid)", "{", "    bool ok;", ""]
    c += ["    switch (sid) {"]
    for e in services:
        c.append(f"    case {_hex(tables['services'][e['service']], 2)}: /* {e['service']} */")
    c += ["        ok = true;", "        break;", "    default:", "        ok = false;"]
    c += ["        break;", "    }", "    return ok;", "}", ""]
    # service_allowed_in_session
    c += ["bool platform_uds_service_allowed_in_session(uint8_t sid, uint8_t session)", "{"]
    c += ["    bool ok;", "", "    switch (sid) {"]
    for e in services:
        cond = " || ".join(f"(session == {_hex(s, 2)})" for s in _session_list(iso, e["sessions"]))
        c += [
            f"    case {_hex(tables['services'][e['service']], 2)}: /* {e['service']} */",
            f"        ok = {cond};",
            "        break;",
        ]
    c += [
        "    default:",
        "        ok = false;",
        "        break;",
        "    }",
        "    return ok;",
        "}",
        "",
    ]
    # session_supported
    cond = " || ".join(f"(session == {_hex(s, 2)})" for s in _session_list(iso, srv["sessions"]))
    c += ["bool platform_uds_session_supported(uint8_t session)", "{", f"    return {cond};"]
    c += ["}", ""]
    # subfunction_supported
    c += ["bool platform_uds_subfunction_supported(uint8_t sid, uint8_t subfunction)", "{"]
    c += ["    uint8_t sub = (uint8_t)(subfunction & 0x7Fu); /* suppressPosRsp bit */"]
    c += ["    bool ok;", "", "    switch (sid) {"]
    for e in services:
        subs = e.get("subfunctions")
        if subs is None:
            continue
        table = tables[SUBFUNCTION_TABLES[e["service"]]]
        cond = " || ".join(f"(sub == {_hex(table[s], 2)})" for s in subs)
        c += [
            f"    case {_hex(tables['services'][e['service']], 2)}: /* {e['service']} */",
            f"        ok = {cond};",
            "        break;",
        ]
    c += [
        "    default:",
        "        ok = false;",
        "        break;",
        "    }",
        "    return ok;",
        "}",
        "",
    ]
    # nrc_suppressed_functional
    c += ["bool platform_uds_nrc_suppressed_functional(uint8_t nrc)", "{"]
    cond = " || ".join(f"(nrc == {_hex(n, 2)})" for n in iso["functional_suppressed_nrcs"])
    c += [f"    return {cond or 'false'};", "}", ""]
    return {"platform_uds.h": "\n".join(h), "platform_uds.c": "\n".join(c)}


# --------------------------------------------------------------------------- Python


def generate_uds_py(iso: dict[str, Any], data: dict[str, Any], vehicle: dict[str, Any]) -> str:
    """vehicle_defs/uds.py: ISO codes and every platform server (host testers)."""
    banner = '"""GENERATED by vehicle-defs tools/codegen from {source}. DO NOT EDIT."""\n'
    lines = [banner.format(source="uds/iso14229.yaml, uds/dids.yaml"), ""]
    tables = iso_tables(iso)
    for table, prefix in (("services", "SID"), ("sessions", "SESSION"),
                          ("tester_present_subfunctions", "TESTER_PRESENT"),
                          ("read_dtc_subfunctions", "READ_DTC"),
                          ("dtc_status_bits", "DTC_STATUS"), ("nrcs", "NRC")):  # fmt: skip
        for name, value in tables[table].items():
            lines.append(f"{prefix}_{name} = 0x{value:02X}")
        lines.append("")
    lines.append(f"POSITIVE_RESPONSE_OFFSET = 0x{iso['positive_response_offset']:02X}")
    lines.append(f"SID_NEGATIVE_RESPONSE = 0x{iso['negative_response_sid']:02X}")
    lines.append(f"SUPPRESS_POS_RSP_BIT = 0x{iso['suppress_pos_rsp_bit']:02X}")
    lines.append(f"GROUP_OF_DTC_ALL = 0x{iso['group_of_dtc_all']:06X}")
    fmt = iso["dtc_format_identifier"]
    lines.append(f"DTC_FORMAT_{fmt['name']} = 0x{fmt['id']:02X}")
    lines.append(
        "FUNCTIONAL_SUPPRESSED_NRCS = frozenset({"
        + ", ".join(f"0x{n:02X}" for n in iso["functional_suppressed_nrcs"])
        + "})"
    )
    lines.append(f"P2_STAR_RESOLUTION_MS = {iso['p2_star_resolution_ms']}")
    lines.append("")
    tr = data["transport"]
    lines.append("TRANSPORT = {")
    for key in (*TRANSPORT_KEYS, "functional_request_id"):
        lines.append(f'    "{key}": {tr[key]},')
    lines += ["}", "", "# node -> server contract (dids: name -> (did, length, encoding))"]
    lines.append("SERVERS = {")
    for node, content in servers(data).items():
        srv = content["server"]
        lines.append(f'    "{node}": {{')
        for key in SERVER_INT_KEYS:
            lines.append(f'        "{key}": {srv[key]},')
        lines.append(f'        "sessions": {tuple(srv["sessions"])!r},')
        svc = {e["service"]: tuple(e["sessions"]) for e in srv["services"]}
        lines.append(f'        "services": {svc!r},')
        lines.append('        "dids": {')
        for d in content.get("dids") or []:
            lines.append(
                f'            "{d["name"]}": (0x{d["did"]:04X}, {did_length(d, vehicle)}, '
                f'"{d["encoding"]}"),'
            )
        lines.append("        },")
        lines.append('        "dtcs": {')
        for t in content.get("dtcs") or []:
            lines.append(f'            "{t["name"]}": (0x{t["dtc"]:06X}, "{t["code"]}"),')
        lines += ["        },", "    },"]
    lines += ["}", ""]
    lines += _record_fields_py(data)
    lines += _ride_records_py(data)
    return "\n".join(lines)


def _record_fields_py(data: dict[str, Any]) -> list[str]:
    """Field layouts of the record/bitfield DIDs (ISSUES E-13 (3)) so host testers (vehicle-
    hil-bench, scripts) decode e.g. 0xFD02 from defs instead of by hand. Ride-summary records
    have their own table below (RIDE_RECORDS). Data only."""
    lines = [
        "# Record and bitfield DIDs (not the ride-summary records): node -> DID name -> did,",
        "# length, field positions ({byte, mask} or {byte, length}, unsigned big-endian) and the",
        "# named values of enumerated fields. Data only (ISSUES E-13 (3)).",
        "RECORD_FIELDS = {",
    ]
    for node, content in servers(data).items():
        items = [
            d for d in content.get("dids") or [] if d.get("fields") and not d.get("ride_record")
        ]
        if not items:
            continue
        lines.append(f'    "{node}": {{')
        for d in items:
            lines += [
                f'        "{d["name"]}": {{',
                f'            "did": 0x{d["did"]:04X},',
                f'            "length": {d["length"]},',
                '            "fields": {',
            ]
            for f in d["fields"]:
                if "mask" in f:
                    pos = f'{{"byte": {f["byte"]}, "mask": 0x{f["mask"]:02X}}}'
                else:
                    pos = f'{{"byte": {f["byte"]}, "length": {f["length"]}}}'
                lines.append(f'                "{f["name"]}": {pos},')
            lines += ["            },", '            "values": {']
            for field, named in (d.get("values") or {}).items():
                pairs = ", ".join(f'"{k}": 0x{v:02X}' for k, v in named.items())
                lines.append(f'                "{field}": {{{pairs}}},')
            lines += ["            },", "        },"]
        lines.append("    },")
    lines += ["}", ""]
    return lines


def _ride_records_py(data: dict[str, Any]) -> list[str]:
    """Data-only layout of the generated ride-summary records (D-098); the raw encoder
    (value -> raw, NOT_AVAILABLE for a missing or out-of-range value) lives in vehicle-server."""
    lines = [
        "# Ride-summary records (D-098): record -> did, length, header positions and the signal",
        "# fields. raw = round((value - range_min) / resolution), unsigned big-endian; `na` (all",
        "# ones) is NOT_AVAILABLE, `raw_max` the largest valid raw value. Data only.",
        f"RIDE_RECORD_LAYOUT_VERSION = {RIDE_RECORD_LAYOUT_VERSION}",
        "RIDE_RECORDS = {",
    ]
    for d in data["nodes"]["RT_CORE"].get("dids") or []:
        if not d.get("ride_record"):
            continue
        lines += [
            f'    "{d["name"]}": {{',
            f'        "did": 0x{d["did"]:04X},',
            f'        "length": {d["length"]},',
            f'        "layout_version": {RIDE_RECORD_LAYOUT_VERSION},',
            '        "header": {',
        ]
        for f in d["fields"]:
            if "ride_signal" in f:
                continue
            if "mask" in f:
                pos = f'{{"byte": {f["byte"]}, "mask": 0x{f["mask"]:02X}}}'
            else:
                pos = f'{{"byte": {f["byte"]}, "length": {f["length"]}}}'
            lines.append(f'            "{f["name"]}": {pos},')
        lines += ["        },", '        "fields": {']
        for f in d["fields"]:
            rs = f.get("ride_signal")
            if rs is None:
                continue
            lines += [
                f'            "{f["name"]}": {{',
                f'                "signal": "{rs["signal"]}",',
                f'                "byte": {f["byte"]},',
                f'                "length": {f["length"]},',
                f'                "range_min": {rs["range_min"]!r},',
                f'                "resolution": {rs["resolution"]!r},',
                f'                "raw_max": {rs["raw_max"]},',
                f'                "na": 0x{field_max(f):0{2 * f["length"]}X},',
                "            },",
            ]
        lines += ["        },", "    },"]
    lines += ["}", ""]
    return lines
