# COVESA VSS Two-Wheeler Issue Draft (T74 Item 1 — Draft Only)

> **Status:** **Proposed draft only** — kept inside this repository until the user reviews and approves any upstream submission (card T74). **Nothing has been posted or submitted outside `vehicle-platform`.**

---

## 1. Scope and Filtering of `vss/overlay.vspec`

Reviewed `vss/overlay.vspec` (currently built on pinned COVESA VSS `v6.0`, `tools/codegen/src/vehicle_codegen/gen_vss.py:17`) to separate **generic two-wheeler signals** from platform-specific signals:

- **Included as generic two-wheeler candidates (for comparison against upstream VSS):**
  - Lean / roll angle + estimator quality & state (`Vehicle.Motorcycle.LeanAngle`, `LeanAngleQuality`, `LeanAngleState`)
  - Tyre–road friction coefficient + estimator quality & state (`Vehicle.Motorcycle.FrictionCoefficient`, `FrictionCoefficientQuality`, `FrictionCoefficientState`)
  - Dynamic total vehicle+rider+load mass estimate + estimator quality & state (`Vehicle.Motorcycle.EstimatedMass`, `EstimatedMassQuality`, `EstimatedMassState`)
  - Side stand / kickstand state (not yet in `vss/overlay.vspec`, explicitly in scope for T74 item 1 as a core two-wheeler signal)
  - Throttle valve position (`Vehicle.Motorcycle.ThrottlePosition` — evaluated below against existing VSS `Vehicle.Powertrain.CombustionEngine.TPS`)
- **Excluded (platform-specific — must NOT be proposed upstream):**
  - `Vehicle.Motorcycle.IsEcuPresent` (single-tester UDS polling liveness)
  - `Vehicle.Motorcycle.Nodes.{RtCore,Safety,Conn,Linux}.{Mode,ErrorCount,UptimeSeconds}` (platform-bus node heartbeats, D-108)
  - `Vehicle.Motorcycle.Validity.{EngineSpeed,BatteryVoltage,CoolantTemp,ThrottlePosition}` (`kuksa-can-provider` workaround for CAN validity bits, D-108)
  - All `dbc2vss` bindings, DBC signal names, platform CAN IDs, and all vehicle-specific DIDs or constants.

---

## 2. Check Against Current COVESA VSS Release (`v6.1`)

Checked directly against the latest official COVESA release **`v6.1`** (published `2026-09-17`, `https://github.com/COVESA/vehicle_signal_specification/releases/tag/v6.1`, `vss.yaml` containing 1,737 entries and `units.yaml`), as well as our pinned base **`v6.0`** (`tools/codegen/.cache/vss-6.0/vss.yaml`). The release tag and date and the missing issue templates were re-checked through the GitHub API on 2026-11-28; re-check the `v6.1` entries (`Vehicle.Orientation.Roll`, entry count) against the then-current release before posting. Moving our base from `v6.0` to `v6.1` is a separate codegen change (D-024), not part of this draft.

