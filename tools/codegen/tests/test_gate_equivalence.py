"""C-6: the single-exit D-020 gate behaves exactly like the multi-exit one it replaced.

`_reference_c()` is the pre-C-6 template (defs v0.3.0, early returns), frozen here and
generated from the current `tester_policy`, with every function renamed `ref_*`. D-059
added one branch to its frame gate: the one FC.CTS, byte for byte, built here from
`transport.flow_control` independently of codegen's `vehicle_fc_frame()`. One C
program links it next to the generated `vehicle_cl250.c` and compares both on the same
inputs. The input space is covered completely wherever a function reads few enough bytes:
every byte the request and frame gates read, every DID, every response byte the decode
path reads. A mismatch is any difference in the return value, the pointer returned by
find(), or what is written to `*out` (bit for bit, NaN included).
"""

import ctypes
import os
import re
import shlex
import shutil
import subprocess

import pytest

from vehicle_codegen import config

# ISSUES C-9 (2): CI also runs the harness with clang (GATE_CC) and MemorySanitizer
# (GATE_EXTRA_CFLAGS), because GCC and cppcheck miss a forgotten assignment in the gate.
CC = os.environ.get("GATE_CC") or shutil.which("gcc") or shutil.which("cc")
pytestmark = pytest.mark.skipif(CC is None, reason="no C compiler")
FLAGS = [
    "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-Wshadow", "-Wconversion",
    *shlex.split(os.environ.get("GATE_EXTRA_CFLAGS", "")),
]  # fmt: skip
GATE_DIR = config.GEN_DIR / "c" / "rt_core"  # conn and hil_sim carry the same file


def _reference_c(vehicle) -> str:
    """The pre-C-6 gate, verbatim but for the `ref_` prefix and `static`."""
    cases = []
    forbidden_subs = config.FORBIDDEN_VEHICLE_SUBFUNCTIONS
    for entry in vehicle["tester_policy"]["allowed"]:
        sid = entry["sid"]
        cases.append(f"    case 0x{sid:02X}u: /* {entry['name']} */")
        subs = entry.get("subfunctions")
        if subs is None:
            cases.append("        return true;")
            continue
        allowed = [s for s in subs if s not in forbidden_subs.get(sid, ())]
        cond = " || ".join(f"(sub == 0x{s:02X}u)" for s in allowed) or "false"
        cases += [
            "        if (size < 2u) {",
            "            return false;",
            "        }",
            "        sub = (uint8_t)(payload[1] & 0x7Fu); /* ignore suppressPosRsp bit */",
            f"        return {cond};",
        ]
    fc = vehicle["transport"]["flow_control"]
    head = [0x30 | fc["flow_status"], fc["block_size"], fc["st_min_ms"]]
    ref_fc = head + [fc["padding_byte"]] * (8 - len(head))
    fc_c = (
        "static const uint8_t ref_fc_cts[8] = { "
        + ", ".join(f"0x{b:02X}u" for b in ref_fc)
        + " };\n"
    )
    return fc_c + _REFERENCE_HEAD + "\n".join(cases) + "\n" + _REFERENCE_TAIL


_REFERENCE_HEAD = """
static const vehicle_cl250_did_t *ref_find(uint16_t did)
{
    size_t i;

    for (i = 0u; i < VEHICLE_CL250_DID_COUNT; i++) {
        if (vehicle_cl250_dids[i].did == did) {
            return &vehicle_cl250_dids[i];
        }
    }
    return NULL;
}

static bool ref_decode(const vehicle_cl250_did_t *entry, const uint8_t *data,
                       size_t size, float *out)
{
    uint32_t raw = 0u;
    float value;
    size_t i;

    if ((entry == NULL) || (data == NULL) || (out == NULL) || (size < entry->length) ||
        (entry->length == 0u) || (entry->length > 4u) || (entry->factor_den == 0)) {
        return false;
    }
    for (i = 0u; i < entry->length; i++) {
        raw = (raw << 8u) | (uint32_t)data[i];
    }
    value = ((float)raw * (float)entry->factor_num) / (float)entry->factor_den;
    value += (float)entry->offset;
    if ((value < entry->min) || (value > entry->max)) {
        return false;
    }
    *out = value;
    return true;
}

static bool ref_request_allowed(const uint8_t *payload, size_t size)
{
    uint8_t sub;

    if ((payload == NULL) || (size == 0u)) {
        return false;
    }
    switch (payload[0]) {
"""

