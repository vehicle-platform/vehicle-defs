"""D-020 allow-list and evidence rules for uds/vehicle_cl250.yaml."""

import pytest

from vehicle_codegen import config
from vehicle_codegen.yaml_checks import (
    check_vehicle,
    did_fault_gap_bounds,
    did_sample_gap_bounds,
    frame_allowed,
    request_allowed,
    single_frame,
)

# The verified legacy DIDs; the D-068 unverified DIDs follow them in the table.
CORE_FIVE = ("ENGINE_SPEED", "VEHICLE_SPEED", "THROTTLE_POS", "COOLANT_TEMP", "BATTERY_VOLTAGE")


def test_unverified_dids_come_last_in_the_normal_class(vehicle, platform_db):
    # D-068 item 1: the core DIDs never queue behind more than one unverified read.
    names = [d["name"] for d in vehicle["dids"]]
    assert names[: len(CORE_FIVE)] == list(CORE_FIVE)
    assert all(d["verified"] for d in vehicle["dids"][: len(CORE_FIVE)])
    assert all(
        not d["verified"] and d["priority"] == "normal" for d in vehicle["dids"][len(CORE_FIVE) :]
    )
    moved = vehicle["dids"].pop(0)
    vehicle["dids"].append(moved)
    errs = check_vehicle(vehicle, platform_db)
    assert any("verified DID after the unverified DID" in e for e in errs)


def test_a_non_bool_verified_fails(vehicle, platform_db):
    vehicle["dids"][-1]["verified"] = 0
    errs = check_vehicle(vehicle, platform_db)
    assert any("verified must be true or false" in e for e in errs)


def test_an_unverified_high_priority_did_fails(vehicle, platform_db):
    vehicle["dids"][-1]["priority"] = "high"
    errs = check_vehicle(vehicle, platform_db)
    assert any("unverified DID must be priority normal (D-068)" in e for e in errs)


def test_policy_allowing_a_forbidden_service_fails(vehicle, platform_db):
    vehicle["tester_policy"]["allowed"].append({"sid": 0x2E, "name": "WriteDataByIdentifier"})
    assert any("forbidden service 0x2E" in e for e in check_vehicle(vehicle, platform_db))


def test_programming_session_is_never_allowed(vehicle, platform_db):
    vehicle["tester_policy"]["allowed"][0]["subfunctions"].append(0x02)
    vehicle["session"]["start"]["request"] = [0x10, 0x02]
    errs = check_vehicle(vehicle, platform_db)
    assert any("0x10 0x02" in e for e in errs)
    assert any("session.start" in e for e in errs)


def test_forbidden_list_must_match_d020(vehicle, platform_db):
    vehicle["tester_policy"]["forbidden"].remove(0x14)
    assert any("differs from the D-020" in e for e in check_vehicle(vehicle, platform_db))


def test_verified_needs_evidence(vehicle, platform_db):
    vehicle["dids"][0]["evidence"] = []
    assert any("without file:line evidence" in e for e in check_vehicle(vehicle, platform_db))


def test_platform_signal_must_exist(vehicle, platform_db):
    vehicle["dids"][0]["platform_signal"] = "VehicleEngine.NOPE"
    assert any("not found in platform.dbc" in e for e in check_vehicle(vehicle, platform_db))


@pytest.mark.parametrize("prio", ["safety", "HIGH", 1, None])
def test_priority_must_be_a_known_class(vehicle, platform_db, prio):
    vehicle["dids"][0]["priority"] = prio
    assert any("priority must be one of" in e for e in check_vehicle(vehicle, platform_db))


def test_priority_is_required(vehicle, platform_db):
    del vehicle["dids"][0]["priority"]
    assert any("missing ['priority']" in e for e in check_vehicle(vehicle, platform_db))


def test_vehicle_speed_is_the_only_high_priority_did(vehicle):
    # D-043 item 2: 0xF40D feeds the rt-core EKF lean estimate.
    high = [d["did"] for d in vehicle["dids"] if d["priority"] == "high"]
    assert high == [0xF40D]


