Status: idea note, not a decision

# Validation Plan Draft — Evidence Levels and Verification Protocol

Idea note (Gemini, 2026-11-26), **not a decision**. Nothing in this document takes effect without a recorded `D-xxx` decision in `DECISIONS.md`.

**Known conflicts with recorded decisions:** none. This note respects invariant 1 (read-only ECU, single tester per D-020/D-027/D-037), invariant 2 (defs-only signals and rules), invariant 3 (isolated safety partition on `vehicle-safety-node`, D-118), invariant 7 (tools compute all numbers, LLM only explains), D-033 (public repository privacy: never commit real ride files, GPS traces, VINs or keys), D-076 (position restricted to user-owned servers), and D-125 (English-only project artifacts).

---

## 1. Evidence Levels

Every validation claim on `vehicle-platform` must state which of the four evidence levels produced it. Higher levels do not replace lower levels; each level eliminates a specific class of failure.

| Level | Label | Source | What it can prove | What it cannot prove |
|---|---|---|---|---|
| **L1** | `synthetic` | Deterministic scenario generators (`vehicle-server` demo scenarios, `vehicle-ml` synthetic faults, unit/eval fixtures) | Pipeline wiring, schema conformance, determinism, regression safety, tool routing, prompt/guard compliance, repeatability across seeds | Real-world threshold validity, sensor noise immunity, real false-alarm rates, physical fault signatures |
| **L2** | `bench` | Restbus and electrical HIL bench (`vehicle-hil-bench`, STM32F4 restbus + bench harnesses) | End-to-end CAN timing, E2E CRC/counter fault handling, timeout fallback on `vehicle-safety-node`, ISO-TP/UDS read-only gating, alert latency under injected bus/sensor faults | Real motorcycle vibration/thermal dynamics, weather/traffic exposure, long-term rider alert fatigue |
| **L3** | `real` (healthy) | Recorded rides on the user's Honda CL250 (Phase 0 / target build, kept outside public git per D-033) | Baseline signal distributions, operating-point coverage, real sensor dropout rates, false-alarm rate (FA/h) of PROVISIONAL rules and anomaly models | True recall / detection delay on real mechanical or electrical faults |
| **L4** | `real` (labelled fault) | Confirmed real faults (worn battery, loose charging connector, cooling fan issue, chain slack) with workshop verification and onset/symptom labels | True sensitivity, precision, detection lead time, and real-world diagnostic utility of catalog matching and physics residuals | Generalisation to unseen motorcycles without multi-vehicle data (D-078 future scope) |

---

## 2. Claim-by-Claim Evidence Matrix

Synthetic data **cannot** validate detection thresholds or model generalisation: when the same assumptions generate the synthetic fault and define the threshold, passing is circular.

| Platform claim | Acceptable evidence | Does NOT count as evidence | Minimum gate before removing `PROVISIONAL` |
|---|---|---|---|
| **Alert rule thresholds** (D-129, D-103 derived constants) | **L2 (`bench`)** for debounce/hysteresis/cooldown mechanics; **L3 (`real` healthy)** replay for false-alarm rate (target: 0 P1 false alarms/ride, bounded P2 FA/h); **L4** or calibrated L2 sweeps for trigger sensitivity | **L1 (`synthetic`)** threshold tuning (circular); single short idle log | Replay over the L3 first-ride set (Section 3) + documented workshop/manual confirmation where available |
| **Anomaly model** (D-083 physics-informed vs non-physics baseline) | **L1** for code correctness, seed stability, and ablation wiring only; **L2 (`bench`)** for sensor-fault attribution; **L3** for healthy residual calibration and operating-point drift; **L4** for real fault detection | **L1 (`synthetic`)** detection scores cited as real-world performance; leaking ride windows across train/val/test splits | L3 healthy residual baseline + L2 bench fault sweeps + honest non-physics comparison on the same split |
| **Fault catalog matching** (D-084, D-127 `check_symptom`) | **L1** for deterministic keyword/symptom routing, D-084 item 5 displayable gating, and unconfirmed `data_only` isolation; **L2** for live signal-direction triggers; **L4** for confirming symptom-to-cause accuracy | Free-form LLM diagnosis text; unverified CONFIRM entries shown as rider advice | Verified service-manual / workshop sources per entry (D-084 item 5) + L1/L2 regression tests |
| **Assistant tool accuracy & safety** (D-121, D-128, D-131, D-132, invariant 7) | **L1** (`vehicle-server chat-eval` + independent held-out eval + safety red-team set in EN/TR) for tool selection, fact grounding, zero invented numbers, zero `advise_stop` contradictions, latency; **L3** anonymized prompt replay (off-repo) for real phrasing | Cherry-picked single prompts; training-set questions reused as eval; claiming LLM accuracy proves physical fault accuracy | Held-out eval + red-team pass across target models (D-132 stage 0 bake-off) + human TR review |
| **Lane keeping / LDW** (future, Raspberry Pi 5 classic CV) | **L1/L2** scenario replay (e.g. ASAM OpenSCENARIO-style structured test scenarios) for geometry and timing; **L3** real road footage across daylight, shadow, wet tarmac, lean angles (kept off-repo) for false-warning rate | Static single-frame demos; car-only datasets without motorcycle lean compensation | Multi-condition L3 false-warning study; remains strictly advisory and off the safety MCU (invariant 3) |

---

## 3. Protocol for the User's First Real Rides (L3)

Before any PROVISIONAL threshold (D-103, D-129) is promoted or any real anomaly baseline is fitted, collect an initial healthy ride cohort on the Honda CL250 following `phase0-data-collection-plan.md` and `vehicle-work-plan.md`:

