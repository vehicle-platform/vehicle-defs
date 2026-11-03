"""Ride-summary record DIDs generated from cl250_derived.yaml (D-098)."""

import copy
import ctypes
import importlib.util
import re
import shutil
import subprocess

import pytest

from vehicle_codegen import config, gen_uds, ride_records
from vehicle_codegen.yaml_checks import load_yaml

CC = shutil.which("gcc") or shutil.which("cc")
FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-Wshadow", "-Wconversion"]
C_DIR = config.GEN_DIR / "c" / "rt_core"

EXPECTED_SIZES = {
    "RIDE_USAGE": 18, "RIDE_FUELING": 12, "RIDE_THERMAL": 14, "RIDE_ELECTRICAL": 8,
    "RIDE_ENGINE_STRESS": 22, "RIDE_DRIVETRAIN": 12, "RIDE_CALIBRATION": 14,
    "RIDE_RIDER_STYLE": 8, "RIDE_ECU_HEALTH": 21, "RIDE_WINDOW_KEY_ON": 16,
    "RIDE_WINDOW_CRANK": 14, "RIDE_WINDOW_WARM_IDLE": 20, "RIDE_WINDOW_CRUISE": 14,
    "RIDE_WINDOW_POST_STOP": 12,
}  # fmt: skip


@pytest.fixture(scope="module")
def derived():
    return load_yaml(config.DERIVED_YAML)


@pytest.fixture(scope="module")
def dids_doc():
    return load_yaml(config.DIDS_YAML)


@pytest.fixture(scope="module")
def entries(derived):
    got, errors = ride_records.synthesize(derived)
    assert errors == []
    return {e["name"]: e for e in got}


# --------------------------------------------------------------------------- width rule


@pytest.mark.parametrize(
    ("raw_max", "width"),
    [(0, 1), (254, 1), (255, 2), (65534, 2), (65535, 4), (0xFFFFFFFE, 4)],
)
def test_width_boundaries(raw_max, width):
    assert ride_records.field_width(raw_max) == width


@pytest.mark.parametrize("raw_max", [0xFFFFFFFF, 1 << 40, -1])
def test_width_error(raw_max):
    with pytest.raises(ValueError, match="raw maximum"):
        ride_records.field_width(raw_max)


def test_raw_max_is_half_even():
    assert ride_records.raw_max_of([0.0, 2.5], 1.0) == 2  # 2.5 -> 2
    assert ride_records.raw_max_of([0.0, 3.5], 1.0) == 4  # 3.5 -> 4
    assert ride_records.raw_max_of([-40.0, 215.0], 1.0) == 255
    assert ride_records.raw_max_of([0.0, 2000.0], 0.01) == 200000


def _mini(signals):
    return {
        "ride_summary_records": {"RIDE_X": {"did": 0xFD40, "description": "X."}},
        "signals": {
            n: {"class": "B", "record": "RIDE_X", "description": "d", **s}
            for n, s in signals.items()
        },
    }


def test_synthesize_widths_in_yaml_order():
    doc = _mini({
        "a": {"range": [0, 254], "resolution": 1},
        "b": {"range": [0, 255], "resolution": 1},
        "c": {"range": [0, 65534], "resolution": 1},
        "d": {"range": [0, 65535], "resolution": 1},
    })  # fmt: skip
    (entry,), errors = ride_records.synthesize(doc)
    assert errors == []
    sig = [f for f in entry["fields"] if "ride_signal" in f]
    assert [(f["name"], f["byte"], f["length"]) for f in sig] == [
        ("A", 4, 1), ("B", 5, 2), ("C", 7, 2), ("D", 9, 4),
    ]  # fmt: skip
    assert entry["length"] == 13


def test_synthesize_errors():
    _, errors = ride_records.synthesize(_mini({"a": {"range": [0, 5e9], "resolution": 1}}))
    assert any("does not fit" in e for e in errors)
    _, errors = ride_records.synthesize(_mini({"a": {"range": [5, 0], "resolution": 1}}))
    assert any("negative" in e for e in errors)


def test_header_name_clash():
    doc = _mini({"ride_counter": {"range": [0, 5], "resolution": 1}})
    _, errors = ride_records.synthesize(doc)
    assert any("clashes" in e for e in errors)