def test_python_vehicle_module_decodes(vehicle):
    ns: dict = {}
    exec((config.GEN_DIR / "python" / "vehicle_defs" / "vehicle_cl250.py").read_text(), ns)  # noqa: S102
    assert ns["decode"]("VEHICLE_SPEED", b"\x3c") == 60.0
    assert ns["decode"]("ENGINE_SPEED", b"\x1a\xf8") == 1726.0
    assert ns["PRIORITIES"] == ("high", "normal")
    assert {n: t[9] for n, t in ns["DIDS"].items()} == {
        d["name"]: d["priority"] for d in vehicle["dids"]
    }


def test_duplicate_did(vehicle, platform_db):
    vehicle["dids"][1]["did"] = vehicle["dids"][0]["did"]
    assert any("duplicate" in e for e in check_vehicle(vehicle, platform_db))


@pytest.mark.parametrize(
    ("payload", "allowed"),
    [
        ([0x10, 0x03], True),
        ([0x10, 0x83], True),  # suppressPosRsp bit is ignored
        ([0x10, 0x01], True),
        ([0x10, 0x02], False),
        ([0x10, 0x82], False),
        ([0x10], False),
        ([0x3E, 0x80], True),
        ([0x3E, 0x01], False),
        ([0x22, 0xF4, 0x0C], True),
        ([0x19, 0x02, 0xFF], True),
        ([0x19, 0x01, 0x0C], True),
        ([0x19, 0x04, 0x01, 0x02, 0x03, 0xFF], True),
        ([0x19, 0x06, 0x01, 0x02, 0x03, 0xFF], True),
        ([0x19, 0x0A], False),  # E-23: only the D-080 / scan sub-functions
        ([0x19, 0x03], False),
        ([0x19], False),
        ([0x01, 0x0C], True),
        ([0x09, 0x02], True),
        ([], False),
        *[([sid, 0x00], False) for sid in sorted(config.FORBIDDEN_VEHICLE_SERVICES)],
        ([0x85, 0x02], False),  # ControlDTCSetting: not on the allow-list
    ],
)
def test_request_allowed(vehicle, payload, allowed):
    assert request_allowed(vehicle["tester_policy"], payload) is allowed


@pytest.mark.parametrize("sid", [0x28, 0x85, 0x3D, 0x04, 0x2A])
def test_policy_wider_than_d020_fails(vehicle, platform_db, sid):
    vehicle["tester_policy"]["allowed"].append({"sid": sid, "name": "not allowed"})
    assert any("not on the D-020 allow-list" in e for e in check_vehicle(vehicle, platform_db))
    with pytest.raises(ValueError):
        config.assert_policy_within_d020(vehicle["tester_policy"])


@pytest.mark.parametrize("sid", [0x3E, 0x19])
def test_any_subfunction_fails(vehicle, platform_db, sid):
    entry = next(e for e in vehicle["tester_policy"]["allowed"] if e["sid"] == sid)
    del entry["subfunctions"]
    assert any("exceed D-020" in e for e in check_vehicle(vehicle, platform_db))


def test_read_dtc_extra_subfunction_fails(vehicle, platform_db):
    entry = next(e for e in vehicle["tester_policy"]["allowed"] if e["sid"] == 0x19)
    entry["subfunctions"].append(0x0A)  # E-23: reportSupportedDTC is not on the list
    assert any("exceed D-020" in e for e in check_vehicle(vehicle, platform_db))


def test_stale_after_must_exceed_poll_period(vehicle, platform_db):
    vehicle["dids"][0]["stale_after_ms"] = vehicle["dids"][0]["poll_period_ms"]
    assert any("stale_after_ms" in e for e in check_vehicle(vehicle, platform_db))


def _gap_bounds(vehicle):
    return did_sample_gap_bounds(vehicle["dids"], vehicle["timing"]["assumed_round_trip_ms"])


def test_sample_gap_bounds_of_the_table_are_within_stale_after(vehicle):
    # D-043 no starvation, worked by hand for the table at C = 20 ms (RPM and speed at
    # 110 ms, D-053): speed (high, P110): w = 20 -> 150; RPM (P110): w = 20 + 20 = 40 -> 170;
    # throttle (P200): w = 60 -> 280; coolant (P800): w = 80 -> 900;
    # battery (P800): w = 100 -> 920.
    # D-068: the unverified DIDs sit after these five in the normal class, so the five
    # bounds are the same as without them.
    assert vehicle["timing"]["assumed_round_trip_ms"] == 20
    bounds = _gap_bounds(vehicle)
    assert {k: bounds[k] for k in CORE_FIVE} == {
        "VEHICLE_SPEED": 150,
        "ENGINE_SPEED": 170,
        "THROTTLE_POS": 280,
        "COOLANT_TEMP": 900,
        "BATTERY_VOLTAGE": 920,
    }
    for d in vehicle["dids"]:
        assert bounds[d["name"]] <= d["stale_after_ms"]


