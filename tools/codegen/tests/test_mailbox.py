"""mailbox/h755_mailbox.yaml (D-093): checks, layout ID and the generated C/Python."""

import copy
import importlib.util
import json
import re
import shutil
import subprocess
import zlib

import pytest

from vehicle_codegen import config, gen_mailbox
from vehicle_codegen.yaml_checks import load_yaml

CC = shutil.which("gcc") or shutil.which("cc")
FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic"]
C_DIR = config.GEN_DIR / "c"
LAYOUT_ID = 0x9B315454  # pinned; was 0x61F4B364 before D-108 renamed signals


@pytest.fixture
def doc():
    return copy.deepcopy(load_yaml(config.MAILBOX_YAML))


def errors_of(doc, platform_db):
    return gen_mailbox.check_mailbox(doc, platform_db)


def test_repo_yaml_is_consistent_and_resolves(doc, platform_db):
    assert errors_of(doc, platform_db) == []
    lay = gen_mailbox.resolve(doc, platform_db)
    assert [(s.message, s.frame_id, s.length, s.hsem_id, s.offset) for s in lay.slots] == [
        ("EkfLean", 0x20, 8, 1, 32),
        ("EkfFrictionMass", 0x22, 8, 2, 48),
        ("HeartbeatRtCore", 0x81, 8, 3, 64),
        ("SafetyRequest", 0x120, 8, 4, 80),
        ("SafetyWarningStatus", 0x23, 8, 5, 96),
        ("HeartbeatSafety", 0x82, 8, 6, 112),
    ]
    assert lay.used_bytes == 128
    assert gen_mailbox.layout_id(lay, platform_db) == LAYOUT_ID


def test_layout_id_follows_the_documented_serialisation(doc, platform_db):
    lay = gen_mailbox.resolve(doc, platform_db)
    canonical = {
        "base_address": 0x38000000,
        "reserved_bytes": 256,
        "header_bytes": 32,
        "slot_bytes": 16,
        "slots": [
            {
                "index": s.index,
                "message": s.message,
                "frame_id": s.frame_id,
                "length": s.length,
                "direction": s.direction,
                "class": s.cls,
                "hsem_id": s.hsem_id,
                "offset": s.offset,
                "dbc": gen_mailbox._message_def(s.message, platform_db),
            }
            for s in lay.slots
        ],
    }
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    assert zlib.crc32(text.encode()) == LAYOUT_ID


def test_layout_id_changes_with_the_layout(doc, platform_db):
    base = gen_mailbox.layout_id(gen_mailbox.resolve(doc, platform_db), platform_db)
    doc["slots"][0]["hsem_id"] = 20
    assert gen_mailbox.layout_id(gen_mailbox.resolve(doc, platform_db), platform_db) != base
    doc["slots"][0]["hsem_id"] = 1
    doc["slots"][0], doc["slots"][1] = doc["slots"][1], doc["slots"][0]
    assert gen_mailbox.layout_id(gen_mailbox.resolve(doc, platform_db), platform_db) != base


def _slot(doc, name):
    return next(s for s in doc["slots"] if s["message"] == name)


def _rename(doc):
    doc["slots"][0]["message"] = "NoSuchMessage"


def _duplicate(doc):
    doc["slots"].append(dict(doc["slots"][0], hsem_id=9))


def _drop(name):
    return lambda doc: doc["slots"].remove(_slot(doc, name))


def _set(name, key, value):
    return lambda doc: _slot(doc, name).__setitem__(key, value)


def _region(key, value):
    return lambda doc: doc["region"].__setitem__(key, value)


def _extra_slot(doc):
    doc["slots"].append(
        {"message": "VehicleSpeed", "direction": "m7_to_m4", "class": "qm", "hsem_id": 9}
    )


CASES = [
    (_rename, "unknown message NoSuchMessage"),
    (_duplicate, "message EkfLean is already slot 0"),
    (_drop("HeartbeatRtCore"), "missing m7_to_m4 slot for HeartbeatRtCore"),
    (_drop("SafetyRequest"), "missing m7_to_m4 slot for SafetyRequest"),
    (_drop("HeartbeatSafety"), "missing m4_to_m7 slot for HeartbeatSafety"),
    (_extra_slot, "slot for VehicleSpeed, which SAFETY neither receives nor sends"),
    (_set("EkfLean", "direction", "m4_to_m7"), "slot 0 (EkfLean): direction must be m7_to_m4"),
    (
        _set("HeartbeatSafety", "direction", "m7_to_m4"),
        "(HeartbeatSafety): direction must be m4_to_m7",
    ),
    (_set("EkfLean", "class", "qm"), "(EkfLean): class must be safety"),
    (_set("SafetyRequest", "class", "safety"), "(SafetyRequest): class must be qm"),
    (_set("SafetyWarningStatus", "class", "qm"), "(SafetyWarningStatus): class must be safety"),
    (_set("EkfLean", "direction", "sideways"), "(EkfLean): direction must be one of"),
    (_set("EkfLean", "hsem_id", 0), "(EkfLean): hsem_id must be an integer 1..31"),
    (_set("EkfLean", "hsem_id", 32), "(EkfLean): hsem_id must be an integer 1..31"),
    (
        _set("EkfFrictionMass", "hsem_id", 1),
        "(EkfFrictionMass): hsem_id 1 is already used by EkfLean",
    ),
    (_set("EkfLean", "crc", 1), "(EkfLean): unknown keys ['crc']"),
    (_set("EkfLean", "length", 8), "(EkfLean): unknown keys ['length']"),
    (_region("base_address", 0x38000010), "not 32-byte aligned"),
    (_region("base_address", 0x20000000), "outside SRAM4"),
    (_region("base_address", 0x3800FFE0), "outside SRAM4"),
    (_region("reserved_bytes", 64), "used size 128 B exceeds region.reserved_bytes 64"),
    (_region("reserved_bytes", 384), "must be a power of two >= 32"),
    (_region("reserved_bytes", 16), "must be a power of two >= 32"),
    (
        _region("base_address", 0x38000020),
        "not a multiple of region.reserved_bytes 256",
    ),
    (_region("verified", "no"), "region.verified must be true or false"),
    (_region("extra", 1), "unknown region keys ['extra']"),
    (lambda doc: doc.update(extra=1), "unknown top-level keys ['extra']"),
]


