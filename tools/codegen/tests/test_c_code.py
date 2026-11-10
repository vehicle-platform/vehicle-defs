"""Generated C: builds warning-free per node and matches the Python reference."""

import ctypes
import random
import shutil
import subprocess

import pytest
from cantools.database.can.c_source import camel_to_snake_case

from vehicle_codegen import config, e2e
from vehicle_codegen.yaml_checks import frame_allowed, request_allowed, single_frame

CC = shutil.which("gcc") or shutil.which("cc")
pytestmark = pytest.mark.skipif(CC is None, reason="no C compiler")
FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-Wshadow", "-Wconversion"]
C_DIR = config.GEN_DIR / "c"


@pytest.mark.parametrize("target", [t.directory for t in config.C_TARGETS])
def test_node_code_compiles_strict(target, tmp_path):
    sources = sorted((C_DIR / target).glob("*.c"))
    assert sources, f"gen/c/{target} is empty; run make gen"
    for src in sources:
        subprocess.run(
            [CC, *FLAGS, "-c", str(src), "-o", str(tmp_path / (src.stem + ".o"))], check=True
        )


class RxState(ctypes.Structure):
    _fields_ = [
        ("last_rx_ms", ctypes.c_uint32),
        ("last_counter", ctypes.c_uint8),
        ("synced", ctypes.c_bool),
    ]


class TxState(ctypes.Structure):
    _fields_ = [("counter", ctypes.c_uint8)]


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    out = tmp_path_factory.mktemp("lib") / "libgen.so"
    d = C_DIR / "hil_sim"  # restbus target: contains every message and the DID table
    srcs = [
        str(d / n) for n in ("vehicle_e2e.c", "platform_e2e.c", "vehicle_cl250.c", "platform.c")
    ]
    subprocess.run([CC, *FLAGS, "-shared", "-fPIC", "-o", str(out), *srcs], check=True)
    so = ctypes.CDLL(str(out))
    so.vehicle_e2e_crc.restype = ctypes.c_uint8
    so.vehicle_e2e_crc.argtypes = [ctypes.c_uint16, ctypes.c_char_p, ctypes.c_size_t]
    so.vehicle_e2e_protect.argtypes = [
        ctypes.c_uint16,
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.POINTER(TxState),
    ]
    so.vehicle_e2e_check.argtypes = [
        ctypes.c_uint16,
        ctypes.c_uint8,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.POINTER(RxState),
        ctypes.c_uint32,
    ]
    so.vehicle_e2e_check_timeout.argtypes = [
        ctypes.POINTER(RxState),
        ctypes.c_uint32,
        ctypes.c_uint32,
    ]
    so.vehicle_e2e_tx_init.restype = None
    so.vehicle_e2e_tx_init.argtypes = [ctypes.POINTER(TxState)]
    so.vehicle_e2e_rx_init.restype = None
    so.vehicle_e2e_rx_init.argtypes = [ctypes.POINTER(RxState)]
    so.vehicle_e2e_is_valid.restype = ctypes.c_bool
    so.vehicle_e2e_is_valid.argtypes = [ctypes.c_int]
    so.vehicle_cl250_request_allowed.restype = ctypes.c_bool
    so.vehicle_cl250_request_allowed.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    so.vehicle_cl250_frame_allowed.restype = ctypes.c_bool
    so.vehicle_cl250_frame_allowed.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    so.vehicle_cl250_parse_response.restype = ctypes.c_bool
    so.vehicle_cl250_parse_response.argtypes = [
        ctypes.c_uint16,
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_float),
    ]
    so.vehicle_cl250_decode.restype = ctypes.c_bool
    so.vehicle_cl250_find.restype = ctypes.c_void_p
    so.vehicle_cl250_decode.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_float),
    ]
    return so


def test_crc_matches_reference(lib):
    rng = random.Random(1234)
    for _ in range(2000):
        data_id = rng.randrange(0x10000)
        payload = bytes(rng.randrange(256) for _ in range(rng.randrange(2, 9)))
        assert lib.vehicle_e2e_crc(data_id, payload, len(payload)) == e2e.compute_crc(
            data_id, payload
        )


