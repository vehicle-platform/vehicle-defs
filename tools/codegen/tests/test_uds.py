"""UDS sources (iso14229.yaml, dids.yaml), Q-021 watch IDs and the generated code (D-040)."""

import copy
import ctypes
import re
import shutil
import subprocess
import types

import pytest

from vehicle_codegen import config, gen_uds
from vehicle_codegen.yaml_checks import check_vehicle, load_yaml

CC = shutil.which("gcc") or shutil.which("cc")
FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-Wshadow", "-Wconversion"]
C_DIR = config.GEN_DIR / "c"


@pytest.fixture
def iso():
    return load_yaml(config.ISO14229_YAML)


@pytest.fixture
def dids():
    return copy.deepcopy(load_yaml(config.DIDS_YAML))


def _errors(dids, iso, vehicle):
    return gen_uds.check_dids(dids, iso, vehicle)


# --------------------------------------------------------------------------- sources


@pytest.mark.parametrize(
    ("code", "dtc"),
    [
        ("U0100-00", 0xC10000),
        ("U3000-00", 0xF00000),
        ("U0001-88", 0xC00188),
        ("P0301-1F", 0x03011F),
        ("C1234-56", 0x523456),
        ("B0000-00", 0x800000),
    ],  # fmt: skip
)
def test_j2012_encoding(code, dtc):
    assert gen_uds.j2012_to_dtc(code) == dtc


@pytest.mark.parametrize("code", ["U0100", "X0100-00", "U4100-00", "u0100-00", "U0100-0"])
def test_j2012_rejects_malformed(code):
    assert gen_uds.j2012_to_dtc(code) is None


def test_iso_duplicate_rejected(iso):
    iso["nrcs"].append({"nrc": 0x31, "name": "AGAIN"})
    assert any("duplicate" in e for e in gen_uds.check_iso(iso))


def test_iso_positive_sid_rejected(iso):
    iso["services"].append({"sid": 0x62, "name": "NOT_A_REQUEST", "clause": "x"})
    assert any("not a request SID" in e for e in gen_uds.check_iso(iso))


def _rt(dids):
    return dids["nodes"]["RT_CORE"]


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda d: _rt(d)["server"].update(physical_request_id=0x720), "0x710"),
        (lambda d: _rt(d)["server"].update(physical_response_id=0x719), "0x718"),
        (lambda d: _rt(d)["server"].update(p2_server_max_ms=6000), "P2 < P2*"),
        (lambda d: _rt(d)["server"].update(p2_star_server_max_ms=5005), "multiple"),
        (lambda d: _rt(d)["server"].update(max_read_dids=40), "rx_buffer"),
        (lambda d: _rt(d)["server"].update(sessions=["EXTENDED"]), "DEFAULT"),
        (
            lambda d: _rt(d)["server"]["services"].append(
                {"service": "CLEAR_DIAGNOSTIC_INFORMATION", "sessions": ["EXTENDED"]}
            ),
            "duplicate",
        ),
        (
            lambda d: _rt(d)["server"]["services"][4].update(sessions=["PROGRAMMING"]),
            "served sessions",
        ),
        (lambda d: _rt(d)["server"]["services"][1].update(subfunctions=["NOPE"]), "sub-functions"),
        (lambda d: _rt(d)["dids"][0].update(access="write"), "only read"),
        (lambda d: _rt(d)["dids"][0].update(did=0xF200), "outside"),
        (lambda d: _rt(d)["dids"][1].update(did=0xF186), "duplicate DID"),
        (lambda d: _rt(d)["dids"][3].update(length=5), "uint length"),
        (lambda d: _rt(d)["dids"][2]["fields"][1].update(mask=0x01), "overlaps"),
        (lambda d: _rt(d)["dids"][4].update(vehicle_did="NOPE"), "not in vehicle_cl250"),
        (lambda d: _rt(d)["dids"][4].update(length=3), "length must be 5"),
        (lambda d: _rt(d)["dtcs"][0].update(code="U0101-00"), "does not encode"),
        (lambda d: _rt(d)["dtcs"][1].update(dtc=0xC10000, code="U0100-00"), "unique"),
        (lambda d: _rt(d)["dtcs"][0].update(dtc=0xFFFFFF), "unique"),
        (lambda d: d["transport"].update(functional_request_id=0x7DE), "0x7DF"),
        (lambda d: d["nodes"]["SAFETY"].update(dids=[{"did": 0xF189}]), "no server"),
        (
            lambda d: d["nodes"]["SAFETY"].update(
                server=_rt(d)["server"], dids=[_rt(d)["dids"][4]]
            ),
            "0x720",
        ),
    ],
)
def test_dids_rejects(dids, iso, vehicle, mutate, needle):
    mutate(dids)
    errors = _errors(dids, iso, vehicle)
    assert any(needle in e for e in errors), errors