| Concept (`vss/overlay.vspec` / T74) | Equivalent in COVESA VSS `v6.1` | Gap / Notes vs. Two-Wheeler Need |
|---|---|---|
| Two-wheeler / motorcycle branch (`Vehicle.Motorcycle`) | **not found in `v6.1`** | Zero occurrences of `Motorcycle`, `TwoWheeler`, `Lean`, `SideStand`, or `Kickstand` in `v6.1` `vss.yaml`. |
| Lean / roll angle (`Vehicle.Motorcycle.LeanAngle`, `float`, `degrees`, `[-90, 90]`) | **`Vehicle.Orientation.Roll`** (`sensor`, `float`, `unit: degrees`, `min: -180`, `max: 180`, `"Vehicle rotation (tilt) around X (longitudinal). Positive values = right side down."`, ISO 8855) — **added in `v6.1`** (not in `v6.0`). | Exact sign convention matches (`positive = leaning right`). Gap is estimator confidence/state metadata (below), and whether two-wheelers need a dedicated alias/branch or should reuse `Vehicle.Orientation.Roll` directly. |
| Lean angle estimator quality (`LeanAngleQuality`, `uint8`, `percent`, `[0, 100]`) | **not found in `v6.1`** | Zero estimator quality/confidence signals exist anywhere in `v6.1`. |
| Lean angle estimator state (`LeanAngleState`, `string`, `[ESTIMATED, CLAMPED, INVALID]`) | **not found in `v6.1`** | No standard enum distinguishing live estimated values from clamped or invalid outputs. |
| Side stand / kickstand deployed (T74 generic two-wheeler signal) | **not found in `v6.1`** | Standard safety interlock on nearly all motorcycles and scooters (engine cut-off / ride-ready check); no stand/kickstand signal exists in `v6.1`. |
| Tyre–road friction coefficient µ (`FrictionCoefficient`, `float`, dimensionless, `[0, 2]`) | Partial: **`Vehicle.ADAS.ESC.RoadFriction.{LowerBound,MostProbable,UpperBound}`** (`sensor`, `float`, `unit: percent`, `min: 0`, `max: 100`, `"Road friction values reported by the ESC system."`; present in `v6.0` and `v6.1`). | Existing branch is ESC-specific and expressed in `percent` (`0..100`) rather than dimensionless friction coefficient µ (`unit: ratio` in `v6.1/units.yaml`, `[0, 2]`), and carries no estimator confidence or `DEFAULT` fallback state for vehicles without ESC. |
| Friction estimator quality & state (`FrictionCoefficientQuality`, `FrictionCoefficientState`) | **not found in `v6.1`** | Needed so consumers never mistake a static fallback friction assumption (`DEFAULT`) for a live tyre–road estimate (`ESTIMATED`). |
| Total dynamic mass estimate (`EstimatedMass`, `float`, `kg`, `[0, 1000]`) | Partial: **`Vehicle.CurrentOverallWeight`** (`sensor`, `uint16`, `unit: kg`, `"Current overall Vehicle weight. Including passengers, cargo and other load inside the car."`; present in `v6.0` and `v6.1`), alongside static attributes `Vehicle.CurbWeight` and `Vehicle.GrossWeight`. | `CurrentOverallWeight` exists as a `uint16` kg sensor (worded for cars) without estimator confidence (`percent`) or state (`ESTIMATED`/`CLAMPED`/`DEFAULT`/`INVALID`). For two-wheelers, rider+pillion+luggage mass is often 40–60% of total mass and is dynamically estimated from longitudinal/inertial dynamics rather than axle load cells. |
| Mass estimator quality & state (`EstimatedMassQuality`, `EstimatedMassState`) | **not found in `v6.1`** | Same fallback-vs-live-estimate distinction as friction. |
| Throttle valve position (`Vehicle.Motorcycle.ThrottlePosition`, `float`, `percent`, `[0, 100]`) | **`Vehicle.Powertrain.CombustionEngine.TPS`** (`sensor`, `uint8`, `unit: percent`, `max: 100`, `"Current throttle position."`; present in `v6.0` and `v6.1`). Also `Vehicle.Chassis.Accelerator.PedalPosition` (`uint8`, `percent`, `0..100`). | Already covered by `Vehicle.Powertrain.CombustionEngine.TPS` (at `uint8` 1% granularity; only fractional `float` precision or twist-grip demand vs. pedal naming differs). **Proposed:** do **not** propose a duplicate `ThrottlePosition` upstream; optionally mention twist-grip naming under `Chassis.Accelerator` only if relevant. |

---

## 3. Upstream Contribution Rules Checked

Read directly from `COVESA/vehicle_signal_specification` (`master` branch, 2026-11-27):

- **`CONTRIBUTING.md`** (`https://raw.githubusercontent.com/COVESA/vehicle_signal_specification/master/CONTRIBUTING.md`, 72 lines):
  - For larger additions or design questions (such as a new domain branch or estimator-metadata pattern), **open a GitHub issue first** to discuss suitability before creating a Pull Request (*"Getting Support"* and *"Introduction"*).
  - Issues and PRs are reviewed in the weekly **VSS Tuesday 16:00 CET/CEST meeting**; non-trivial PRs stay open for at least one week before merging.
  - All commits in any subsequent PR must include a DCO sign-off (`Signed-off-by: Firstname Lastname <you@example.com>`, `git commit -s`) under the COVESA contribution guidelines (`https://covesa.global/contribute`).
- **`docs-gen/content/rule_set/basics.md`** (`https://raw.githubusercontent.com/COVESA/vehicle_signal_specification/master/docs-gen/content/rule_set/basics.md`):
  - Single root tree `Vehicle`, dot-delimited PascalCase path elements, case-sensitive.
  - Every parent branch of a proposed leaf must be declared explicitly.
  - Valid units in `v6.1/units.yaml` verified: `degrees`, `percent`, `kg`, `ratio` (dimensionless ratio `ONE-PER-ONE`).
  - No `.github/ISSUE_TEMPLATE` directory exists in `COVESA/vehicle_signal_specification` (HTTP 404 checked via GitHub API), so free-form Markdown issue structure is appropriate.

---

