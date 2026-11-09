"""Negative tests: each rule of the platform ID plan / E2E layout is enforced."""

import re

from conftest import parse_dbc

from vehicle_codegen import config
from vehicle_codegen.dbc_checks import check_platform_dbc


def errors_for(text: str) -> list[str]:
    return check_platform_dbc(parse_dbc(text))


def test_duplicate_data_id_is_rejected(platform_text):
    text = platform_text.replace('BA_ "E2E_DataID" BO_ 33 4129;', 'BA_ "E2E_DataID" BO_ 33 4128;')
    assert any("already used" in e for e in errors_for(text))


def test_safety_range_requires_e2e(platform_text):
    text = platform_text.replace('BA_ "E2E_Protected" BO_ 33 1;', 'BA_ "E2E_Protected" BO_ 33 0;')
    errs = errors_for(text)
    assert any("E2E is mandatory" in e for e in errs)
    assert any("E2E_DataID set but" in e for e in errs)


def test_safety_node_never_receives_vehicle_speed(platform_text):
    # D-041: re-adding SAFETY to 0x021 would regenerate speed code into safety-node.
    text = platform_text.replace('"km/h" CONN,LINUX', '"km/h" SAFETY,CONN,LINUX')
    assert any("VehicleSpeed" in e and "SAFETY may not receive" in e for e in errors_for(text))


def test_safety_node_receives_only_the_allow_list(platform_db):
    got = {m.name for m in platform_db.messages if "SAFETY" in m.receivers}
    assert got == {"EkfLean", "EkfFrictionMass", "HeartbeatRtCore", "SafetyRequest"}
    # D-072 item 7: SafetyRequest is QM and used by the immobilizer alone.
    assert config.SAFETY_RX_SAFETY_INPUTS == {"EkfLean", "EkfFrictionMass", "HeartbeatRtCore"}
    assert config.SAFETY_RX_QM_IMMOBILIZER == {"SafetyRequest"}


def _choices(db, msg, sig):
    signal = db.get_message_by_name(msg).get_signal_by_name(sig)
    return {int(k): str(v) for k, v in signal.choices.items()}


def test_safety_status_and_request_value_tables(platform_db):
    # D-072 item 7 (user, 2026-10-18): raw 0 is the no-information value.
    level = {0: "UNAVAILABLE", 1: "GREEN", 2: "YELLOW", 3: "RED"}
    bsm = {0: "UNAVAILABLE", 1: "CLEAR", 2: "PRESENT", 3: "APPROACHING"}
    assert _choices(platform_db, "SafetyWarningStatus", "CORNERING_LEVEL") == level
    assert _choices(platform_db, "SafetyWarningStatus", "CORNERING_SOURCE") == {
        0: "NONE",
        1: "EKF",
        2: "OWN_IMU",
        3: "RESERVED",
    }
    assert _choices(platform_db, "SafetyWarningStatus", "BSM_LEFT") == bsm
    assert _choices(platform_db, "SafetyWarningStatus", "BSM_RIGHT") == bsm
    assert _choices(platform_db, "SafetyWarningStatus", "IMMOBILIZER_STATE") == {
        0: "UNKNOWN",
        1: "UNLOCKED",
        2: "LOCKED",
        3: "AUTH_PENDING",
        4: "FAULT",
    }
    unknown = {0: "UNKNOWN", 3: "RESERVED"}
    assert _choices(platform_db, "SafetyRequest", "IGNITION_STATE") == {
        **unknown,
        1: "OFF",
        2: "ON",
    }
    assert _choices(platform_db, "SafetyRequest", "PARK_MODE") == {
        **unknown,
        1: "INACTIVE",
        2: "ACTIVE",
    }
    # LOCK = 3: every single-bit error from NONE or LOCK lands on a reserved value.
    assert _choices(platform_db, "SafetyRequest", "IMMOBILIZER_LOCK_REQUEST") == {
        0: "NONE",
        1: "RESERVED",
        2: "RESERVED",
        3: "LOCK",
    }


def test_all_zero_decodes_to_no_information(platform_db):
    for name in ("SafetyWarningStatus", "SafetyRequest"):
        msg = platform_db.get_message_by_name(name)
        decoded = msg.decode(bytes(8), decode_choices=True)
        for sig in msg.signals:
            if sig.choices:
                assert str(decoded[sig.name]) in config.NO_INFORMATION_NAMES, (name, sig.name)


