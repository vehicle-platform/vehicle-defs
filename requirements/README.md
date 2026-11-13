# requirements/ (DRAFT, proposal for Q-006)

Requirements per domain, one file each: `cornering`, `blind_spot`, `immobilizer`, `mailbox`,
`tester`, `platform_bus`. Ids are `REQ-<DOMAIN>-NNN` (ARCHITECTURE section 8: requirement
ids appear in test names or comments for traceability). Fields are in `schema.yaml`.

- Every requirement cites a recorded decision, a platform invariant or a safety goal of
  `../safety/hara.yaml` in `derives_from`. Nothing is invented; no ASIL is assigned (D-046).
- `status: implemented` means a README or decision says the behaviour exists today;
  `planned` means it is recorded but has no code yet (blind spot, immobilizer, LED driver).
- `tests` lists existing test names (`file::name`, repo-relative to the allocated repo).
  Tests do not carry REQ ids yet; adding them is a follow-up once Q-006 is decided.
- Check: `python3 scripts/check_requirements.py` (needs PyYAML; in CI it runs through the
  codegen uv project).

This is a proposal and does not change DECISIONS.md. Q-006 stays open until the user decides.
