"""derived/cl250_derived.yaml (D-070 item 3)."""

import copy

import pytest

from vehicle_codegen import config, derived, gen_ble, gen_c, gen_python
from vehicle_codegen.dbc_checks import load_dbc
from vehicle_codegen.derived import check_derived
from vehicle_codegen.yaml_checks import load_yaml


@pytest.fixture(scope="module")
def refs():
    return {
        "vehicle": load_yaml(config.VEHICLE_YAML),
        "constants": load_yaml(config.VEHICLE_CONSTANTS_YAML),
        "ble": gen_ble.load_schema(),
        "db": load_dbc(config.PLATFORM_DBC),
        "dids": load_yaml(config.DIDS_YAML),
    }


@pytest.fixture
def doc():
    return copy.deepcopy(load_yaml(config.DERIVED_YAML))


def _check(doc, refs, dids=None):
    return check_derived(
        doc, refs["vehicle"], refs["constants"], refs["ble"], refs["db"], dids or refs["dids"]
    )


def _has(errors, *parts):
    return any(all(p in e for p in parts) for e in errors)


def _add(doc, name, **fields):
    base = {
        "class": "A",
        "description": "test signal",
        "catalog": "Longitudinal acceleration, jerk",
        "unit": "m/s2",
        "range": [-10.0, 10.0],
        "resolution": 0.01,
        "inputs": ["did.VEHICLE_SPEED"],
        "period_ms": 110,
        "stale_after_ms": 330,
        "output": ["log"],
    }
    doc["signals"][name] = {k: v for k, v in {**base, **fields}.items() if v is not None}


def test_committed_definitions_are_consistent(doc, refs):
    assert _check(doc, refs) == []


@pytest.mark.parametrize(
    "ref", ["did.NOT_A_DID", "sensor.not_a_sensor", "const.not_a_constant", "can.EkfLean"]
)
def test_an_input_must_be_defined_in_defs(doc, refs, ref):
    _add(doc, "t_sig", inputs=["did.VEHICLE_SPEED", ref])
    assert _has(_check(doc, refs), "t_sig", ref, "not defined")


def test_a_derived_input_must_be_defined_above(doc, refs):
    first = next(iter(doc["signals"]))
    doc["signals"][first]["inputs"].append("derived.trip_distance")
    _add(doc, "t_self", inputs=["derived.t_self"])
    errors = _check(doc, refs)
    assert _has(errors, first, "derived.trip_distance", "defined above")
    assert _has(errors, "t_self", "defined above")


def test_class_rules(doc, refs):
    _add(doc, "t_live_from_ride", inputs=["derived.ride_distance"])
    _add(
        doc,
        "t_trend_from_did",
        **{"class": "C", "output": ["server"], "period_ms": None, "stale_after_ms": None},
    )
    _add(doc, "t_bad_output", output=["log", "can"])
    _add(
        doc,
        "t_d_without_pending",
        **{"class": "D", "output": ["server"], "period_ms": None, "stale_after_ms": None},
    )
    errors = _check(doc, refs)
    assert _has(errors, "t_live_from_ride", "class A cannot use class-B")
    assert _has(errors, "t_trend_from_did", "class C uses class-B/C signals only")
    assert _has(errors, "t_bad_output", "output must be ['log']")
    assert _has(errors, "t_d_without_pending", "pending_inputs")


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"period_ms": 50, "stale_after_ms": 150}, "faster than its fastest input (110 ms)"),
        (
            {"inputs": ["sensor.imu_accel_x"], "period_ms": 10, "stale_after_ms": 30},
            "period_ms must be",
        ),  # fmt: skip
        ({"stale_after_ms": 100}, "stale_after_ms must be"),
        (
            {
                "inputs": ["sensor.imu_accel_x", "did.VEHICLE_SPEED"],
                "stale_after_ms": 60,
                "period_ms": 20,
            },
            "below its slowest input's period (110 ms)",
        ),
        ({"period_ms": None}, "exactly one of period_ms and event"),
        ({"period_ms": None, "event": True}, "an event has no stale_after_ms"),
        ({"window_ms": 0}, "window_ms"),
        ({"window_ms": 65536}, "window_ms"),
    ],
)
def test_live_timing(doc, refs, fields, message):
    _add(doc, "t_timing", **fields)
    assert _has(_check(doc, refs), "t_timing", message)


