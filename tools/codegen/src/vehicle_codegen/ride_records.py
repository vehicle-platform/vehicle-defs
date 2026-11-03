"""Ride-summary record DIDs generated from derived/cl250_derived.yaml (D-098).

Every `ride_summary_records` entry that has scalar class-B signals becomes one ordinary
`record` DID of the RT_CORE platform UDS server: a 4-byte header, then one unsigned
big-endian field per signal. Nothing of this is typed into uds/dids.yaml (invariant 2).

Field encoding: raw = round_half_even((value - range.min) / resolution). The width is the
smallest of 1, 2 or 4 bytes whose all-ones value is above the largest valid raw value; the
all-ones value is NOT_AVAILABLE (never a saturated value, D-070: no clamping).
"""

from __future__ import annotations

import copy
from typing import Any

from . import gen_uds

HEADER_LENGTH = 4
WIDTHS = (1, 2, 4)
HEADER_FIELDS: tuple[dict[str, Any], ...] = (
    {"name": "LAYOUT_VERSION", "byte": 0, "length": 1,
     "description": "Layout version of the ride record (D-098)."},
    {"name": "RIDE_COUNTER", "byte": 1, "length": 2,
     "description": "Stop-epoch counter of the closed ride; every value is valid (D-098)."},
    {"name": "RIDE_CLOSED", "byte": 3, "mask": 0x01,
     "description": "1 = a ride was closed since boot, 0 = none (all fields NOT_AVAILABLE)."},
    {"name": "RESERVED", "byte": 3, "mask": 0xFE, "description": "Reserved, zero."},
)  # fmt: skip
GENERATED_NOTE = "Generated from derived/cl250_derived.yaml (D-098)."


def is_multi_element(sig: dict[str, Any]) -> bool:
    return "bins" in sig or "per_gear" in sig


def raw_max_of(rng: list[float], resolution: float) -> int:
    """Largest valid raw value; Python round (half to even), like the raw encoder."""
    return round((rng[1] - rng[0]) / resolution)


def field_width(raw_max: int) -> int:
    """Smallest of 1, 2, 4 bytes whose all-ones value is strictly above raw_max."""
    if raw_max < 0:
        raise ValueError(f"raw maximum {raw_max} is negative")
    for width in WIDTHS:
        if (1 << (8 * width)) - 1 > raw_max:
            return width
    raise ValueError(f"raw maximum {raw_max} does not fit 4 bytes with a NOT_AVAILABLE value")


def field_name(record: str, signal: str) -> str:
    """The signal in UPPER_CASE, minus a leading copy of the record name (RIDE_WINDOW_CRANK
    + window_crank_cranking_dip -> CRANKING_DIP). Keeps every macro name inside the 63
    significant characters of MISRA C:2012 rule 5.4; the signal itself stays in the field."""
    name = signal.upper()
    prefix = record.removeprefix("RIDE_") + "_"
    if name.startswith(prefix) and len(name) > len(prefix):
        return name[len(prefix) :]
    return name


def synthesize(derived: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """The generated RT_CORE DID entries in ride_summary_records order, and any errors."""
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    header_names = {f["name"] for f in HEADER_FIELDS}
    for key, rec in derived["ride_summary_records"].items():
        fields: list[dict[str, Any]] = []
        offset = HEADER_LENGTH
        for sname, sig in derived["signals"].items():
            if sig.get("class") != "B" or sig.get("record") != key or is_multi_element(sig):
                continue
            where = f"ride record {key}: signal {sname}"
            fname = field_name(key, sname)
            if fname in header_names or any(f["name"] == fname for f in fields):
                errors.append(f"{where}: field name {fname} clashes")
                continue
            try:
                raw_max = raw_max_of(sig["range"], sig["resolution"])
                width = field_width(raw_max)
            except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
                errors.append(f"{where}: {exc}")
                continue
            fields.append({
                "name": fname,
                "byte": offset,
                "length": width,
                "description": str(sig["description"]),
                "ride_signal": {
                    "signal": sname,
                    "range_min": float(sig["range"][0]),
                    "resolution": float(sig["resolution"]),
                    "raw_max": raw_max,
                },
            })  # fmt: skip
            offset += width
        if not fields:
            continue  # e.g. RIDE_OPERATING_POINTS: only a histogram, not served in v1
        entries.append({
            "did": rec["did"],
            "name": key,
            "length": offset,
            "encoding": "record",
            "access": "read",
            "description": f"{str(rec['description']).rstrip()} {GENERATED_NOTE}",
            "ride_record": True,
            "fields": [copy.deepcopy(f) for f in HEADER_FIELDS] + fields,
        })  # fmt: skip
    return entries, errors


def check_ride_records(derived: dict[str, Any], dids_doc: dict[str, Any], iso: dict[str, Any],
                       vehicle: dict[str, Any]) -> list[str]:  # fmt: skip
    """Synthesis errors, DID collisions with the explicit DIDs and the ordinary DID checks."""
    entries, errors = synthesize(derived)
    explicit = dids_doc["nodes"]["RT_CORE"]["dids"]
    seen = {d["did"] for d in explicit}
    names = {d["name"] for d in explicit}
    for entry in entries:
        errors += gen_uds._check_did("RT_CORE", entry, vehicle, True, seen, names)
    return errors


def with_ride_records(dids_doc: dict[str, Any], derived: dict[str, Any]) -> dict[str, Any]:
    """Copy of the dids document whose RT_CORE DIDs get the ride records appended after the
    explicit ones (so every existing platform_uds_did_index_t value stays unchanged)."""
    out = copy.deepcopy(dids_doc)
    entries, errors = synthesize(derived)
    if errors:
        raise ValueError("; ".join(errors))
    out["nodes"]["RT_CORE"]["dids"] = [*out["nodes"]["RT_CORE"]["dids"], *entries]
    return out
