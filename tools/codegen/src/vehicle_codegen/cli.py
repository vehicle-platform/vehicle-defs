"""`vehicle-codegen gen|check` entry point (called by the repo Makefile)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import (
    config,
    gen_ble,
    gen_c,
    gen_catalog,
    gen_mailbox,
    gen_python,
    gen_uds,
    gen_vss,
    ride_records,
)
from .dbc_checks import check_cl250_dbc, check_platform_dbc, load_dbc
from .derived import check_derived
from .yaml_checks import (
    check_dtc_snapshot,
    check_dtc_warm_idle,
    check_limits,
    check_vehicle,
    check_vehicle_constants,
    load_yaml,
)


def run_checks(with_vss: bool = True) -> list[str]:
    errors: list[str] = []
    platform_db = load_dbc(config.PLATFORM_DBC)
    errors += check_platform_dbc(platform_db)
    errors += check_cl250_dbc(load_dbc(config.CL250_DBC))
    errors += check_vehicle(load_yaml(config.VEHICLE_YAML), platform_db)
    iso = load_yaml(config.ISO14229_YAML)
    iso_errors = gen_uds.check_iso(iso)
    errors += iso_errors
    if not iso_errors:
        errors += check_dtc_snapshot(load_yaml(config.VEHICLE_YAML), iso)
        errors += check_dtc_warm_idle(
            load_yaml(config.VEHICLE_YAML), load_yaml(config.DERIVED_YAML)
        )
        errors += gen_uds.check_dids(
            load_yaml(config.DIDS_YAML), iso, load_yaml(config.VEHICLE_YAML)
        )
    errors += check_limits(
        load_yaml(config.LIMITS_YAML), load_yaml(config.VEHICLE_YAML), platform_db
    )
    const_errors = check_vehicle_constants(load_yaml(config.VEHICLE_CONSTANTS_YAML))
    errors += const_errors
    ble = gen_ble.load_schema()
    ble_errors = gen_ble.check_schema(ble)
    errors += ble_errors
    if not ble_errors:
        errors += gen_ble.check_vehicle_signal_table(ble, load_yaml(config.VEHICLE_YAML))
    if not (const_errors or ble_errors or iso_errors):
        derived_errors = check_derived(
            load_yaml(config.DERIVED_YAML),
            load_yaml(config.VEHICLE_YAML),
            load_yaml(config.VEHICLE_CONSTANTS_YAML),
            ble,
            platform_db,
            load_yaml(config.DIDS_YAML),
        )
        errors += derived_errors
        if not (derived_errors or iso_errors):
            errors += ride_records.check_ride_records(
                load_yaml(config.DERIVED_YAML),
                load_yaml(config.DIDS_YAML),
                iso,
                load_yaml(config.VEHICLE_YAML),
            )
    errors += gen_mailbox.check_mailbox(load_yaml(config.MAILBOX_YAML), platform_db)
    errors += gen_catalog.check_catalog(
        load_yaml(config.OBD_CATALOG_YAML), load_yaml(config.VEHICLE_YAML)
    )
    if with_vss:
        base = gen_vss.fetch_base()
        errors += gen_vss.check_overlay(
            gen_vss.load_overlay(), gen_vss.base_paths(base), platform_db
        )
    return errors


def render_all(with_vss: bool = True) -> dict[Path, str]:
    """Every generated file, keyed by path relative to gen/."""
    db = load_dbc(config.PLATFORM_DBC)
    vehicle = load_yaml(config.VEHICLE_YAML)
    limits = load_yaml(config.LIMITS_YAML)
    constants = load_yaml(config.VEHICLE_CONSTANTS_YAML)
    derived = load_yaml(config.DERIVED_YAML)
    iso = load_yaml(config.ISO14229_YAML)
    dids = load_yaml(config.DIDS_YAML)
    mailbox = load_yaml(config.MAILBOX_YAML)
    dids = ride_records.with_ride_records(dids, derived)  # D-098, after the explicit DIDs
    servers = gen_uds.servers(dids)
    files: dict[Path, str] = {}
    for target in config.C_TARGETS:
        out = Path("c") / target.directory
        parts = {**gen_c.generate_platform_c(db, target), **gen_c.generate_e2e_c(db, target)}
        if target.vehicle_dids:
            parts.update(gen_c.generate_vehicle_c(vehicle, derived))
        if target.limits:
            parts.update(gen_c.generate_limits_c(limits, target.node))
        if target.vehicle_constants:
            parts.update(gen_c.generate_vehicle_constants_c(constants))
            parts.update(gen_c.generate_derived_c(derived, constants))
        if target.mailbox:
            parts.update(gen_mailbox.generate_c(mailbox, db))
        if target.uds_iso is not None:
            parts.update(gen_uds.generate_iso_c(iso, client_only=target.uds_iso == "client"))
        if target.node in servers:
            parts.update(
                gen_uds.generate_server_c(target.node, servers[target.node], dids, iso, vehicle)
            )
        for name, text in parts.items():
            files[out / name] = text
    ble = gen_ble.load_schema()
    for name, text in gen_ble.generate_c(ble).items():
        files[Path("c") / "conn" / name] = text
    for name, text in gen_ble.generate_dart(ble).items():
        files[Path("dart") / "vehicle_defs" / name] = text
    # D-066: the signal catalog goes to host consumers only (no C target).
    cand = load_yaml(config.OBD_CATALOG_YAML)
    files[Path("dart") / "vehicle_defs" / "lib" / "vehicle_signals.dart"] = (
        gen_catalog.generate_dart(cand, vehicle)
    )
    py = Path("python") / "vehicle_defs"
    files[py / "__init__.py"] = gen_python.generate_init_py()
    files[py / "platform.py"] = gen_python.generate_platform_py(db)
    files[py / "vehicle_cl250.py"] = gen_python.generate_vehicle_py(vehicle, derived)
    files[py / "e2e.py"] = gen_python.generate_e2e_py()
    files[py / "limits.py"] = gen_python.generate_limits_py(limits)
    files[py / "vehicle_constants.py"] = gen_python.generate_vehicle_constants_py(constants)
    files[py / "vehicle_derived.py"] = gen_python.generate_derived_py(derived)
    files[py / "uds.py"] = gen_uds.generate_uds_py(iso, dids, vehicle)
    files[py / "mailbox.py"] = gen_mailbox.generate_python(mailbox, db)
    files[py / "ble.py"] = gen_ble.generate_python(ble)
    files[py / "vehicle_catalog.py"] = gen_catalog.generate_python(cand, vehicle, iso)
    if with_vss:
        files[Path("vss") / "vss_dbc.json"] = gen_vss.export_json(gen_vss.fetch_base())
    return files


def write_all(files: dict[Path, str], gen_dir: Path = config.GEN_DIR) -> None:
    for sub in sorted({rel.parts[0] for rel in files}):  # only the parts being regenerated
        shutil.rmtree(gen_dir / sub, ignore_errors=True)
    for rel, text in files.items():
        path = gen_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vehicle-codegen")
    parser.add_argument("command", choices=["check", "gen"])
    parser.add_argument("--no-vss", action="store_true", help="skip the VSS base download/export")
    args = parser.parse_args(argv)

    errors = run_checks(with_vss=not args.no_vss)
    for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} error(s); nothing generated.", file=sys.stderr)
        return 1
    print("checks: OK")
    if args.command == "gen":
        files = render_all(with_vss=not args.no_vss)
        write_all(files)
        print(f"gen: wrote {len(files)} files to {config.GEN_DIR.relative_to(config.REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
