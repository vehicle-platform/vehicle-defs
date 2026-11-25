"""Fault catalog (D-084): faults/catalog.yaml + vehicle/cl250_faults.yaml."""

import copy

import pytest

from vehicle_codegen import config, faults
from vehicle_codegen.cli import render_all
from vehicle_codegen.yaml_checks import load_yaml


@pytest.fixture(scope="module")
def refs():
    return {
        "vehicle": load_yaml(config.VEHICLE_YAML),
        "derived": load_yaml(config.DERIVED_YAML),
    }


@pytest.fixture
def catalog():
    return copy.deepcopy(load_yaml(config.FAULT_CATALOG_YAML))


@pytest.fixture
def applic():
    return copy.deepcopy(load_yaml(config.FAULTS_CL250_YAML))


def _check(catalog, applic, refs):
    return faults.check_faults(catalog, applic, refs["vehicle"], refs["derived"])


def _has(errors, *parts):
    return any(all(p in e for p in parts) for e in errors)


def test_committed_catalog_is_consistent(catalog, applic, refs):
    assert _check(catalog, applic, refs) == []


def _entry(catalog):
    return catalog["entries"][0]


def _mild_entry(catalog):
    """An entry that needs no advise_stop as committed (severity < 8, no high-risk subsystem)."""
    return next(
        e for e in catalog["entries"] if not e["advise_stop"] and e["rating"]["severity"] < 8
    )


@pytest.mark.parametrize(
    ("mutate", "parts"),
    [
        (lambda e: e.update(id="chg-3"), ("id must match",)),
        (lambda e: e.update(subsystem="engine"), ("subsystem must be one of",)),
        (lambda e: e.pop("action"), ("missing key 'action'",)),
        (lambda e: e.update(bogus=1), ("unknown key 'bogus'",)),
        (lambda e: e.update(root_cause=" "), ("root_cause",)),
        (lambda e: e.update(detectable_now="no"), ("detectable_now",)),
        (lambda e: e.update(symptoms=[]), ("symptoms must be a non-empty list",)),
        (lambda e: e["symptoms"][0].update(direction="sideways"), ("direction",)),
        (lambda e: e["symptoms"][0].update(signal="BATTERY"), ("signal must be",)),
        (lambda e: e["symptoms"][0].update(window="W9_NONE"), ("window", "W9_NONE")),
        (lambda e: e["symptoms"][0].update(condition=""), ("condition",)),
        (lambda e: e.update(needs=["did.BATTERY_VOLTAGE"]), ("not listed in needs",)),
        (lambda e: e["rating"].update(severity=11), ("rating.severity",)),
        (lambda e: e["rating"].update(occurrence=True), ("rating.occurrence",)),
        (lambda e: e["rating"].pop("detectability"), ("rating must have",)),
        (lambda e: e.update(sources=[{"ref": "x", "confidence": "certain"}]), ("sources[0]",)),
        (lambda e: e.update(sources="manual"), ("sources must be a list",)),
    ],
)
def test_schema_violations(catalog, applic, refs, mutate, parts):
    mutate(_entry(catalog))
    assert _has(_check(catalog, applic, refs), *parts)


def test_duplicate_id(catalog, applic, refs):
    catalog["entries"].append(copy.deepcopy(_entry(catalog)))
    assert _has(_check(catalog, applic, refs), "duplicate id")


def test_applies_unknown_id(catalog, applic, refs):
    applic["applies"].append("XXX-999")
    assert _has(_check(catalog, applic, refs), "XXX-999", "not a catalog entry")


def test_applied_entry_with_undefined_signal(catalog, applic, refs):
    e = _entry(catalog)
    e["symptoms"][0]["signal"] = "did.NOT_A_DID"
    e["needs"].append("did.NOT_A_DID")
    assert _has(_check(catalog, applic, refs), "did.NOT_A_DID", "not defined")


def test_unapplied_entry_may_name_other_signals(catalog, applic, refs):
    e = copy.deepcopy(_entry(catalog))
    e["id"] = "TST-999"
    e["symptoms"][0]["signal"] = "did.NOT_A_DID"
    e["needs"].append("did.NOT_A_DID")
    catalog["entries"].append(e)
    assert _check(catalog, applic, refs) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.update(subsystem="brakes_abs"),
        lambda e: e.update(subsystem="wheels_tyres"),
        lambda e: e.update(subsystem="suspension_steering"),
        lambda e: e.update(subsystem="fuel_air", root_cause="Fuel line LEAK"),
        lambda e: e["rating"].update(severity=8),
    ],
)
def test_advise_stop_required(catalog, applic, refs, mutate):
    e = _mild_entry(catalog)
    mutate(e)
    assert _has(_check(catalog, applic, refs), "advise_stop: true")
    e["advise_stop"] = True
    assert _check(catalog, applic, refs) == []


@pytest.mark.parametrize("phrase", ["It is Safe To Ride on.", "You are safe to continue."])
def test_rider_text_never_says_safe(catalog, applic, refs, phrase):
    _entry(catalog)["rider_text"] = phrase
    assert _has(_check(catalog, applic, refs), "rider_text must never say")


@pytest.mark.parametrize(
    ("sources", "shown"),
    [
        ([], False),
        ([{"ref": "a", "confidence": "low"}], False),
        ([{"ref": "a", "confidence": "low"}, {"ref": "b", "confidence": "medium"}], True),
        ([{"ref": "a", "confidence": "high"}], True),
    ],
)
def test_displayable_rule(sources, shown):
    assert faults.displayable({"sources": sources}) is shown