def test_multi_element_and_empty_record_skipped():
    doc = _mini({"h": {"range": [0, 5], "resolution": 1, "bins": [{"count": 3}]},
                 "g": {"range": [0, 5], "resolution": 1, "per_gear": True}})  # fmt: skip
    entries, errors = ride_records.synthesize(doc)
    assert entries == [] and errors == []


# --------------------------------------------------------------------------- real YAML


def test_sizes_and_skipped_record(entries):
    assert {n: e["length"] for n, e in entries.items()} == EXPECTED_SIZES
    assert "RIDE_OPERATING_POINTS" not in entries
    assert 0xFD42 not in {e["did"] for e in entries.values()}


def test_no_multi_element_signal_in_a_record(derived, entries):
    multi = {n.upper() for n, s in derived["signals"].items() if ride_records.is_multi_element(s)}
    assert multi  # the YAML has some
    for e in entries.values():
        for f in e["fields"]:
            assert f.get("ride_signal", {}).get("signal", "").upper() not in multi


def test_header_layout(entries):
    for e in entries.values():
        head = e["fields"][:4]
        assert [(f["name"], f["byte"], f.get("length"), f.get("mask")) for f in head] == [
            ("LAYOUT_VERSION", 0, 1, None),
            ("RIDE_COUNTER", 1, 2, None),
            ("RIDE_CLOSED", 3, None, 0x01),
            ("RESERVED", 3, None, 0xFE),
        ]
        assert e["fields"][4]["byte"] == ride_records.HEADER_LENGTH
        assert e["ride_record"] is True and e["encoding"] == "record" and e["access"] == "read"
        assert "D-098" in e["description"]