_REFERENCE_TAIL = """    default:
        return false; /* includes every D-020 forbidden service */
    }
}

static bool ref_frame_allowed(const uint8_t *frame, size_t size)
{
    size_t len;
    size_t i;

    if ((frame == NULL) || (size < 2u)) {
        return false;
    }
    if ((frame[0] & 0xF0u) != 0u) { /* D-059: not a Single Frame, so the FC.CTS or nothing */
        if (size != 8u) {
            return false;
        }
        for (i = 0u; i < 8u; i++) {
            if (frame[i] != ref_fc_cts[i]) {
                return false;
            }
        }
        return true;
    }
    len = (size_t)(frame[0] & 0x0Fu);
    if ((len == 0u) || (len > 7u) || ((len + 1u) > size)) {
        return false;
    }
    return ref_request_allowed(&frame[1], len);
}

static bool ref_parse_response(uint16_t expected_did, const uint8_t *frame,
                               size_t size, float *out)
{
    const vehicle_cl250_did_t *entry = ref_find(expected_did);
    size_t len;

    if ((entry == NULL) || (frame == NULL) || (out == NULL) || (size < 1u) ||
        ((frame[0] & 0xF0u) != 0u)) {
        return false;
    }
    len = (size_t)(frame[0] & 0x0Fu);
    if ((len > 7u) || ((len + 1u) > size) || (len < (3u + (size_t)entry->length))) {
        return false;
    }
    if ((frame[1] != 0x62u) || (frame[2] != (uint8_t)(expected_did >> 8u)) ||
        (frame[3] != (uint8_t)(expected_did & 0xFFu))) {
        return false;
    }
    return ref_decode(entry, &frame[4], len - 3u, out);
}
"""