def test_ride_summary_records(doc, refs):
    ride = doc["signals"]["ride_distance"]
    del ride["record"]
    assert _has(_check(doc, refs), "ride_distance", "needs a record")
    ride["record"] = "RIDE_USAGE"
    doc["ride_summary_records"]["RIDE_USAGE"]["did"] = 0xFD3F
    assert _has(_check(doc, refs), "RIDE_USAGE", "0xFD40-0xFD5F")
    doc["ride_summary_records"]["RIDE_USAGE"]["did"] = 0xFD40
    doc["ride_summary_records"]["RIDE_EXTRA"] = {"did": 0xFD40, "description": "x"}
    assert _has(_check(doc, refs), "RIDE_EXTRA", "also used by RIDE_USAGE")
    doc["ride_summary_records"]["RIDE_EXTRA"]["did"] = 0xFD5F
    assert _has(_check(doc, refs), "RIDE_EXTRA", "no class-B signal")


def test_a_record_did_never_reuses_an_rt_core_did(doc, refs):
    dids = copy.deepcopy(refs["dids"])
    did = doc["ride_summary_records"]["RIDE_USAGE"]["did"]
    dids["nodes"]["RT_CORE"]["dids"].append({"did": did, "name": "TAKEN"})
    assert _has(_check(doc, refs, dids), "RIDE_USAGE", "already an rt-core DID")


def test_sensor_sources_resolve(doc, refs):
    s = doc["sensors"]
    s["imu_accel_x"]["phase0"] = "ble.imuBlock.bx"
    s["lean_angle"]["rt_core"] = "can.EkfLean.NOT_A_SIGNAL"
    s["can_bus_off_count"]["rt_core"] = "uds.RT_CORE_HEALTH.NOT_A_FIELD"
    s["gps_heading"]["phase0"] = None
    errors = _check(doc, refs)
    assert _has(errors, "imu_accel_x", "not a ble/ble_schema.json field")
    assert _has(errors, "lean_angle", "not a platform.dbc signal")
    assert _has(errors, "can_bus_off_count", "uds.<DID>.<FIELD>")
    assert _has(errors, "gps_heading", "defined nowhere")


def test_units_ranges_and_catalog(doc, refs):
    _add(doc, "t_unit", unit="furlong")
    _add(doc, "t_range", range=[5.0, 5.0])
    _add(doc, "t_res", resolution=50.0)
    _add(doc, "t_catalog", catalog="Not a catalog row")
    errors = _check(doc, refs)
    assert _has(errors, "t_unit", "furlong")
    assert _has(errors, "t_range", "min < max")
    assert _has(errors, "t_res", "resolution")
    assert _has(errors, "t_catalog", "not a row of catalog section 5")


def test_bins(doc, refs):
    _add(doc, "t_bins", bins=[{"input": "did.ENGINE_SPEED", "min": 0.0, "max": 1.0, "count": 4}])
    assert _has(_check(doc, refs), "t_bins", "input must be one of inputs")


def test_readiness_follows_sensor_sources_and_pending_inputs(doc, refs):
    _add(doc, "t_imu", inputs=["sensor.imu_accel_x"], period_ms=20, stale_after_ms=60)
    _add(doc, "t_lean", inputs=["sensor.lean_angle"], period_ms=100, stale_after_ms=300)
    _add(doc, "t_pending", pending_inputs=["0xA6 odometer (catalog 2.1, not defined)"])
    _add(doc, "t_chain", inputs=["derived.t_imu"], period_ms=20, stale_after_ms=60)
    assert _check(doc, refs) == []
    assert derived.ready(doc, "t_imu", "phase0") and not derived.ready(doc, "t_imu", "rt_core")
    assert derived.ready(doc, "t_lean", "phase0") and derived.ready(doc, "t_lean", "rt_core")
    assert not derived.ready(doc, "t_pending", "phase0")
    assert not derived.ready(doc, "t_chain", "rt_core")


def test_generated_c_holds_classes_a_and_b_only(doc, refs):
    files = gen_c.generate_derived_c(doc, refs["constants"])
    h, c = files["vehicle_cl250_derived.h"], files["vehicle_cl250_derived.c"]
    names = derived.rt_core_signals(doc)
    assert f"#define VEHICLE_CL250_DERIVED_COUNT ({len(names)}u)" in h
    for name, sig in doc["signals"].items():
        assert (f"VEHICLE_CL250_DERIVED_{name.upper()} (" in h) == (sig["class"] in "AB")
        assert (f"/* {name} [" in c) == (sig["class"] in "AB")
    for key, rec in doc["ride_summary_records"].items():
        assert f"({rec['did']:#06X}u)".replace("0X", "0x") in h, key
    assert "const." not in c


def test_histogram_element_count(doc, refs):
    sig = doc["signals"]["operating_point_time"]
    assert derived.element_count(sig, refs["constants"]) == 16 * 16
    sig["per_gear"] = True
    assert derived.element_count(sig, refs["constants"]) == 16 * 16 * 6