def test_a_stale_after_below_the_sample_gap_bound_fails(vehicle, platform_db):
    rpm = next(d for d in vehicle["dids"] if d["name"] == "ENGINE_SPEED")
    rpm["stale_after_ms"] = 169  # bound 170
    errs = check_vehicle(vehicle, platform_db)
    assert any("ENGINE_SPEED: worst-case sample gap 170 ms > stale_after_ms 169" in e for e in errs)
    rpm["stale_after_ms"] = 170
    assert not any("sample gap" in e for e in check_vehicle(vehicle, platform_db))


def test_the_bound_follows_the_priority_order(vehicle):
    # Making throttle high puts it ahead of RPM: RPM's interference grows.
    before = _gap_bounds(vehicle)
    next(d for d in vehicle["dids"] if d["name"] == "THROTTLE_POS")["priority"] = "high"
    after = _gap_bounds(vehicle)
    assert after["ENGINE_SPEED"] > before["ENGINE_SPEED"]
    assert after["THROTTLE_POS"] < before["THROTTLE_POS"]


def test_an_overloaded_table_is_unbounded_and_fails(vehicle, platform_db):
    for d in vehicle["dids"]:
        d["poll_period_ms"] = 30
        d["stale_after_ms"] = 60
    errs = check_vehicle(vehicle, platform_db)
    assert any("polling budget" in e for e in errs)
    assert any("worst-case sample gap unbounded" in e for e in errs)


def _fault_bounds(vehicle, step=None):
    t = vehicle["timing"]
    return did_fault_gap_bounds(
        vehicle["dids"],
        t["assumed_round_trip_ms"],
        t["response_timeout_base_ms"],
        t["max_consecutive_timeouts"],
        t["client_step_max_ms"] if step is None else step,
    )


def test_fault_gap_bounds_of_the_table_are_within_stale_after(vehicle):
    # D-050..D-053, worked by hand (B = 100, S = 10, so a faulty read holds the slot for
    # H = B + S = 110; C = 20; RPM and speed at P = 110; any one DID faulty, its reads
    # alternate P_f and P_f + B apart, at most 2 * 5 - 2 = 8 after the blocking one):
    # RPM: throttle, coolant or battery faulty (normal DIDs, E-8 (2)): w = H + 2 * C
    #   (speed) = 150 -> 260;
    # speed: only the blocking read is ahead of it: w = H = 110 -> 220;
    # throttle: RPM or speed faulty: w = H + 1 * H + 3 * C = 280 -> 480;
    # coolant: RPM or speed faulty: w = H + 5 * H + 14 * C = 940 -> 1740;
    # battery: RPM or speed faulty: w = H + 8 * H (the cap) + 24 * C = 1470 -> 2270.
    t = vehicle["timing"]
    assert (t["assumed_round_trip_ms"], t["response_timeout_base_ms"]) == (20, 100)
    assert (t["client_step_max_ms"], t["max_consecutive_timeouts"]) == (10, 5)
    # D-068: unchanged by the unverified DIDs after them (only the blocking read).
    fault = _fault_bounds(vehicle)
    assert {k: fault[k] for k in CORE_FIVE} == {
        "ENGINE_SPEED": 260,
        "VEHICLE_SPEED": 220,
        "THROTTLE_POS": 480,
        "COOLANT_TEMP": 1740,
        "BATTERY_VOLTAGE": 2270,
    }
    for d in vehicle["dids"]:
        assert fault[d["name"]] <= d["stale_after_ms"]
    assert not any("fault-mode" in e for e in check_vehicle(vehicle, None))


def test_a_faulty_read_holds_the_slot_until_the_step_that_sees_its_timeout(vehicle):
    # Safety review MINOR-1 on D-053: the tester ends a faulty read at the step that sees
    # its base timeout, up to one step after it, so the model holds B + S per faulty read.
    without, with_step = _fault_bounds(vehicle, step=0), _fault_bounds(vehicle)
    assert (without["VEHICLE_SPEED"], with_step["VEHICLE_SPEED"]) == (210, 220)
    assert all(with_step[n] >= without[n] for n in without)