# Sizes: every value below the 8-byte CAN frame and past it; SIZE_MAX for the edge.
_HARNESS = r"""
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define SENTINEL 0xA5A5A5A5u
static const size_t sizes[] = { 0u, 1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 16u, SIZE_MAX };
#define N_SIZES (sizeof(sizes) / sizeof(sizes[0]))

static unsigned long mismatches;

static uint32_t bits(float f)
{
    uint32_t u;

    (void)memcpy(&u, &f, sizeof(u));
    return u;
}

static float sentinel(void)
{
    float f;
    uint32_t u = SENTINEL;

    (void)memcpy(&f, &u, sizeof(f));
    return f;
}

/* Runs one decode call on both sides; returns the (equal) result. */
static int both_decode(const vehicle_cl250_did_t *e, const uint8_t *d, size_t n, int null_out)
{
    float a = sentinel();
    float b = sentinel();
    bool ra = vehicle_cl250_decode(e, d, n, null_out ? NULL : &a);
    bool rb = ref_decode(e, d, n, null_out ? NULL : &b);

    if ((ra != rb) || (bits(a) != bits(b))) {
        mismatches++;
    }
    return ra ? 1 : 0;
}

static int both_parse(uint16_t did, const uint8_t *f, size_t n, int null_out)
{
    float a = sentinel();
    float b = sentinel();
    bool ra = vehicle_cl250_parse_response(did, f, n, null_out ? NULL : &a);
    bool rb = ref_parse_response(did, f, n, null_out ? NULL : &b);

    if ((ra != rb) || (bits(a) != bits(b))) {
        mismatches++;
    }
    return ra ? 1 : 0;
}

int main(void)
{
    unsigned long calls = 0u;
    unsigned long hits = 0u;
    uint32_t v;
    size_t s;
    uint8_t buf[16];

    /* find(): every 16-bit DID. */
    for (v = 0u; v <= 0xFFFFu; v++) {
        if (vehicle_cl250_find((uint16_t)v) != ref_find((uint16_t)v)) {
            mismatches++;
        }
        hits += (vehicle_cl250_find((uint16_t)v) != NULL) ? 1u : 0u;
        calls++;
    }
    printf("find calls=%lu hits=%lu\n", calls, hits);

    /* request_allowed(): it reads payload[0] and payload[1]; every pair, every size.
     * The bytes it must not read get a varying pattern. */
    calls = 0u;
    hits = 0u;
    for (s = 0u; s < N_SIZES; s++) {
        if (vehicle_cl250_request_allowed(NULL, sizes[s]) != ref_request_allowed(NULL, sizes[s])) {
            mismatches++;
        }
        for (v = 0u; v <= 0xFFFFu; v++) {
            bool a;

            (void)memset(buf, (int)(v * 7u) & 0xFF, sizeof(buf));
            buf[0] = (uint8_t)(v >> 8u);
            buf[1] = (uint8_t)v;
            a = vehicle_cl250_request_allowed(buf, sizes[s]);
            if (a != ref_request_allowed(buf, sizes[s])) {
                mismatches++;
            }
            hits += a ? 1u : 0u;
            calls++;
        }
    }
    printf("request calls=%lu hits=%lu\n", calls, hits);

    /* frame_allowed(): a Single Frame reads frame[0..2]; all 2^24 values, every size.
     * The bytes after them hold the padding, so the FC.CTS is among the inputs. */
    calls = 0u;
    hits = 0u;
    (void)memset(buf, ref_fc_cts[7], sizeof(buf));
    for (s = 0u; s < N_SIZES; s++) {
        if (vehicle_cl250_frame_allowed(NULL, sizes[s]) != ref_frame_allowed(NULL, sizes[s])) {
            mismatches++;
        }
        for (v = 0u; v <= 0xFFFFFFu; v++) {
            bool a;

            buf[0] = (uint8_t)(v >> 16u);
            buf[1] = (uint8_t)(v >> 8u);
            buf[2] = (uint8_t)v;
            buf[3] = (uint8_t)(v * 13u);
            a = vehicle_cl250_frame_allowed(buf, sizes[s]);
            if (a != ref_frame_allowed(buf, sizes[s])) {
                mismatches++;
            }
            hits += a ? 1u : 0u;
            calls++;
        }
    }
    printf("frame calls=%lu hits=%lu\n", calls, hits);

    /* D-059: the FC branch reads frame[0..7]. From the allowed FC.CTS, every value of
     * every pair of byte positions (one position when p == q), every size. */
    calls = 0u;
    hits = 0u;
    for (s = 0u; s < N_SIZES; s++) {
        size_t p;
        size_t q;

        for (p = 0u; p < 8u; p++) {
            for (q = p; q < 8u; q++) {
                for (v = 0u; v <= 0xFFFFu; v++) {
                    bool a;

                    (void)memcpy(buf, ref_fc_cts, 8u);
                    (void)memset(&buf[8], ref_fc_cts[7], sizeof(buf) - 8u);
                    buf[p] = (uint8_t)(v >> 8u);
                    buf[q] = (uint8_t)v;
                    a = vehicle_cl250_frame_allowed(buf, sizes[s]);
                    if (a != ref_frame_allowed(buf, sizes[s])) {
                        mismatches++;
                    }
                    hits += a ? 1u : 0u;
                    calls++;
                }
            }
        }
    }
    printf("fc calls=%lu hits=%lu\n", calls, hits);

    /* decode(): the table entries and synthetic ones for every guard and the NaN
     * range bounds; every value of up to two data bytes, sampled beyond. */
    {
        vehicle_cl250_did_t syn[VEHICLE_CL250_DID_COUNT + 8u];
        size_t ne = 0u;
        size_t k;

        for (k = 0u; k < VEHICLE_CL250_DID_COUNT; k++) {
            syn[ne] = vehicle_cl250_dids[k];
            ne++;
        }
        syn[ne] = vehicle_cl250_dids[0]; syn[ne].length = 0u; ne++;
        syn[ne] = vehicle_cl250_dids[0]; syn[ne].length = 3u; ne++;
        syn[ne] = vehicle_cl250_dids[0]; syn[ne].length = 4u; syn[ne].max = 1.0e12f; ne++;
        syn[ne] = vehicle_cl250_dids[0]; syn[ne].length = 5u; ne++;
        syn[ne] = vehicle_cl250_dids[0]; syn[ne].factor_den = 0; ne++;
        syn[ne] = vehicle_cl250_dids[1]; syn[ne].min = NAN; ne++;
        syn[ne] = vehicle_cl250_dids[1]; syn[ne].max = NAN; ne++;
        syn[ne] = vehicle_cl250_dids[1]; syn[ne].factor_num = -3; syn[ne].min = -1000.0f; ne++;

        calls = 0u;
        hits = 0u;
        for (s = 0u; s < N_SIZES; s++) {
            size_t n = sizes[s];

            hits += (unsigned long)both_decode(NULL, buf, n, 0);
            for (k = 0u; k < ne; k++) {
                hits += (unsigned long)both_decode(&syn[k], NULL, n, 0);
                hits += (unsigned long)both_decode(&syn[k], buf, n, 1);
                for (v = 0u; v <= 0xFFFFu; v++) {
                    buf[0] = (uint8_t)(v >> 8u);
                    buf[1] = (uint8_t)v;
                    buf[2] = (uint8_t)(v * 31u);
                    buf[3] = (uint8_t)(v * 17u + 5u);
                    buf[4] = (uint8_t)(v * 3u);
                    hits += (unsigned long)both_decode(&syn[k], buf, n, 0);
                    calls++;
                }
            }
        }
        printf("decode calls=%lu hits=%lu\n", calls, hits);
    }

    /* parse_response(): every DID in the table plus unknown ones; every PCI byte;
     * SID and DID echo right and wrong; all data bytes on the path that decodes. */
    {
        uint16_t dids[VEHICLE_CL250_DID_COUNT + 3u];
        static const uint8_t sids[] = { 0x62u, 0x7Fu, 0x22u, 0x63u, 0x00u, 0xE2u };
        size_t nd = 0u;
        size_t k;
        size_t m;
        uint32_t pci;
        uint32_t echo;

        for (k = 0u; k < VEHICLE_CL250_DID_COUNT; k++) {
            dids[nd] = vehicle_cl250_dids[k].did;
            nd++;
        }
        dids[nd] = 0x0000u; nd++;
        dids[nd] = 0xFFFFu; nd++;
        dids[nd] = (uint16_t)(vehicle_cl250_dids[0].did ^ 0x0001u); nd++;

        calls = 0u;
        hits = 0u;
        for (k = 0u; k < nd; k++) {
            uint16_t did = dids[k];

            for (s = 0u; s < N_SIZES; s++) {
                size_t n = sizes[s];

                hits += (unsigned long)both_parse(did, NULL, n, 0);
                for (pci = 0u; pci <= 0xFFu; pci++) {
                    for (m = 0u; m < sizeof(sids); m++) {
                        for (echo = 0u; echo < 4u; echo++) {
                            uint8_t hi = (uint8_t)(did >> 8u);
                            uint8_t lo = (uint8_t)did;
                            int full = (pci <= 7u) && (m == 0u) && (echo == 0u);

                            (void)memset(buf, 0xAA, sizeof(buf));
                            buf[0] = (uint8_t)pci;
                            buf[1] = sids[m];
                            buf[2] = (echo == 1u) ? (uint8_t)(hi ^ 0x80u) : hi;
                            buf[3] = (echo == 2u) ? (uint8_t)(lo ^ 0x01u) : lo;
                            if (echo == 3u) {
                                buf[2] = lo;
                                buf[3] = hi;
                            }
                            hits += (unsigned long)both_parse(did, buf, n, 1);
                            for (v = 0u; v <= (full ? 0xFFFFu : 3u); v++) {
                                buf[4] = (uint8_t)(v >> 8u);
                                buf[5] = (uint8_t)v;
                                buf[6] = (uint8_t)(v * 7u);
                                hits += (unsigned long)both_parse(did, buf, n, 0);
                                calls++;
                            }
                        }
                    }
                }
            }
        }
        printf("parse calls=%lu hits=%lu\n", calls, hits);
    }

    printf("mismatches=%lu\n", mismatches);
    return (mismatches == 0u) ? 0 : 1;
}
"""