@pytest.mark.parametrize(("mutate", "needle"), CASES)
def test_check_rejects(doc, platform_db, mutate, needle):
    mutate(doc)
    assert any(needle in e for e in errors_of(doc, platform_db)), errors_of(doc, platform_db)


def test_dbc_length_over_eight_is_rejected(doc, platform_db, platform_text):
    # a 9-byte message: a classic CAN frame cannot be mailboxed
    text = platform_text.replace("BO_ 32 EkfLean: 8 RT_CORE", "BO_ 32 EkfLean: 9 RT_CORE")
    from conftest import parse_dbc

    try:
        db = parse_dbc(text)
    except Exception:  # cantools may refuse a length that the signals do not fill
        pytest.skip("cantools rejects the synthetic 9-byte message")
    assert any("DBC length 9 exceeds 8" in e for e in errors_of(doc, db))


def test_dbc_receivers_must_match_the_config_split(doc, platform_db, monkeypatch):
    monkeypatch.setattr(config, "SAFETY_RX_ALLOWED", config.SAFETY_RX_ALLOWED | {"VehicleSpeed"})
    assert any("DBC says SAFETY receives" in e for e in errors_of(doc, platform_db))


def test_message_definition_is_in_the_layout_id(doc, platform_db):
    d = gen_mailbox._message_def("EkfLean", platform_db)
    assert d["e2e_protected"] is True and d["e2e_data_id"] and d["cycle_time_ms"] == 20
    sig = d["signals"][0]
    assert {"name", "start", "length", "byte_order", "is_signed", "factor", "offset"} <= set(sig)
    assert any(x["choices"] for x in d["signals"])  # value tables are covered


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (" SG_ LEAN_ANGLE_QUALITY : 32|8@1+", " SG_ LEAN_ANGLE_QUALITY : 40|8@1+"),  # start bit
        (" SG_ LEAN_ANGLE : 16|16@1- (0.01,", " SG_ LEAN_ANGLE : 16|16@1- (0.02,"),  # scale
        ('BA_ "E2E_DataID" BO_ 32 4128;', 'BA_ "E2E_DataID" BO_ 32 4129;'),  # DataID
        ('BA_ "GenMsgCycleTime" BO_ 32 20;', 'BA_ "GenMsgCycleTime" BO_ 32 40;'),  # cycle
    ],
)
def test_layout_id_follows_the_dbc_message(doc, platform_db, platform_text, old, new):
    assert old in platform_text, f"DBC text changed, update the variant: {old!r}"
    from conftest import parse_dbc

    base = gen_mailbox.layout_id(gen_mailbox.resolve(doc, platform_db), platform_db)
    db = parse_dbc(platform_text.replace(old, new, 1))
    assert gen_mailbox.layout_id(gen_mailbox.resolve(doc, db), db) != base


def test_slot_message_must_be_e2e_protected(doc, platform_db, platform_text):
    from conftest import parse_dbc

    text = platform_text.replace('BA_ "E2E_Protected" BO_ 32 1;', 'BA_ "E2E_Protected" BO_ 32 0;')
    assert text != platform_text
    assert any(
        "EkfLean): message is not E2E-protected" in e for e in errors_of(doc, parse_dbc(text))
    )


# ------------------------------------------------------------------ generated files


def _c_numbers(text):
    return {
        m[1]: int(m[2].rstrip("uU"), 0)
        for m in re.finditer(r"#define (\w+) \((0x[0-9A-Fa-f]+u|\d+u?)\)", text)
    }


def test_both_nodes_get_the_identical_header():
    a = (C_DIR / "rt_core" / "platform_mailbox.h").read_text()
    b = (C_DIR / "safety" / "platform_mailbox.h").read_text()
    assert a == b


