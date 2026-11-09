"""Consistency checks for dbc/platform.dbc beyond cantools' strict parsing.

Each check returns a list of human-readable error strings; empty means OK.
"""

from __future__ import annotations

import re
from pathlib import Path

import cantools
from cantools.database.can import Database, Message

from . import config

MESSAGE_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
SIGNAL_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def load_dbc(path: Path | str) -> Database:
    """Strict load: overlapping signals or out-of-frame bits raise."""
    return cantools.database.load_file(str(path), strict=True)


def _attr(obj, name: str, db: Database):
    """Attribute value with DBC default fallback (None if undefined)."""
    attrs = obj.dbc.attributes if obj.dbc is not None else {}
    if name in attrs:
        return attrs[name].value
    definition = db.dbc.attribute_definitions.get(name)
    return None if definition is None else definition.default_value


def is_e2e_protected(msg: Message, db: Database) -> bool:
    value = _attr(msg, "E2E_Protected", db)
    definition = db.dbc.attribute_definitions.get("E2E_Protected")
    if isinstance(value, int) and definition is not None and definition.choices:
        value = definition.choices[value]
    return value == "Yes"


def e2e_data_id(msg: Message, db: Database) -> int:
    return int(_attr(msg, "E2E_DataID", db) or 0)


def cycle_time_ms(msg: Message) -> int:
    return int(msg.cycle_time or 0)


def node_id(db: Database, node_name: str) -> int | None:
    for node in db.nodes:
        if node.name == node_name:
            value = _attr(node, "NodeId", db)
            return None if value is None else int(value)
    return None


# Widest signal the generated single-precision encode converts exactly (float mantissa).
USE_FLOAT_MAX_BITS = 24