@pytest.mark.parametrize("opt", ["-O0", "-O2"])
def test_single_exit_gate_equals_previous_gate(vehicle, tmp_path, opt):
    src = tmp_path / "equivalence.c"
    src.write_text('#include "vehicle_cl250.h"\n' + _reference_c(vehicle) + _HARNESS)
    exe = tmp_path / "equivalence"
    subprocess.run(
        [CC, *FLAGS, opt, "-I", str(GATE_DIR), str(src), str(GATE_DIR / "vehicle_cl250.c"),
         "-o", str(exe)],
        check=True,
    )  # fmt: skip
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=600)
    report = dict(
        (line.split()[0], dict(kv.split("=") for kv in line.split()[1:]))
        for line in run.stdout.splitlines()
        if " calls=" in line
    )
    assert run.returncode == 0, run.stdout
    assert run.stdout.splitlines()[-1] == "mismatches=0"
    # Not vacuous: each function accepted something and rejected something.
    assert int(report["find"]["hits"]) == len(vehicle["dids"])
    assert int(report["request"]["calls"]) == 12 * 0x10000
    assert int(report["frame"]["calls"]) == 12 * 0x1000000
    assert int(report["fc"]["calls"]) == 12 * 36 * 0x10000
    for name, counts in report.items():
        assert 0 < int(counts["hits"]) < int(counts["calls"]), (name, counts)


