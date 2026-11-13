#!/usr/bin/env python3
"""Validate safety/hara.yaml and requirements/*.yaml (Q-006 draft). Stdlib + PyYAML."""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
errors = []


def err(msg):
    errors.append(msg)


def load(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        err(f"{path.relative_to(ROOT)}: cannot parse: {e}")
        return None


decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
REF = re.compile(r"^(D-\d{3}|Q-\d{3}|SG-\d{3}|invariant-[1-8])$")


def check_refs(where, refs, goals):
    if not isinstance(refs, list) or not refs:
        err(f"{where}: derives_from/source must be a non-empty list")
        return
    for r in refs:
        if not isinstance(r, str) or not REF.match(r):
            err(f"{where}: bad reference {r!r} (want D-nnn, Q-nnn, SG-nnn or invariant-1..8)")
        elif r[0] in "DQ" and not re.search(rf"\b{r}\b", decisions):
            err(f"{where}: {r} does not occur in docs/DECISIONS.md")
        elif r.startswith("SG-") and r not in goals:
            err(f"{where}: {r} is not a safety goal in safety/hara.yaml")


def need(where, d, keys):
    for k in keys:
        if k not in d or d[k] in (None, ""):
            err(f"{where}: missing field {k}")


# --- HARA ---
hara = load(ROOT / "safety" / "hara.yaml") or {}
goals, items = set(), set()
if hara.get("schema_version") != 1:
    err("safety/hara.yaml: schema_version must be 1")
for it in hara.get("items", []):
    need(f"item {it.get('id')}", it, ["id", "name", "description"])
    items.add(it.get("id"))
for sg in hara.get("safety_goals", []):
    w = f"safety goal {sg.get('id')}"
    need(w, sg, ["id", "text", "derives_from"])
    if not re.fullmatch(r"SG-\d{3}", str(sg.get("id"))):
        err(f"{w}: id must match SG-nnn")
    if sg.get("id") in goals:
        err(f"{w}: duplicate id")
    goals.add(sg.get("id"))
    check_refs(w, sg.get("derives_from"), goals | {sg.get("id")})
RATING = {"S": {"TBD", "S0", "S1", "S2", "S3"}, "E": {"TBD", "E0", "E1", "E2", "E3", "E4"},
          "C": {"TBD", "C0", "C1", "C2", "C3"}, "asil": {"TBD", "QM", "A", "B", "C", "D"}}
seen = set()
for hz in hara.get("hazards", []):
    w = f"hazard {hz.get('id')}"
    need(w, hz, ["id", "item", "hazard", "operational_situation", "effect", "S", "E", "C",
                 "asil", "safety_goal_id", "source"])
    if not re.fullmatch(r"HZ-\d{3}", str(hz.get("id"))):
        err(f"{w}: id must match HZ-nnn")
    if hz.get("id") in seen:
        err(f"{w}: duplicate id")
    seen.add(hz.get("id"))
    if hz.get("item") not in items:
        err(f"{w}: unknown item {hz.get('item')!r}")
    if hz.get("safety_goal_id") not in goals:
        err(f"{w}: unknown safety goal {hz.get('safety_goal_id')!r}")
    for k, ok in RATING.items():
        if hz.get(k) not in ok:
            err(f"{w}: {k} must be one of {sorted(ok)}")
    check_refs(w, hz.get("source"), goals)
    if "candidate" in hz and not isinstance(hz["candidate"], bool):
        err(f"{w}: candidate must be a boolean")

# --- requirements ---
TYPES = {"FSR", "TSR", "constraint"}
VERIF = {"host test", "HIL", "review", "analysis"}
STATUS = {"implemented", "planned"}
ids = set()
files = sorted((ROOT / "requirements").glob("*.yaml"))
for f in files:
    if f.name == "schema.yaml":
        continue
    doc = load(f) or {}
    dom = str(doc.get("domain", ""))
    if dom != f.stem:
        err(f"{f.name}: domain {dom!r} must equal the file name")
    for r in doc.get("requirements", []):
        rid = str(r.get("id"))
        w = f"{f.name} {rid}"
        need(w, r, ["id", "text", "type", "derives_from", "allocated_to", "verification", "status"])
        if "tests" not in r or not isinstance(r["tests"], list):
            err(f"{w}: tests must be a list (may be empty)")
        m = re.fullmatch(r"REQ-([A-Z_]+)-(\d{3})", rid)
        if not m:
            err(f"{w}: id must match REQ-<DOMAIN>-NNN")
        elif m.group(1) != dom.upper():
            err(f"{w}: DOMAIN {m.group(1)} does not match file domain {dom.upper()}")
        if rid in ids:
            err(f"{w}: duplicate id")
        ids.add(rid)
        if not re.search(r"\bshall\b", str(r.get("text", ""))):
            err(f"{w}: text must contain 'shall'")
        for k, ok in (("type", TYPES), ("verification", VERIF), ("status", STATUS)):
            if r.get(k) not in ok:
                err(f"{w}: {k} must be one of {sorted(ok)}")
        check_refs(w, r.get("derives_from"), goals)

if not ids:
    err("no requirements found")
if errors:
    print("check_requirements: FAILED")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"check_requirements: OK ({len(hara.get('hazards', []))} hazards, {len(goals)} goals, {len(ids)} requirements)")