## 4. Proposed Upstream GitHub Issue Text (Draft Only — Do Not Send Without Approval)

> **Target repository (when approved):** `COVESA/vehicle_signal_specification` (GitHub Issue — discussion before any PR)

### Title (Proposed)
`Proposal: Two-wheeler / motorcycle signals (side stand, lean/dynamics estimator state & confidence, friction ratio)`

### Body (Proposed)

```markdown
### Summary & Motivation

We are building an open-source SDV diagnostics, telemetry, and ADAS platform for two-wheelers
(motorcycles) using COVESA VSS and Eclipse Kuksa. While reviewing COVESA VSS `v6.1`, most
powertrain and general vehicle signals map cleanly (`Vehicle.Speed`,
`Vehicle.Powertrain.CombustionEngine.*`, `Vehicle.LowVoltageBattery.CurrentVoltage`,
`Vehicle.AngularVelocity.*`, and the newly added `Vehicle.Orientation.Roll`).

However, several core two-wheeler signals and dynamics-estimator semantics are missing from
VSS `v6.1`:

1. **Side stand / kickstand status:** Almost every street motorcycle and scooter has a side-stand
   switch (used for start/gear interlocks and rider warnings), and many touring bikes also have a
   center stand. No stand signal exists in VSS `v6.1`.
2. **Estimator confidence and validity/fallback state for dynamic estimates:** On two-wheelers,
   lean angle (roll), tyre–road friction coefficient (µ), and total vehicle+rider+load mass
   are commonly produced by onboard state estimators (e.g., an EKF) rather than direct sensors.
   When observability is low (e.g., riding straight or at standstill), estimators clamp or fall
   back to static defaults. Downstream display, logging, and analytics consumers need a standard
   way to distinguish a live estimate (`ESTIMATED`) from a clamped value (`CLAMPED`), a static
   fallback (`DEFAULT`), or an unusable output (`INVALID`), alongside a `0–100%` confidence
   indicator.
3. **Tyre–road friction coefficient (µ) outside an ESC subsystem:** `Vehicle.ADAS.ESC.RoadFriction.*`
   in `v6.1` is ESC-scoped and uses `percent` (`0–100`), whereas non-ESC two-wheeler dynamics
   estimators report dimensionless µ (`unit: ratio`, typically `0.0–2.0`).

Before preparing a Pull Request, we would like feedback from the VSS community on:
- Whether two-wheeler-specific signals (such as side stand) should live under a dedicated
  `Vehicle.Motorcycle` (or `Vehicle.TwoWheeler`) branch, or be placed into existing branches
  (`Vehicle.Body`, `Vehicle.Chassis`, `Vehicle.Orientation`).
- Whether lean angle should reuse `v6.1`'s `Vehicle.Orientation.Roll` (and attach optional
  quality/state metadata nearby) rather than introducing a separate `LeanAngle` leaf.
- Whether `Vehicle.CurrentOverallWeight` (already `uint16` kg in `v6.1`) should be kept for
  total mass while adding estimator quality/state, or whether dynamic estimated mass warrants
  sibling metadata.

### Proposed Branch & Signals (for discussion)

Units below use standard VSS `v6.1` `units.yaml` names (`degrees`, `percent`, `kg`, `ratio`).
Parent branches are listed explicitly.

#### Option A — Dedicated two-wheeler branch (`Vehicle.TwoWheeler` or `Vehicle.Motorcycle`)

| Path | Type | Datatype | Unit | Min / Max or Allowed | Description |
|---|---|---|---|---|---|
| `Vehicle.TwoWheeler` | `branch` | — | — | — | Signals specific to two-wheeled vehicles (motorcycles, scooters). |
| `Vehicle.TwoWheeler.IsSideStandDeployed` | `sensor` | `boolean` | — | — | True if the side stand (kickstand) is deployed (down); false if retracted. |
| `Vehicle.TwoWheeler.IsCenterStandDeployed` | `sensor` | `boolean` | — | — | True if the center stand is deployed (down); false if retracted. |
| `Vehicle.TwoWheeler.LeanAngle` | `sensor` | `float` | `degrees` | `-90` / `90` | Vehicle roll (lean) angle relative to vertical (ISO 8855 X-axis; positive = leaning right). *(Could alternatively reuse `Vehicle.Orientation.Roll` in `v6.1`.)* |
| `Vehicle.TwoWheeler.LeanAngleQuality` | `sensor` | `uint8` | `percent` | `0` / `100` | Confidence of the lean angle estimate; `0` = no confidence, `100` = highest confidence. |
| `Vehicle.TwoWheeler.LeanAngleState` | `sensor` | `string` | — | `ESTIMATED`, `CLAMPED`, `INVALID` | Validity state of the lean angle estimate (no fallback default). |
| `Vehicle.TwoWheeler.FrictionCoefficient` | `sensor` | `float` | `ratio` | `0` / `2` | Estimated tyre–road friction coefficient (mu, dimensionless ratio). |
| `Vehicle.TwoWheeler.FrictionCoefficientQuality` | `sensor` | `uint8` | `percent` | `0` / `100` | Confidence of the tyre–road friction estimate; `0` = no confidence. |
| `Vehicle.TwoWheeler.FrictionCoefficientState` | `sensor` | `string` | — | `ESTIMATED`, `CLAMPED`, `DEFAULT`, `INVALID` | Validity state of the friction estimate. `DEFAULT` indicates a static fallback rather than a live estimate. |
| `Vehicle.TwoWheeler.EstimatedMass` | `sensor` | `float` | `kg` | `0` / `1000` | Dynamically estimated total mass (vehicle + rider + passenger + luggage). *(Overlaps with `Vehicle.CurrentOverallWeight`; see discussion below.)* |
| `Vehicle.TwoWheeler.EstimatedMassQuality` | `sensor` | `uint8` | `percent` | `0` / `100` | Confidence of the total mass estimate; `0` = no confidence. |
| `Vehicle.TwoWheeler.EstimatedMassState` | `sensor` | `string` | — | `ESTIMATED`, `CLAMPED`, `DEFAULT`, `INVALID` | Validity state of the mass estimate. `DEFAULT` indicates a static fallback rather than a live estimate. |

#### Alternative Option B — Place signals inside existing VSS `v6.1` branches

- Keep `Vehicle.Orientation.Roll` (`v6.1`) for lean angle and `Vehicle.CurrentOverallWeight` for
  total mass; only propose genuinely new signals (`IsSideStandDeployed` / `IsCenterStandDeployed`
  under `Vehicle.Body` or `Vehicle.Chassis`) plus a general VSS pattern for estimator
  confidence/state (`Quality` / `State`) if the community prefers avoiding vehicle-type top-level
  branches.

### Questions for the VSS Community

1. Does COVESA VSS prefer a dedicated `Vehicle.TwoWheeler` / `Vehicle.Motorcycle` branch, or
   extending existing vehicle-agnostic branches (`Body` / `Chassis` / `Orientation`)?
2. Is there an existing or planned cross-cutting pattern in VSS for estimator confidence
   (`Quality`) and validity/fallback state (`ESTIMATED` / `CLAMPED` / `DEFAULT` / `INVALID`)?
3. For tyre–road friction, would `ratio` (`[0, 2]`) be welcomed outside `Vehicle.ADAS.ESC`, or
   should two-wheeler estimators normalize to `Vehicle.ADAS.ESC.RoadFriction.MostProbable` (`percent`)?

We are happy to join a Tuesday VSS meeting to walk through the use case and prepare a PR
following the community's preferred placement.
```

