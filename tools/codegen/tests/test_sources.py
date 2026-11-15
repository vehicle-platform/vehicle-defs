"""The committed definitions pass every check."""

from vehicle_codegen import config, gen_vss
from vehicle_codegen.dbc_checks import check_cl250_dbc, check_platform_dbc, load_dbc
from vehicle_codegen.gen_uds import check_dids, check_iso
from vehicle_codegen.yaml_checks import check_vehicle, load_yaml


def test_platform_dbc_is_consistent(platform_db):
    assert check_platform_dbc(platform_db) == []


def test_cl250_dbc_is_a_skeleton():
    db = load_dbc(config.CL250_DBC)
    assert check_cl250_dbc(db) == []
    assert db.messages == []  # Q-001: no passive broadcast known yet


def test_vehicle_yaml_is_consistent(platform_db, vehicle):
    assert check_vehicle(vehicle, platform_db) == []


def test_every_vehicle_did_is_verified_or_a_d068_standard_pid(vehicle):
    # D-068: unverified DIDs are the standard J1979 PIDs over 0xF400 | PID, no evidence.
    for d in vehicle["dids"]:
        if not d["verified"]:
            assert d["did"] == 0xF400 | d["obd_pid"] and d["evidence"] == []


def test_uds_sources_are_consistent(vehicle):
    iso = load_yaml(config.ISO14229_YAML)
    assert check_iso(iso) == []
    assert check_dids(load_yaml(config.DIDS_YAML), iso, vehicle) == []


def test_overlay_maps_existing_signals_only(platform_db):
    overlay = gen_vss.load_overlay()
    # Base paths are checked in test_gen_drift (needs the pinned VSS download).
    errors = [
        e for e in gen_vss.check_overlay(overlay, set(overlay), platform_db) if "COVESA" not in e
    ]
    assert errors == []
    extensions = {p for p in overlay if p.startswith("Vehicle.Motorcycle")}
    assert extensions == set(gen_vss.APPROVED_EXTENSIONS)  # only user-approved paths (D-028)


def test_overlay_rejects_ambiguous_and_unknown_choices(platform_db):
    bad = {
        "Vehicle.Speed": {"dbc2vss": {"signal": "E2E_CRC", "interval_ms": 100}},
        "Vehicle.Motorcycle.IsEcuPresent": {
            "dbc2vss": {
                "signal": "ECU_PRESENT",
                "interval_ms": 100,
                "transform": {"mapping": [{"from": "MAYBE", "to": True}]},
            }
        },
    }
    errors = gen_vss.check_overlay(bad, set(bad), platform_db)
    assert any("ambiguous" in e for e in errors)
    assert any("unknown choice MAYBE" in e for e in errors)