def _health(dids):
    return next(d for d in _rt(dids)["dids"] if d["name"] == "RT_CORE_HEALTH")


def _health_field(dids, name):
    return next(f for f in _health(dids)["fields"] if f["name"] == name)


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda d: _health_field(d, "STEP_OVERRUNS").update(length=3), "1, 2 or 4"),
        (lambda d: _health_field(d, "PLATFORM_NAS_ABORTS").update(byte=22), "1, 2 or 4"),
        (lambda d: _health_field(d, "STEP_GAP_MAX_MS").update(byte=2), "overlaps"),
        (lambda d: _health_field(d, "VEHICLE_LATCHED").update(byte=1), "overlaps"),
        (lambda d: _health(d).update(length=24), "not covered"),
        (lambda d: _health_field(d, "VEHICLE_STATE").pop("description"), "description missing"),
        (lambda d: _health_field(d, "VEHICLE_STATE").update(name="STEP_OVERRUNS"), "duplicate"),
        (lambda d: _health_field(d, "VEHICLE_STATE").update({"see values.": None}), "unknown"),
        (lambda d: _health(d)["values"].update(VEHICLE_STATE={"BIG": 256}), "values.VEHICLE_STATE"),
        (lambda d: _health(d)["values"].update(NOPE={"A": 0}), "values.NOPE"),
        (lambda d: _health(d).update(fields=[]), "record needs fields"),
        (lambda d: _health_field(d, "STEP_OVERRUNS").update(length=True), "not bool"),
        (lambda d: _health_field(d, "VEHICLE_LATCHED").update(mask=True), "not bool"),
        (lambda d: _health_field(d, "VEHICLE_STATE").update(name="A-B"), "UPPER_CASE"),
        (lambda d: _health(d)["values"]["VEHICLE_STATE"].update(AGAIN=3), "values.VEHICLE"),
        (lambda d: _health(d)["values"]["VEHICLE_STATE"].update({"lower": 9}), "values.VEHICLE"),
        (lambda d: _health(d)["values"]["VEHICLE_STATE"].update(FLAG=True), "values.VEHICLE"),
        (lambda d: _rt(d)["dids"][2]["fields"][0].update(length=1), "byte/mask invalid"),
        (lambda d: _rt(d)["dids"][2]["fields"][0].pop("mask"), "byte/mask invalid"),
    ],
)
def test_record_rejects(dids, iso, vehicle, mutate, needle):
    mutate(dids)
    errors = _errors(dids, iso, vehicle)
    assert any(needle in e for e in errors), errors