def test_generated_content(catalog, applic):
    text = faults.generate_python(catalog, applic)
    ns: dict = {}
    exec(text, ns)  # noqa: S102 - generated file, own output
    assert text.startswith('"""GENERATED by vehicle-defs')
    assert ns["APPLIES_CL250"] == tuple(applic["applies"])
    assert set(ns["FAULTS"]) == {e["id"] for e in catalog["entries"]}
    for e in catalog["entries"]:
        gen = ns["FAULTS"][e["id"]]
        assert gen["displayable"] is faults.displayable(e)
        assert gen["rating"] == e["rating"]
        assert gen["detectable_now"] is e["detectable_now"]
    # Every displayable entry rests on a high/medium source (D-084 item 5).
    for v in ns["FAULTS"].values():
        if v["displayable"]:
            assert any(src["confidence"] in ("high", "medium") for src in v["sources"])


def test_generated_file_has_no_drift():
    py = config.GEN_DIR / "python" / "vehicle_defs" / "faults.py"
    files = render_all(with_vss=False)
    assert files[py.relative_to(config.GEN_DIR)] == py.read_text(encoding="utf-8")


def test_an_intake_air_leak_is_not_a_fuel_leak(catalog, applic, refs):
    e = _mild_entry(catalog)
    e.update(subsystem="fuel_air", root_cause="Intake (vacuum) leak at the throttle body")
    assert _check(catalog, applic, refs) == []
    e["root_cause"] = "Leaking fuel injector seal"
    assert _has(_check(catalog, applic, refs), "advise_stop: true")


# --- complaints and locale files (D-127) ---


@pytest.fixture
def locales():
    return copy.deepcopy(faults.load_locales(config.FAULT_I18N_DIR))


def test_committed_locales_are_consistent(catalog, locales):
    assert "tr" in locales
    assert faults.check_locales(catalog, locales) == []


@pytest.mark.parametrize(
    ("value", "parts"),
    [
        ([], ("complaints", "non-empty list")),
        ("ticking", ("complaints", "non-empty list")),
        ([" "], ("complaints", "non-empty")),
        (["Ticking", "ticking"], ("complaints", "twice")),
    ],
)
def test_complaints_schema(catalog, applic, refs, value, parts):
    _entry(catalog)["complaints"] = value
    assert _has(_check(catalog, applic, refs), *parts)


def test_complaints_are_optional(catalog, applic, refs):
    _entry(catalog).pop("complaints", None)
    assert _check(catalog, applic, refs) == []


def test_locale_unknown_id(catalog, locales):
    locales["tr"]["complaints"]["ZZZ-999"] = ["x"]
    assert _has(faults.check_locales(catalog, locales), "ZZZ-999", "not a catalog entry")


def test_locale_unknown_locale(catalog, locales):
    locales["xx"] = {"schema_version": 1, "locale": "xx", "complaints": {}}
    assert _has(faults.check_locales(catalog, locales), "xx", "unknown locale")


def test_locale_name_must_match_file(catalog, locales):
    locales["tr"]["locale"] = "de"
    assert _has(faults.check_locales(catalog, locales), "must equal the file name")


def test_locale_phrases_must_be_lists_of_text(catalog, locales):
    first = next(iter(locales["tr"]["complaints"]))
    locales["tr"]["complaints"][first] = "not a list"
    assert _has(faults.check_locales(catalog, locales), first, "non-empty list")


def test_sensorless_entry_rules(catalog, applic, refs):
    e = next(x for x in catalog["entries"] if x["subsystem"] == "engine_mechanical")
    assert e["symptoms"] == [] and e["needs"] == [] and e["detectable_now"] is False
    assert _check(catalog, applic, refs) == []
    e["detectable_now"] = True
    assert _has(_check(catalog, applic, refs), "detectable_now: false")
    e["detectable_now"] = False
    e["subsystem"] = "charging"
    assert _has(_check(catalog, applic, refs), "symptoms must be a non-empty list")


def test_valve_complaint_matches_the_rider_report(catalog):
    """The rider's own words ('valves make a noise') must reach a catalog entry."""
    hits = [e["id"] for e in catalog["entries"] if "valves make a noise" in e.get("complaints", [])]
    assert hits == ["ENG-001"]


def test_generated_complaints(catalog, applic, locales):
    ns: dict = {}
    exec(faults.generate_python(catalog, applic, locales), ns)  # noqa: S102 - own output
    for e in catalog["entries"]:
        assert ns["FAULTS"][e["id"]]["complaints"] == tuple(e.get("complaints", ()))
    assert set(ns["COMPLAINTS_I18N"]) == set(locales)
    tr = ns["COMPLAINTS_I18N"]["tr"]
    assert set(tr) == set(locales["tr"]["complaints"])
    assert all(isinstance(v, tuple) and v for v in tr.values())
    assert set(tr) <= set(ns["FAULTS"])


def test_displayable_entries_have_complaints(catalog):
    """A displayable entry nobody can reach by words is dead weight; most carry complaints."""
    shown = [e for e in catalog["entries"] if faults.displayable(e)]
    assert shown
    assert all(e.get("complaints") for e in shown)
