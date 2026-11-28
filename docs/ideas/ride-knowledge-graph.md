# Ride Knowledge Graph Design (Proposed — T61, D-132 Stage 3)

**Status: proposed** (design note under `docs/ideas/`, not a recorded decision; no code or schema files modified). Prepared for roadmap card **T61** and **D-132** item 2(a) ("symbolic knowledge: defs signals, the fault catalog, physics models, alert rules and their relations (`signal <-> subsystem <-> fault <-> symptom <-> check`) as a queryable knowledge graph behind tools, so relations are looked up, never generated").

Consistent with `docs/ideas/ride-llm.md` §0 and §5, this proposal uses **plain SQLite relational tables with typed foreign keys and SQL joins** compiled from the pinned `vehicle-defs` package at build/startup time — not a property-graph database (Neo4j/Kuzu), RDF/OWL store, or LLM-extracted GraphRAG.

**D-135 / D-033 compliance:** No vehicle-specific CAN identifiers, proprietary DID hex addresses, real ride data, or GPS positions appear in this document. Signal references use logical `vehicle-defs` namespace names (`did.*`, `derived.*`, `sensor.*`) only.

---

## 1. Snapshot and Reconciled Inventory of Existing Sources

All counts below were verified against `vehicle-defs` `main` (`63e1906`) and `vehicle-mcp` `main` (`7c1eb32`). Totals reconcile across every breakdown.

| Source file (repo) | What it defines today | Reconciled counts |
|---|---|---|
| `faults/catalog.yaml` (`vehicle-defs`) | Vehicle-independent FMEA fault entries, symptoms, required signals, English complaints, severity/occurrence/detectability ratings, rider wording, inspection actions, and source citations (D-084, D-127) | **68** entries across **14** subsystems; **31** `displayable` (at least one `high`/`medium` source) + **37** unconfirmed/CONFIRM (`low` sources only) = 68; **39** `detectable_now: true` + **29** `false` = 68; **36** `advise_stop: true` + **32** `false` = 68; **127** symptom edges across **66** entries (**2** `engine_mechanical` entries have empty `symptoms`/`needs`); **135** `needs` edges across **66** entries; **3** `residual` links (`CHG-001`..`CHG-003` -> `charging.output_vs_rpm`); **111** source citations; **210** English complaint phrases across all 68 entries |
| `faults/i18n/tr.yaml` (`vehicle-defs`) | Turkish rider complaint phrases per fault id (D-125 i18n resource exception, D-127) | **210** Turkish complaint phrases across **68** fault ids (1:1 entry coverage with `catalog.yaml`) |
| `vehicle/cl250_faults.yaml` (`vehicle-defs`) | Per-vehicle fault applicability list (D-078, D-084 item 2) | **68** applied fault ids (currently all 68 catalog entries) |
| `faults/alert_rules.yaml` (`vehicle-defs`) | Live/replay in-ride alert rules and signal gates (D-129) | **5** rules (**3** `P1`: `ALR-001`..`ALR-003`, all linked via `fault_id` to `COL-001`, `CHG-002`, `CHG-003`; **2** `P2`: `ALR-004`, `ALR-005`, unlinked data-quality/trend rules) and **4** gates (`engine_running`, `moving`, `stationary`, `warm`) |
| `uds/vehicle_cl250.yaml` (`vehicle-defs`) | Polled ECU DID signals (logical names, units, ranges, poll periods, staleness, priority) | **40** polled DIDs (**1** `high` priority + **39** `normal` = 40) |
| `uds/obd_catalog.yaml` (`vehicle-defs`) | Vehicle-independent OBD/UDS signal catalog (host-only, D-066, D-078) | **40** `polled`, **47** `candidates`, **10** `identification`, **8** `groups` |
| `derived/cl250_derived.yaml` (`vehicle-defs`) | Derived signals (classes A–D), non-DID sensors, health windows, and ride-summary records (D-070, D-079, D-098, D-103..D-106) | **155** derived signals (Class A: **66**, Class B: **75**, Class C: **12**, Class D: **2**; sum = 155; **131** without `pending_inputs` + **24** with `pending_inputs` = 155); **19** non-DID `sensors`; **5** health `windows` (`W1_KEY_ON`..`W5_POST_STOP`); **15** `ride_summary_records` |
| `vehicle/cl250_constants.yaml` (`vehicle-defs`) | Vehicle specifications, calculated parameters, and provisional thresholds with provenance (D-070, D-103) | **80** constants (`spec`: **16**, `calculated`: **3**, `provisional`: **61**; sum = 80) |
| `src/vehicle_mcp/matching.py::TOPICS` and `src/vehicle_mcp/explain.py::RELATED` (`vehicle-mcp`) | Canonical rider data-card topics and explain-mode related scalar/series tables (currently in Python code, not yet in `vehicle-defs`) | **10** canonical topics (`coolant`, `battery`, `idle`, `speed`, `rpm`, `throttle`, `fuel`, `stops`, `gears`, `ride`) |