def test_permissive_raw_zero_is_rejected(platform_text):
    text = platform_text.replace(
        'VAL_ 35 BSM_LEFT 0 "UNAVAILABLE" 1 "CLEAR"', 'VAL_ 35 BSM_LEFT 0 "CLEAR" 1 "UNAVAILABLE"'
    )
    assert any("BSM_LEFT raw 0 must mean no information" in e for e in errors_for(text))


def test_missing_data_id_is_rejected(platform_text):
    text = platform_text.replace('BA_ "E2E_DataID" BO_ 34 4130;\n', "")
    assert any("E2E_DataID missing" in e for e in errors_for(text))


def test_e2e_layout_is_enforced(platform_text):
    text = platform_text.replace(
        ' SG_ E2E_COUNTER : 8|4@1+ (1,0) [0|15] "" SAFETY,LINUX\n SG_ LEAN_ANGLE_STATE',
        ' SG_ E2E_COUNTER : 8|3@1+ (1,0) [0|7] "" SAFETY,LINUX\n SG_ LEAN_ANGLE_STATE',
        1,
    )
    assert any("E2E_COUNTER must be 8|4" in e for e in errors_for(text))


def test_heartbeat_id_must_match_sender_node_id(platform_text):
    text = platform_text.replace("BO_ 132 HeartbeatConn: 8 CONN", "BO_ 132 HeartbeatConn: 8 LINUX")
    assert any("0x080 + NodeId" in e for e in errors_for(text))


def test_ids_outside_plan_are_rejected(platform_text):
    for bad_id in (0x005, 0x090, 0x7E0):
        text = re.sub(r"\b272\b", str(bad_id), platform_text)
        assert any("0x" in e and ("range" in e or "outside" in e) for e in errors_for(text)), bad_id


def test_naming_rules(platform_text):
    text = platform_text.replace("VehicleEngine", "vehicle_engine").replace(
        "ECU_PRESENT", "EcuPresent"
    )
    errs = errors_for(text)
    assert any("PascalCase" in e for e in errs)
    assert any("SNAKE_CASE" in e for e in errs)


def test_unknown_node_id_attribute(platform_text):
    text = platform_text.replace('BA_ "NodeId" BU_ SAFETY 2;', 'BA_ "NodeId" BU_ SAFETY 7;')
    assert any("NodeId 7 != 2" in e for e in errors_for(text))


def test_cl250_rejects_diagnostic_ids_and_missing_evidence():
    from vehicle_codegen.dbc_checks import check_cl250_dbc

    text = """VERSION ""
NS_ :
BS_:
BU_: CL250_ECU
BO_ 2564485392 Diag29: 8 CL250_ECU
 SG_ X : 0|8@1+ (1,0) [0|255] "" Vector__XXX
BO_ 2024 Diag11: 8 CL250_ECU
 SG_ Y : 0|8@1+ (1,0) [0|255] "" Vector__XXX
BO_ 256 Broadcast: 8 CL250_ECU
 SG_ Z : 0|8@1+ (1,0) [0|255] "" Vector__XXX
CM_ BO_ 2564485392 "UNVERIFIED - sniffed once";
CM_ BO_ 2024 "VERIFIED - log 3";
"""
    errs = check_cl250_dbc(parse_dbc(text))
    assert any("Diag29" in e and "diagnostic ID" in e for e in errs)
    assert any("Diag11" in e and "diagnostic ID" in e for e in errs)
    assert any("Broadcast" in e and "VERIFIED" in e for e in errs)
    assert not any("Broadcast" in e and "diagnostic" in e for e in errs)


def test_signal_wider_than_the_float_encode_is_rejected(platform_text):
    # ISSUES C-9 (4): the use_float encode has no range check above 24 bits. A fresh parse,
    # never the session fixture, is widened after the strict parse.
    db = parse_dbc(platform_text)
    db.get_message_by_name("VehicleSpeed").get_signal_by_name("VEHICLE_SPEED").length = 25
    errs = check_platform_dbc(db)
    assert any("VEHICLE_SPEED is 25 bits" in e for e in errs)