@pytest.mark.parametrize("max_delta", [1, 2])
def test_protect_and_check_match_reference(lib, max_delta):
    rng = random.Random(99 + max_delta)
    data_id = 0x1021
    c_tx, py_tx = TxState(), e2e.TxState()
    c_rx, py_rx = RxState(), e2e.RxState()
    now = 0xFFFFFF00  # exercises the uint32 wrap
    prev = bytearray(8)
    seen = set()
    for _ in range(3000):
        buf = bytearray(rng.randrange(256) for _ in range(8))
        cbuf = ctypes.create_string_buffer(bytes(buf), 8)
        lib.vehicle_e2e_protect(data_id, cbuf, 8, ctypes.byref(c_tx))
        e2e.protect(data_id, buf, py_tx)
        assert cbuf.raw == bytes(buf)
        action = rng.random()
        if action < 0.1:  # corrupt
            buf[rng.randrange(8)] ^= 1 << rng.randrange(8)
        elif action < 0.15:  # drop
            continue
        elif action < 0.25:  # repeat the previous frame (frozen sender)
            buf = bytearray(prev)
        prev = bytearray(buf)
        now = (now + rng.choice([10, 20, 20, 20, 90])) & 0xFFFFFFFF
        for fn in ("timeout", "check"):
            if fn == "timeout":
                c = lib.vehicle_e2e_check_timeout(ctypes.byref(c_rx), 60, now)
                p = e2e.check_timeout(py_rx, 60, now)
            else:
                c = lib.vehicle_e2e_check(
                    data_id, max_delta, 60, bytes(buf), 8, ctypes.byref(c_rx), now
                )
                p = e2e.check(data_id, max_delta, 60, bytes(buf), py_rx, now)
            assert c == p
            seen.add(e2e.E2EStatus(p))
        assert (c_rx.last_counter, c_rx.last_rx_ms, c_rx.synced) == (
            py_rx.last_counter,
            py_rx.last_rx_ms,
            py_rx.synced,
        )
    # every receiver outcome except BAD_ARGUMENT must have been exercised
    expected = set(e2e.E2EStatus) - {e2e.E2EStatus.BAD_ARGUMENT}
    if max_delta == 1:
        expected.discard(e2e.E2EStatus.OK_SOME_LOST)  # impossible with max delta 1
    assert seen == expected


BAD = int(e2e.E2EStatus.BAD_ARGUMENT)


def _rx(synced=True):
    return RxState(last_rx_ms=1000, last_counter=3, synced=synced)


def _rx_tuple(s):
    return (s.last_rx_ms, s.last_counter, s.synced)


def test_e2e_protect_bad_arguments(lib):
    """NULL data or state, or fewer than 2 bytes: BAD_ARGUMENT, nothing written."""
    for data, size, state in (
        (None, 8, TxState(5)),
        (ctypes.create_string_buffer(b"\x11" * 8, 8), 8, None),
        (ctypes.create_string_buffer(b"\x11" * 8, 8), 1, TxState(5)),
        (ctypes.create_string_buffer(b"\x11" * 8, 8), 0, TxState(5)),
    ):
        st = ctypes.byref(state) if state is not None else None
        assert lib.vehicle_e2e_protect(0x1021, data, size, st) == BAD
        if data is not None:
            assert data.raw == b"\x11" * 8
        if state is not None:
            assert state.counter == 5
    with pytest.raises(ValueError):  # the Python reference refuses the short payload too
        e2e.protect(0x1021, bytearray(1), e2e.TxState())


def test_e2e_check_bad_arguments(lib):
    data_id = 0x1021
    frame = bytearray(8)
    e2e.protect(data_id, frame, e2e.TxState())
    frame = bytes(frame)  # a valid frame: only the argument makes it BAD_ARGUMENT
    cases = [(None, 8, 1, True), (frame, 8, 1, False), (frame, 1, 1, True), (frame, 0, 1, True)]
    cases += [(frame, 8, d, True) for d in (0, *range(15, 256))]
    for data, size, max_delta, with_state in cases:
        rx = _rx()
        st = ctypes.byref(rx) if with_state else None
        assert lib.vehicle_e2e_check(data_id, max_delta, 60, data, size, st, 1010) == BAD
        assert _rx_tuple(rx) == (1000, 3, True)  # state untouched
        if data is not None and with_state:
            ref = e2e.RxState(1000, 3, True)
            assert e2e.check(data_id, max_delta, 60, data[:size], ref, 1010) == BAD
    for max_delta in range(1, 15):  # the valid range never answers BAD_ARGUMENT
        status = lib.vehicle_e2e_check(data_id, max_delta, 60, frame, 8, ctypes.byref(_rx()), 1010)
        assert status != BAD
    assert not lib.vehicle_e2e_is_valid(BAD)