def test_health_record_layout(dids):
    """D-055: 23 bytes, flags then u16 step counters, then 9 bytes per CAN port."""
    item = _health(dids)
    assert (item["did"], item["length"], item["encoding"]) == (0xFD02, 23, "record")
    fields = {f["name"]: (f["byte"], f.get("length"), f.get("mask")) for f in item["fields"]}
    assert fields["STEP_STATS_FRESH"] == (0, None, 0x01)
    assert fields["VEHICLE_LATCHED"] == (0, None, 0x02)
    assert fields["STEP_OVERRUNS"] == (1, 2, None)
    assert fields["STEP_GAP_MAX_MS"] == (3, 2, None)
    for port, base in (("VEHICLE", 5), ("PLATFORM", 14)):
        assert fields[f"{port}_STATE"] == (base, 1, None)
        for i, name in enumerate(("BUS_OFFS", "RECOVERIES", "RECOVER_DEFERRED", "NAS_ABORTS")):
            assert fields[f"{port}_{name}"] == (base + 1 + 2 * i, 2, None)
    assert _rt(dids)["dids"][-2] is item  # appended: existing indices unchanged


def test_lean_health_record_layout(dids):
    """D-067: 0xFD03 after 0xFD02, flag byte then two u16 counters (5 bytes)."""
    item = _rt(dids)["dids"][-1]  # appended: existing indices unchanged
    assert (item["did"], item["name"], item["length"]) == (0xFD03, "LEAN_HEALTH", 5)
    assert (item["encoding"], item["access"], item["max_age_ms"]) == ("record", "read", 500)
    fields = {f["name"]: (f["byte"], f.get("length"), f.get("mask")) for f in item["fields"]}
    assert fields == {
        "RECORD_FRESH": (0, None, 0x01),
        "OFFSET_LEARNED": (0, None, 0x02),
        "OFFSET_REJECTED": (0, None, 0x04),
        "SPEED_PRODUCER_FAULT": (0, None, 0x08),
        "OUTPUT_CONSUMER_FAULT": (0, None, 0x10),
        "SPEED_CONSUMER_FAULT": (0, None, 0x20),
        "EKF_ALIVE_OK": (0, None, 0x40),
        "RESERVED": (0, None, 0x80),
        "OFFSET_REJECTS": (1, 2, None),
        "UNLEARNED_S": (3, 2, None),
    }
    assert item["values"] == {"UNLEARNED_S": {"UNKNOWN": 0xFFFF}}  # fail-safe, never "learnt"


def test_vehicle_sample_needs_vehicle_node(dids, iso, vehicle):
    safety = dids["nodes"]["SAFETY"]
    safety["server"] = copy.deepcopy(_rt(dids)["server"])
    safety["server"].update(physical_request_id=0x720, physical_response_id=0x728)
    safety["dids"] = [copy.deepcopy(_rt(dids)["dids"][4])]
    assert any("vehicle_sample needs" in e for e in _errors(dids, iso, vehicle))


def test_platform_uds_ids_are_not_in_the_dbc(platform_db, dids):
    ids = {m.frame_id for m in platform_db.messages}
    srv = _rt(dids)["server"]
    assert {srv["physical_request_id"], srv["physical_response_id"], 0x7DF}.isdisjoint(ids)


# --------------------------------------------------------------------------- Q-021 watch


def test_functional_watch_must_be_watch_only(vehicle, platform_db):
    vehicle["addressing"]["functional_watch"]["watch_only"] = False
    assert any("watch_only" in e for e in check_vehicle(vehicle, platform_db))


def test_functional_watch_is_required(vehicle, platform_db):
    del vehicle["addressing"]["functional_watch"]
    assert any("functional_watch missing" in e for e in check_vehicle(vehicle, platform_db))


def test_functional_watch_cannot_alias_the_request_id(vehicle, platform_db):
    vehicle["addressing"]["functional_watch"]["ids"].append(
        {"id_type": "extended_29bit", "id": vehicle["addressing"]["primary"]["request_id"]}
    )
    assert any("duplicates" in e for e in check_vehicle(vehicle, platform_db))


def test_functional_watch_ids_are_the_obd_ones(vehicle):
    ids = {(w["id"], w["id_type"]) for w in vehicle["addressing"]["functional_watch"]["ids"]}
    assert ids == {(0x7DF, "standard_11bit"), (0x18DB33F1, "extended_29bit")}


def test_functional_watch_is_generated(vehicle):
    text = (C_DIR / "rt_core" / "vehicle_cl250.c").read_text()
    assert "{ 0x7DFu, false }" in text and "{ 0x18DB33F1u, true }" in text


