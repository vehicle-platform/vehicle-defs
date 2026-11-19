"""C-7: the generated cantools C (pack/unpack/init/decode) at runtime, against cantools Python.

Each node's `platform.c` is built as a shared library and driven through ctypes. The
structs are read from the node's `platform.h`, so the test follows the DBC without
naming a message or signal. `_MISRA_FIXUPS` is checked on a synthetic DBC that makes
cantools emit every pattern a fixup rewrites.
"""

import ctypes
import math
import random
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest
from cantools.database.can import Message, Signal
from cantools.database.can.c_source import camel_to_snake_case, generate
from conftest import parse_dbc
from test_c_code import RxState, TxState

from vehicle_codegen import config, gen_c

CC = shutil.which("gcc") or shutil.which("cc")
pytestmark = pytest.mark.skipif(CC is None, reason="no C compiler")
FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-Wshadow", "-Wconversion"]
C_DIR = config.GEN_DIR / "c"
RANDOM_PAYLOADS = 10_000

_CTYPES = {
    f"{s}int{w}_t": getattr(ctypes, f"c_{s}int{w}") for s in ("", "u") for w in (8, 16, 32, 64)
}
_STRUCT_RE = re.compile(r"^struct (\w+)_t \{$(.*?)^\};$", re.MULTILINE | re.DOTALL)
_MEMBER_RE = re.compile(r"^    (u?int(?:8|16|32|64)_t) (\w+);$", re.MULTILINE)


@dataclass
class CMessage:
    msg: Message
    struct: Any  # ctypes.Structure subclass built from the header
    signals: dict[str, Signal]  # struct member -> DBC signal
    init: Any
    pack: Any | None
    unpack: Any | None
    decode: dict[str, Any]  # struct member -> <msg>_<member>_decode()
    encode: dict[str, Any]  # struct member -> <msg>_<member>_encode()
    in_range: dict[str, Any]  # struct member -> <msg>_<member>_is_in_range()
    pack_checked: Any | None = None  # <msg>_pack_checked(): every sent message (E-6)
    unpack_checked: Any | None = None  # <msg>_unpack_checked(): every received message (E-5)
    encode_checked: dict[str, Any] = field(default_factory=dict)  # <msg>_<member>_encode_checked
    is_defined: dict[str, Any] = field(default_factory=dict)  # enum member -> *_is_defined()


def _build(sources: list, out, flags=FLAGS):
    subprocess.run([CC, *flags, "-shared", "-fPIC", "-o", str(out), *map(str, sources)], check=True)
    return ctypes.CDLL(str(out))


def load_api(so, header: str, prefix: str, db) -> dict[str, CMessage]:
    by_snake = {camel_to_snake_case(m.name): m for m in db.messages}
    api = {}
    for found in _STRUCT_RE.finditer(header):
        name = found[1].removeprefix(f"{prefix}_")
        msg = by_snake[name]
        fields = [(m[2], _CTYPES[m[1]]) for m in _MEMBER_RE.finditer(found[2])]
        signals = {camel_to_snake_case(s.name): s for s in msg.signals}
        assert {f for f, _ in fields} == set(signals), name
        struct = type(name, (ctypes.Structure,), {"_fields_": fields})
        fn = f"{prefix}_{name}"

        def bind(symbol, restype, argtypes):
            if not re.search(rf"^\w+ {symbol}\(", header, re.MULTILINE):
                return None
            f = getattr(so, symbol)
            f.restype, f.argtypes = restype, argtypes
            return f

        ptr = ctypes.POINTER(struct)
        api[name] = CMessage(
            msg=msg,
            struct=struct,
            signals=signals,
            init=bind(f"{fn}_init", ctypes.c_int, [ptr]),
            pack=bind(f"{fn}_pack", ctypes.c_int, [ctypes.c_char_p, ptr, ctypes.c_size_t]),
            unpack=bind(f"{fn}_unpack", ctypes.c_int, [ptr, ctypes.c_char_p, ctypes.c_size_t]),
            decode={
                member: f
                for member, ctype in fields
                if (f := bind(f"{fn}_{member}_decode", ctypes.c_float, [ctype])) is not None
            },
            encode={
                member: f
                for member, ctype in fields
                if (f := bind(f"{fn}_{member}_encode", ctype, [ctypes.c_float])) is not None
            },
            in_range={
                member: f
                for member, ctype in fields
                if (f := bind(f"{fn}_{member}_is_in_range", ctypes.c_bool, [ctype])) is not None
            },
            pack_checked=bind(
                f"{fn}_pack_checked", ctypes.c_int, [ctypes.c_char_p, ptr, ctypes.c_size_t]
            ),
            unpack_checked=bind(
                f"{fn}_unpack_checked", ctypes.c_int, [ptr, ctypes.c_char_p, ctypes.c_size_t]
            ),
            encode_checked={
                member: f
                for member, ctype in fields
                if (
                    f := bind(
                        f"{fn}_{member}_encode_checked",
                        ctypes.c_int,
                        [ctypes.c_float, ctypes.POINTER(ctype)],
                    )
                )
                is not None
            },
            is_defined={
                member: f
                for member, ctype in fields
                if (f := bind(f"{fn}_{member}_is_defined", ctypes.c_bool, [ctype])) is not None
            },
        )
    return api