def test_e2e_null_state_helpers(lib):
    assert lib.vehicle_e2e_check_timeout(None, 60, 0) == BAD
    lib.vehicle_e2e_tx_init(None)  # must not crash
    lib.vehicle_e2e_rx_init(None)
    # Documents, not endorses: protect()/check() refuse NULL data before calling crc(),
    # so this path is never reached through them. It must not crash, and it covers the
    # DataID only, like an empty payload.
    assert lib.vehicle_e2e_crc(0x1021, None, 8) == e2e.compute_crc(0x1021, b"")


def test_request_allow_list_matches_policy_exhaustively(lib, vehicle):
    policy = vehicle["tester_policy"]
    for sid in range(256):
        assert lib.vehicle_cl250_request_allowed(bytes([sid]), 1) == request_allowed(policy, [sid])
        for sub in range(256):
            payload = bytes([sid, sub])
            assert lib.vehicle_cl250_request_allowed(payload, 2) == request_allowed(policy, payload)
    assert not lib.vehicle_cl250_request_allowed(None, 0)
    for sid in config.FORBIDDEN_VEHICLE_SERVICES:
        assert not any(lib.vehicle_cl250_request_allowed(bytes([sid, s]), 2) for s in range(256))


@pytest.mark.parametrize(
    ("did", "data", "expected"),
    [
        (0xF40C, b"\x1a\xf8", 1726.0),  # (0x1A*256+0xF8)/4
        (0xF40C, b"\xff\xff", 16383.75),
        (0xF40D, b"\x3c", 60.0),
        (0xF405, b"\x00", -40.0),
        (0xF405, b"\x7d", 85.0),
        (0xF411, b"\xff", 100.0),
        (0xF442, b"\x30\xd4", 12.5),
    ],
)
def test_did_decode(lib, did, data, expected):
    entry = lib.vehicle_cl250_find(did)
    assert entry
    out = ctypes.c_float()
    assert lib.vehicle_cl250_decode(entry, data, len(data), ctypes.byref(out))
    assert out.value == pytest.approx(expected, rel=1e-6)


def test_did_decode_rejects_short_and_unknown(lib):
    out = ctypes.c_float()
    assert not lib.vehicle_cl250_decode(
        lib.vehicle_cl250_find(0xF40C), b"\x01", 1, ctypes.byref(out)
    )
    assert lib.vehicle_cl250_find(0x1234) is None


def test_did_priorities_match_yaml(vehicle, tmp_path):
    """D-043: the C table carries each DID's class; lower value = more urgent."""
    from vehicle_codegen.yaml_checks import DID_PRIORITIES

    src = tmp_path / "t.c"
    src.write_text(
        '#include "vehicle_cl250.h"\n#include <stdio.h>\n'
        "int main(void){size_t i;for(i=0u;i<VEHICLE_CL250_DID_COUNT;i++)"
        '{(void)printf("%04X %u\\n",(unsigned)vehicle_cl250_dids[i].did,'
        "(unsigned)vehicle_cl250_dids[i].priority);}return 0;}\n"
    )
    exe = tmp_path / "t"
    d = C_DIR / "rt_core"
    subprocess.run([CC, *FLAGS, "-I", str(d), str(src), str(d / "vehicle_cl250.c"), "-o", str(exe)],
                   check=True)  # fmt: skip
    out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
    expected = "".join(
        f"{v['did']:04X} {DID_PRIORITIES.index(v['priority'])}\n" for v in vehicle["dids"]
    )
    assert out == expected
    header = (d / "vehicle_cl250.h").read_text()
    assert "#define VEHICLE_CL250_PRIORITY_HIGH (0u)" in header
    assert "#define VEHICLE_CL250_PRIORITY_NORMAL (1u)" in header