def test_a_round_trip_not_above_the_step_is_refused(vehicle, platform_db):
    # assumed_round_trip_ms covers the ECU's answer plus one step (D-043, D-053).
    vehicle["timing"]["assumed_round_trip_ms"] = 10
    errs = check_vehicle(vehicle, platform_db)
    assert any(
        "timing.assumed_round_trip_ms 10 must exceed client_step_max_ms 10" in e for e in errs
    )


def test_a_poll_period_below_the_base_timeout_is_refused(vehicle, platform_db):
    # D-052 (ISSUES E-8 (1)): with the legacy 50 ms, an RPM answer at 51-99 ms (no NRC 0x78)
    # made RPM due again at once and starved the later normal DIDs.
    rpm = next(d for d in vehicle["dids"] if d["name"] == "ENGINE_SPEED")
    rpm["poll_period_ms"], rpm["stale_after_ms"] = 50, 150
    errs = check_vehicle(vehicle, platform_db)
    assert any(
        "ENGINE_SPEED: poll_period_ms 50 < response_timeout_base_ms 100 + client_step_max_ms 10"
        in e
        for e in errs
    )
    # The fault-mode model needs the rule, so it is not evaluated without it.
    assert not any("fault-mode" in e for e in errs)


def test_a_poll_period_equal_to_the_base_timeout_is_refused(vehicle, platform_db):
    # D-053 (ISSUES E-9): at P = B an answer just inside B, seen by a late step, makes its
    # DID due again at once with no timeout and no skip. One step more is required.
    for d in vehicle["dids"]:
        if d["name"] in ("ENGINE_SPEED", "VEHICLE_SPEED"):
            d["poll_period_ms"] = 100
    errs = check_vehicle(vehicle, platform_db)
    for name in ("ENGINE_SPEED", "VEHICLE_SPEED"):
        assert any(
            f"{name}: poll_period_ms 100 < response_timeout_base_ms 100 + client_step_max_ms 10"
            " (D-052, D-053)" in e
            for e in errs
        )
    for d in vehicle["dids"]:
        if d["name"] in ("ENGINE_SPEED", "VEHICLE_SPEED"):
            d["poll_period_ms"] = 110
    assert not any("D-053" in e for e in check_vehicle(vehicle, platform_db))


def test_a_base_timeout_plus_step_above_a_period_is_refused(vehicle, platform_db):
    for key, value in (("response_timeout_base_ms", 101), ("client_step_max_ms", 11)):
        saved = vehicle["timing"][key]
        vehicle["timing"][key] = value
        errs = check_vehicle(vehicle, platform_db)
        for name in ("ENGINE_SPEED", "VEHICLE_SPEED"):
            assert any(f"{name}: poll_period_ms 110 < response_timeout_base_ms" in e for e in errs)
        vehicle["timing"][key] = saved
    assert not any("D-053" in e for e in check_vehicle(vehicle, platform_db))


@pytest.mark.parametrize("value", [None, 0, -5, "10", True])
def test_client_step_max_is_required_for_the_period_rule(vehicle, platform_db, value):
    if value is None:
        del vehicle["timing"]["client_step_max_ms"]
    else:
        vehicle["timing"]["client_step_max_ms"] = value
    errs = check_vehicle(vehicle, platform_db)
    assert any("timing.client_step_max_ms must be a positive integer" in e for e in errs)
    # Without the step the period rule and the fault-mode model are not evaluated.
    assert not any("fault-mode" in e for e in errs)


def test_a_normal_did_ahead_of_rpm_breaks_the_fault_mode_bound(vehicle, platform_db):
    # RPM's 260 ms relies on no normal DID being ahead of it in table order.
    dids = vehicle["dids"]
    rpm = next(i for i, d in enumerate(dids) if d["name"] == "ENGINE_SPEED")
    tps = next(i for i, d in enumerate(dids) if d["name"] == "THROTTLE_POS")
    dids[rpm], dids[tps] = dids[tps], dids[rpm]
    errs = check_vehicle(vehicle, platform_db)
    assert not any("worst-case sample gap" in e for e in errs)  # the nominal bound holds
    assert any(
        "ENGINE_SPEED: fault-mode request gap 370 ms > stale_after_ms 330" in e for e in errs
    )


