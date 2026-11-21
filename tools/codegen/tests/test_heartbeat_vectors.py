"""Heartbeat golden wire vectors (T36): file vs the independent Python path vs the generated C."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from vehicle_codegen import config, heartbeat_vectors

CC = shutil.which("gcc") or shutil.which("cc")
FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-Wshadow", "-Wconversion"]
C_DIR = config.GEN_DIR / "c"
# C target that contains both heartbeats with pack + protect (the restbus sends everything).
TARGET = "hil_sim"
FN = {"HeartbeatRtCore": "heartbeat_rt_core", "HeartbeatSafety": "heartbeat_safety"}
PREFIX = {"HeartbeatRtCore": "rt_core", "HeartbeatSafety": "safety"}


def test_file_is_in_sync_with_the_independent_reference() -> None:
    expected = heartbeat_vectors.render(heartbeat_vectors.build())
    assert heartbeat_vectors.VECTORS_JSON.read_text(encoding="utf-8") == expected, (
        "run: python -m vehicle_codegen.heartbeat_vectors"
    )


def test_vector_set_covers_the_required_cases() -> None:
    vectors = heartbeat_vectors.load()
    for name, block in vectors["messages"].items():
        assert block["length"] == 8
        cases = block["cases"]
        assert len({c["bytes"] for c in cases}) == len(cases), name
        for key, wanted in (
            ("node_mode", {0, 1, 2, 3, 4, 5, 15}),
            ("error_count", {0, 255}),
            ("uptime", {0, 65535}),
            ("counter", {0, 15}),
        ):
            assert wanted <= {c[key] for c in cases}, (name, key)
    assert vectors["messages"]["HeartbeatRtCore"]["can_id"] == 0x081
    assert vectors["messages"]["HeartbeatRtCore"]["e2e_data_id"] == 0x1081
    assert vectors["messages"]["HeartbeatSafety"]["can_id"] == 0x082
    assert vectors["messages"]["HeartbeatSafety"]["e2e_data_id"] == 0x1082


def _c_source() -> str:
    """One C program: for every case pack + protect (counter forced) and print the 8 bytes."""
    vectors = heartbeat_vectors.load()
    lines = [
        "#include <stdio.h>",
        "#include <string.h>",
        '#include "platform.h"',
        '#include "platform_e2e.h"',
        "int main(void) {",
        "    uint8_t buf[8];",
        "    vehicle_e2e_tx_state_t tx;",
    ]
    for name, block in vectors["messages"].items():
        fn, pre = FN[name], PREFIX[name]
        for case in block["cases"]:
            lines += [
                "    {",
                f"        struct platform_{fn}_t m;",
                f"        (void)platform_{fn}_init(&m);",
                f"        m.{pre}_node_mode = {case['node_mode']}u;",
                f"        m.{pre}_error_count = {case['error_count']}u;",
                f"        m.{pre}_uptime = {case['uptime']}u;",
                "        (void)memset(buf, 0, sizeof buf);",
                f"        if (platform_{fn}_pack(buf, &m, sizeof buf) != 8) return 2;",
                "        vehicle_e2e_tx_init(&tx);",
                f"        tx.counter = {case['counter']}u;",
                f"        if (platform_{fn}_e2e_protect(buf, sizeof buf, &tx) != VEHICLE_E2E_OK)",
                "            return 3;",
                '        printf("%02x%02x%02x%02x%02x%02x%02x%02x\\n", buf[0], buf[1], buf[2],',
                "               buf[3], buf[4], buf[5], buf[6], buf[7]);",
                "    }",
            ]
    lines += ["    return 0;", "}"]
    return "\n".join(lines) + "\n"


@pytest.mark.skipif(CC is None, reason="no C compiler")
def test_generated_c_pack_and_protect_produce_exactly_the_vectors(tmp_path) -> None:
    src = tmp_path / "hb.c"
    src.write_text(_c_source(), encoding="utf-8")
    d = C_DIR / TARGET
    exe = tmp_path / "hb"
    subprocess.run(
        [CC, *FLAGS, "-I", str(d), str(src), str(d / "platform.c"),
         str(d / "platform_e2e.c"), str(d / "vehicle_e2e.c"), "-o", str(exe)],
        check=True,
    )  # fmt: skip
    got = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.split()
    vectors = heartbeat_vectors.load()
    expected = [c["bytes"] for b in vectors["messages"].values() for c in b["cases"]]
    assert got == expected