### Reconciled Breakdown of Fault-Catalog Subsystems and Signal Coverage

- **Subsystems (14 total, 68 entries):** `fuel_air` (9), `cooling` (6), `brakes_abs` (6), `charging` (5), `battery_starting` (5), `ignition` (5), `clutch_gearbox` (5), `final_drive` (5), `lubrication` (4), `wheels_tyres` (4), `suspension_steering` (4), `wiring` (4), `lighting` (4), `engine_mechanical` (2). Sum: `9 + 6 + 6 + 5 + 5 + 5 + 5 + 5 + 4 + 4 + 4 + 4 + 4 + 2 = 68`.
- **Symptom edges by direction (127 total):** `up` (49), `unstable` (48), `down` (22), `absent` (8). Sum: `49 + 48 + 22 + 8 = 127`. Optional `window` key populated on **0/127** edges today.
- **Distinct signals referenced by faults:**
  - `symptoms` reference **30** distinct signals (`9` `did.*`, `13` `derived.*`, `8` `sensor.*`; `9 + 13 + 8 = 30`), all 30 verified present in `uds/vehicle_cl250.yaml` or `derived/cl250_derived.yaml` (`0` unmatched).
  - `needs` reference **31** distinct signals (`10` `did.*`, `13` `derived.*`, `8` `sensor.*`; `10 + 13 + 8 = 31`, `0` unmatched). `needs` is a strict superset of `symptoms` signals, adding `did.AMBIENT_AIR_TEMP` (required by `FUE-007` as a comparison baseline for `did.INTAKE_AIR_TEMP`).

---

## 2. Proposed Relational Knowledge-Graph Tables (Built Only from Existing Defs)

All tables below are **proposed** read-only SQLite tables (or in-memory read-only SQLite built deterministically from the generated `vehicle_defs` Python package at `vehicle-mcp` startup; no runtime mutation, no hand-written literals, invariant 2).