def _raw_range(sig: Signal) -> tuple[int, int]:
    if sig.is_signed:
        return -(1 << (sig.length - 1)), (1 << (sig.length - 1)) - 1
    return 0, (1 << sig.length) - 1


def _boundaries(sig: Signal) -> list[int]:
    lo, hi = _raw_range(sig)
    values = {lo, lo + 1, hi - 1, hi, 0, min(1, hi)}
    for limit in (sig.minimum, sig.maximum):
        if limit is not None:
            raw = round(sig.conversion.scaled_to_raw(limit))
            values |= {raw - 1, raw, raw + 1}
    return sorted(v for v in values if lo <= v <= hi)


def _c_unpack(cm: CMessage, data: bytes, extra: int = 0) -> dict[str, int]:
    """`extra` trailing bytes: a frame longer than the DBC length must decode the same."""
    s = cm.struct()
    assert cm.unpack(ctypes.byref(s), data + b"\x5a" * extra, len(data) + extra) == 0
    return {member: getattr(s, member) for member in cm.signals}


def _c_pack(cm: CMessage, raw: dict[str, int]) -> bytes:
    s = cm.struct(**raw)
    buf = ctypes.create_string_buffer(b"\xa5" * 16, 16)
    assert cm.pack(buf, ctypes.byref(s), 16) == cm.msg.length
    assert buf.raw[cm.msg.length :] == b"\xa5" * (16 - cm.msg.length)  # writes `length` bytes only
    return buf.raw[: cm.msg.length]


def _py_raw(cm: CMessage, data: bytes) -> dict[str, int]:
    decoded = cm.msg.decode(data, decode_choices=False, scaling=False)
    return {member: decoded[sig.name] for member, sig in cm.signals.items()}


def _py_pack(cm: CMessage, raw: dict[str, int]) -> bytes:
    by_name = {sig.name: raw[member] for member, sig in cm.signals.items()}
    return bytes(cm.msg.encode(by_name, scaling=False, padding=False, strict=False))


def check_round_trip(
    cm: CMessage, rng: random.Random, payloads: int, encode_rounds: bool = True
) -> None:
    """unpack == cantools decode, pack == cantools encode, both ways, and the guards.
    encode_rounds=False: raw cantools output, whose encode() still truncates."""
    n = cm.msg.length
    datas = [bytes(rng.randrange(256) for _ in range(n)) for _ in range(payloads)]
    datas += [b"\x00" * n, b"\xff" * n]
    raws = [_py_raw(cm, d) for d in datas]
    for member, sig in cm.signals.items():  # one signal at a boundary, the others 0 or all ones
        for base in (0x00, 0xFF):
            for value in _boundaries(sig):
                raw = _py_raw(cm, bytes([base]) * n)
                raw[member] = value
                raws.append(raw)
                datas.append(_py_pack(cm, raw))
    for data, raw in zip(datas, raws, strict=True):
        if cm.unpack is not None:
            extra = rng.choice((0, 1, 8 - n, 56))
            assert _c_unpack(cm, data, extra) == raw, (cm.msg.name, data.hex(), extra)
        if cm.pack is not None:
            packed = _c_pack(cm, raw)
            assert packed == _py_pack(cm, raw), (cm.msg.name, raw)
            assert _py_raw(cm, packed) == raw, (cm.msg.name, raw)
    for member, fn in cm.decode.items():
        sig = cm.signals[member]
        for value in {r[member] for r in raws}:
            expected = sig.conversion.raw_to_scaled(value, decode_choices=False)
            assert fn(value) == pytest.approx(expected, rel=1e-6, abs=1e-6), (sig.name, value)
    for member in cm.signals:
        check_signal_helpers(cm, member, encode_rounds)
    if cm.pack is not None:
        check_pack_masks_each_member(cm)
    check_guards(cm)


def _truncate(sig: Signal, value: int) -> int:
    """`value` cut to the signal's width, as the DBC layout stores it."""
    value &= (1 << sig.length) - 1
    if sig.is_signed and value >> (sig.length - 1):
        value -= 1 << sig.length
    return value


