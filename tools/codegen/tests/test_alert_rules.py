"""In-ride alert rules (D-129 item 2): faults/alert_rules.yaml."""

import copy

import pytest

from vehicle_codegen import alert_rules, config
from vehicle_codegen.cli import render_all
from vehicle_codegen.yaml_checks import load_yaml


@pytest.fixture(scope="module")
def refs():
    return {
        "vehicle": load_yaml(config.VEHICLE_YAML),
        "derived": load_yaml(config.DERIVED_YAML),
        "catalog": load_yaml(config.FAULT_CATALOG_YAML),
    }


@pytest.fixture
def data():
    return copy.deepcopy(load_yaml(config.ALERT_RULES_YAML))


def _check(data, refs):
    return alert_rules.check_alert_rules(data, refs["catalog"], refs["vehicle"], refs["derived"])


def _has(errors, *parts):
    return any(all(p in e for p in parts) for e in errors)


def _rule(data, rid):
    return next(r for r in data["rules"] if r["id"] == rid)


def test_committed_rules_are_consistent(data, refs):
    assert _check(data, refs) == []


def test_seed_set_is_honest(data):
    ids = [r["id"] for r in data["rules"]]
    assert ids == sorted(set(ids))
    for r in data["rules"]:
        assert r["class"] in ("P1", "P2")
        assert r["status"] == "PROVISIONAL"
        assert r["source"]["confidence"] == "low"


def test_duplicate_id(data, refs):
    data["rules"][1]["id"] = data["rules"][0]["id"]
    assert _has(_check(data, refs), "duplicate id")


def test_bad_id_format(data, refs):
    data["rules"][0]["id"] = "ALR-1"
    assert _has(_check(data, refs), "ALR-000")


def test_p0_forbidden(data, refs):
    data["rules"][0]["class"] = "P0"
    assert _has(_check(data, refs), "P0", "invariant 3")


@pytest.mark.parametrize("cls", ["P3", "p1", "urgent"])
def test_unknown_class(data, refs, cls):
    data["rules"][0]["class"] = cls
    assert _has(_check(data, refs), "class must be one of")


def test_unknown_signal(data, refs):
    data["rules"][0]["signal"] = "did.NO_SUCH_SIGNAL"
    assert _has(_check(data, refs), "not a did.* or derived.* defs signal")


def test_sensor_signal_not_allowed(data, refs):
    data["rules"][0]["signal"] = "sensor.lean_angle"
    assert _has(_check(data, refs), "not a did.* or derived.* defs signal")


def test_derived_signal_resolves(data, refs):
    r = _rule(data, "ALR-001")
    r["signal"] = "derived.coolant_rate"
    r["unit"] = "degC/min"
    assert _check(data, refs) == []


def test_unit_must_match_defs(data, refs):
    _rule(data, "ALR-001")["unit"] = "K"
    assert _has(_check(data, refs), "ALR-001", "unit")


def test_rate_unit_is_per_minute(data, refs):
    _rule(data, "ALR-005")["unit"] = "degC"
    assert _has(_check(data, refs), "ALR-005", "degC/min")


def test_unknown_gate(data, refs):
    _rule(data, "ALR-001")["while"] = ["flying"]
    assert _has(_check(data, refs), "gate 'flying'")


def test_gate_signal_and_unit_checked(data, refs):
    data["gates"]["moving"]["unit"] = "mph"
    data["gates"]["warm"]["signal"] = "did.NOPE"
    errors = _check(data, refs)
    assert _has(errors, "gate moving", "unit")
    assert _has(errors, "gate warm", "defs signal")


def test_unknown_condition(data, refs):
    _rule(data, "ALR-001")["condition"] = "equals"
    assert _has(_check(data, refs), "condition must be one of")


@pytest.mark.parametrize("key", ["sustain_s", "cooldown_s"])
@pytest.mark.parametrize("bad", [0, -1, "5"])
def test_times_must_be_positive(data, refs, key, bad):
    _rule(data, "ALR-001")[key] = bad
    assert _has(_check(data, refs), key, "positive")


def test_cap_must_be_positive_int(data, refs):
    _rule(data, "ALR-001")["max_spoken_per_ride"] = 0
    assert _has(_check(data, refs), "max_spoken_per_ride")