def test_a_faulty_normal_did_sets_the_rpm_fault_bound(vehicle, platform_db):
    # ISSUES E-8 (2): the worst case for RPM is a faulty normal DID behind it (its read
    # just started), which the D-051 check did not model: P + H + 2 * C (speed) = 260.
    next(d for d in vehicle["dids"] if d["name"] == "ENGINE_SPEED")["stale_after_ms"] = 259
    errs = check_vehicle(vehicle, platform_db)
    assert any(
        "ENGINE_SPEED: fault-mode request gap 260 ms > stale_after_ms 259" in e for e in errs
    )


def test_slow_answers_between_timeouts_count_toward_the_faulty_reads(vehicle):
    # D-052 (ISSUES E-8 (3)): a slow answer does not reset the skip count, so each
    # timeout before the skip may come with one slow answer, and the first failing read
    # may itself be a slow answer: 2 * max - 1 faulty reads after it, 2 * max - 2 after the
    # blocking one (safety review MINOR-1). Battery's window reaches the cap: 4 at max 3,
    # 8 at max 5.
    dids, t = vehicle["dids"], vehicle["timing"]
    rtt, base, step = (
        t["assumed_round_trip_ms"],
        t["response_timeout_base_ms"],
        t["client_step_max_ms"],
    )
    assert did_fault_gap_bounds(dids, rtt, base, 3, step)["BATTERY_VOLTAGE"] == 1650
    assert did_fault_gap_bounds(dids, rtt, base, 5, step)["BATTERY_VOLTAGE"] == 2270


def test_without_the_skip_a_faulty_did_starves_the_slow_dids(vehicle, platform_db):
    # The skip after max_consecutive_timeouts caps the faulty reads; without it a faulty
    # RPM or speed, with the others, fills battery's window.
    vehicle["timing"]["max_consecutive_timeouts"] = 100
    errs = check_vehicle(vehicle, platform_db)
    assert any(
        "BATTERY_VOLTAGE: fault-mode request gap unbounded > stale_after_ms 2400" in e for e in errs
    )


def test_without_a_high_priority_did_every_did_is_still_covered(vehicle, platform_db):
    # Since D-052 any one DID may be faulty, not only a demoted high one. Every DID gets a
    # finite bound; but with speed behind RPM in table order a faulty RPM read (H = 110)
    # pushes speed to 110 + 110 + 110 = 330 > 300, so speed needs its high priority.
    for d in vehicle["dids"]:
        d["priority"] = "normal"
    bounds = _fault_bounds(vehicle)
    assert set(bounds) == {d["name"] for d in vehicle["dids"]}
    assert all(b is not None for b in bounds.values())
    errs = [e for e in check_vehicle(vehicle, platform_db) if "fault-mode" in e]
    assert len(errs) == 1
    assert "VEHICLE_SPEED: fault-mode request gap 330 ms > stale_after_ms 300" in errs[0]


@pytest.mark.parametrize("value", [None, 0, -5, "20", True])
def test_assumed_round_trip_is_required_for_the_budget_and_gap_checks(vehicle, platform_db, value):
    if value is None:
        del vehicle["timing"]["assumed_round_trip_ms"]
    else:
        vehicle["timing"]["assumed_round_trip_ms"] = value
    errs = check_vehicle(vehicle, platform_db)
    assert any("timing.assumed_round_trip_ms must be a positive integer" in e for e in errs)


def test_budget_within_0_8_but_gap_bound_failing_is_refused(vehicle, platform_db):
    # Budget 0.0257 * 21 = 0.54 passes; RPM's bound at C = 21 is 110 + 42 + 21 = 173.
    vehicle["timing"]["assumed_round_trip_ms"] = 21
    next(d for d in vehicle["dids"] if d["name"] == "ENGINE_SPEED")["stale_after_ms"] = 172
    errs = check_vehicle(vehicle, platform_db)
    assert not any("polling budget" in e for e in errs)
    assert any("ENGINE_SPEED: worst-case sample gap 173 ms > stale_after_ms 172" in e for e in errs)