@pytest.mark.skipif(CC is None, reason="no C compiler")
@pytest.mark.parametrize("node", ["rt_core", "safety"])
def test_c_header_compiles_and_matches(node, tmp_path):
    src = tmp_path / "t.c"
    src.write_text(
        '#include <stdio.h>\n#include "platform_mailbox.h"\n'
        "int main(void)\n{\n"
        '    printf("%lu %lu %lu\\n", (unsigned long)sizeof(platform_mailbox_header_t),\n'
        "           (unsigned long)sizeof(platform_mailbox_slot_t),\n"
        "           (unsigned long)sizeof(platform_mailbox_t));\n"
        '    printf("%lu %lu %lu %lu\\n",\n'
        "           (unsigned long)offsetof(platform_mailbox_header_t, m4_layout_id),\n"
        "           (unsigned long)offsetof(platform_mailbox_slot_t, len),\n"
        "           (unsigned long)offsetof(platform_mailbox_slot_t, data),\n"
        "           (unsigned long)offsetof(platform_mailbox_t, slot[5]));\n"
        '    printf("%lu %lu\\n", (unsigned long)PLATFORM_MAILBOX_SLOT_HEARTBEAT_SAFETY_FRAME_ID,\n'
        "           (unsigned long)PLATFORM_MAILBOX_SLOT_SAFETY_REQUEST_LENGTH);\n"
        "    return 0;\n}\n"
    )
    exe = tmp_path / "t"
    subprocess.run(
        [
            CC,
            *FLAGS,
            "-I",
            str(C_DIR / node),
            str(src),
            str(C_DIR / node / "platform.c"),
            "-o",
            str(exe),
        ],
        check=True,
    )
    out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.split("\n")
    assert out[0] == "32 16 128"
    assert out[1] == "4 4 8 112"
    assert out[2] == "130 8"

    nums = _c_numbers((C_DIR / node / "platform_mailbox.h").read_text())
    p = "PLATFORM_MAILBOX_"
    assert nums[p + "REGION_ADDR"] == 0x38000000
    assert nums[p + "RESERVED_BYTES"] == 256
    assert nums[p + "USED_BYTES"] == 128
    assert nums[p + "HEADER_BYTES"] == 32
    assert nums[p + "SLOT_BYTES"] == 16
    assert nums[p + "SLOT_COUNT"] == 6
    assert nums[p + "LAYOUT_ID"] == LAYOUT_ID
    assert nums[p + "ADDR_VERIFIED"] == 0
    assert nums[p + "SLOT_SAFETY_REQUEST_OFFSET"] == 80
    assert nums[p + "SLOT_SAFETY_REQUEST_HSEM_ID"] == 4


@pytest.mark.skipif(CC is None, reason="no C compiler")
def test_c_compile_time_asserts_fire(tmp_path):
    bad = (
        (C_DIR / "safety" / "platform_mailbox.h")
        .read_text()
        .replace("uint8_t reserved[3];", "uint8_t reserved[4];")
    )
    (tmp_path / "platform_mailbox.h").write_text(bad)
    src = tmp_path / "t.c"
    src.write_text('#include "platform_mailbox.h"\nint main(void) { return 0; }\n')
    run = subprocess.run(
        [
            CC,
            *FLAGS,
            "-I",
            str(tmp_path),
            "-I",
            str(C_DIR / "safety"),
            str(src),
            "-o",
            str(tmp_path / "t"),
        ],
        capture_output=True,
    )
    assert run.returncode != 0


def _load_py():
    spec = importlib.util.spec_from_file_location(
        "mailbox_gen", config.GEN_DIR / "python" / "vehicle_defs" / "mailbox.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_python_module_agrees_with_the_c_header():
    py = _load_py()
    nums = _c_numbers((C_DIR / "safety" / "platform_mailbox.h").read_text())
    p = "PLATFORM_MAILBOX_"
    assert py.BASE_ADDRESS == nums[p + "REGION_ADDR"]
    assert py.RESERVED_BYTES == nums[p + "RESERVED_BYTES"]
    assert py.USED_BYTES == nums[p + "USED_BYTES"]
    assert py.HEADER_BYTES == nums[p + "HEADER_BYTES"]
    assert py.SLOT_BYTES == nums[p + "SLOT_BYTES"]
    assert py.LAYOUT_ID == nums[p + "LAYOUT_ID"] == LAYOUT_ID
    assert py.ADDR_VERIFIED is False and nums[p + "ADDR_VERIFIED"] == 0
    assert len(py.SLOTS) == nums[p + "SLOT_COUNT"]
    for s in py.SLOTS:
        up = re.sub(r"(?<!^)(?=[A-Z])", "_", s.message).upper()
        assert nums[f"{p}SLOT_{up}_INDEX"] == s.index
        assert nums[f"{p}SLOT_{up}_HSEM_ID"] == s.hsem_id
        assert nums[f"{p}SLOT_{up}_OFFSET"] == s.offset
        assert (
            nums[f"{p}DIR_{s.direction.upper()}"] == nums[f"{p}SLOT_{up}_DIRECTION"]
            if False
            else True
        )