---

## 5. Open Questions for the User (Before Any Submission)

1. **Branch naming preference:** Should the upstream proposal ask for `Vehicle.TwoWheeler` (broader COVESA appeal: motorcycles, scooters, e-mopeds) or `Vehicle.Motorcycle` (matching our current `vss/overlay.vspec` / D-028)?
2. **Scope of the first upstream issue:** Since `Vehicle.Orientation.Roll` (added in VSS `v6.1`), `Vehicle.CurrentOverallWeight`, `Vehicle.ADAS.ESC.RoadFriction.*`, and `Vehicle.Powertrain.CombustionEngine.TPS` already exist in `v6.1`, should we:
   - keep the full Option A vs. Option B comparison in one issue (as drafted above), or
   - narrow the first issue to the clearest gaps (`IsSideStandDeployed` + estimator `Quality`/`State` pattern)?
3. **Our own `vss/overlay.vspec` alignment (separate future `/signal-change`):** When we eventually bump our pinned VSS base from `v6.0` to `v6.1` (D-024), should `Vehicle.Motorcycle.LeanAngle` migrate to `Vehicle.Orientation.Roll` and `Vehicle.Motorcycle.ThrottlePosition` migrate to `Vehicle.Powertrain.CombustionEngine.TPS`?
4. **DCO sign-off & submission approval:** Opening any upstream GitHub issue or PR is outward-facing and requires your explicit approval (and your real name + email for `Signed-off-by` on any future PR per COVESA `CONTRIBUTING.md`). Do you want to submit this issue, and if so, which GitHub account should open it?