@pytest.mark.parametrize("key", ["response_timeout_base_ms", "did_skip_cooldown_ms"])
def test_a_bool_timing_value_is_refused(vehicle, platform_db, key):
    # YAML `true` is an int subclass in Python and would pass as 1 ms (E-6 n3).
    vehicle["timing"][key] = True
    errs = check_vehicle(vehicle, platform_db)
    assert any(f"timing.{key} must be a positive integer" in e for e in errs)


def test_requests_in_flight_true_is_not_one(vehicle, platform_db):
    vehicle["timing"]["requests_in_flight"] = True
    errs = check_vehicle(vehicle, platform_db)
    assert any("requests_in_flight must be 1" in e for e in errs)


@pytest.mark.parametrize("key", ["poll_period_ms", "stale_after_ms"])
def test_a_bool_did_period_is_refused(vehicle, platform_db, key):
    vehicle["dids"][0][key] = True
    errs = check_vehicle(vehicle, platform_db)
    assert any("poll_period_ms and stale_after_ms must be positive integers" in e for e in errs)


# --- D-059: the one FC.CTS (golden copy) and the discovery scan ---


def test_current_flow_control_and_scan_pass(vehicle, platform_db):
    errs = check_vehicle(vehicle, platform_db)
    assert not [e for e in errs if "flow_control" in e or "discovery" in e], errs


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("flow_status", 0x1, "ContinueToSend"),  # WAIT
        ("flow_status", 0x2, "ContinueToSend"),  # OVFLW
        ("block_size", 8, "one FC per reception"),
        ("st_min_ms", 0xF1, "0..127"),  # 100 us units
        ("st_min_ms", True, "0..127"),
        ("padding_byte", 0x00, "a byte equal to transport.padding_byte"),
        ("max_ff_dl", 4096, "8..4095"),  # 32-bit FF_DL escape
        ("max_ff_dl", 7, "8..4095"),  # fits a Single Frame
        ("flow_status", False, "ContinueToSend"),  # YAML bool, not an int
        ("block_size", False, "one FC per reception"),
        ("padding_byte", True, "a byte equal to transport.padding_byte"),
        ("padding_byte", 0x1AA, "a byte equal to transport.padding_byte"),
    ],
)
def test_flow_control_outside_the_golden_copy_fails(vehicle, platform_db, key, value, message):
    vehicle["transport"]["flow_control"][key] = value
    errs = check_vehicle(vehicle, platform_db)
    assert any(message in e for e in errs), errs
    with pytest.raises(ValueError):
        config.vehicle_fc_frame(vehicle["transport"])


def test_missing_flow_control_fails(vehicle, platform_db):
    del vehicle["transport"]["flow_control"]
    assert any("flow_control missing" in e for e in check_vehicle(vehicle, platform_db))


def test_generator_refuses_a_widened_flow_control(vehicle):
    from vehicle_codegen import gen_c

    vehicle["transport"]["flow_control"]["block_size"] = 1
    with pytest.raises(ValueError):
        gen_c.generate_vehicle_c(vehicle)


def test_generator_refuses_a_bad_scan_entry(vehicle):
    from vehicle_codegen import gen_c

    vehicle["discovery_scan"]["requests"].append({"name": "CLEAR", "request": [0x04]})
    with pytest.raises(ValueError):
        gen_c.generate_vehicle_c(vehicle)


def test_cf_burst_follows_max_ff_dl(vehicle):
    assert config.vehicle_fc_max_cf_burst(vehicle["transport"]) == 36  # ceil(249 / 7)
    for ff_dl, burst in ((8, 1), (13, 1), (14, 2), (4095, 585)):
        vehicle["transport"]["flow_control"]["max_ff_dl"] = ff_dl
        assert config.vehicle_fc_max_cf_burst(vehicle["transport"]) == burst


def test_fc_frame_is_byte_exact(vehicle):
    assert config.vehicle_fc_frame(vehicle["transport"]) == bytes([0x30, 0, 0] + [0xAA] * 5)


def test_frame_gate_twin_passes_only_sf_requests_and_the_fc(vehicle):
    fc = config.vehicle_fc_frame(vehicle["transport"])
    assert frame_allowed(vehicle, fc)
    assert not frame_allowed(vehicle, fc[:7])
    assert not frame_allowed(vehicle, bytes([0x10, 0x14]) + fc[2:])  # First Frame
    assert not frame_allowed(vehicle, bytes([0x21]) + fc[1:])  # Consecutive Frame
    assert frame_allowed(vehicle, single_frame(vehicle, [0x09, 0x02]))
    assert not frame_allowed(vehicle, single_frame(vehicle, [0x04]))  # OBD clear DTCs


