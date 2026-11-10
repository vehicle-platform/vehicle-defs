"""Each vehicle DID's stale_after_ms is the same value in the C table and in vehicle_defs."""

import ctypes
import importlib
import shutil
import subprocess
import sys

import pytest

from vehicle_codegen import config
from vehicle_codegen.yaml_checks import load_yaml

CC = shutil.which("gcc") or shutil.which("cc")
C_DIR = config.GEN_DIR / "c"
PY_DIR = config.GEN_DIR / "python"

PROBE = """
#include "vehicle_cl250.h"
size_t probe_count(void) { return VEHICLE_CL250_DID_COUNT; }
uint16_t probe_did(size_t i) { return vehicle_cl250_dids[i].did; }
uint16_t probe_poll(size_t i) { return vehicle_cl250_dids[i].poll_period_ms; }
uint16_t probe_stale(size_t i) { return vehicle_cl250_dids[i].stale_after_ms; }
"""


def _vehicle_module(monkeypatch):
    monkeypatch.syspath_prepend(str(PY_DIR))
    for name in [n for n in sys.modules if n == "vehicle_defs" or n.startswith("vehicle_defs.")]:
        monkeypatch.delitem(sys.modules, name)
    return importlib.import_module("vehicle_defs.vehicle_cl250")


def test_python_has_a_stale_after_ms_for_every_did(monkeypatch):
    mod = _vehicle_module(monkeypatch)
    assert set(mod.DID_STALE_AFTER_MS) == set(mod.DIDS)
    for name, ms in mod.DID_STALE_AFTER_MS.items():
        poll_ms = mod.DIDS[name][8]
        assert isinstance(ms, int) and poll_ms < ms <= 0xFFFF, name


DIRECTORIES = sorted(p.parent.name for p in C_DIR.glob("*/vehicle_cl250.c"))


@pytest.mark.skipif(CC is None, reason="no C compiler")
@pytest.mark.parametrize("directory", DIRECTORIES)
def test_python_and_c_agree_on_stale_after_ms(directory, monkeypatch, tmp_path):
    mod = _vehicle_module(monkeypatch)
    d = C_DIR / directory
    probe = tmp_path / "probe.c"
    probe.write_text(PROBE)
    out = tmp_path / "libprobe.so"
    subprocess.run(
        [CC, "-std=c99", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", "-I", str(d),
         "-o", str(out), str(d / "vehicle_cl250.c"), str(probe)],
        check=True,
    )  # fmt: skip
    so = ctypes.CDLL(str(out))
    so.probe_count.restype = ctypes.c_size_t
    for fn in (so.probe_did, so.probe_poll, so.probe_stale):
        fn.restype, fn.argtypes = ctypes.c_uint16, [ctypes.c_size_t]
    count = so.probe_count()
    assert count == len(mod.DIDS)
    by_did = {v[0]: (name, v[8]) for name, v in mod.DIDS.items()}
    for i in range(count):
        name, poll_ms = by_did[so.probe_did(i)]
        assert so.probe_poll(i) == poll_ms, name
        assert so.probe_stale(i) == mod.DID_STALE_AFTER_MS[name], name


def test_python_has_a_verified_flag_for_every_did(monkeypatch):
    """D-104: a record-only consumer needs `verified` to recognise a stopped DID (D-068)."""
    mod = _vehicle_module(monkeypatch)
    vehicle = load_yaml(config.VEHICLE_YAML)
    assert mod.DID_VERIFIED == {d["name"]: d["verified"] for d in vehicle["dids"]}