# --------------------------------------------------------------------------- ISO header


def _defines(text: str) -> dict[str, int]:
    return {
        m.group(1): int(m.group(2), 16)
        for m in re.finditer(r"#define (UDS_\w+) \((0x[0-9A-F]+)u\)", text)
    }


def test_full_iso_header_is_identical_on_every_full_node():
    texts = {t.directory: (C_DIR / t.directory / "uds_iso14229.h").read_text()
             for t in config.C_TARGETS if t.uds_iso == "full"}  # fmt: skip
    assert len(set(texts.values())) == 1


def test_client_subset_names_nothing_outside_d020():
    """CONN is a vehicle-bus tester only: no name for 0x14, 0x10 02 or server NRCs."""
    defs = _defines((C_DIR / "conn" / "uds_iso14229.h").read_text())
    sids = {
        v for k, v in defs.items() if k.startswith("UDS_SID_") and k != "UDS_SID_NEGATIVE_RESPONSE"
    }
    assert sids <= set(config.ALLOWED_VEHICLE_SERVICES)
    assert "UDS_SID_CLEAR_DIAGNOSTIC_INFORMATION" not in defs
    assert "UDS_SESSION_PROGRAMMING" not in defs
    assert "UDS_GROUP_OF_DTC_ALL" not in defs
    assert {k for k in defs if k.startswith("UDS_NRC_")} == {
        "UDS_NRC_SERVICE_NOT_SUPPORTED",  # D-080: tester records 0x19 as not served
        "UDS_NRC_SUBFUNCTION_NOT_SUPPORTED",  # D-080
        "UDS_NRC_RESPONSE_PENDING",
        "UDS_NRC_SUBFUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION",
        "UDS_NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION",
        "UDS_NRC_REQUEST_OUT_OF_RANGE",  # D-068 item 2: stops an unverified DID
    }


def test_iso_header_keeps_the_client_names():
    """The names rt-core's client used from its temporary header (D-039 item 1)."""
    for d in ("rt_core", "conn"):
        defs = _defines((C_DIR / d / "uds_iso14229.h").read_text())
        assert defs["UDS_SID_READ_DATA_BY_IDENTIFIER"] == 0x22
        assert defs["UDS_SID_NEGATIVE_RESPONSE"] == 0x7F
        assert defs["UDS_NRC_RESPONSE_PENDING"] == 0x78
        assert defs["UDS_NRC_SUBFUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION"] == 0x7E
        assert defs["UDS_NRC_SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION"] == 0x7F


# --------------------------------------------------------------------------- generated C


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    if CC is None:
        pytest.skip("no C compiler")
    out = tmp_path_factory.mktemp("uds") / "libuds.so"
    d = C_DIR / "rt_core"
    srcs = [str(d / "platform_uds.c"), str(d / "vehicle_cl250.c")]
    subprocess.run([CC, *FLAGS, "-shared", "-fPIC", "-o", str(out), *srcs], check=True)
    so = ctypes.CDLL(str(out))
    for fn in ("platform_uds_service_supported", "platform_uds_session_supported",
               "platform_uds_nrc_suppressed_functional"):  # fmt: skip
        getattr(so, fn).argtypes = [ctypes.c_uint8]
        getattr(so, fn).restype = ctypes.c_bool
    for fn in ("platform_uds_service_allowed_in_session", "platform_uds_subfunction_supported"):
        getattr(so, fn).argtypes = [ctypes.c_uint8, ctypes.c_uint8]
        getattr(so, fn).restype = ctypes.c_bool
    so.platform_uds_find_did.argtypes = [ctypes.c_uint16]
    so.platform_uds_find_did.restype = ctypes.POINTER(DidEntry)
    so.vehicle_cl250_request_allowed.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    so.vehicle_cl250_request_allowed.restype = ctypes.c_bool
    return so