| # | Proposed table | Primary key | Foreign keys / references | Source file(s) | Current row count (reconciled) | Key columns |
|---|---|---|---|---|---|---|
| 1 | `signals` | `signal_id` (`did.*`, `derived.*`, `sensor.*`) | Optional `window_id -> windows.window_id` | `uds/vehicle_cl250.yaml` (`dids`), `derived/cl250_derived.yaml` (`signals`, `sensors`) | **214** (`40` `did.*` + `155` `derived.*` + `19` `sensor.*`) | `signal_id`, `namespace` (`did`\|`derived`\|`sensor`), `name`, `unit`, `range_min`, `range_max`, `signal_class` (`A`..`D` or `NULL`), `period_ms`, `stale_after_ms`, `has_pending_inputs`, `description` |
| 2 | `signal_inputs` | `(signal_id, input_ref)` | `signal_id -> signals.signal_id` | `derived/cl250_derived.yaml` (`signals.*.inputs`) | Derived from 155 signals' `inputs` lists (includes `did.*`, `derived.*`, `sensor.*`, `const.*`, `window.*`) | `signal_id`, `input_ref`, `input_kind` (`did`\|`derived`\|`sensor`\|`const`\|`window`) |
| 3 | `constants` | `const_id` (`const.<name>`) | Referenced by `signal_inputs.input_ref` | `vehicle/cl250_constants.yaml` (`constants`) | **80** (`16` `spec` + `3` `calculated` + `61` `provisional`) | `const_id`, `value`, `unit`, `status`, `source` |
| 4 | `windows` | `window_id` | — | `derived/cl250_derived.yaml` (`windows`) | **5** (`W1_KEY_ON`..`W5_POST_STOP`) | `window_id`, `description` |
| 5 | `subsystems` | `subsystem_id` | — | Distinct `subsystem` values in `faults/catalog.yaml` | **14** | `subsystem_id` |
| 6 | `faults` | `fault_id` | `subsystem_id -> subsystems.subsystem_id` | `faults/catalog.yaml` (`entries`) + `vehicle/cl250_faults.yaml` (`applies`) | **68** (all 68 apply to CL250 today) | `fault_id`, `subsystem_id`, `root_cause`, `residual`, `severity`, `occurrence`, `detectability`, `detectable_now`, `advise_stop`, `displayable`, `rider_text`, `action`, `applies_to_vehicle` |
| 7 | `fault_sources` | `(fault_id, seq)` | `fault_id -> faults.fault_id` | `faults/catalog.yaml` (`entries.*.sources`) | **111** | `fault_id`, `seq`, `ref`, `confidence` (`high`\|`medium`\|`low`) |
| 8 | `fault_symptoms` | `(fault_id, signal_id, direction, condition)` | `fault_id -> faults.fault_id`, `signal_id -> signals.signal_id`, optional `window_id -> windows.window_id` | `faults/catalog.yaml` (`entries.*.symptoms`) | **127** (`67` `did.*` + `43` `derived.*` + `17` `sensor.*`) | `fault_id`, `signal_id`, `direction` (`up`\|`down`\|`unstable`\|`absent`), `condition`, `window_id` (`NULL` for all 127 today) |
| 9 | `fault_needs` | `(fault_id, signal_id)` | `fault_id -> faults.fault_id`, `signal_id -> signals.signal_id` | `faults/catalog.yaml` (`entries.*.needs`) | **135** (`74` `did.*` + `44` `derived.*` + `17` `sensor.*`) | `fault_id`, `signal_id` |
| 10 | `complaints` | `(fault_id, locale, phrase)` | `fault_id -> faults.fault_id` | `faults/catalog.yaml` (`entries.*.complaints` for `en`), `faults/i18n/tr.yaml` (`complaints` for `tr`) | **420** (`210` `en` + `210` `tr`) | `fault_id`, `locale`, `phrase` |
| 11 | `alert_rules` | `rule_id` | `signal_id -> signals.signal_id`, optional `fault_id -> faults.fault_id` | `faults/alert_rules.yaml` (`rules`) | **5** (`3` `P1` linked to faults + `2` `P2` unlinked) | `rule_id`, `alert_class` (`P1`\|`P2`), `signal_id`, `fault_id`, `condition`, `threshold`, `unit`, `rate_window_s`, `sustain_s`, `clear_hysteresis`, `cooldown_s`, `max_spoken_per_ride`, `status`, `text`, `source_ref`, `source_confidence` |
| 12 | `alert_gates` | `gate_id` | `signal_id -> signals.signal_id` | `faults/alert_rules.yaml` (`gates`) | **4** (`engine_running`, `moving`, `stationary`, `warm`) | `gate_id`, `signal_id`, `op`, `value`, `unit`, `source` |
| 13 | `alert_rule_gates` | `(rule_id, gate_id)` | `rule_id -> alert_rules.rule_id`, `gate_id -> alert_gates.gate_id` | `faults/alert_rules.yaml` (`rules.*.while`) | **6** (`ALR-001..004`: 1 gate each; `ALR-005`: 2 gates) | `rule_id`, `gate_id` |
| 14 | `checks` *(view / projection)* | `fault_id` | `fault_id -> faults.fault_id` | `faults/catalog.yaml` (`entries.*.action`, `entries.*.needs`, `entries.*.detectable_now`) | **68** (1 check record per fault; **31** displayable, **37** unconfirmed/gated) | `fault_id`, `action`, `detectable_now`, `displayable` |
| 15 | `data_card_topics` *(current code table; proposed move to defs)* | `topic_id` | Maps to signal name patterns / ride-summary scalars | `vehicle-mcp:src/vehicle_mcp/matching.py::TOPICS` and `explain.py::RELATED` (not yet in `vehicle-defs`) | **10** topics (`coolant`..`ride`) | `topic_id`, `include_patterns`, `exclude_patterns`, `related_scalars`, `related_series` |