def check_platform_dbc(db: Database) -> list[str]:
    errors: list[str] = []
    for name in ("GenMsgCycleTime", "E2E_Protected", "E2E_DataID", "NodeId"):
        if name not in db.dbc.attribute_definitions:
            errors.append(f"attribute definition {name} missing (BA_DEF_)")
    if errors:
        return errors

    node_names = [n.name for n in db.nodes]
    if set(node_names) != set(config.NODE_IDS):
        errors.append(f"nodes {sorted(node_names)} != expected {sorted(config.NODE_IDS)}")
    for name, expected in config.NODE_IDS.items():
        actual = node_id(db, name)
        if name in node_names and actual != expected:
            errors.append(f"node {name}: NodeId {actual} != {expected}")

    data_ids: dict[int, str] = {}
    for msg in db.messages:
        where = f"{msg.name} (0x{msg.frame_id:03X})"
        if not MESSAGE_NAME_RE.match(msg.name):
            errors.append(f"{where}: message name must be PascalCase")
        if msg.is_extended_frame or msg.frame_id > 0x7FF:
            errors.append(f"{where}: platform bus uses 11-bit standard IDs only")
            continue
        if msg.is_fd or msg.length > 8:
            errors.append(f"{where}: platform bus is classic CAN (DLC <= 8)")
        rng = config.id_range_of(msg.frame_id)
        if rng is None:
            errors.append(f"{where}: ID is outside every range of the ID plan")
            continue
        if not rng.allowed_in_dbc:
            errors.append(f"{where}: ID is in the '{rng.name}' range, not usable for messages")
            continue

        if len(msg.senders) != 1:
            errors.append(f"{where}: exactly one sender required, got {msg.senders}")
        for node in [*msg.senders, *msg.receivers]:
            if node not in node_names:
                errors.append(f"{where}: unknown node {node}")
        if not msg.receivers:
            errors.append(f"{where}: no receivers")
        if "SAFETY" in msg.receivers and msg.name not in config.SAFETY_RX_ALLOWED:
            errors.append(f"{where}: SAFETY may not receive it (D-041, SAFETY_RX_ALLOWED)")
        if is_e2e_protected(msg, db) and "SAFETY" in [*msg.senders, *msg.receivers]:
            for sig in msg.signals:
                if not sig.choices or (msg.name, sig.name) in config.NO_INFORMATION_EXEMPT:
                    continue
                zero = sig.choices.get(0)
                if zero is None or str(zero) not in config.NO_INFORMATION_NAMES:
                    errors.append(
                        f"{where}: {sig.name} raw 0 must mean no information "
                        f"({sorted(config.NO_INFORMATION_NAMES)}), got {zero} (D-072)"
                    )
        if cycle_time_ms(msg) <= 0:
            errors.append(f"{where}: GenMsgCycleTime must be > 0")

        for sig in msg.signals:
            if not SIGNAL_NAME_RE.match(sig.name):
                errors.append(f"{where}: signal {sig.name} must be SNAKE_CASE")
            if sig.length > USE_FLOAT_MAX_BITS:
                # ISSUES C-9 (4): the generated *_encode() (use_float) converts a float to the
                # raw type without a range check; above 24 bits that conversion can overflow.
                errors.append(
                    f"{where}: signal {sig.name} is {sig.length} bits; the float encode "
                    f"supports at most {USE_FLOAT_MAX_BITS}"
                )

        protected = is_e2e_protected(msg, db)
        if rng.e2e_mandatory and not protected:
            errors.append(f"{where}: E2E is mandatory in the '{rng.name}' range")
        if protected:
            errors.extend(_check_e2e_layout(msg, where))
            data_id = e2e_data_id(msg, db)
            if data_id == 0:
                errors.append(f"{where}: E2E_DataID missing or 0")
            elif data_id in data_ids:
                errors.append(
                    f"{where}: E2E_DataID 0x{data_id:04X} already used by {data_ids[data_id]}"
                )
            else:
                data_ids[data_id] = msg.name
        elif e2e_data_id(msg, db):
            errors.append(f"{where}: E2E_DataID set but E2E_Protected is not Yes")

        if rng.name == "heartbeat":
            sender = msg.senders[0] if msg.senders else None
            nid = node_id(db, sender) if sender else None
            if nid is None or msg.frame_id != config.HEARTBEAT_BASE_ID + nid:
                errors.append(f"{where}: heartbeat ID must be 0x080 + NodeId of its sender")
            if cycle_time_ms(msg) != config.HEARTBEAT_CYCLE_MS:
                errors.append(f"{where}: heartbeat cycle must be {config.HEARTBEAT_CYCLE_MS} ms")
    return errors


def _check_e2e_layout(msg: Message, where: str) -> list[str]:
    errors = []
    expected = {"E2E_CRC": (0, 8), "E2E_COUNTER": (8, 4)}
    for name, (start, length) in expected.items():
        try:
            sig = msg.get_signal_by_name(name)
        except KeyError:
            errors.append(f"{where}: E2E message lacks signal {name}")
            continue
        if (
            sig.start != start
            or sig.length != length
            or sig.byte_order != "little_endian"
            or sig.is_signed
            or sig.scale != 1
            or sig.offset != 0
        ):
            errors.append(f"{where}: {name} must be {start}|{length}@1+ (1,0)")
    return errors


def check_cl250_dbc(db: Database) -> list[str]:
    """Future passive-broadcast frames: never a diagnostic ID, always with evidence."""
    errors = []
    for msg in db.messages:
        diag_11 = not msg.is_extended_frame and 0x7DF <= msg.frame_id <= 0x7EF
        diag_29 = msg.is_extended_frame and (msg.frame_id >> 16) in (0x18DA, 0x18DB)
        if diag_11 or diag_29:
            errors.append(
                f"{msg.name}: 0x{msg.frame_id:X} is a diagnostic ID, not a broadcast frame"
            )
        if "VERIFIED" not in (msg.comment or ""):  # also matches "UNVERIFIED - <evidence>"
            errors.append(f"{msg.name}: comment must state VERIFIED or UNVERIFIED - <evidence>")
    return errors
