# Physics-informed anomaly model and fault catalog (idea note)

Idea note (Claude, 2026-10-23), **not a decision**. The decisions are D-083 (staged physics-informed model, compared with a model without physics) and D-084 (fault catalog in defs, matched by vehicle-mcp, explained by the LLM). This note holds D-083 stage 0 and the D-084 schema draft. Known conflicts with recorded decisions: none; every signal below must come from defs (invariant 2), and inputs marked `pending` do not exist yet.

## 1. Stage 0: subsystem physics models (D-083 level 1)

| Subsystem | Model (lumped) | Parameters identified | Inputs and status | Faults it separates |
|---|---|---|---|---|
| Battery | V = OCV(SOC, T) - I*R0 - V_RC; dV_RC/dt = -V_RC/(R1*C1) + I/C1 (one-RC Thevenin) | R0, R1, C1, capacity | battery voltage at 1 kHz (D-079 W1/W2, pending: ADC); current (ACS758LCB-200B, D-082, pending); battery NTC (pending) | sulfation (R0 up), capacity loss, weak cell (crank dip shape) |
| Charging | regulated plateau 14.0-15.0 V (CONFIRM, baseline note); output current vs RPM up to the regulator limit | plateau voltage, cut-in RPM, output slope | `did.BATTERY_VOLTAGE`, `did.ENGINE_SPEED`; current (pending); R/R NTC (pending); ripple needs Q-036 | regulator over-temperature, stator phase open (ripple, Q-036), poor connection (sag under load) |
| Cooling | C*dT/dt = Q_engine(RPM, MAP) - hA*(T - T_amb)*f(speed) - Q_fan | thermal time constant, heat-transfer gain, fan effect | `did.COOLANT_TEMP`, `did.ENGINE_SPEED`, MAP DID, `sensor` vehicle speed; ambient (BME280, pending) | thermostat stuck open/closed, low coolant, fan failure |
| Air/fuel | speed-density: air mass ~ MAP * RPM * VE / IAT; fuel trim residual | volumetric-efficiency map offset, trim bias | MAP, IAT, RPM, STFT/LTFT DIDs (tier and verification per D-068) | vacuum leak (lean at idle, trims high), clogged injector, MAP sensor drift |
| Longitudinal | m*dv/dt = F_drive - 0.5*rho*CdA*v^2 - C_rr*m*g - m*g*sin(theta); RPM/speed ratio per gear | drag area, rolling resistance, ratio per gear | RPM, vehicle speed, `gear_estimate` (D-070) | clutch slip (ratio off under load), brake drag, tyre pressure (rolling resistance up) |

Not here on purpose: cornering kinematics (lean from yaw rate and speed). It sits next to the safety function; the anomaly model never feeds the safety partition (invariant 3).

Stage 1 estimators (classical, before any network): recursive least squares for R0/R1/C1 on the W2 crank window, a first-order thermal model fitted on W3/W4, the per-gear ratio table from `gear_estimate`. Their residuals are the first anomaly features, and the same features feed the baseline without physics (D-083 item 3).

## 2. Fault catalog schema draft (D-084)

Implemented in faults/catalog.yaml (defs 0.28.0).

One entry per fault, YAML, vehicle-independent; a per-vehicle list says which entries apply.

```yaml
- id: CHG-003                      # subsystem prefix + number
  subsystem: charging
  root_cause: Stator phase open circuit
  symptoms:                        # every signal must exist in defs (codegen check)
    - signal: did.BATTERY_VOLTAGE
      direction: down
      condition: window W4_CRUISE   # D-079 window, or an expression on defs signals
    - signal: derived.charging_ripple
      direction: up
      condition: rpm above idle band
  needs: [did.BATTERY_VOLTAGE, did.ENGINE_SPEED, derived.charging_ripple]
  residual: charging.output_vs_rpm  # D-083 level-1 model residual or parameter
  rating: {severity: 6, occurrence: 4, detectability: 6}   # 1-10, AIAG-VDA scales
  detectable_now: false             # derived.charging_ripple waits for Q-036
  rider_text: >
    The charging system is not keeping the battery charged at higher engine speeds.
    The battery may run down on longer rides.
  action: Have the stator windings and the regulator/rectifier measured.
  sources:
    - {ref: "<service manual section or paper>", confidence: high}
```

Rules: no entry without a source is shown to a rider (CONFIRM until sourced); high-severity entries (brakes, steering, tyres, fuel leak) always advise stopping and an inspection; the text never says riding on is safe.

## 3. Deep-research brief (for the user's research tool)

Copy as the research prompt. The output maps one-to-one onto the schema above.

> Research the failure modes of a small single-cylinder, fuel-injected, liquid-cooled motorcycle (reference vehicle: Honda CL250, 2023+, Keihin PGM-FI, 12 V AGM battery, three-phase permanent-magnet alternator with a shunt regulator/rectifier). Cover these subsystems: battery and starting, charging, ignition, fuel and air (injection, MAP/IAT/TPS/O2 sensors, idle control), cooling, lubrication, clutch and gearbox, final drive (chain/sprockets), brakes and ABS, wheels and tyres, suspension and steering, electrical wiring and connectors, lighting and indicators.
> For each failure mode give: (1) root cause; (2) observable symptoms as measurable signal changes (which signal, which direction, under which operating condition: key-on, cranking, warm idle, cruise, after stop); (3) whether it sets a DTC and which (SAE J2012 code if standard); (4) severity, typical occurrence and how detectable it is from these signals: engine RPM, vehicle speed, coolant temperature, intake air temperature, MAP, throttle position, short/long fuel trims, battery voltage (1 kHz), battery current, IMU acceleration and rotation rates, engine-case vibration, ambient temperature, exhaust gas temperature; mark modes that none of these can observe; (5) a plain-language explanation for a rider with no technical knowledge; (6) the recommended check or repair; (7) at least one source per mode (service manual, SAE/ISO standard, peer-reviewed paper, or a documented repair case) with a confidence level. Do not invent sensor names, DTC numbers or part numbers; write "unknown" when a fact has no source. Output as a table or YAML, one row per failure mode.