### Why `checks` Is a Projection Today

`faults/catalog.yaml` currently stores inspection checks as a single free-text `action` string per fault entry (plus the structured `needs` signal list and `detectable_now` boolean), rather than a separate normalized check table with prerequisites (e.g., cold engine, key-on, visual inspection vs. meter test). Until `vehicle-defs` introduces structured check items (proposed in §5), the graph exposes `checks` as a 1:1 projection of `faults` joined with `fault_needs`, gated by `displayable`.

---

## 3. Core Joins the Assistant Needs

Every join below runs deterministically in SQL/Python inside `vehicle-mcp` (invariant 7: no LLM graph traversal or text-to-SQL).

1. **Complaint -> candidate faults -> required signals and checks** ("which signals bear on this complaint, and what can the bike measure?")
   - `complaints` (matched via `matching.PhraseIndex` / IDF + optional hybrid RAG over `phrase` for `locale`) `JOIN faults ON fault_id` `LEFT JOIN fault_needs ON fault_id` `LEFT JOIN signals ON signal_id` `LEFT JOIN fault_symptoms ON (fault_id, signal_id)`.
   - Applies the **D-127 addendum gate**: if `faults.displayable = 0`, return only the `signals` measurements and trends (`kind: "data_only"`), stripping `fault_id`, `root_cause`, `rider_text`, `action`, `severity`, and `advise_stop`.
2. **Observed signal + direction -> matching faults -> subsystem -> alerts and checks** ("coolant climbed high; which faults, alerts, and subsystems share that signature?")
   - `fault_symptoms` (`WHERE signal_id = ? AND direction = ?`) `JOIN faults ON fault_id` `JOIN subsystems ON subsystem_id` `LEFT JOIN alert_rules ON alert_rules.fault_id = faults.fault_id`.
   - Replaces linear catalog scans in `explain_context` and adds reverse lookup from a live/replay alert rule (`ALR-001`..`ALR-005`) to its linked fault and co-occurring signals.
3. **Alert rule -> signal -> gates -> linked fault -> related signals** ("why did alert ALR-001 fire, and what other signals should we inspect?")
   - `alert_rules` `JOIN signals` `JOIN alert_rule_gates` `JOIN alert_gates` `LEFT JOIN faults ON alert_rules.fault_id = faults.fault_id` `LEFT JOIN fault_needs ON faults.fault_id = fault_needs.fault_id`.
   - For `ALR-001` (`COL-001`, unconfirmed), returns the rule's own `text`, threshold (`110.0 degC`), gate (`engine_running`: `did.ENGINE_SPEED > 0`), and `COL-001`'s `needs` (`did.COOLANT_TEMP`, `derived.coolant_rate`) without exposing unconfirmed `COL-001` wording.
4. **Derived signal -> upstream input signals and provisional constants** ("what inputs and thresholds produced `derived.coolant_rate` or `derived.cranking_dip`?")
   - `signals` `JOIN signal_inputs` `LEFT JOIN constants ON signal_inputs.input_ref = constants.const_id` `LEFT JOIN signals AS upstream ON signal_inputs.input_ref = upstream.signal_id`.
   - Enables `explain_context` to cite exact defs constants with their `status` (`spec`/`calculated`/`provisional`) and `source` directly from `vehicle/cl250_constants.yaml` instead of ad-hoc lookups.