def test_python_module_carries_every_class_and_readiness(doc):
    py = gen_python.generate_derived_py(doc)
    ns: dict = {}
    exec(compile(py, "vehicle_derived.py", "exec"), ns)
    assert set(ns["SIGNALS"]) == set(doc["signals"])
    assert set(ns["SENSORS"]) == set(doc["sensors"])
    for name, sig in ns["SIGNALS"].items():
        assert sig["ready_phase0"] == derived.ready(doc, name, "phase0")
        assert sig["ready_rt_core"] == derived.ready(doc, name, "rt_core")


def test_only_rt_core_gets_the_derived_table():
    assert [t.node for t in config.C_TARGETS if t.vehicle_constants] == ["RT_CORE"]


def test_health_windows_are_defined_in_the_free_record_block(doc):
    assert list(doc["windows"]) == [
        "W1_KEY_ON",
        "W2_CRANK",
        "W3_WARM_IDLE",
        "W4_CRUISE",
        "W5_POST_STOP",
    ]
    dids = [doc["ride_summary_records"][w["record"]]["did"] for w in doc["windows"].values()]
    assert dids == [0xFD4A, 0xFD4B, 0xFD4C, 0xFD4D, 0xFD4E]
    for key, w in doc["windows"].items():
        mine = [s for s in doc["signals"].values() if s.get("window") == key]
        assert mine and all(s["class"] == "B" and s["record"] == w["record"] for s in mine)
        assert any(
            n.endswith("_count") for n, s in doc["signals"].items() if s.get("window") == key
        )


@pytest.mark.parametrize(
    "path, value, message",
    [
        (("W1_KEY_ON", "opens_on"), "on_tuesday", "opens_on must be one of"),
        (("W1_KEY_ON", "conditions", 0, "op"), "approx", "op must be one of"),
        (("W1_KEY_ON", "conditions", 0, "input"), "did.NOT_A_DID", "is not a did, a sensor"),
        (("W1_KEY_ON", "conditions", 0, "input"), "const.gear_count", "is not a did, a sensor"),
        (("W1_KEY_ON", "conditions", 0, "input"), "derived.ride_distance", "class-A derived"),
        (("W1_KEY_ON", "conditions", 0, "value"), "hot", "value must be a number"),
        (("W1_KEY_ON", "conditions"), [], None),  # allowed: key_on needs no condition
        (("W3_WARM_IDLE", "conditions"), [], "needs at least one condition"),
        (("W4_CRUISE", "stable", 0, "input"), "did.NOT_A_DID", "stable[0] input"),
        (("W4_CRUISE", "stable", 0, "max_spread"), 0.0, "max_spread must be"),
        (("W4_CRUISE", "stable"), [], "stable must be a non-empty list"),
        (("W1_KEY_ON", "min_duration_ms"), 0, "min_duration_ms must be"),
        (("W1_KEY_ON", "max_duration_ms"), 1000, "max_duration_ms must be"),
        (("W1_KEY_ON", "max_duration_ms"), 2**32, "max_duration_ms must be"),
        (("W1_KEY_ON", "record"), "RIDE_NOPE", "is not a ride_summary_records entry"),
        (("W1_KEY_ON", "record"), "RIDE_USAGE", "belongs to window"),
        (("W2_CRANK", "record"), "RIDE_WINDOW_KEY_ON", "is also the record of W1_KEY_ON"),
    ],
)
def test_window_entries(doc, refs, path, value, message):
    target = doc["windows"]
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    errors = _check(doc, refs)
    if message is None:
        assert errors == []
    else:
        assert _has(errors, "derived window", message) or _has(errors, "derived ride_", message), (
            errors
        )


def test_window_needs_a_record_in_the_block(doc, refs):
    doc["ride_summary_records"]["RIDE_WINDOW_KEY_ON"]["did"] = 0xFD60
    assert _has(_check(doc, refs), "RIDE_WINDOW_KEY_ON", "0xFD40-0xFD5F")


def test_a_window_without_signals_is_refused(doc, refs):
    doc["windows"]["W6_EMPTY"] = {
        "description": "no signal",
        "opens_on": "key_on",
        "conditions": [],
        "min_duration_ms": 1000,
        "record": "RIDE_USAGE_X",
    }
    doc["ride_summary_records"]["RIDE_USAGE_X"] = {"did": 0xFD5F, "description": "x"}
    _add(
        doc,
        "t_ride_x",
        record="RIDE_USAGE_X",
        output=["log", "ride_summary"],
        period_ms=None,
        stale_after_ms=None,
        **{"class": "B"},
    )
    assert _has(_check(doc, refs), "W6_EMPTY", "no signal reports it")