def test_scan_has_the_d059_requests(vehicle):
    reqs = [e["request"] for e in vehicle["discovery_scan"]["requests"]]
    assert [0x01, 0x00] in reqs and [0x09, 0x00] in reqs and [0x09, 0x02] in reqs
    assert [0x19, 0x01, 0xFF] in reqs and [0x19, 0x02, 0xFF] in reqs
    assert [0x22, 0xF4, 0x00] in reqs and [0x22, 0xF4, 0x20] in reqs


@pytest.mark.parametrize(
    "request_bytes",
    [[0x04], [0x14, 0xFF, 0xFF, 0xFF][:3], [0x2E, 0xF4, 0x00], [0x10, 0x02], [0x31, 0x01, 0x00]],
)
def test_scan_request_outside_the_policy_fails(vehicle, platform_db, request_bytes):
    vehicle["discovery_scan"]["requests"].append({"name": "BAD", "request": request_bytes})
    errs = check_vehicle(vehicle, platform_db)
    assert any("discovery BAD" in e and "tester_policy" in e for e in errs), errs


def test_scan_request_too_long_fails(vehicle, platform_db):
    vehicle["discovery_scan"]["requests"].append({"name": "LONG", "request": [0x22, 0xF4, 0x0C, 0]})
    assert any("discovery LONG" in e for e in check_vehicle(vehicle, platform_db))


def test_scan_duplicate_request_fails(vehicle, platform_db):
    vehicle["discovery_scan"]["requests"].append({"name": "DUP", "request": [0x09, 0x02]})
    assert any("listed twice" in e for e in check_vehicle(vehicle, platform_db))


def test_scan_chained_bitmap_needs_the_previous_last_bit(vehicle, platform_db):
    entries = vehicle["discovery_scan"]["requests"]
    second = next(e for e in entries if e["request"] == [0x01, 0x20])
    del second["after"]
    errs = check_vehicle(vehicle, platform_db)
    assert any("previous bitmap's last bit" in e for e in errs), errs


def test_scan_after_must_name_an_earlier_bitmap(vehicle, platform_db):
    entries = vehicle["discovery_scan"]["requests"]
    vin = next(e for e in entries if e["request"] == [0x09, 0x02])
    vin["after"] = {"name": "DTC_COUNT", "id": 0x02}
    errs = check_vehicle(vehicle, platform_db)
    assert any("earlier bitmap request" in e for e in errs), errs
    vin["after"] = {"name": "OBD_INFOTYPES_01_20", "id": 0x21}
    errs = check_vehicle(vehicle, platform_db)
    assert any("outside OBD_INFOTYPES_01_20" in e for e in errs), errs


def test_scan_sensitive_flag_is_true_or_absent_and_not_on_a_bitmap(vehicle, platform_db):
    entries = vehicle["discovery_scan"]["requests"]
    vin = next(e for e in entries if e["request"] == [0x09, 0x02])
    assert vin.get("sensitive") is True  # D-033, ISSUES E-15 (1)
    assert [e["name"] for e in entries if e.get("sensitive")] == ["OBD_VIN"]
    vin["sensitive"] = "yes"
    errs = check_vehicle(vehicle, platform_db)
    assert any("sensitive is true or absent" in e for e in errs), errs
    vin["sensitive"] = True
    bitmap = next(e for e in entries if e["request"] == [0x09, 0x00])
    bitmap["sensitive"] = True
    errs = check_vehicle(vehicle, platform_db)
    assert any("not sensitive data" in e for e in errs), errs


def test_scan_vin_request_must_be_sensitive(vehicle, platform_db):
    """safety-reviewer MAJOR-1 (E-15 (1)): a defs data error can never unmask a VIN."""
    entries = vehicle["discovery_scan"]["requests"]
    vin = next(e for e in entries if e["request"] == [0x09, 0x02])
    del vin["sensitive"]
    errs = check_vehicle(vehicle, platform_db)
    assert any("a VIN request must be sensitive" in e for e in errs), errs