5. **Subsystem -> faults -> observable signals -> anomaly-model residuals (D-132 item 1a)** ("show everything observable for the charging subsystem")
   - `subsystems` `JOIN faults` `LEFT JOIN fault_needs` `LEFT JOIN signals` (grouping `faults.residual` where non-null, currently `charging.output_vs_rpm` on `CHG-001..003`).
   - Provides the structured bridge between `vehicle-ml`'s per-subsystem anomaly residuals and `vehicle-mcp`'s explanation tools.
6. **Unobservable complaint -> nearest observable signals in the same subsystem** ("my valves tick — what *can* the bike see?")
   - When `faults.detectable_now = 0` or `fault_needs` is empty (`ENG-001`, `ENG-002`), join `faults.subsystem_id` (or an explicit related-signal link once proposed in §5) to report explicitly `observable: false`, which signals are missing, and — only when `displayable = 1` — the catalog inspection `action`.

---

## 4. Proposed Read-Only `vehicle-mcp` Knowledge-Graph Tools

All tools below are **proposed** read-only `vehicle-mcp` tools (strictly no writes, no vehicle-bus access, no GPS position fields per D-076, no invented signal literals per invariant 2, no LLM arithmetic per invariant 7). Descriptions respect `vehicle-mcp/src/vehicle_mcp/specs.py` budgets (`<= 160` chars per tool description, `<= 80` chars per argument description) so the 4k-context router prompt stays compact.

### Common D-127 / D-084 Safety & Confirmability Contract (Applies to Every Tool Below)

- **Displayable entries (`displayable: true`):** May return `id`, `subsystem`, `root_cause`, `rider_text`, `action`, `severity`, `advise_stop`, `detectable_now`, `symptoms`, `needs`, `sources`, and measured ride values.
- **Unconfirmed / CONFIRM entries (`displayable: false`, 37/68 entries today):** Must return **`kind: "data_only"`** only — exposing solely signal labels, units, measured values/trends, and (when querying an alert rule) the rule's own approved `text`, threshold, and `status: "PROVISIONAL"`. Never return `fault_id`, `root_cause`, `rider_text`, `action`, `severity`, or `advise_stop` for unconfirmed entries.
- **Untrusted text:** No rider-written notes (e.g., ride marks) ever enter knowledge-graph tool results.
- **Display labels:** Every rider-facing signal entry uses humanised labels (`matching.human_label`), never raw `did.*`/`derived.*`/`sensor.*` tokens in prose templates.

### Proposed Tool 1: `kg_signal_relations`

- **Description (126 chars):** `Look up faults, alert rules, derived dependents and constants linked to one signal. Definitions only, not a diagnosis.`
- **Arguments:**
  - `signal` (`str`, required; `<= 80` chars: `Signal or topic name, e.g. coolant or COOLANT_TEMP.`)
  - `direction` (`str`, optional; enum `["up", "down", "unstable", "absent"]`; `Optional observed direction to filter matching symptoms.`)
- **Proposed result shape:**
  ```json
  {
    "kind": "kg_signal_relations",
    "diagnosis": false,
    "signal": {"id": "did.COOLANT_TEMP", "label": "coolant temp", "unit": "degC", "namespace": "did"},
    "derived_dependents": [{"id": "derived.coolant_rate", "label": "coolant rate", "class": "A", "unit": "degC/min"}],
    "constants": [{"name": "derived_operating_coolant_degc", "value": 80.0, "unit": "degC", "status": "provisional", "source": "..."}],
    "alert_rules": [{"id": "ALR-001", "class": "P1", "condition": "above", "threshold": 110.0, "unit": "degC", "gates": ["engine_running"], "status": "PROVISIONAL"}],
    "faults": [
      {"kind": "catalog", "id": "...", "subsystem": "...", "direction": "up", "condition": "...", "detectable_now": true, "advise_stop": true, "rider_text": "...", "action": "..."}
    ],
    "unconfirmed_signal_links": {
      "kind": "data_only",
      "count": 5,
      "related_signals": [{"id": "derived.coolant_rate", "label": "coolant rate", "unit": "degC/min"}]
    }
  }
  ```
  *(Note: unconfirmed fault entries are aggregated into `unconfirmed_signal_links` as counts + related signals only — zero unconfirmed fault IDs or wording exposed.)*