def test_request_allow_list_is_exactly_d020(lib):
    """Golden test, independent of the YAML: what C allows is D-020, nothing more."""
    for sid in range(256):
        for sub in range(256):
            golden = config.ALLOWED_VEHICLE_SERVICES.get(sid, "absent")
            if golden == "absent":
                expected = False
            elif golden is None:
                expected = True
            else:
                expected = (sub & 0x7F) in golden
            assert lib.vehicle_cl250_request_allowed(bytes([sid, sub]), 2) == expected, (sid, sub)


@pytest.mark.parametrize(
    ("frame", "allowed"),
    [
        (b"\x02\x10\x03" + b"\xaa" * 5, True),
        (b"\x02\x3e\x80" + b"\xaa" * 5, True),
        (b"\x03\x22\xf4\x0c" + b"\xaa" * 4, True),
        (b"\x01\x04" + b"\xaa" * 6, False),  # OBD mode 04 = clear DTCs
        (b"\x02\x10\x02" + b"\xaa" * 5, False),
        (b"\x02\x11\x01" + b"\xaa" * 5, False),
        (b"\x10\x08\x22\xf4\x0c\x00\x00\x00", False),  # First Frame
        (b"\x21\x22\xf4\x0c\x00\x00\x00\x00", False),  # Consecutive Frame
        (b"\x00\x22\xf4\x0c\x00\x00\x00\x00", False),  # SF length 0
        (b"\x08\x22\xf4\x0c\x00\x00\x00\x00", False),  # SF length > 7
        (b"\x07\x22\xf4", False),  # length beyond the buffer
        # D-059: the one FC.CTS, byte for byte; any other FC refused
        (b"\x30\x00\x00" + b"\xaa" * 5, True),
        (b"\x31\x00\x00" + b"\xaa" * 5, False),  # FC.WAIT
        (b"\x32\x00\x00" + b"\xaa" * 5, False),  # FC.OVFLW
        (b"\x30\x01\x00" + b"\xaa" * 5, False),  # other BS
        (b"\x30\x00\x0a" + b"\xaa" * 5, False),  # other STmin
        (b"\x30\x00\xf1" + b"\xaa" * 5, False),  # STmin in 100 us units
        (b"\x30\x00\x00" + b"\xaa" * 4 + b"\x00", False),  # other padding
        (b"\x30\x00\x00" + b"\x00" * 5, False),  # unpadded
        (b"\x30\x00\x00" + b"\xaa" * 4, False),  # 7 bytes
        (b"\x30\x00\x00" + b"\xaa" * 6, False),  # 9 bytes
        (b"\x30\x00", False),  # short FC
    ],
)
def test_frame_allowed(lib, frame, allowed):
    assert lib.vehicle_cl250_frame_allowed(frame, len(frame)) is allowed


def test_fc_cts_array_is_the_frame_the_gate_passes(lib, vehicle):
    """The client sends vehicle_cl250_fc_cts[]; it is the YAML frame and passes."""
    fc = (ctypes.c_uint8 * 8).in_dll(lib, "vehicle_cl250_fc_cts")
    frame = bytes(fc)
    assert frame == config.vehicle_fc_frame(vehicle["transport"])
    assert lib.vehicle_cl250_frame_allowed(frame, len(frame))


def test_frame_gate_matches_python_twin(lib, vehicle):
    """yaml_checks.frame_allowed() (used to check the scan list) equals the C gate."""
    rng = random.Random(59)
    fc = config.vehicle_fc_frame(vehicle["transport"])
    frames = [fc, fc[:7], fc + b"\xaa"]
    frames += [fc[:i] + bytes([b]) + fc[i + 1 :] for i in range(8) for b in range(256)]
    frames += [bytes(rng.randrange(256) for _ in range(rng.randrange(2, 10))) for _ in range(20000)]
    for pci in range(16):
        for sid in range(256):
            frames.append(bytes([pci, sid, 0x00]) + b"\xaa" * 5)
    for frame in frames:
        expected = frame_allowed(vehicle, frame)
        assert lib.vehicle_cl250_frame_allowed(frame, len(frame)) == expected, frame


