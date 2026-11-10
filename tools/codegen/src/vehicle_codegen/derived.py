"""derived/cl250_derived.yaml (D-070 item 3): checks and the helpers codegen needs.

Definitions only: every input must resolve to something defs already defines
(invariant 2), class rules follow D-070 item 1 and the ride-summary DIDs stay in the
rt-core block reserved by uds/dids.yaml (item 4).
"""

from __future__ import annotations

import math
import re
from typing import Any

from cantools.database.can import Database

from . import config

DERIVED_CLASSES = ("A", "B", "C", "D")
# Class -> the only allowed `output` list (D-070 item 4: no CAN or VSS without a consumer).
DERIVED_OUTPUT = {"A": ["log"], "B": ["log", "ride_summary"], "C": ["server"], "D": ["server"]}
# Derived inputs each class may use: live values never wait for a ride to close.
DERIVED_INPUT_CLASSES = {"A": ("A",), "B": ("A", "B"), "C": ("B", "C"), "D": ("A", "B", "C", "D")}
RECORD_DID_MIN = 0xFD40  # uds/dids.yaml: rt-core block for the class-B ride summaries
RECORD_DID_MAX = 0xFD5F
MIN_PERIOD_MS = 20  # 50 Hz at most (D-070 item 1)
U16_MAX = 0xFFFF  # period_ms, stale_after_ms and the element count are uint16_t in C
AXIS_MAX = 2  # bins: at most a 2-D map (operating points, trim cells)
DERIVED_UNITS = frozenset({
    "", "enum", "flag", "count", "%", "ratio",
    "s", "ms", "min", "h", "day",
    "m", "km", "m/s", "km/h", "m/s2", "m/s3", "deg", "deg/s", "1/s", "1/m", "1/km",
    "rpm", "Nm", "kW", "N", "kg/m", "m2",
    "degC", "degC/s", "degC/min", "kPa", "kg/m3", "V", "V/day", "A", "mOhm",
    "g/s", "L/h", "L", "L/100km", "km/L", "mg", "g/kWh", "count/krev",
})  # fmt: skip

SIGNAL_REQUIRED = (
    "class",
    "description",
    "catalog",
    "unit",
    "range",
    "resolution",
    "inputs",
    "output",
)
SIGNAL_OPTIONAL = (
    "pending_inputs",
    "period_ms",
    "event",
    "window_ms",
    "stale_after_ms",
    "bins",
    "per_gear",
    "record",
    "window",
    "values",
    "bits",
)
SENSOR_KEYS = {"description", "unit", "sample_period_ms", "stale_after_ms", "phase0", "rt_core"}
RECORD_KEYS = {"did", "description"}
WINDOW_KEYS = {"description", "opens_on", "conditions", "min_duration_ms", "record"}
WINDOW_OPTIONAL = {"stable", "max_duration_ms"}
# D-079: how a health-snapshot window opens (gen_c.py numbers them in this order).
WINDOW_OPENS_ON = ("key_on", "engine_start", "condition", "engine_stop")
WINDOW_OPS = ("lt", "le", "gt", "ge", "eq")  # gen_c.py numbers them in this order
U32_MAX = 0xFFFFFFFF  # window durations are uint32_t in C
BLE_GROUPS = ("telemetry", "imuBlock", "gpsBlock")

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
_UPPER = re.compile(r"^[A-Z][A-Z0-9_]*$")
_WINDOW_KEY = re.compile(r"^W[0-9]+_[A-Z][A-Z0-9_]*$")


# --------------------------------------------------------------------------- resolvers


def ble_fields(ble: dict[str, Any]) -> set[str]:
    """`<group>.<field>` names a sensor's phase0 source may use."""
    out = {f"telemetry.{f['name']}" for f in ble["fields"]}
    out |= {f"imuBlock.{f['name']}" for f in ble["imuBlock"]["sampleFields"]}
    out |= {f"gpsBlock.{f['name']}" for f in ble["gpsBlock"]["fields"]}
    return out