### Proposed Tool 2: `kg_subsystem_overview`

- **Description (129 chars):** `List observable signals, alert rules, anomaly residuals and displayable faults for one bike subsystem. Not a diagnosis.`
- **Arguments:**
  - `subsystem` (`str`, required; enum of the 14 `subsystems` from defs; `Subsystem name, e.g. cooling or charging.`)
  - `session_id` (`str`, optional; `Optional ride id to attach latest measured signal values.`)
- **Proposed result shape:**
  ```json
  {
    "kind": "kg_subsystem_overview",
    "diagnosis": false,
    "subsystem": "charging",
    "signals": [{"id": "did.BATTERY_VOLTAGE", "label": "battery voltage", "unit": "V", "measured": {"min": 12.1, "mean": 13.9, "max": 14.3}}],
    "residuals": ["charging.output_vs_rpm"],
    "alert_rules": [{"id": "ALR-002", "class": "P1", "condition": "below", "threshold": 12.4, "unit": "V", "status": "PROVISIONAL"}],
    "displayable_fault_count": 0,
    "unconfirmed_fault_count": 5,
    "displayable_faults": []
  }
  ```
  *(Totals reconcile: `displayable_fault_count + unconfirmed_fault_count = total entries in subsystem`, e.g. `0 + 5 = 5` for `charging`.)*

### Proposed Tool 3: `kg_explain_alert`

- **Description (121 chars):** `Explain an in-ride alert rule: threshold, gates, linked signals, constants and displayable catalog causes. Not a diagnosis.`
- **Arguments:**
  - `rule_id` (`str`, required; `Alert rule id, e.g. ALR-001.`)
  - `session_id` (`str`, optional; `Optional ride id to include the ride's signal values.`)
- **Proposed result shape:**
  ```json
  {
    "kind": "kg_explain_alert",
    "diagnosis": false,
    "rule": {
      "id": "ALR-001", "class": "P1", "signal": "did.COOLANT_TEMP",
      "condition": "above", "threshold": 110.0, "unit": "degC",
      "sustain_s": 10, "clear_hysteresis": 5.0, "status": "PROVISIONAL",
      "text": "Coolant temperature is very high. Stop somewhere safe, switch off and let the engine cool."
    },
    "gates": [{"id": "engine_running", "signal": "did.ENGINE_SPEED", "op": "gt", "value": 0.0, "unit": "rpm"}],
    "linked_fault": {"kind": "data_only", "related_signals": [{"id": "did.COOLANT_TEMP", "unit": "degC"}, {"id": "derived.coolant_rate", "unit": "degC/min"}]}
  }
  ```
  *(If a future alert links to a `displayable: true` fault, `linked_fault` switches from `kind: "data_only"` to `kind: "catalog"` with `id`, `root_cause`, `rider_text`, `action`, `advise_stop`.)*

### Integration With Existing Tools (Rather Than Duplicating Them)

Per the small-model token budget (`vehicle-mcp/src/vehicle_mcp/specs.py` and D-128 item 3), adding too many tools hurts small-model routing (`docs/ideas/ride-llm.md` §1). **Proposed rollout order:**
1. Back the existing `check_symptom` and `explain_context` tools with the SQLite KG internally first (zero extra tools in the router menu; immediately adds derived-input provenance, alert-rule cross-links, and co-occurring `needs` signals).
2. Expose `kg_explain_alert` when riders tap "why this alert" from the D-129 alert banner/inbox (can be routed deterministically by `ALR-\d{3}` regex, zero LLM routing cost).
3. Expose `kg_signal_relations` and `kg_subsystem_overview` behind an opt-in config flag and gate adoption on eval accuracy (D-132 item 3).

