"""Reference E2E behaviour (docs/e2e-profile.md)."""

from vehicle_codegen import e2e
from vehicle_codegen.e2e import E2EStatus as S

DATA_ID = 0x1020
T = 60  # timeout ms (3 x 20 ms cycle)


def test_crc8_sae_j1850_check_value():
    # Catalogue check value of CRC-8/SAE-J1850 (init 0xFF, xorout 0xFF).
    assert e2e.crc8_sae_j1850(b"123456789") ^ 0xFF == 0x4B


def frames(n, tx=None):
    tx = tx or e2e.TxState()
    out = []
    for i in range(n):
        buf = bytearray([0, 0x30, i, 0, 0, 0, 0, 0])
        e2e.protect(DATA_ID, buf, tx)
        out.append(bytes(buf))
    return out


def test_counter_and_upper_nibble():
    f = frames(17)
    assert [x[1] & 0x0F for x in f] == [*range(16), 0]
    assert all(x[1] & 0xF0 == 0x30 for x in f)  # other signals in byte 1 untouched


def test_happy_path_then_repeated_then_timeout():
    rx = e2e.RxState()
    f = frames(3)
    assert e2e.check(DATA_ID, 1, T, f[0], rx, 0) == S.INITIAL
    assert e2e.check(DATA_ID, 1, T, f[1], rx, 20) == S.OK
    assert e2e.check(DATA_ID, 1, T, f[1], rx, 40) == S.REPEATED
    assert e2e.check_timeout(rx, 60, 70) == S.OK
    assert e2e.check_timeout(rx, 60, 81) == S.NO_NEW_DATA
    assert e2e.check(DATA_ID, 1, T, f[2], rx, 90) == S.INITIAL  # resync after timeout


def test_lost_frames():
    f = frames(5)
    rx = e2e.RxState()
    e2e.check(DATA_ID, 1, T, f[0], rx, 0)
    assert e2e.check(DATA_ID, 1, T, f[2], rx, 1) == S.WRONG_SEQUENCE
    assert e2e.check(DATA_ID, 1, T, f[3], rx, 2) == S.OK
    rx2 = e2e.RxState()
    e2e.check(DATA_ID, 2, T, f[0], rx2, 0)
    assert e2e.check(DATA_ID, 2, T, f[2], rx2, 1) == S.OK_SOME_LOST


def test_corruption_and_masquerade_are_detected():
    f = frames(2)
    rx = e2e.RxState()
    e2e.check(DATA_ID, 1, T, f[0], rx, 0)
    bad = bytearray(f[1])
    bad[5] ^= 0x01
    assert e2e.check(DATA_ID, 1, T, bytes(bad), rx, 1) == S.WRONG_CRC
    assert e2e.check(DATA_ID + 1, 1, T, f[1], rx, 1) == S.WRONG_CRC  # wrong DataID
    for bit in range(64):  # every single-bit error in the frame
        b = bytearray(f[1])
        b[bit // 8] ^= 1 << (bit % 8)
        assert e2e.check(DATA_ID, 1, T, bytes(b), e2e.RxState(), 0) == S.WRONG_CRC


def test_timeout_wraps_around_uint32():
    rx = e2e.RxState()
    e2e.check(DATA_ID, 1, T, frames(1)[0], rx, 0xFFFFFFF0)
    assert e2e.check_timeout(rx, 60, 0x10) == S.OK  # 0x20 ms elapsed across the wrap
    assert e2e.check_timeout(rx, 60, 0x40) == S.NO_NEW_DATA


def test_bad_arguments():
    assert e2e.check(DATA_ID, 1, T, b"\x00", e2e.RxState(), 0) == S.BAD_ARGUMENT
    assert e2e.check(DATA_ID, 0, T, bytes(8), e2e.RxState(), 0) == S.BAD_ARGUMENT
    assert e2e.check(DATA_ID, 15, T, bytes(8), e2e.RxState(), 0) == S.BAD_ARGUMENT


def test_only_ok_statuses_are_valid():
    assert {s for s in S if e2e.is_valid(s)} == {S.OK, S.OK_SOME_LOST}


def test_stalled_sender_never_resumes_as_ok():
    f = frames(3)
    rx = e2e.RxState()
    e2e.check(DATA_ID, 1, T, f[0], rx, 0)
    # 1000 ms stall, then counter + 1: must resync, not OK (even without check_timeout)
    assert e2e.check(DATA_ID, 1, T, f[1], rx, 1000) == S.INITIAL
    assert e2e.check_timeout(rx, T, 1000) == S.OK
    assert e2e.check(DATA_ID, 1, T, f[2], rx, 1020) == S.OK


def test_sixteen_lost_frames_do_not_alias_to_ok():
    f = frames(18)
    rx = e2e.RxState()
    e2e.check(DATA_ID, 1, T, f[0], rx, 0)
    e2e.check(DATA_ID, 1, T, f[1], rx, 20)
    # frames 2..16 lost: f[17] counter = 17 & 0xF = 1 + 16, i.e. delta 1 after a wrap
    assert e2e.check(DATA_ID, 1, T, f[17], rx, 20 + 16 * 20) == S.INITIAL


def test_sender_restart_is_not_ok_on_first_frame():
    rx = e2e.RxState()
    old = frames(6)
    for i, fr in enumerate(old):
        e2e.check(DATA_ID, 1, T, fr, rx, i * 20)
    new = frames(2)  # restarted sender: counter starts again at 0
    assert e2e.check(DATA_ID, 1, T, new[0], rx, 120) == S.WRONG_SEQUENCE
    assert e2e.check(DATA_ID, 1, T, new[1], rx, 140) == S.OK


def test_wrong_crc_keeps_receiver_unsynced():
    rx = e2e.RxState()
    bad = bytearray(frames(1)[0])
    bad[0] ^= 0xFF
    assert e2e.check(DATA_ID, 1, T, bytes(bad), rx, 0) == S.WRONG_CRC
    assert rx.synced is False
    assert e2e.check_timeout(rx, T, 0) == S.NO_NEW_DATA


def test_e2e_id_ranges_are_exported_for_every_c_target():
    """ISSUES E-14 (5): senders read the E2E-mandatory platform ID ranges from gen/."""
    from vehicle_codegen import config, gen_c
    from vehicle_codegen.dbc_checks import load_dbc

    db = load_dbc(config.PLATFORM_DBC)
    mandatory = [r for r in config.ID_RANGES if r.e2e_mandatory]
    assert {r.name for r in mandatory} == {"safety", "heartbeat"}
    for target in config.C_TARGETS:
        h = gen_c.generate_e2e_c(db, target)["platform_e2e.h"]
        for r in mandatory:
            name = r.name.upper()
            assert f"#define PLATFORM_E2E_RANGE_{name}_FIRST_ID (0x{r.first:03X}u)" in h
            assert f"#define PLATFORM_E2E_RANGE_{name}_LAST_ID (0x{r.last:03X}u)" in h