1. **What to record per ride:**
   - Full telemetry + IMU session from the read-only tester (`vehicle-connectivity-node` in Phase 0, later `vehicle-rt-core`), ingested locally on the user's `vehicle-server`.
   - Lightweight ride metadata logged outside git: date, approximate ambient temperature band (`<15 °C`, `15–25 °C`, `>25 °C`), route type (urban / suburban / highway), cold vs warm start, and a post-ride rider note ("normal ride" or any observed issue).
   - **Privacy (D-033, D-076):** Raw sessions, GPS traces, and VINs stay strictly on the user's own storage and are never committed to any public repository.
2. **Minimum initial cohort (target: 10–15 rides, >= 6 riding hours):**
   - **Cold starts (≥ 3 rides):** engine off ≥ 6 h before key-on, capturing crank voltage dip and warm-up curve.
   - **Urban stop-and-go (≥ 3 rides):** sustained idle and low-speed traffic to observe peak normal coolant temperature and radiator fan cycling.
   - **Steady cruise / highway (≥ 3 rides):** sustained speed/RPM across upper gears to verify charging plateau and gear-ratio bands.
   - **Varied ambient / load (≥ 2 rides):** cooler morning/evening vs warmer midday runs to expose operating-point shift (compare with `vehicle-ml` Stage 2 holdout caveat).
3. **PROVISIONAL alert-rule false-alarm check by replay:**
   - After ingesting the cohort, run `vehicle-server alerts replay --all --dry-run` (D-129) over all healthy L3 rides.
   - Record per-rule triggers, duration, peak value, and false alarms per riding hour (`FA/h`), split by priority class (**P1 urgent** vs **P2 advisory**).
   - Any P1 rule that fires on a verified healthy ride blocks promotion of that rule until the debounce, hysteresis, or threshold is investigated against real measurements (never silently suppressed).

---

## 4. Safe Fault Injection Boundaries (L2 Only)

Fault injection is essential to verify error detection, debounce, and fail-safe fallback, as recommended for system-level and software-level verification in **ISO 26262-4:2018** and **ISO 26262-6:2018**. On this platform, fault injection is strictly bounded:

- **Bench / HIL only (`vehicle-hil-bench`):** All fault injection happens on the restbus HIL bench or an isolated bench harness — never on the live motorcycle in traffic.
- **ECU stays read-only (invariant 1, D-020, D-027, D-037):** Never inject faults by sending UDS write, clear, reset, I/O control, or reprogramming requests to the Honda CL250 ECU. All vehicle-bus fault scenarios (e.g., over-temperature, voltage sag, bus-off, dropped DIDs, corrupted E2E CRC/counter) are emulated by the STM32F4 restbus node on the bench.
- **Never disable safety hardware (invariant 3, D-118):** Never bypass watchdogs, disconnect safety-node LED/dead-man outputs on the bike, or route safety-partition inputs (cornering, blind spot, immobilizer) through QM software (Raspberry Pi, phone, LLM, ML) during testing. Bench tests verify that `vehicle-safety-node` detects missing/invalid platform-bus E2E frames and falls back cleanly to its local IMU (D-042).
- **Structured scenario definitions:** Bench and simulation fault scenarios should follow reproducible, versioned scenario files (conceptually aligned with scenario-based testing in **ASAM OpenSCENARIO**) specifying initial conditions, fault onset time, magnitude, duration, and expected verdict.

---

## 5. Mandatory Data-Provenance Labeling in `docs/test-results/`

Every run folder under `vehicle-defs/docs/test-results/<family>/<date>-<slug>/` must declare its provenance explicitly in its header and summary table so synthetic benchmarks are never mistaken for on-vehicle validation:

```markdown
- **Data provenance:** `synthetic` | `bench` | `real` (pick all that apply; never omit)
- **Evidence level:** `L1` | `L2` | `L3` | `L4`
- **Scope note:** One sentence stating what this run proves and what it does not prove.
```

Rules for applying labels:

1. **`synthetic` (L1):** Generated scenarios, mock fixtures, or LLM eval runs against synthetic rides. Raw English JSON/Markdown artifacts may be committed next to the write-up (per `docs/test-results/README.md`).
2. **`bench` (L2):** Restbus HIL or bench-harness captures (`vehicle-hil-bench`). Record bench firmware commit, defs tag, fault-injection script, and hardware setup.
3. **`real` (L3/L4):** Derived strictly from on-vehicle CL250 recordings. **Never commit raw ride files, GPS coordinates, timestamps that reveal home/work locations, or VINs** (D-033, D-076). Commit only aggregate anonymized metrics (e.g., session count, total hours, FA/h per rule, residual quantiles) together with the software/defs commits used to compute them.
4. **Mixed runs** (e.g., L3 healthy rides combined with L2 bench fault sweeps) must list each label separately per table row — never merge synthetic and real metrics into one headline number.

---

## 6. References

- **ISO 26262-4:2018** — *Road vehicles — Functional safety — Part 4: Product development at the system level* (system integration and verification, including fault injection methods): https://www.iso.org/standard/68386.html
- **ISO 26262-6:2018** — *Road vehicles — Functional safety — Part 6: Product development at the software level* (software verification and fault injection testing): https://www.iso.org/standard/68388.html
- **ASAM OpenSCENARIO** — Scenario-based testing standard for ADAS and automated driving systems: https://www.asam.net/standards/detail/openscenario/ (XML specification: https://www.asam.net/standards/detail/openscenario-xml/, DSL specification: https://www.asam.net/standards/detail/openscenario-dsl/)
- Internal platform references: `DECISIONS.md` (D-020, D-027, D-033, D-037, D-042, D-076, D-078, D-083, D-084, D-103, D-118, D-121, D-125, D-127–D-132), `phase0-data-collection-plan.md`, `vehicle-work-plan.md`, `test-results/README.md`.