def test_negative_hysteresis(data, refs):
    _rule(data, "ALR-001")["clear_hysteresis"] = -1
    assert _has(_check(data, refs), "clear_hysteresis")


def test_threshold_required_unless_absent(data, refs):
    del _rule(data, "ALR-001")["threshold"]
    assert _has(_check(data, refs), "threshold must be a number")


def test_absent_takes_no_threshold(data, refs):
    _rule(data, "ALR-004")["threshold"] = 0
    assert _has(_check(data, refs), "ALR-004", "no threshold")


def test_rate_needs_window(data, refs):
    del _rule(data, "ALR-005")["rate_window_s"]
    assert _has(_check(data, refs), "rate_window_s")


def test_window_only_on_rate(data, refs):
    _rule(data, "ALR-001")["rate_window_s"] = 60
    assert _has(_check(data, refs), "rate_window_s only")


def test_unknown_key(data, refs):
    _rule(data, "ALR-001")["priority"] = 1
    assert _has(_check(data, refs), "unknown key 'priority'")


def test_fault_id_must_exist(data, refs):
    _rule(data, "ALR-001")["fault_id"] = "COL-999"
    assert _has(_check(data, refs), "fault_id", "not a catalog entry")


def test_confirm_entry_needs_own_text(data, refs):
    del _rule(data, "ALR-002")["text"]
    assert _has(_check(data, refs), "text is required", "CONFIRM")


def test_no_fault_needs_own_text(data, refs):
    del _rule(data, "ALR-004")["text"]
    assert _has(_check(data, refs), "text is required", "fault_id is absent")


def test_displayable_entry_supplies_text(data, refs):
    r = _rule(data, "ALR-001")
    r["fault_id"] = "LUB-001"  # displayable in the catalog
    assert _has(_check(data, refs), "text must be omitted")
    del r["text"]
    assert _check(data, refs) == []
    rule = next(x for x in alert_rules.resolve(data, refs["catalog"]) if x["id"] == "ALR-001")
    assert rule["text_source"] == "fault"
    lub = next(e for e in refs["catalog"]["entries"] if e["id"] == "LUB-001")
    assert rule["text"] == lub["rider_text"]


def test_forbidden_phrase(data, refs):
    _rule(data, "ALR-001")["text"] = "It is safe to ride on."
    assert _has(_check(data, refs), "safe to ride")


def test_tuned_needs_real_source(data, refs):
    _rule(data, "ALR-001")["status"] = "TUNED"
    assert _has(_check(data, refs), "low-confidence", "PROVISIONAL")


def test_unknown_status(data, refs):
    _rule(data, "ALR-001")["status"] = "FINAL"
    assert _has(_check(data, refs), "status must be one of")


def test_source_shape(data, refs):
    _rule(data, "ALR-001")["source"] = {"ref": "x", "confidence": "certain"}
    assert _has(_check(data, refs), "source must be")


def test_generated_python_matches_rules(data, refs):
    files = render_all(with_vss=False)
    ns: dict = {}
    code = files[next(p for p in files if p.name == "alert_rules.py")]
    exec(compile(code, "alert_rules.py", "exec"), ns)  # noqa: S102
    rules = ns["ALERT_RULES"]
    assert [r.id for r in rules] == [r["id"] for r in data["rules"]]
    assert set(ns["ALERT_GATES"]) == set(data["gates"])
    first = ns["ALERT_RULES_BY_ID"]["ALR-001"]
    assert first.alert_class == "P1" and first.threshold == 110.0 and first.unit == "degC"
    absent = ns["ALERT_RULES_BY_ID"]["ALR-004"]
    assert absent.threshold is None and absent.clear_hysteresis is None
    assert ns["ALERT_RULES_BY_ID"]["ALR-005"].rate_window_s == 60.0
    with pytest.raises(Exception):  # noqa: B017  frozen dataclass
        first.threshold = 1.0


def test_generated_dart(data):
    files = render_all(with_vss=False)
    dart = files[next(p for p in files if p.name == "alert_rules.dart")]
    assert "const List<AlertRule> alertRules" in dart
    assert "AlertCondition.rateAbove" in dart and "AlertClass.p2" in dart
    assert dart.count("  AlertRule(") == len(data["rules"])
    barrel = files[next(p for p in files if p.name == "vehicle_defs.dart")]
    assert "export 'alert_rules.dart';" in barrel