class DidEntry(ctypes.Structure):
    _fields_ = [
        ("did", ctypes.c_uint16),
        ("length", ctypes.c_uint8),
        ("encoding", ctypes.c_uint8),
        ("vehicle_idx", ctypes.c_uint8),
    ]


def test_service_session_matrix_matches_yaml(lib, iso, dids):
    tables = gen_uds.iso_tables(iso)
    srv = _rt(dids)["server"]
    offered = {tables["services"][e["service"]]: e for e in srv["services"]}
    served = {tables["sessions"][s] for s in srv["sessions"]}
    for sid in range(256):
        assert lib.platform_uds_service_supported(sid) == (sid in offered)
        for session in range(256):
            want = sid in offered and session in {
                tables["sessions"][s] for s in offered[sid]["sessions"]
            }
            assert lib.platform_uds_service_allowed_in_session(sid, session) == want
    for session in range(256):
        assert lib.platform_uds_session_supported(session) == (session in served)
    assert not lib.platform_uds_session_supported(0x02)  # no bootloader yet
    assert lib.platform_uds_service_allowed_in_session(0x14, 0x03)
    assert not lib.platform_uds_service_allowed_in_session(0x14, 0x01)  # extended only


def test_subfunctions_match_yaml(lib):
    for sub in range(256):
        assert lib.platform_uds_subfunction_supported(0x3E, sub) == ((sub & 0x7F) == 0x00)
        assert lib.platform_uds_subfunction_supported(0x19, sub) == (
            (sub & 0x7F) in (0x01, 0x02, 0x0A)
        )
        assert not lib.platform_uds_subfunction_supported(0x22, sub)
        assert not lib.platform_uds_subfunction_supported(0x14, sub)


def test_functional_nrc_suppression(lib, iso):
    for nrc in range(256):
        assert lib.platform_uds_nrc_suppressed_functional(nrc) == (
            nrc in iso["functional_suppressed_nrcs"]
        )


def test_did_table_matches_yaml(lib, dids, vehicle):
    vidx = {d["name"]: i for i, d in enumerate(vehicle["dids"])}
    for item in _rt(dids)["dids"]:
        entry = lib.platform_uds_find_did(item["did"]).contents
        assert entry.length == gen_uds.did_length(item, vehicle)
        assert entry.encoding == gen_uds.ENCODINGS.index(item["encoding"])
        want = vidx[item["vehicle_did"]] if item["encoding"] == "vehicle_sample" else 0xFF
        assert entry.vehicle_idx == want
    assert not lib.platform_uds_find_did(0xF190)


@pytest.mark.parametrize(
    "payload",
    [b"\x14\xff\xff\xff", b"\x10\x02", b"\x10\x82", b"\x11\x01", b"\x27\x01", b"\x2e\xf1\x90"],
)
def test_vehicle_gate_still_refuses_server_services(lib, payload):
    """Naming 0x14 / 0x10 02 in uds_iso14229.h widens nothing on the vehicle bus (D-020)."""
    assert not lib.vehicle_cl250_request_allowed(payload, len(payload))


# --------------------------------------------------------------------------- Python


def test_python_module_matches(dids, vehicle):
    ns: dict = {}
    exec((config.GEN_DIR / "python" / "vehicle_defs" / "uds.py").read_text(), ns)  # noqa: S102
    rt = ns["SERVERS"]["RT_CORE"]
    assert rt["physical_request_id"] == 0x710 and rt["physical_response_id"] == 0x718
    assert ns["TRANSPORT"]["functional_request_id"] == 0x7DF
    assert rt["dids"]["VEHICLE_ENGINE_SPEED"] == (0xFD10, 5, "vehicle_sample")
    assert rt["dtcs"]["VEHICLE_ECU_COMM_LOST"] == (0xC10000, "U0100-00")
    assert rt["dtcs"]["VEHICLE_BUS_OFF_LATCHED"] == (0xC00188, "U0001-88")
    assert rt["dids"]["RT_CORE_HEALTH"] == (0xFD02, 23, "record")
    assert ns["SID_CLEAR_DIAGNOSTIC_INFORMATION"] == 0x14