---

## 5. What Is Missing in `vehicle-defs` (Proposed Defs Changes — Not Made)

None of the changes below are made in this PR (everything in `vehicle-defs` outside `docs/` is red-zone / requires `/signal-change` by Claude). Each gap cites the exact file checked:

1. **Data-card and explain-mode topic tables live in `vehicle-mcp`, not `vehicle-defs`** (`vehicle-mcp/src/vehicle_mcp/matching.py::TOPICS`, `explain.py::RELATED`).
   - *Proposed defs change:* Add a vehicle-independent topic mapping YAML (e.g., `faults/topics.yaml` or `derived/topics.yaml`) mapping the 10 canonical topics to `did.*`/`derived.*` signal names and ride-summary scalars, validated by codegen against existing signals (invariant 2).
2. **Fault symptoms do not populate `window` yet** (`faults/catalog.yaml`: `0/127` symptom rows set `window`, even though `derived/cl250_derived.yaml` defines 5 health windows `W1_KEY_ON`..`W5_POST_STOP` and symptom `condition` prose already says `"warm idle"`, `"cranking"`, `"cruise"`, `"key on"`, `"after_stop"`).
   - *Proposed defs change:* Populate the already-declared optional `window:` field on `faults/catalog.yaml` symptoms with validated IDs from `derived/cl250_derived.yaml::windows` (or an explicit `any` enum), enabling exact window-scoped joins between health-window summaries and fault signatures.
3. **Anomaly-model `residual` links exist on only 3/68 fault entries** (`faults/catalog.yaml`: `CHG-001`, `CHG-002`, `CHG-003` -> `charging.output_vs_rpm`; `65/68` entries have no `residual`, including all `cooling` entries even though `vehicle-ml` already implements `physics/cooling.py`).
   - *Proposed defs change:* Add a `residuals` registry in `vehicle-defs` (or link `cooling.*` / `charging.*` residual keys in `faults/catalog.yaml` as `vehicle-ml` models stabilize) so ML -> LLM interaction (D-132 item 1a) joins anomaly residuals to catalog entries without string guesswork.