def check_pack_masks_each_member(cm: CMessage) -> None:
    """A member with bits set beyond its signal width must not leak into its neighbours
    (the E2E CRC and counter share bytes with other signals)."""
    zero = dict.fromkeys(cm.signals, 0)
    for member, sig in cm.signals.items():
        width = 8 * ctypes.sizeof(dict(cm.struct._fields_)[member])
        all_ones = -1 if sig.is_signed else (1 << width) - 1
        packed = _c_pack(cm, {**zero, member: all_ones})
        assert _py_raw(cm, packed) == {**zero, member: _truncate(sig, all_ones)}, (sig.name,)


def check_signal_helpers(cm: CMessage, member: str, encode_rounds: bool = True) -> None:
    """is_in_range() at the raw limits and one step outside; encode() back to raw."""
    sig = cm.signals[member]
    lo, hi = _raw_range(sig)
    in_range, encode, decode = cm.in_range.get(member), cm.encode.get(member), cm.decode.get(member)
    if in_range is not None:
        raw_min = lo if sig.minimum is None else round(sig.conversion.scaled_to_raw(sig.minimum))
        raw_max = hi if sig.maximum is None else round(sig.conversion.scaled_to_raw(sig.maximum))
        for raw, expected in ((raw_min - 1, False), (raw_min, True), (raw_max, True),
                              (raw_max + 1, False)):  # fmt: skip
            if lo <= raw <= hi:
                assert in_range(raw) is expected, (sig.name, raw)
    if encode is not None and encode_rounds:
        check_encode_rounds(sig, encode, decode)
        check_encode_saturates(cm, member, encode)