class ScanEntry(ctypes.Structure):
    _fields_ = [
        ("request", ctypes.c_uint8 * 3),
        ("size", ctypes.c_uint8),
        ("bitmap_offset", ctypes.c_uint8),
        ("after", ctypes.c_uint8),
        ("after_id", ctypes.c_uint8),
        ("sensitive", ctypes.c_bool),
    ]


def test_discovery_table_matches_yaml_and_passes_the_gate(lib, vehicle):
    """D-059 item 2: the generated table is the YAML list, and every request, sent as a
    padded Single Frame, passes the C gate."""
    entries = vehicle["discovery_scan"]["requests"]
    table = (ScanEntry * len(entries)).in_dll(lib, "vehicle_cl250_discovery_scan")
    index = {e["name"]: i for i, e in enumerate(entries)}
    for e, row in zip(entries, table, strict=True):
        req = bytes(row.request[: row.size])
        assert list(req) == e["request"], e["name"]
        assert row.bitmap_offset == (len(req) if e.get("bitmap") else 0), e["name"]
        assert row.sensitive == bool(e.get("sensitive")), e["name"]
        after = e.get("after")
        assert row.after == (index[after["name"]] if after else 0xFF), e["name"]
        assert row.after_id == (after["id"] if after else 0), e["name"]
        frame = single_frame(vehicle, e["request"])
        assert lib.vehicle_cl250_frame_allowed(frame, len(frame)), e["name"]


@pytest.mark.parametrize(
    ("did", "frame", "ok", "value"),
    [
        (0xF40D, b"\x04\x62\xf4\x0d\x3c\xaa\xaa\xaa", True, 60.0),
        (0xF40C, b"\x05\x62\xf4\x0c\x1a\xf8\xaa\xaa", True, 1726.0),
        (0xF40D, b"\x04\x62\xf4\x11\x3c\xaa\xaa\xaa", False, None),  # late TPS answer
        (0xF40D, b"\x03\x7f\x22\x31\xaa\xaa\xaa\xaa", False, None),  # NRC
        (0xF40D, b"\x04\x7f\xf4\x0d\x3c\xaa\xaa\xaa", False, None),  # wrong SID, echo ok
        (0xF40D, b"\x04\x22\xf4\x0d\x3c\xaa\xaa\xaa", False, None),  # own request echoed
        (0xF40C, b"\x04\x62\xf4\x0c\x1a\xaa\xaa\xaa", False, None),  # too short
        (0xF40D, b"\x10\x08\x62\xf4\x0d\x3c\x00\x00", False, None),  # First Frame
        (0x1234, b"\x04\x62\x12\x34\x00\xaa\xaa\xaa", False, None),  # unknown DID
    ],
)
def test_parse_response(lib, did, frame, ok, value):
    out = ctypes.c_float()
    assert lib.vehicle_cl250_parse_response(did, frame, len(frame), ctypes.byref(out)) is ok
    if ok:
        assert out.value == pytest.approx(value)


def test_e2e_wrapper_constants(platform_db):
    from vehicle_codegen.dbc_checks import cycle_time_ms, e2e_data_id, is_e2e_protected

    header = (C_DIR / "hil_sim" / "platform_e2e.h").read_text()
    source = (C_DIR / "hil_sim" / "platform_e2e.c").read_text()
    for m in platform_db.messages:
        if not is_e2e_protected(m, platform_db):
            continue
        up = "PLATFORM_" + camel_to_snake_case(m.name).upper()
        assert e2e_data_id(m, platform_db) == 0x1000 + m.frame_id
        assert f"#define {up}_E2E_DATA_ID (0x{0x1000 + m.frame_id:04X}u)" in header
        assert f"#define {up}_E2E_TIMEOUT_MS ({3 * cycle_time_ms(m)}u)" in header
        fn = "platform_" + camel_to_snake_case(m.name)
        body = source.split(f"{fn}_e2e_check(const")[1].split("}")[0]
        assert f"{up}_E2E_DATA_ID" in body and f"{up}_E2E_TIMEOUT_MS" in body