def test_generated_gate_files_are_identical():
    """conn (the temporary tester), rt_core and hil_sim link the same gate."""
    texts = {(config.GEN_DIR / "c" / d / "vehicle_cl250.c").read_text() for d in
             ("conn", "rt_core", "hil_sim")}  # fmt: skip
    assert len(texts) == 1


def test_gate_functions_have_a_single_exit():
    """MISRA 15.5 and 16.3 by construction: one `return`, as the last statement.

    cppcheck checks 15.5 on this file, but it does not report 16.1/16.3 for a
    switch-clause that ends in `return`, so the structure is pinned here as well."""
    text = (GATE_DIR / "vehicle_cl250.c").read_text()
    bodies = re.findall(r"^(\S[^;{]*?\))\n\{\n(.*?)^\}$", text, re.MULTILINE | re.DOTALL)
    names = [re.search(r"(\w+)\(", sig)[1] for sig, _ in bodies]
    assert names == [
        "vehicle_cl250_find",
        "vehicle_cl250_decode",
        "vehicle_cl250_request_allowed",
        "vehicle_cl250_frame_allowed",
        "vehicle_cl250_parse_response",
    ]
    for name, (_, body) in zip(names, bodies, strict=True):
        assert len(re.findall(r"\breturn\b", body)) == 1, name
        if name != "vehicle_cl250_find":  # fail-closed: a path that forgets `ok` refuses
            assert "\n    bool ok = false; /* fail-closed default */\n" in f"\n{body}", name
        assert re.search(r"\n    return \w+;\n$", body), name
    switch = text.split("switch (payload[0]) {")[1].split("\n        }\n")[0]
    clauses = re.split(r"\n        (?:case 0x[0-9A-F]{2}u|default):", switch)[1:]
    assert clauses and all(c.rstrip().endswith("break;") for c in clauses)


def test_policy_with_no_allowed_subfunction_builds_and_refuses(vehicle, tmp_path):
    """A narrowed policy may keep a service with `subfunctions: []`: it must still build
    warning-free (no unused `sub`) and refuse that service for every sub-function."""
    from vehicle_codegen import gen_c
    from vehicle_codegen.yaml_checks import request_allowed

    policy = vehicle["tester_policy"]
    # 0x19 (sub-functions since E-23) stays: the D-080 dtc_snapshot and the D-059 scan
    # requests must pass the policy, so codegen refuses an empty 0x19 list.
    narrowed = [e for e in policy["allowed"] if e.get("subfunctions") and e["sid"] != 0x19]
    assert narrowed, "the policy has no service with sub-functions"
    for entry in narrowed:
        entry["subfunctions"] = []
    files = gen_c.generate_vehicle_c(vehicle)
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    so = tmp_path / "libgate.so"
    subprocess.run(
        [CC, *FLAGS, "-shared", "-fPIC", "-o", str(so), str(tmp_path / "vehicle_cl250.c")],
        check=True,
    )
    lib = ctypes.CDLL(str(so))
    lib.vehicle_cl250_request_allowed.restype = ctypes.c_bool
    lib.vehicle_cl250_request_allowed.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    for entry in narrowed:
        for sub in range(256):
            assert not lib.vehicle_cl250_request_allowed(bytes([entry["sid"], sub]), 2)
    for sid in range(256):
        for sub in range(256):
            payload = bytes([sid, sub])
            assert lib.vehicle_cl250_request_allowed(payload, 2) == request_allowed(policy, payload)
