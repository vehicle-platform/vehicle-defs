# safety/ — HARA (location per D-113, PROVISIONAL)

**Status: provisional.** Q-006 is provisionally resolved by D-113 (2026-11-13, Claude's
recommendation adopted on the user's instruction; the user revises). Every S/E/C/ASIL stays
`TBD` until the user assigns them (D-046). These files are a scaffold: they collect
what the recorded decisions and platform invariants already say, in ISO 26262 vocabulary, so
the thesis chapter Ç8 (process documentation, `docs/ARCHITECTURE.md` §8-§9) has a
checkable place to grow.

## Authority order

`docs/DECISIONS.md` > `docs/ARCHITECTURE.md` > the files in `safety/` and `requirements/`.
If one of these files disagrees with a decision, the decision wins and the file is wrong.
Every hazard and requirement cites the decision or invariant it comes from; nothing is
invented here. A hazard that is plausible but whose mitigation is not recorded is marked
`candidate: true`.

## No ASIL is assigned yet (D-046)

D-046 makes MISRA and coverage floors blocking, but no ASIL has been assigned to any item.
Every rating field (`S`, `E`, `C`, `asil`) is therefore `TBD`, to be filled by the user in a
rating session (Claude proposes, the user decides, `safety-reviewer` checks). The checker
refuses a value that is not a legal ISO 26262 rating, but it does not judge the rating.

## Vocabulary (ISO 26262, used loosely for a senior thesis prototype)

| Term | Meaning here |
|---|---|
| item | A function with a safety impact: `cornering_warning`, `blind_spot_warning`, `immobilizer`, `led_ring_output`, `inter_core_mailbox` |
| hazard | A malfunctioning behaviour of an item that can lead to harm, in one operational situation |
| S / E / C | Severity (S0-S3), exposure (E0-E4), controllability (C0-C3) of the hazard in that situation |
| ASIL | Automotive Safety Integrity Level (QM, A-D) derived from S, E, C; `TBD` everywhere today |
| safety goal (SG) | Top-level requirement that avoids a hazard (`SG-001`...) |
| FSR | Functional safety requirement derived from a safety goal (`type: FSR`) |
| TSR | Technical safety requirement allocated to a repo and module (`type: TSR`) |
| constraint | A rule from a recorded decision or invariant that is not derived from a hazard (`type: constraint`) |

## Files

- `hara.yaml` — items, hazards, safety goals (schema in its header comment).
- `../requirements/` — requirements per domain, schema, README.
- `../scripts/check_requirements.py` — the consistency check run in CI.

An FMEA is not part of this draft. The fault catalog (`faults/`, D-084) is a different
thing: vehicle faults for the diagnostics feature, not a safety analysis of our own items.