def test_window_signals_follow_their_window(doc, refs):
    sigs = doc["signals"]
    sigs["window_crank_count"]["window"] = "W9_NOPE"
    sigs["window_crank_min_voltage"]["record"] = "RIDE_WINDOW_KEY_ON"
    errors = _check(doc, refs)
    assert _has(errors, "window_crank_count", "W9_NOPE", "not an entry of windows")
    assert _has(errors, "window_crank_min_voltage", "window W2_CRANK", "RIDE_WINDOW_CRANK")
    _add(doc, "t_live_window", window="W1_KEY_ON")
    assert _has(_check(doc, refs), "t_live_window", "only class B has a window")


def test_the_window_table_in_python(doc):
    ns: dict = {}
    exec(compile(gen_python.generate_derived_py(doc), "vehicle_derived.py", "exec"), ns)
    windows = ns["WINDOWS"]
    assert set(windows) == set(doc["windows"])
    idle = windows["W3_WARM_IDLE"]
    assert idle["opens_on"] == "condition" and idle["min_duration_ms"] == 20000
    assert {"input": "did.COOLANT_TEMP", "op": "gt", "value": 80.0} in idle["conditions"]
    assert windows["W4_CRUISE"]["stable"][0] == {"input": "did.VEHICLE_SPEED", "max_spread": 4.0}
    assert windows["W2_CRANK"]["conditions"] == []
    assert "window_crank_count" in windows["W2_CRANK"]["signals"]
    for key, w in windows.items():
        assert ns["RIDE_SUMMARY_RECORDS"][w["record"]][0] in range(0xFD40, 0xFD60), key


def test_the_window_table_in_c(doc, refs):
    files = gen_c.generate_derived_c(doc, refs["constants"])
    h, c = files["vehicle_cl250_derived.h"], files["vehicle_cl250_derived.c"]
    assert f"#define VEHICLE_CL250_WINDOW_COUNT ({len(doc['windows'])}u)" in h
    assert "#define VEHICLE_CL250_WINDOW_W3_WARM_IDLE (2u)" in h
    assert "#define VEHICLE_CL250_RIDE_WINDOW_CRANK_DID (0xFD4Bu)" in h
    assert "extern const vehicle_cl250_window_t vehicle_cl250_window[" in h
    for key in doc["windows"]:
        assert f"{{ /* {key} */" in c
    assert "VEHICLE_CL250_WINDOW_OP_GT, 80.0f" in c
    assert "VEHICLE_CL250_DERIVED_GEAR_ESTIMATE }, VEHICLE_CL250_WINDOW_OP_GE, 4.0f" in c
    assert "0xFD4Bu" not in c  # records are named, never literals
    # The window signals are class B: they are in the signal table with their record.
    assert "/* window_cruise_count [count] */" in c


def _enum(doc, name, values, **fields):
    _add(doc, name, unit="enum", range=[0.0, 2.0], resolution=1.0, values=values, **fields)


def test_enum_values_are_checked(doc, refs):
    _enum(doc, "t_ok", {0: "low", 1: "mid", 2: "high"})
    assert _check(doc, refs) == []
    _enum(doc, "t_out", {3: "beyond"})
    _enum(doc, "t_bool", {True: "yes"})
    _enum(doc, "t_case", {0: "Low"})
    _enum(doc, "t_dup", {0: "same", 1: "same"})
    _enum(doc, "t_empty", {})
    _add(doc, "t_unit", values={0: "zero"})
    errors = _check(doc, refs)
    assert _has(errors, "t_out", "within the range")
    assert _has(errors, "t_bool", "within the range")
    assert _has(errors, "t_case", "snake_case")
    assert _has(errors, "t_dup", "unique")
    assert _has(errors, "t_empty", "non-empty")
    assert _has(errors, "t_unit", "only unit enum")
    assert not any("t_ok" in e for e in errors)


def test_enum_value_name_cannot_collide_with_a_signal(doc, refs):
    _enum(doc, "t_state", {0: "idle"})
    _add(doc, "value_t_state_idle")
    assert _has(_check(doc, refs), "t_state", "collides with a signal name")


def test_generated_c_names_every_enum_value(doc, refs):
    h = gen_c.generate_derived_c(doc, refs["constants"])["vehicle_cl250_derived.h"]
    names = derived.rt_core_signals(doc)
    coded = [n for n in names if "values" in doc["signals"][n]]
    assert {"gear_estimate", "clutch_state", "neutral_coasting_state"} <= set(coded)
    for n in coded:
        for code, label in doc["signals"][n]["values"].items():
            define = f"VEHICLE_CL250_DERIVED_{derived.value_define(n, label)} ({code}.0f)"
            assert define in h
    assert gen_python.generate_derived_py(doc).count("'values': {") == len(
        [s for s in doc["signals"].values() if "values" in s]
    )