def test_fields_are_contiguous(entries):
    for e in entries.values():
        end = ride_records.HEADER_LENGTH
        for f in e["fields"][4:]:
            assert f["byte"] == end
            end += f["length"]
            rs = f["ride_signal"]
            assert rs["raw_max"] < (1 << (8 * f["length"])) - 1
            assert f["length"] == 1 or rs["raw_max"] >= (1 << (8 * (f["length"] // 2))) - 1
        assert end == e["length"]


def test_checks_accept_generated_entries(derived, dids_doc):
    iso = load_yaml(config.ISO14229_YAML)
    vehicle = load_yaml(config.VEHICLE_YAML)
    assert ride_records.check_ride_records(derived, dids_doc, iso, vehicle) == []
    merged = ride_records.with_ride_records(dids_doc, derived)
    assert gen_uds.check_dids(merged, iso, vehicle) == []


def test_collision_with_explicit_did_is_reported(derived, dids_doc):
    iso = load_yaml(config.ISO14229_YAML)
    vehicle = load_yaml(config.VEHICLE_YAML)
    doc = copy.deepcopy(dids_doc)
    doc["nodes"]["RT_CORE"]["dids"][0]["did"] = 0xFD40
    assert any(
        "duplicate DID" in e for e in ride_records.check_ride_records(derived, doc, iso, vehicle)
    )


def test_explicit_dids_keep_their_index(derived, dids_doc):
    merged = ride_records.with_ride_records(dids_doc, derived)
    explicit = dids_doc["nodes"]["RT_CORE"]["dids"]
    assert merged["nodes"]["RT_CORE"]["dids"][: len(explicit)] == explicit
    assert dids_doc["nodes"]["RT_CORE"]["dids"] == explicit  # input not mutated
    header = (C_DIR / "platform_uds.h").read_text()
    for i, d in enumerate(explicit):
        assert f"PLATFORM_UDS_IDX_{d['name']} = {i}," in header


# --------------------------------------------------------------------------- C output


def test_c_defines(entries):
    h = (C_DIR / "platform_uds.h").read_text()
    assert "#define PLATFORM_UDS_RIDE_RECORD_LAYOUT_VERSION (1u)" in h
    p = "PLATFORM_UDS_RIDE_USAGE"
    assert f"#define {p}_RIDE_DISTANCE_BYTE (4u)" in h
    assert f"#define {p}_RIDE_DISTANCE_LENGTH (4u)" in h
    assert re.search(
        rf"#define {p}_RIDE_DISTANCE_MAX \(0x00030D40u\) /\* largest valid raw value", h
    )
    assert re.search(
        rf"#define {p}_RIDE_DISTANCE_NA \(0xFFFFFFFFu\) /\* NOT_AVAILABLE \(D-098\)", h
    )
    assert f"#define {p}_RIDE_DISTANCE_RANGE_MIN (0.0f)" in h
    assert f"#define {p}_RIDE_DISTANCE_RESOLUTION (0.01f)" in h
    assert f"#define {p}_RIDE_COUNTER_BYTE (1u)" in h
    assert f"#define {p}_RIDE_CLOSED_MASK (0x01u)" in h
    assert "#define PLATFORM_UDS_DID_RIDE_USAGE_LENGTH (18u)" in h
    for name, size in EXPECTED_SIZES.items():
        assert f"#define PLATFORM_UDS_DID_{name}_LENGTH ({size}u)" in h


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    if CC is None:
        pytest.skip("no C compiler")
    out = tmp_path_factory.mktemp("ride") / "libride.so"
    srcs = [C_DIR / n for n in ("platform_uds.c", "vehicle_cl250.c", "vehicle_cl250_derived.c")]
    subprocess.run([CC, *FLAGS, "-shared", "-fPIC", "-o", str(out), *map(str, srcs)], check=True)
    return ctypes.CDLL(str(out))


class RideField(ctypes.Structure):
    _fields_ = [
        ("did_idx", ctypes.c_uint8),
        ("byte", ctypes.c_uint8),
        ("length", ctypes.c_uint8),
        ("signal", ctypes.c_uint16),
        ("range_min", ctypes.c_float),
        ("resolution", ctypes.c_float),
        ("raw_max", ctypes.c_uint32),
        ("na", ctypes.c_uint32),
    ]


def test_c_table_compiles_and_matches(lib, derived, dids_doc, entries):
    h = (C_DIR / "platform_uds.h").read_text()
    count = int(re.search(r"PLATFORM_UDS_RIDE_FIELD_COUNT \((\d+)u\)", h).group(1))
    rows = (RideField * count).in_dll(lib, "platform_uds_ride_fields")
    merged = ride_records.with_ride_records(dids_doc, derived)["nodes"]["RT_CORE"]["dids"]
    names = [d["name"] for d in merged]
    signals = list(derived["signals"])
    rt_core = [n for n in signals if derived["signals"][n]["class"] in ("A", "B")]
    expect = [
        (names.index(e["name"]), f)
        for e in entries.values()
        for f in e["fields"]
        if "ride_signal" in f
    ]
    assert count == len(expect)
    for row, (idx, f) in zip(rows, expect, strict=True):
        rs = f["ride_signal"]
        assert (row.did_idx, row.byte, row.length) == (idx, f["byte"], f["length"])
        assert rt_core[row.signal] == rs["signal"]
        assert row.raw_max == rs["raw_max"]
        assert row.na == (1 << (8 * f["length"])) - 1
        assert row.range_min == pytest.approx(rs["range_min"], rel=1e-6)
        assert row.resolution == pytest.approx(rs["resolution"], rel=1e-6)


# --------------------------------------------------------------------------- Python output


def test_python_ride_records_shape(entries):
    spec = importlib.util.spec_from_file_location(
        "gen_uds_py", config.GEN_DIR / "python" / "vehicle_defs" / "uds.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.RIDE_RECORD_LAYOUT_VERSION == 1
    assert set(mod.RIDE_RECORDS) == set(EXPECTED_SIZES)
    rec = mod.RIDE_RECORDS["RIDE_USAGE"]
    assert (rec["did"], rec["length"], rec["layout_version"]) == (0xFD40, 18, 1)
    assert rec["header"] == {
        "LAYOUT_VERSION": {"byte": 0, "length": 1},
        "RIDE_COUNTER": {"byte": 1, "length": 2},
        "RIDE_CLOSED": {"byte": 3, "mask": 0x01},
        "RESERVED": {"byte": 3, "mask": 0xFE},
    }
    assert rec["fields"]["RIDE_DISTANCE"] == {
        "signal": "ride_distance", "byte": 4, "length": 4, "range_min": 0.0,
        "resolution": 0.01, "raw_max": 200000, "na": 0xFFFFFFFF,
    }  # fmt: skip
    for name, e in entries.items():
        assert mod.RIDE_RECORDS[name]["length"] == e["length"]
        assert mod.SERVERS["RT_CORE"]["dids"][name] == (e["did"], e["length"], "record")