def rt_core_did_fields(dids_doc: dict[str, Any]) -> set[str]:
    """`<DID>` and `<DID>.<FIELD>` of rt-core's own UDS DIDs (uds/dids.yaml)."""
    out: set[str] = set()
    for d in dids_doc["nodes"]["RT_CORE"]["dids"]:
        out.add(d["name"])
        out |= {f"{d['name']}.{f['name']}" for f in d.get("fields", [])}
    return out


def rt_core_dids(dids_doc: dict[str, Any]) -> set[int]:
    return {d["did"] for d in dids_doc["nodes"]["RT_CORE"]["dids"]}


def catalog_rows() -> set[str]:
    """First cells of the catalog section 5 tables (docs/vehicle-data-catalog.md)."""
    rows: set[str] = set()
    inside = False
    for line in config.CATALOG_MD.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.startswith("## 5.")
        elif inside and line.startswith("| ") and not line.startswith("| ---"):
            rows.add(line.split("|")[1].strip())
    return rows


def split_ref(ref: str) -> tuple[str, str]:
    kind, _, name = ref.partition(".")
    return kind, name


def input_period_ms(ref: str, doc: dict[str, Any], vehicle: dict[str, Any]) -> int | None:
    """Sample period of an input, None if it has none (constant, event, per ride)."""
    kind, name = split_ref(ref)
    if kind == "did":
        return next(d["poll_period_ms"] for d in vehicle["dids"] if d["name"] == name)
    if kind == "sensor":
        return doc["sensors"][name]["sample_period_ms"]
    if kind == "derived":
        return doc["signals"][name].get("period_ms")
    return None


def ready(doc: dict[str, Any], name: str, where: str) -> bool:
    """True if every input of signal `name` is defined for `where` (phase0 | rt_core)."""
    sig = doc["signals"][name]
    if sig.get("pending_inputs"):
        return False
    if where == "rt_core" and sig["class"] not in ("A", "B"):
        return False
    for ref in sig["inputs"]:
        kind, ref_name = split_ref(ref)
        if kind == "sensor" and doc["sensors"][ref_name][where] is None:
            return False
        if kind == "derived" and not ready(doc, ref_name, where):
            return False
    return True


def rt_core_signals(doc: dict[str, Any]) -> list[str]:
    """Classes A and B in file order: the rt-core table (C/D are server-side)."""
    return [n for n, s in doc["signals"].items() if s["class"] in ("A", "B")]


def window_input_ok(ref: Any, doc: dict[str, Any], vehicle: dict[str, Any]) -> bool:
    """A window condition or stability input: a DID, a sensor or a class-A derived signal
    (the rt-core table holds classes A and B; a window reads live values only)."""
    if not isinstance(ref, str):
        return False
    kind, name = split_ref(ref)
    if kind == "did":
        return any(d["name"] == name for d in vehicle["dids"])
    if kind == "sensor":
        return name in doc["sensors"]
    if kind == "derived":
        sig = doc["signals"].get(name)
        return isinstance(sig, dict) and sig.get("class") == "A"
    return False


def element_count(sig: dict[str, Any], constants: dict[str, Any]) -> int:
    """Values one signal holds: bins per axis x gears (1 = a scalar)."""
    n = math.prod(b["count"] for b in sig.get("bins", []))
    if sig.get("per_gear"):
        n *= constants["constants"]["gear_count"]["value"]
    return n


# --------------------------------------------------------------------------- checks