def _mask(doc, name, bits, hi=7.0, **fields):
    _add(doc, name, unit="enum", range=[0.0, hi], resolution=1.0, bits=bits, **fields)


def test_mask_bits_are_checked(doc, refs):
    _mask(doc, "t_ok", {0: "low", 1: "mid", 2: "high"})
    assert _check(doc, refs) == []
    _mask(doc, "t_wide", {0: "a", 1: "b"})  # range 0..7 but only two bits
    _mask(doc, "t_neg", {-1: "a"}, hi=1.0)
    _mask(doc, "t_bool", {True: "yes"}, hi=1.0)
    _mask(doc, "t_case", {0: "Low"}, hi=1.0)
    _mask(doc, "t_dup", {0: "same", 1: "same"}, hi=3.0)
    _mask(doc, "t_empty", {})
    _mask(doc, "t_both", {0: "a"}, hi=1.0, values={0: "zero"})
    _add(doc, "t_unit", bits={0: "zero"})
    _mask(doc, "t_poll", {0: "poll_110ms", 1: "poll_999ms"}, hi=3.0)
    errors = _check(doc, refs)
    assert _has(errors, "t_wide", "range must be")
    assert _has(errors, "t_neg", "0..31")
    assert _has(errors, "t_bool", "0..31")
    assert _has(errors, "t_case", "snake_case")
    assert _has(errors, "t_dup", "unique")
    assert _has(errors, "t_empty", "non-empty")
    assert _has(errors, "t_both", "not both")
    assert _has(errors, "t_unit", "only unit enum")
    assert _has(errors, "t_poll", "each tester poll period")
    assert not any("t_ok" in e for e in errors)


def test_mask_bit_name_cannot_collide_with_a_signal(doc, refs):
    _mask(doc, "t_mask", {0: "lost"}, hi=1.0)
    _add(doc, "bit_t_mask_lost")
    assert _has(_check(doc, refs), "t_mask", "collides with a signal name")


def test_data_quality_mask_has_one_poll_bit_per_poll_period(doc, refs):
    """D-104: the poll bits follow the tester table; adding a poll period fails the check."""
    bits = doc["signals"]["data_quality_mask"]["bits"]
    periods = sorted({d["poll_period_ms"] for d in refs["vehicle"]["dids"]})
    assert [v for _, v in sorted(bits.items())][: len(periods)] == [f"poll_{p}ms" for p in periods]
    assert {"bus_off", "tester_stall"} <= set(bits.values())
    refs["vehicle"]["dids"][0]["poll_period_ms"] = 333
    assert _has(_check(doc, refs), "data_quality_mask", "each tester poll period")


def test_generated_c_names_every_mask_bit(doc, refs):
    h = gen_c.generate_derived_c(doc, refs["constants"])["vehicle_cl250_derived.h"]
    masked = [n for n in derived.rt_core_signals(doc) if "bits" in doc["signals"][n]]
    assert masked == ["data_quality_mask"]
    for n in masked:
        for bit, label in doc["signals"][n]["bits"].items():
            assert f"VEHICLE_CL250_DERIVED_{derived.bit_define(n, label)} ({1 << bit}u)" in h
    assert gen_python.generate_derived_py(doc).count("'bits': {") == 1


def test_timing_macros_equal_the_table_data(doc, refs):
    """Static sizing in rt-core uses these compile-time copies; they must equal the tables."""
    h = gen_c.generate_derived_c(doc, refs["constants"])["vehicle_cl250_derived.h"]
    for n in derived.rt_core_signals(doc):
        sig = doc["signals"][n]
        for key, macro in (("period_ms", "PERIOD_MS"), ("window_ms", "WINDOW_MS")):
            line = f"#define VEHICLE_CL250_{macro}_{n.upper()} ("
            assert (line in h) == (key in sig), n
            if key in sig:
                assert f"{line}{sig[key]}u)" in h
    for key, w in doc["windows"].items():
        line = f"#define VEHICLE_CL250_MAX_DURATION_MS_{key} ("
        assert (line in h) == ("max_duration_ms" in w)
    vh = gen_c.generate_vehicle_c(refs["vehicle"], doc)["vehicle_cl250.h"]
    for d in refs["vehicle"]["dids"]:
        assert f"#define VEHICLE_CL250_POLL_MS_{d['name']} ({d['poll_period_ms']}u)" in vh