def test_did_length_and_max_age_macros(dids, vehicle):
    text = (C_DIR / "rt_core" / "platform_uds.h").read_text()
    for item in _rt(dids)["dids"]:
        length = gen_uds.did_length(item, vehicle)
        assert f"#define PLATFORM_UDS_DID_{item['name']}_LENGTH ({length}u)" in text
    assert "#define PLATFORM_UDS_VEHICLE_TESTER_STATUS_MAX_AGE_MS (500u)" in text
    assert "#define PLATFORM_UDS_VEHICLE_TESTER_STATUS_FAULT_NOT_RUNNING (4u)" in text


def test_record_macros(dids):
    text = (C_DIR / "rt_core" / "platform_uds.h").read_text()
    p = "#define PLATFORM_UDS_RT_CORE_HEALTH"
    assert "PLATFORM_UDS_ENC_RECORD = 4" in text
    assert f"{p}_MAX_AGE_MS (500u)" in text
    for f in _health(dids)["fields"]:
        assert f"{p}_{f['name']}_BYTE ({f['byte']}u)" in text
        if "mask" in f:
            assert f"{p}_{f['name']}_MASK (0x{f['mask']:02X}u)" in text
        else:
            top = (1 << (8 * f["length"])) - 1
            assert f"{p}_{f['name']}_LENGTH ({f['length']}u)" in text
            line = f"{p}_{f['name']}_MAX (0x{top:0{2 * f['length']}X}u)"
            assert line in text
            # E-13 (1): a state (enum) field is no counter, so no saturation note on its MAX.
            saturates = f"{line} /* counters saturate here */" in text
            assert saturates == (f["name"] not in _health(dids)["values"]), f["name"]
    assert f"{p}_VEHICLE_STATE_LATCHED (3u)" in text
    for port in ("VEHICLE", "PLATFORM"):  # safety review MAJOR-1: 0 is healthy, so no zero
        assert f"{p}_{port}_STATE_UNKNOWN (255u)" in text
    assert "#define PLATFORM_UDS_DTC_VEHICLE_BUS_OFF_LATCHED (0xC00188u) /* U0001-88 */" in text
    assert "#define PLATFORM_UDS_MAX_DID_LENGTH (23u)" in text


def test_max_age_rejected_when_invalid(dids, iso, vehicle):
    _rt(dids)["dids"][2]["max_age_ms"] = 0
    assert any("max_age_ms" in e for e in _errors(dids, iso, vehicle))


def test_record_fields_cover_every_record_did_with_fields():
    """ISSUES E-13 (3): host testers decode record/bitfield DIDs from vehicle_defs.uds."""
    data = load_yaml(config.DIDS_YAML)
    iso = load_yaml(config.ISO14229_YAML)
    vehicle = load_yaml(config.VEHICLE_YAML)
    text = gen_uds.generate_uds_py(iso, data, vehicle)
    module = types.ModuleType("uds_under_test")
    exec(text, module.__dict__)  # the generated module under test
    for node, content in gen_uds.servers(data).items():
        for d in content.get("dids") or []:
            if not d.get("fields") or d.get("ride_record"):
                continue
            rec = module.RECORD_FIELDS[node][d["name"]]
            assert rec["did"] == d["did"] and rec["length"] == d["length"]
            assert list(rec["fields"]) == [f["name"] for f in d["fields"]]
            for f in d["fields"]:
                pos = rec["fields"][f["name"]]
                assert pos["byte"] == f["byte"]
                assert pos.get("mask") == f.get("mask") and pos.get("length") == f.get("length")
            assert rec["values"] == {k: dict(v) for k, v in (d.get("values") or {}).items()}
    health = module.RECORD_FIELDS["RT_CORE"]["RT_CORE_HEALTH"]
    assert health["did"] == 0xFD02 and health["values"]["VEHICLE_STATE"]["UNKNOWN"] == 0xFF