def _is_real(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _check_sensors(
    doc: dict[str, Any], ble: set[str], db: Database, rt_dids: set[str]
) -> list[str]:
    errors: list[str] = []
    sensors = doc.get("sensors")
    if not isinstance(sensors, dict) or not sensors:
        return ["derived: `sensors` must be a non-empty mapping"]
    for key, s in sensors.items():
        where = f"derived sensor {key}"
        if not isinstance(key, str) or not _SNAKE.match(key):
            errors.append(f"{where}: key must be snake_case")
        if not isinstance(s, dict) or set(s) != SENSOR_KEYS:
            errors.append(f"{where}: needs exactly {sorted(SENSOR_KEYS)}")
            continue
        if s["unit"] not in DERIVED_UNITS:
            errors.append(f"{where}: unit {s['unit']!r} not in DERIVED_UNITS")
        period, stale = s["sample_period_ms"], s["stale_after_ms"]
        if not _is_pos_int(period) or not _is_pos_int(stale) or stale > U16_MAX:
            errors.append(f"{where}: sample_period_ms and stale_after_ms must be integers > 0")
        elif stale < period:
            errors.append(f"{where}: stale_after_ms < sample_period_ms (never valid)")
        src0, src_rt = s["phase0"], s["rt_core"]
        if src0 is None and src_rt is None:
            errors.append(f"{where}: defined nowhere (phase0 and rt_core are both null)")
        if src0 is not None:
            kind, name = split_ref(str(src0))
            if kind != "ble" or name not in ble:
                errors.append(f"{where}: phase0 {src0!r} is not a ble/ble_schema.json field")
        if src_rt is not None:
            kind, name = split_ref(str(src_rt))
            if kind == "can":
                msg, _, sig = name.partition(".")
                try:
                    db.get_message_by_name(msg).get_signal_by_name(sig)
                except KeyError:
                    errors.append(f"{where}: rt_core {src_rt!r} is not a platform.dbc signal")
            elif kind != "uds" or name not in rt_dids:
                errors.append(
                    f"{where}: rt_core {src_rt!r} must be can.<Msg>.<SIG> or uds.<DID>.<FIELD>"
                )
    return errors


def _check_records(doc: dict[str, Any], used_dids: set[int]) -> list[str]:
    errors: list[str] = []
    records = doc.get("ride_summary_records")
    if not isinstance(records, dict) or not records:
        return ["derived: `ride_summary_records` must be a non-empty mapping"]
    seen: dict[int, str] = {}
    for key, r in records.items():
        where = f"derived record {key}"
        if not isinstance(key, str) or not _UPPER.match(key):
            errors.append(f"{where}: key must be UPPER_SNAKE_CASE")
        if not isinstance(r, dict) or set(r) != RECORD_KEYS:
            errors.append(f"{where}: needs exactly {sorted(RECORD_KEYS)}")
            continue
        did = r["did"]
        if not _is_pos_int(did) or not RECORD_DID_MIN <= did <= RECORD_DID_MAX:
            errors.append(f"{where}: did must be in 0x{RECORD_DID_MIN:04X}-0x{RECORD_DID_MAX:04X}")
        elif did in seen:
            errors.append(f"{where}: did 0x{did:04X} also used by {seen[did]}")
        elif did in used_dids:
            errors.append(f"{where}: did 0x{did:04X} is already an rt-core DID in uds/dids.yaml")
        else:
            seen[did] = key
    return errors


def _check_window_conditions(
    where: str, w: dict[str, Any], doc: dict[str, Any], vehicle: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    conditions = w["conditions"]
    if not isinstance(conditions, list):
        return [f"{where}: conditions must be a list"]
    if w["opens_on"] == "condition" and not conditions:
        errors.append(f"{where}: opens_on condition needs at least one condition")
    for i, c in enumerate(conditions):
        if not isinstance(c, dict) or set(c) != {"input", "op", "value"}:
            errors.append(f"{where}: conditions[{i}] needs exactly input, op, value")
            continue
        if not window_input_ok(c["input"], doc, vehicle):
            errors.append(
                f"{where}: conditions[{i}] input {c['input']!r} is not a did, a sensor"
                " or a class-A derived signal of defs"
            )
        if c["op"] not in WINDOW_OPS:
            errors.append(f"{where}: conditions[{i}] op must be one of {WINDOW_OPS}")
        if not _is_real(c["value"]):
            errors.append(f"{where}: conditions[{i}] value must be a number")
    stable = w.get("stable", [])
    if not isinstance(stable, list) or ("stable" in w and not stable):
        return errors + [f"{where}: stable must be a non-empty list"]
    for i, st in enumerate(stable):
        if not isinstance(st, dict) or set(st) != {"input", "max_spread"}:
            errors.append(f"{where}: stable[{i}] needs exactly input, max_spread")
            continue
        if not window_input_ok(st["input"], doc, vehicle):
            errors.append(
                f"{where}: stable[{i}] input {st['input']!r} is not a did, a sensor"
                " or a class-A derived signal of defs"
            )
        if not _is_real(st["max_spread"]) or st["max_spread"] <= 0:
            errors.append(f"{where}: stable[{i}] max_spread must be a number > 0")
    return errors


def _check_windows(doc: dict[str, Any], vehicle: dict[str, Any]) -> list[str]:
    """`windows` (D-079): entries, then the links to the signals and records."""
    windows = doc.get("windows")
    if not isinstance(windows, dict) or not windows:
        return ["derived: `windows` must be a non-empty mapping"]
    errors: list[str] = []
    records = doc["ride_summary_records"]
    owner: dict[str, str] = {}
    for key, w in windows.items():
        where = f"derived window {key}"
        if not isinstance(key, str) or not _WINDOW_KEY.match(key):
            errors.append(f"{where}: key must look like W1_KEY_ON")
        if not isinstance(w, dict) or not WINDOW_KEYS <= set(w) <= WINDOW_KEYS | WINDOW_OPTIONAL:
            errors.append(
                f"{where}: needs {sorted(WINDOW_KEYS)}, optional {sorted(WINDOW_OPTIONAL)}"
            )
            continue
        if not isinstance(w["description"], str) or not w["description"].strip():
            errors.append(f"{where}: description must be text")
        if w["opens_on"] not in WINDOW_OPENS_ON:
            errors.append(f"{where}: opens_on must be one of {WINDOW_OPENS_ON}")
        errors += _check_window_conditions(where, w, doc, vehicle)
        low, high = w["min_duration_ms"], w.get("max_duration_ms")
        if not _is_pos_int(low) or low > U32_MAX:
            errors.append(f"{where}: min_duration_ms must be an integer in 1..{U32_MAX}")
        elif "max_duration_ms" in w and (not _is_pos_int(high) or high > U32_MAX or high < low):
            errors.append(
                f"{where}: max_duration_ms must be an integer in min_duration_ms..{U32_MAX}"
            )
        rec = w["record"]
        if rec not in records:
            errors.append(f"{where}: record {rec!r} is not a ride_summary_records entry")
        elif not RECORD_DID_MIN <= records[rec]["did"] <= RECORD_DID_MAX:
            errors.append(
                f"{where}: record {rec} is outside 0x{RECORD_DID_MIN:04X}-0x{RECORD_DID_MAX:04X}"
            )
        elif rec in owner:
            errors.append(f"{where}: record {rec} is also the record of {owner[rec]}")
        else:
            owner[rec] = key
    users: dict[str, int] = dict.fromkeys(windows, 0)
    for name, sig in doc["signals"].items():
        win, rec = sig.get("window"), sig.get("record")
        if win is not None:
            if win not in windows:
                errors.append(f"derived {name}: window {win!r} is not an entry of windows")
                continue
            users[win] += 1
            if rec != windows[win]["record"]:
                errors.append(
                    f"derived {name}: a signal of window {win} reports in"
                    f" {windows[win]['record']}, not {rec}"
                )
        elif rec in owner:
            errors.append(f"derived {name}: record {rec} belongs to window {owner[rec]}")
    errors += [f"derived window {k}: no signal reports it" for k, n in users.items() if n == 0]
    return errors


def _check_signal(
    name: str,
    sig: dict[str, Any],
    doc: dict[str, Any],
    earlier: dict[str, str],
    known: dict[str, set[str]],
    vehicle: dict[str, Any],
    catalog: set[str],
) -> list[str]:
    where = f"derived {name}"
    errors: list[str] = []
    missing = [k for k in SIGNAL_REQUIRED if k not in sig]
    extra = sorted(set(sig) - set(SIGNAL_REQUIRED) - set(SIGNAL_OPTIONAL))
    if missing or extra:
        return [f"{where}: missing {missing}, unknown {extra}"]
    cls = sig["class"]
    if cls not in DERIVED_CLASSES:
        return [f"{where}: class must be one of {DERIVED_CLASSES}"]
    if not isinstance(sig["description"], str) or not sig["description"].strip():
        errors.append(f"{where}: description must be text")
    if sig["catalog"] not in catalog:
        errors.append(f"{where}: catalog {sig['catalog']!r} is not a row of catalog section 5")
    if sig["unit"] not in DERIVED_UNITS:
        errors.append(f"{where}: unit {sig['unit']!r} not in DERIVED_UNITS")
    rng, res = sig["range"], sig["resolution"]
    if (
        not (isinstance(rng, list) and len(rng) == 2 and all(_is_real(v) for v in rng))
        or rng[0] >= rng[1]
    ):
        errors.append(f"{where}: range must be [min, max] with min < max")
    elif not _is_real(res) or res <= 0 or res > rng[1] - rng[0]:
        errors.append(f"{where}: resolution must be > 0 and within the range")
    if sig["output"] != DERIVED_OUTPUT[cls]:
        errors.append(f"{where}: class {cls} output must be {DERIVED_OUTPUT[cls]}")

    pending = sig.get("pending_inputs", [])
    if not isinstance(pending, list) or not all(isinstance(p, str) and p.strip() for p in pending):
        errors.append(f"{where}: pending_inputs must be a list of text")
        pending = []
    inputs = sig["inputs"]
    if not isinstance(inputs, list) or not all(isinstance(i, str) for i in inputs):
        return errors + [f"{where}: inputs must be a list of references"]
    if not inputs and not pending:
        errors.append(f"{where}: no inputs and no pending_inputs")
    if len(set(inputs)) != len(inputs):
        errors.append(f"{where}: duplicate inputs")
    for ref in inputs:
        kind, ref_name = split_ref(ref)
        if kind == "derived":
            if ref_name == name or ref_name not in earlier:
                errors.append(f"{where}: input {ref} must be a signal defined above it")
            elif earlier[ref_name] not in DERIVED_INPUT_CLASSES[cls]:
                errors.append(f"{where}: class {cls} cannot use class-{earlier[ref_name]} {ref}")
        elif kind not in known or ref_name not in known[kind]:
            errors.append(f"{where}: input {ref} is not defined in vehicle-defs")
        elif cls == "C" and kind != "const":
            errors.append(f"{where}: class C uses class-B/C signals only, not {ref}")
    if cls == "D" and not pending:
        errors.append(f"{where}: class D names its off-vehicle inputs in pending_inputs")
    if errors:
        return errors

    errors += _check_timing(where, sig, doc, vehicle)
    for i, b in enumerate(sig.get("bins", [])):
        if not isinstance(b, dict) or set(b) != {"input", "min", "max", "count"}:
            errors.append(f"{where}: bins[{i}] needs exactly input, min, max, count")
        elif b["input"] not in inputs or not _is_pos_int(b["count"]):
            errors.append(f"{where}: bins[{i}] input must be one of inputs, count > 0")
        elif not (_is_real(b["min"]) and _is_real(b["max"]) and b["min"] < b["max"]):
            errors.append(f"{where}: bins[{i}] needs min < max")
    if "bins" in sig and not 1 <= len(sig["bins"]) <= AXIS_MAX:
        errors.append(f"{where}: bins has 1 to {AXIS_MAX} axes")
    if "per_gear" in sig and sig["per_gear"] is not True:
        errors.append(f"{where}: per_gear is true or absent")
    if cls == "B":
        if sig.get("record") not in doc.get("ride_summary_records", {}):
            errors.append(f"{where}: class B needs a record of ride_summary_records")
    elif "record" in sig:
        errors.append(f"{where}: only class B has a record")
    if "window" in sig and cls != "B":
        errors.append(f"{where}: only class B has a window")
    if "values" in sig:
        errors += _check_values(where, name, sig, doc)
    if "bits" in sig:
        errors += _check_bits(where, name, sig, doc, vehicle)
    return errors


def value_define(signal: str, value_name: str) -> str:
    """C name of an enum value (gen_c.py): VEHICLE_CL250_DERIVED_<this>."""
    return f"VALUE_{signal}_{value_name}".upper()


def _check_values(where: str, name: str, sig: dict[str, Any], doc: dict[str, Any]) -> list[str]:
    """`values`: integer code -> snake_case name of an enum signal, so no consumer writes
    the codes by hand (gen_c.py: one float define each; gen_python.py: SIGNALS[...])."""
    values = sig["values"]
    if sig["unit"] != "enum":
        return [f"{where}: only unit enum has values"]
    if not isinstance(values, dict) or not values:
        return [f"{where}: values must be a non-empty mapping of code -> name"]
    errors: list[str] = []
    lo, hi = sig["range"]
    taken = {s.upper() for s in doc["signals"]}
    for code, label in values.items():
        if isinstance(code, bool) or not isinstance(code, int) or not lo <= code <= hi:
            errors.append(f"{where}: value code {code!r} must be an integer within the range")
        if not isinstance(label, str) or not _SNAKE.match(label):
            errors.append(f"{where}: value name {label!r} must be snake_case")
        elif value_define(name, label) in taken:
            errors.append(f"{where}: value {label} collides with a signal name")
    labels = list(values.values())
    if len(set(labels)) != len(labels):
        errors.append(f"{where}: value names must be unique")
    return errors


def bit_define(signal: str, bit_name: str) -> str:
    """C name of a bit-mask bit (gen_c.py): VEHICLE_CL250_DERIVED_<this>."""
    return f"BIT_{signal}_{bit_name}".upper()


_POLL_BIT = re.compile(r"^poll_([0-9]+)ms$")


def _check_bits(
    where: str, name: str, sig: dict[str, Any], doc: dict[str, Any], vehicle: dict[str, Any]
) -> list[str]:
    """`bits`: bit number -> snake_case name of a bit-mask signal (D-104), so no consumer
    writes the bit positions by hand (gen_c.py: one mask define each; gen_python.py:
    SIGNALS[...]). The range is exactly 0 .. 2^(highest bit + 1) - 1. A `poll_<N>ms` bit
    stands for the polled DIDs with poll_period_ms N, so the poll bits name every poll
    period of the vehicle's tester table exactly once."""
    bits = sig["bits"]
    if sig["unit"] != "enum":
        return [f"{where}: only unit enum has bits"]
    if "values" in sig:
        return [f"{where}: a signal has values or bits, not both"]
    if not isinstance(bits, dict) or not bits:
        return [f"{where}: bits must be a non-empty mapping of bit -> name"]
    errors: list[str] = []
    taken = {s.upper() for s in doc["signals"]}
    numbers = [b for b in bits if not isinstance(b, bool) and isinstance(b, int)]
    for bit, label in bits.items():
        if isinstance(bit, bool) or not isinstance(bit, int) or not 0 <= bit <= 31:
            errors.append(f"{where}: bit {bit!r} must be an integer in 0..31")
        if not isinstance(label, str) or not _SNAKE.match(label):
            errors.append(f"{where}: bit name {label!r} must be snake_case")
        elif bit_define(name, label) in taken:
            errors.append(f"{where}: bit {label} collides with a signal name")
    labels = [v for v in bits.values() if isinstance(v, str)]
    if len(set(labels)) != len(labels):
        errors.append(f"{where}: bit names must be unique")
    if numbers and list(sig["range"]) != [0.0, float((1 << (max(numbers) + 1)) - 1)]:
        errors.append(f"{where}: range must be [0, 2^(highest bit + 1) - 1]")
    polls = [int(m.group(1)) for v in labels if (m := _POLL_BIT.match(v))]
    if polls:
        periods = sorted({d["poll_period_ms"] for d in vehicle["dids"]})
        if sorted(polls) != periods:
            errors.append(
                f"{where}: poll bits {sorted(polls)} must name each tester poll period "
                f"{periods} once"
            )
    return errors


def _check_timing(
    where: str, sig: dict[str, Any], doc: dict[str, Any], vehicle: dict[str, Any]
) -> list[str]:
    cls, period, event = sig["class"], sig.get("period_ms"), sig.get("event")
    stale, window = sig.get("stale_after_ms"), sig.get("window_ms")
    if window is not None and (not _is_pos_int(window) or window > U16_MAX):
        return [f"{where}: window_ms must be an integer in 1..{U16_MAX}"]
    if cls != "A":
        if period is not None or event is not None or stale is not None:
            return [f"{where}: period_ms, event and stale_after_ms are class A only"]
        return []
    if event is not None and event is not True:
        return [f"{where}: event is true or absent"]
    if (period is None) == (event is None):
        return [f"{where}: class A needs exactly one of period_ms and event"]
    if event:
        if stale is not None:
            return [f"{where}: an event has no stale_after_ms"]
        return []
    if not _is_pos_int(period) or not MIN_PERIOD_MS <= period <= U16_MAX:
        return [f"{where}: period_ms must be an integer in {MIN_PERIOD_MS}..{U16_MAX}"]
    if not _is_pos_int(stale) or not period <= stale <= U16_MAX:
        return [f"{where}: stale_after_ms must be an integer in period_ms..{U16_MAX}"]
    periods = [p for ref in sig["inputs"] if (p := input_period_ms(ref, doc, vehicle)) is not None]
    if periods and period < min(periods):
        return [f"{where}: period_ms {period} is faster than its fastest input ({min(periods)} ms)"]
    # The output is only as fresh as its slowest input: a stale_after_ms below that
    # input's period would call an output fresh while it carries an older sample.
    if periods and stale < max(periods):
        slowest = max(periods)
        return [
            f"{where}: stale_after_ms {stale} is below its slowest input's period ({slowest} ms)"
        ]
    return []


def check_derived(
    doc: dict[str, Any],
    vehicle: dict[str, Any],
    constants: dict[str, Any],
    ble: dict[str, Any],
    platform_db: Database,
    dids_doc: dict[str, Any],
) -> list[str]:
    """derived/cl250_derived.yaml against the files its references point into."""
    if doc.get("schema_version") != 1:
        return ["derived: schema_version must be 1"]
    errors = _check_sensors(doc, ble_fields(ble), platform_db, rt_core_did_fields(dids_doc))
    errors += _check_records(doc, rt_core_dids(dids_doc))
    signals = doc.get("signals")
    if not isinstance(signals, dict) or not signals:
        return errors + ["derived: `signals` must be a non-empty mapping"]
    if errors:
        return errors
    known = {
        "did": {d["name"] for d in vehicle["dids"]},
        "sensor": set(doc["sensors"]),
        "const": set(constants["constants"]),
    }
    catalog = catalog_rows()
    earlier: dict[str, str] = {}
    used_records: set[str] = set()
    for name, sig in signals.items():
        if not isinstance(name, str) or not _SNAKE.match(name):
            errors.append(f"derived {name}: key must be snake_case")
        if not isinstance(sig, dict):
            errors.append(f"derived {name}: must be a mapping")
            continue
        errors += _check_signal(name, sig, doc, earlier, known, vehicle, catalog)
        if sig.get("class") in DERIVED_CLASSES:
            earlier[name] = sig["class"]
        if isinstance(sig.get("record"), str):
            used_records.add(sig["record"])
    for key in doc["ride_summary_records"]:
        if key not in used_records:
            errors.append(f"derived record {key}: no class-B signal reports in it")
    if errors:
        return errors
    errors += _check_windows(doc, vehicle)
    if errors:
        return errors
    for name in rt_core_signals(doc):
        n = element_count(signals[name], constants)
        if n > U16_MAX:
            errors.append(f"derived {name}: {n} elements do not fit uint16_t")
        if len(signals[name]["inputs"]) > 255:
            errors.append(f"derived {name}: more than 255 inputs")
    return errors