def _encode_raws(sig: Signal) -> list[int]:
    """Raw values whose physical value encode() must map back exactly: the boundaries plus
    a sweep, within the physical range (outside it, the caller checks is_in_phys_range())
    and within 2^24 (float holds every integer up to there; past it the float-to-int
    conversion can overflow, undefined in C; no platform signal is wider than 16 bits)."""
    lo, hi = _raw_range(sig)
    if sig.minimum is not None and sig.maximum is not None and sig.maximum > sig.minimum:
        lo = max(lo, round(sig.conversion.scaled_to_raw(sig.minimum)))
        hi = min(hi, round(sig.conversion.scaled_to_raw(sig.maximum)))
    lo, hi = max(lo, -(1 << 24)), min(hi, 1 << 24)
    # Every raw value up to 16 bits (BATTERY_VOLTAGE lost a step on 38863 of 65536).
    sweep = range(lo, hi + 1, 1 if hi - lo <= 1 << 16 else (hi - lo) // 4096)
    return sorted({*sweep, *(r for r in _boundaries(sig) if lo <= r <= hi)})


def check_encode_rounds(sig: Signal, encode, decode) -> None:
    """D-056: encode() rounds (value - offset) / scale to the nearest raw value like the
    cantools Python reference, so decode() -> encode() is exact and a value up to 0.45
    raw steps off still maps to its raw value (the float quotient of 0.010 V by 0.001
    used to truncate to 9). Ties are not tested: C rounds halves away from zero, Python
    to even."""
    for raw in _encode_raws(sig):
        # Off-step values only up to 2^18, where float still resolves 1/32 of a raw step.
        for frac in (0.0, -0.45, 0.45) if abs(raw) <= 1 << 18 else (0.0,):
            value = sig.conversion.raw_to_scaled(raw + frac, decode_choices=False)
            assert round(sig.conversion.scaled_to_raw(value)) == raw  # the Python reference
            assert encode(value) == raw, (sig.name, raw, frac)
        if decode is not None:
            assert encode(decode(raw)) == raw, (sig.name, raw)


def check_encode_saturates(cm: CMessage, member: str, encode) -> None:
    """D-056 (safety review MAJOR-2): outside the C type's range encode() returns the type
    limit, never a wrapped value (a float-to-int conversion out of range is undefined in C;
    + 0.5 had made [max + 0.5, max + 1) such a case: AGE 2556 ms could read 0 = fresh),
    and NaN returns 0."""
    sig = cm.signals[member]
    ctype = dict(cm.struct._fields_)[member]
    bits = 8 * ctypes.sizeof(ctype)
    signed = ctype(-1).value < 0
    t_min, t_max = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    if bits > 24:  # float cannot hold the 32/64-bit limits: the nearest float toward zero
        t_max = gen_c._f32_toward_zero(t_max)
    probes = [(t_max * 2.0 + 10.0, t_max), (t_min * 2.0 - 10.0, t_min), (1e30, t_max),
              (-1e30, t_min)]  # fmt: skip
    if bits <= 16:  # half a step past the limit, where float still resolves it
        probes += [(t_max + 0.4, t_max), (t_max + 0.6, t_max), (t_min - 0.4, t_min),
                   (t_min - 0.6, t_min)]  # fmt: skip
    for raw, expected in probes:
        value = sig.conversion.raw_to_scaled(raw, decode_choices=False)
        assert encode(value) == expected, (sig.name, raw)
    signs = (1.0, -1.0) if sig.scale > 0 else (-1.0, 1.0)
    assert encode(signs[0] * float("inf")) == t_max, sig.name
    assert encode(signs[1] * float("inf")) == t_min, sig.name
    assert encode(float("nan")) == 0, sig.name


def check_guards(cm: CMessage) -> None:
    n = cm.msg.length
    assert cm.init(None) < 0
    s = cm.struct()
    ctypes.memset(ctypes.byref(s), 0xFF, ctypes.sizeof(s))
    assert cm.init(ctypes.byref(s)) == 0
    assert bytes(s) == bytes(ctypes.sizeof(s))
    if cm.unpack is not None:
        for size in range(n):  # too short: rejected, destination untouched
            ctypes.memset(ctypes.byref(s), 0x5A, ctypes.sizeof(s))
            assert cm.unpack(ctypes.byref(s), b"\xff" * n, size) < 0
            assert bytes(s) == b"\x5a" * ctypes.sizeof(s)
    if cm.pack is not None:
        for size in range(n):
            buf = ctypes.create_string_buffer(b"\xa5" * n, n)
            assert cm.pack(buf, ctypes.byref(cm.struct()), size) < 0
            assert buf.raw == b"\xa5" * n


def _defined(sig: Signal) -> set[int]:
    return {int(v) for v, name in (sig.choices or {}).items() if str(name) != "RESERVED"}


SENTINELS = (b"\xa5" * 16, b"\x5a" * 16)


def _checked_pack(
    cm: CMessage, raw: dict[str, int], size: int = 16, fill: bytes = SENTINELS[0]
) -> tuple[int, bytes]:
    buf = ctypes.create_string_buffer(fill, 16)
    return cm.pack_checked(buf, ctypes.byref(cm.struct(**raw)), size), buf.raw


def _untouched(cm: CMessage, raw: dict[str, int], size: int = 16) -> bool:
    """Negative return and the buffer unchanged, with two different sentinel fills."""
    for fill in SENTINELS:
        rc, buf = _checked_pack(cm, raw, size, fill)
        if rc >= 0 or buf != fill:
            return False
    return True


def _c_range(ctype: Any) -> range:
    """Every value of the member's C type (the struct member is wider than the bit field)."""
    bits = 8 * ctypes.sizeof(ctype)
    signed = ctype(-1).value < 0
    return range(-(1 << (bits - 1)), 1 << (bits - 1)) if signed else range(1 << bits)


def check_pack_checked(cm: CMessage, rng: random.Random) -> None:
    enums = {m: s for m, s in cm.signals.items() if s.choices}
    assert set(cm.is_defined) == set(enums)
    ctypes_of = dict(cm.struct._fields_)
    for member, sig in enums.items():  # is_defined() is the value table minus RESERVED
        for v in _c_range(ctypes_of[member]):  # the whole C type, not just the bit field
            assert bool(cm.is_defined[member](v)) == (v in _defined(sig)), (cm.msg.name, member, v)
    base = {
        m: min(_defined(s)) if m in enums else next(v for v in _boundaries(s) if cm.in_range[m](v))
        for m, s in cm.signals.items()
    }
    plain = _c_pack(cm, base)
    assert _checked_pack(cm, base) == (cm.msg.length, plain + b"\xa5" * (16 - cm.msg.length))
    for _ in range(200):  # in-range values: identical to the plain pack
        raw = {}
        for m, sig in cm.signals.items():
            lo, hi = _raw_range(sig)
            raw[m] = rng.choice(sorted(_defined(sig))) if m in enums else rng.randint(lo, hi)
            if m not in enums and not cm.in_range[m](raw[m]):
                raw[m] = base[m]
        rc, buf = _checked_pack(cm, raw)
        assert rc == cm.msg.length and buf[: cm.msg.length] == _c_pack(cm, raw)
    refused_by_defined_only = 0
    for member, sig in cm.signals.items():  # one bad member: error, buffer untouched
        full = _c_range(ctypes_of[member])  # e.g. a 1-bit VALID at 2 and 3 (3 would mask to 1)
        lo, hi = _raw_range(sig)
        values = list(full) if len(full) <= 256 else [lo - 1, lo, hi, hi + 1, full[0], full[-1]]
        for v in values:
            if v not in full:
                continue
            in_rng = bool(cm.in_range[member](v))
            ok = in_rng and (member not in enums or v in _defined(sig))
            if ok:
                assert _checked_pack(cm, {**base, member: v})[0] == cm.msg.length, (member, v)
            else:
                assert _untouched(cm, {**base, member: v}), (cm.msg.name, member, v)
                refused_by_defined_only += in_rng
    cm_refused_by_defined_only[cm.msg.name] = refused_by_defined_only
    for size in range(cm.msg.length):  # too small: error, untouched
        assert _untouched(cm, base, size)
    for fill in SENTINELS:
        buf = ctypes.create_string_buffer(fill, 16)
        assert cm.pack_checked(None, ctypes.byref(cm.struct(**base)), 16) < 0
        assert cm.pack_checked(buf, None, 16) < 0
        assert buf.raw == fill


def check_encode_checked(cm: CMessage) -> None:
    """E-7: NaN, +-Inf and out-of-range floats are refused with *raw_p unchanged."""
    expected = {m for m in cm.signals if not cm.signals[m].name.startswith("E2E_")}
    assert set(cm.encode_checked) == expected, cm.msg.name
    nan, inf = float("nan"), float("inf")
    for member, fn in cm.encode_checked.items():
        sig = cm.signals[member]
        ctype = cm.encode_checked[member].argtypes[1]._type_
        out = ctype(77)
        lo, hi = sig.minimum, sig.maximum
        bad = [nan, inf, -inf]
        if hi is not None:
            bad.append(hi + max(1.0, abs(hi)))
        if lo is not None:
            bad.append(lo - max(1.0, abs(lo)))
        for value in bad:
            out.value = 77
            assert fn(ctypes.c_float(value), ctypes.byref(out)) < 0, (cm.msg.name, member, value)
            assert out.value == 77
        assert fn(ctypes.c_float(0.0), None) < 0
        for limit, beyond in ((lo, -math.inf), (hi, math.inf)):  # one float32 ulp past a limit
            if limit is None:
                continue
            f32 = struct.unpack("<f", struct.pack("<f", limit))[0]
            bits = struct.unpack("<i", struct.pack("<f", f32))[0]
            step = (1 if (f32 > 0) == (beyond > 0) else -1) if f32 != 0 else 1
            if f32 == 0:
                nxt = struct.unpack("<f", struct.pack("<i", 1))[0] * (1 if beyond > 0 else -1)
            else:
                nxt = struct.unpack("<f", struct.pack("<i", bits + step))[0]
            if (nxt > f32) != (beyond > 0):  # wrong direction: flip
                nxt = struct.unpack("<f", struct.pack("<i", bits - step))[0]
            out.value = 77
            assert fn(ctypes.c_float(nxt), ctypes.byref(out)) < 0, (cm.msg.name, member, nxt)
            assert out.value == 77
        for value in (lo, hi):  # the DBC limits themselves are accepted and match the encode
            if value is None:
                continue
            assert fn(ctypes.c_float(value), ctypes.byref(out)) == 0, (cm.msg.name, member, value)
            assert out.value == cm.encode[member](ctypes.c_float(value)), (cm.msg.name, member)


def check_unpack_checked(cm: CMessage, rng: random.Random) -> None:
    """E-5 at the codec level: exactly the DBC length, every signal in range, dst untouched."""
    length = cm.msg.length
    frame = next(  # a frame whose signals are all in range (a receiver has no plain pack)
        d
        for d in (bytes(rng.randrange(256) for _ in range(length)) for _ in range(5000))
        if all(cm.in_range[m](v) for m, v in _c_unpack(cm, d).items())
    )
    good = cm.struct()
    assert cm.unpack_checked(ctypes.byref(good), frame, length) == 0
    assert {m: getattr(good, m) for m in cm.signals} == _c_unpack(cm, frame)
    sentinel = cm.struct(**{m: 1 for m in cm.signals})
    before = bytes(sentinel)
    for size in sorted({0, 1, length - 1, length + 1, 12, 64} - {length}):
        assert cm.unpack_checked(ctypes.byref(sentinel), frame + b"\x00" * 64, size) < 0
        assert bytes(sentinel) == before  # wrong length: nothing written
    assert cm.unpack_checked(None, frame, length) < 0
    assert cm.unpack_checked(ctypes.byref(sentinel), None, length) < 0
    for _ in range(300):  # random frames: accepted exactly when every signal is in range
        data = bytes(rng.randrange(256) for _ in range(length))
        raw = _c_unpack(cm, data)
        ok = all(cm.in_range[m](v) for m, v in raw.items())
        dst = cm.struct(**{m: 1 for m in cm.signals})
        rc = cm.unpack_checked(ctypes.byref(dst), data, length)
        assert (rc == 0) == ok, (cm.msg.name, raw)
        if not ok:
            assert bytes(dst) == before
        if ok:
            assert {m: getattr(dst, m) for m in cm.signals} == raw


# message -> number of (member, value) pairs that is_in_range() accepts but is_defined() refuses
cm_refused_by_defined_only: dict[str, int] = {}


@pytest.mark.parametrize("target", config.C_TARGETS, ids=lambda t: t.directory)
def test_node_cantools_code_matches_cantools_python(target, platform_db, tmp_path):
    d = C_DIR / target.directory
    so = _build([d / "platform.c"], tmp_path / "libplatform.so")
    api = load_api(so, (d / "platform.h").read_text(), "platform", platform_db)
    # The node gets pack for what it sends and unpack for what it receives, nothing else.
    by_name = {cm.msg.name: cm for cm in api.values()}
    sends = {m.name for m in platform_db.messages if gen_c._sends(target, m)}
    receives = {m.name for m in platform_db.messages if gen_c._receives(target, m)}
    assert {n for n, cm in by_name.items() if cm.pack} == sends
    assert {n for n, cm in by_name.items() if cm.unpack} == receives
    assert set(by_name) == sends | receives
    rng = random.Random(f"c7-{target.directory}")
    for cm in api.values():
        check_round_trip(cm, rng, RANDOM_PAYLOADS)
    # pack_checked() exists for exactly the sent messages (E-6, every one, enum or not),
    # unpack_checked() for exactly the received ones; the plain functions are untouched
    # (check_round_trip above).
    assert {n for n, cm in by_name.items() if cm.pack_checked} == sends
    assert {n for n, cm in by_name.items() if cm.unpack_checked} == receives
    for name in sorted(sends):
        check_pack_checked(by_name[name], rng)
        check_encode_checked(by_name[name])
    for name in sorted(receives):
        check_unpack_checked(by_name[name], rng)
    if target.directory == "hil_sim":  # is_defined (not is_in_range) is what refuses these
        assert cm_refused_by_defined_only["HeartbeatSafety"] > 0  # NODE_MODE [0|15] vs 0..5
        assert cm_refused_by_defined_only["EkfLean"] > 0  # LEAN_ANGLE_STATE RESERVED = 2
        assert cm_refused_by_defined_only["SafetyRequest"] > 0  # RESERVED lock requests


# Every pattern _MISRA_FIXUPS rewrites: memset (pack), the one-line NULL guard (init),
# and the unpack shift helpers at 16, 32 and 64 bits, little- and big-endian, signed.
SYNTHETIC_DBC = """VERSION ""

NS_ :

BS_:

BU_: TX RX

BO_ 256 Mixed: 8 TX
 SG_ U4 : 0|4@1+ (1,0) [0|15] "" RX
 SG_ S12 : 4|12@1- (0.5,-3) [-1027|1020.5] "" RX
 SG_ U16 : 16|16@1+ (1,0) [0|65535] "" RX
 SG_ S32 : 32|32@1- (1,0) [0|0] "" RX

BO_ 257 Wide: 8 TX
 SG_ U64 : 0|64@1+ (1,0) [0|0] "" RX

BO_ 258 Motorola: 8 TX
 SG_ M13 : 7|13@0+ (1,0) [0|8191] "" RX
 SG_ MS7 : 30|7@0- (1,0) [-64|63] "" RX
 SG_ M20 : 34|20@0+ (0.25,100) [100|262243.75] "" RX
"""


def test_misra_fixups_rewrite_every_pattern_and_keep_behaviour(tmp_path):
    db = parse_dbc(SYNTHETIC_DBC)
    header, source, _, _ = generate(
        db, "synth", "synth.h", "synth.c", "synth_fuzzer.c",
        floating_point_numbers=True, use_float=True,
    )  # fmt: skip
    memset, guard, widen = (p for p, _ in gen_c._MISRA_FIXUPS)
    # cantools still emits each pattern (a silent format change would make a fixup dead) ...
    assert len(memset.findall(source)) == 2 * len(db.messages)  # *_pack() and *_init()
    assert len(guard.findall(source)) == len(db.messages)  # only the *_init() NULL guards
    assert {m[1] for m in widen.finditer(source)} == {"uint16_t", "uint32_t", "uint64_t"}
    # ... and none survives the rewrite.
    fixed = gen_c._misra_fixups(source)
    for pattern, _ in gen_c._MISRA_FIXUPS:
        assert not pattern.search(fixed), pattern.pattern
    fixed = gen_c._encode_rounding(fixed, header)  # the full generate_platform_c() pipeline
    assert fixed.count("(void)memset(") == 2 * len(db.messages)
    # Same behaviour: original and rewritten source both match cantools Python.
    for kind, text in (("orig", source), ("fixed", fixed)):
        d = tmp_path / kind
        d.mkdir()
        (d / "synth.h").write_text(header)
        (d / "synth.c").write_text(text)
        flags = FLAGS if kind == "fixed" else [f for f in FLAGS if f != "-Werror"]
        so = _build([d / "synth.c"], d / "libsynth.so", flags)
        api = load_api(so, header, "synth", db)
        assert len(api) == len(db.messages)
        rng = random.Random("c7-synthetic")
        for cm in api.values():
            check_round_trip(cm, rng, 2000, encode_rounds=kind == "fixed")


def test_encode_rounding_rewrites_every_encode_and_refuses_an_unknown_body():
    """D-056: every <msg>_<signal>_encode() of the synthetic DBC (unsigned, signed, scale
    and offset, 4 to 64 bits) is rewritten; a body cantools might emit in a later version
    stops the generation instead of shipping a truncating encode()."""
    db = parse_dbc(SYNTHETIC_DBC)
    header, source, _, _ = generate(
        db, "synth", "synth.h", "synth.c", "synth_fuzzer.c",
        floating_point_numbers=True, use_float=True,
    )  # fmt: skip
    signals = sum(len(m.signals) for m in db.messages)
    assert len(gen_c._ENCODE_RE.findall(source)) == signals
    rounded = gen_c._encode_rounding(source, header)
    assert not gen_c._ENCODE_RE.search(rounded)
    assert rounded.count("const float raw = ") == signals
    assert ": (raw - 0.5f);" in rounded  # signed
    assert "? 4294967040.0f :" in rounded  # S32/U64 limits: the nearest float below
    body = "_encode(float value)\n{\n    return"
    changed = source.replace(body, body.replace("    return", "  return"), 1)
    with pytest.raises(ValueError, match="encode rounding"):
        gen_c._encode_rounding(changed, header)


def _safety_messages(directory: str, tmp_path, platform_db) -> dict[str, CMessage]:
    d = C_DIR / directory
    so = _build([d / "platform.c"], tmp_path / "libplatform.so")
    api = load_api(so, (d / "platform.h").read_text(), "platform", platform_db)
    return {cm.msg.name: cm for cm in api.values()}


def _packed(cm: CMessage, **raw: int) -> tuple[int, bytes]:
    full = {m: 0 for m in cm.signals} | {k.lower(): v for k, v in raw.items()}
    return _checked_pack(cm, full)


def test_safety_warning_status_checked_pack(platform_db, tmp_path):
    """0x023 (SAFETY sender): raw 0 is no information and packs; undefined values do not."""
    cm = _safety_messages("safety", tmp_path, platform_db)["SafetyWarningStatus"]
    assert cm.msg.frame_id == 0x023
    plain_zero = _c_pack(cm, dict.fromkeys(cm.signals, 0))
    rc, buf = _packed(cm)  # every field 0 = no information
    assert rc == cm.msg.length and buf[:8] == plain_zero
    for level in (1, 2, 3):
        assert _packed(cm, cornering_level=level)[0] == 8
    for member, last in (
        ("bsm_left", 3),
        ("bsm_right", 3),
        ("immobilizer_state", 4),
    ):  # all defined
        for v in range(last + 1):
            assert _packed(cm, **{member: v})[0] == 8
    # cornering_source 3 is accepted by is_in_range() and refused by is_defined() alone (RESERVED)
    assert cm.in_range["cornering_source"](3) and not cm.is_defined["cornering_source"](3)
    assert _packed(cm, cornering_source=3)[0] < 0
    for member, bad in (  # refused by is_in_range() (DBC max) or by the 2/3-bit field width
        ("cornering_level", 4),
        ("immobilizer_state", 5),  # DBC [0|4]
        ("immobilizer_state", 7),
        ("bsm_left", 4),
        ("bsm_right", 255),
    ):
        assert not cm.in_range[member](bad), (member, bad)
        assert _packed(cm, **{member: bad})[0] < 0, (member, bad)
    # Each signal is checked alone: these cross-field combinations are accepted (MINOR-4).
    assert _packed(cm, cornering_level=2, cornering_source=0)[0] == 8
    assert _packed(cm, cornering_level=0, cornering_source=1)[0] == 8


def test_safety_request_checked_pack(platform_db, tmp_path):
    """0x120 (RT_CORE sender): LOCK = 3 packs; the reserved 1 and 2 and undefined values do not."""
    cm = _safety_messages("rt_core", tmp_path, platform_db)["SafetyRequest"]
    assert cm.msg.frame_id == 0x120
    assert _packed(cm)[0] == 8  # all 0 = UNKNOWN / NONE
    rc, buf = _packed(cm, immobilizer_lock_request=3, ignition_state=1, park_mode=2)
    plain = _c_pack(cm, {**dict.fromkeys(cm.signals, 0), "immobilizer_lock_request": 3,
                         "ignition_state": 1, "park_mode": 2})  # fmt: skip
    assert rc == 8 and buf[:8] == plain
    for member, bad in (
        ("immobilizer_lock_request", 1),  # RESERVED: in range, not defined
        ("immobilizer_lock_request", 2),
        ("ignition_state", 3),
        ("park_mode", 3),
        ("ignition_state", 200),
    ):
        assert _untouched(cm, {**dict.fromkeys(cm.signals, 0), member: bad}), (member, bad)


SYNTHETIC_CHECKED = """VERSION ""

NS_ :

BS_:

BU_: TX RX

BO_ 256 M: 8 TX
 SG_ A : 0|2@1+ (1,0) [{rng}] "" RX

VAL_ 256 A {values} ;
"""


def _synthetic_checked(rng: str, values: str):
    db = parse_dbc(SYNTHETIC_CHECKED.format(rng=rng, values=values))
    msg = db.messages[0]
    return gen_c._checked_pack("\n#ifdef __cplusplus\n}\n#endif\n", "", [msg])


def test_checked_pack_accepts_a_consistent_synthetic_dbc():
    header, source = _synthetic_checked("0|3", '0 "NONE" 1 "ON" 3 "RESERVED"')
    assert "platform_m_a_is_defined" in header and "(value == 0u) || (value == 1u)" in source


@pytest.mark.parametrize(
    ("rng", "values", "message"),
    [
        ("0|5", '0 "NONE" 1 "ON"', "outside the 2-bit field"),  # raw max beyond the bit field
        ("0|3", '0 "NONE" 4 "ON"', "outside raw"),  # key beyond the bit field and the range
        ("0|2", '0 "NONE" 3 "ON"', "outside raw"),  # key beyond [min|max]
        ("0|3", '0 "NONE" 1 "Reserved"', "looks reserved"),
        ("0|3", '0 "NONE" 1 "RESERVED_1"', "looks reserved"),
        ("0|3", '0 "NONE" 1 "RSVD"', "looks reserved"),
        ("0|3", '0 "NONE" 1 "RES"', "looks reserved"),
    ],
)
def test_checked_pack_refuses_an_inconsistent_synthetic_dbc(rng, values, message):
    with pytest.raises(ValueError, match=message):
        _synthetic_checked(rng, values)


def test_checked_pack_accepts_names_that_only_start_like_reserved():
    _synthetic_checked("0|3", '0 "NONE" 1 "RESET" 2 "RESUME"')


def test_checked_pack_round_trips_through_e2e(platform_db, tmp_path):
    """pack_checked -> *_e2e_protect -> receiver *_e2e_check = OK, for every E2E message."""
    d = C_DIR / "hil_sim"
    so = _build(
        [d / "platform.c", d / "platform_e2e.c", d / "vehicle_e2e.c"], tmp_path / "libe2e.so"
    )
    header = (d / "platform.h").read_text()
    api = {cm.msg.name: cm for cm in load_api(so, header, "platform", platform_db).values()}
    e2e_header = (d / "platform_e2e.h").read_text()
    names = re.findall(r"^vehicle_e2e_status_t platform_(\w+)_e2e_protect\(", e2e_header, re.M)
    assert names
    ok_status = 0
    so.vehicle_e2e_tx_init.argtypes = [ctypes.POINTER(TxState)]
    so.vehicle_e2e_rx_init.argtypes = [ctypes.POINTER(RxState)]
    by_snake = {camel_to_snake_case(n): cm for n, cm in api.items()}
    for snake in names:
        cm = by_snake[snake]
        protect = getattr(so, f"platform_{snake}_e2e_protect")
        check = getattr(so, f"platform_{snake}_e2e_check")
        protect.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(TxState)]
        check.argtypes = [
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(RxState),
            ctypes.c_uint32,
        ]
        tx, rx = TxState(), RxState()
        so.vehicle_e2e_tx_init(ctypes.byref(tx))
        so.vehicle_e2e_rx_init(ctypes.byref(rx))
        raw = {
            m: min(_defined(s))
            if s.choices
            else next(v for v in _boundaries(s) if cm.in_range[m](v))
            for m, s in cm.signals.items()
        }
        if "cornering_level" in raw:  # 0x023: the CORNERING fields must survive protect
            raw.update(cornering_level=3, cornering_source=2)
        statuses = []
        for step in range(3):
            buf = ctypes.create_string_buffer(16)
            pack = cm.pack_checked or cm.pack
            assert pack(buf, ctypes.byref(cm.struct(**raw)), 16) == cm.msg.length
            before = bytes(buf.raw[: cm.msg.length])
            assert protect(buf, cm.msg.length, ctypes.byref(tx)) == ok_status
            frame = bytes(buf.raw[: cm.msg.length])
            if "cornering_level" in raw:
                assert frame[1] >> 4 == 3 | (2 << 2)  # LEVEL bits 4-5, SOURCE bits 6-7
            assert frame[2:] == before[2:]  # only CRC and counter change
            statuses.append(check(frame, cm.msg.length, ctypes.byref(rx), 100 + step * 10))
        assert statuses[0] == 2 and statuses[1:] == [ok_status, ok_status], (snake, statuses)