4. **37/68 catalog entries (including all `charging`, `battery_starting`, and `cooling` entries) remain CONFIRM (`displayable: false`)** (`faults/catalog.yaml`: `31` displayable, `37` CONFIRM). Because of D-084 item 5 and D-127 addendum, KG queries on `cooling` (`0/6` displayable), `charging` (`0/5`), and `battery_starting` (`0/5`) can only return `data_only` signal measurements today.
   - *Proposed defs change:* Upgrade source confidence only when primary/medium sources (e.g., Honda CL250 service/owner's manual sections) are verified; never relax D-084 item 5.
5. **Structured inspection `checks` and `preconditions` are prose-only in `faults/catalog.yaml::action`** (no machine-readable split of `engine_cold`, `key_on`, `visual_only`, `needs_meter`, `dealer_tool`).
   - *Proposed defs change:* Optional structured `checks: [{step, precondition, tool_needed}]` per catalog entry, keeping `action` as the concise summary.
6. **Alert rules (`faults/alert_rules.yaml`) have no i18n resource file** (`ALR-001..005` carry English `text` only; unlike `faults/i18n/tr.yaml` for complaints, no `faults/i18n/alerts_tr.yaml` exists in `vehicle-defs`).
   - *Proposed defs change:* Add locale resource files for alert rule text (D-125) so `kg_explain_alert` and D-129 banners do not mix English rule text into Turkish answers.
7. **No explicit subsystem-to-signal mapping for `engine_mechanical` (`ENG-001`, `ENG-002`)** (`faults/catalog.yaml`: both entries have empty `symptoms: []` and `needs: []`).
   - *Proposed defs change:* Optional `context_signals` (e.g., `did.ENGINE_SPEED`, `did.COOLANT_TEMP` for cold-start vs. warm context on `ENG-002`) kept distinct from `symptoms`/`needs` so `detectable_now` remains `false` while the assistant can still show whether the ride started cold.
8. **No per-signal humanised display metadata or reference-range links in `uds/vehicle_cl250.yaml` / `derived/cl250_derived.yaml`** (`explain_context` currently relies on substring matching and hand-mapped locale labels in `vehicle-server/src/vehicle_server/chat/locales/*.json`).
   - *Proposed defs change:* Optional `normal_ref_constants: [const.*]` links on signals so the KG can join a signal directly to its reference constants (e.g., `did.COOLANT_TEMP` -> `derived_operating_coolant_degc`, `ride_fan_on_temperature_coolant_min_degc`) without scanning constant names.

---

## 6. Proposed Evaluation Plan (D-132 Item 3 Gate)

Per D-132 item 3, the knowledge-graph stage is adopted only if a before/after run on the same evaluation suites demonstrates improvement with zero regressions in safety or grounding.

### Target Evaluation Items

1. **Existing `vehicle-server` dev suite (`src/vehicle_server/chat/eval/spec.json`, `en` + `tr`):**
   - **Explain & explain follow-up items (`explain-1..5`, `explain-fu-1..6`, `mt-01-t3`, `mt-03-t4`, `mt-06-t2`, `mt-07-t4`, `mt-08-t2`, `mt-09-t4`, `mt-10-t2`):** Verify that KG-backed `explain_context` surfaces the exact defs reference constants (with `status` and `source`), window-relevant ride conditions, and matching displayable faults without inventing signal names or exposing CONFIRM wording.
   - **Symptom & complaint items (`symptom-1..17` + G9-2 `symptom-18..27`, `mt-04-t1`, `mt-07-t1`, `mt-10-t1`, `mt-11-t3..t4`, `mt-12-t3..t4`, `mt-15-t3..t4`):** Verify higher precision/coverage of returned `needs` signals and `data_only` fallbacks for CONFIRM complaints (`COL-*`, `CHG-*`, `BAT-*`, `ENG-002`).
   - **Fault catalog items (`faults-1..3`):** Verify reconciled subsystem counts and zero `active_fault` / `diagnosis` forbidden hits.
   - **Safety red-team items (G9-2 `safety-ride-1..6` and `guard-refuse-01..15`):** Verify `0` reassurance hits, `0` unconfirmed wording leaks, and preservation of `advise_stop` on all displayable stop-advised faults.
2. **Frozen held-out suite (`vehicle-ml` held-out split, scored only — never tuned on):**
   - Published Stage-0 bake-off (`docs/test-results/ride-llm-bakeoff/2026-11-27-stage0-3models/README.md`) noted `explain` (`0/15`) and `knowledge` (`0/10` `en`, `0–1/10` `tr`) as the largest tool-accuracy gaps prior to T57/KG/RAG. Re-score the frozen held-out split before and after wiring the KG into `vehicle-mcp` and report exact before/after accuracy, fact coverage, forbidden hits (`0` target), and latency p50/p95.
3. **New deterministic unit tests in `vehicle-mcp` (when T61 is implemented):**
   - Graph integrity test: every `fault_symptoms.signal_id`, `fault_needs.signal_id`, `alert_rules.signal_id`, and `alert_gates.signal_id` resolves in `signals` (zero dangling foreign keys).
   - Reconciliation test: SQLite table row counts equal `len(FAULTS)`, `len(ALERT_RULES)`, `len(CL250_DIDS)`, etc. from pinned `vehicle_defs`.
   - D-127 gate test: querying any of the 37 CONFIRM entries via `kg_signal_relations`, `kg_subsystem_overview`, or `kg_explain_alert` never leaks `fault_id`, `root_cause`, `rider_text`, `action`, `severity`, or `advise_stop`.
   - Prompt-budget test: adding any new KG tool still passes `vehicle-mcp`'s small-model spec length and total router-prompt budget tests.
