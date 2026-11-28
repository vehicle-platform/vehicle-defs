# Charging balance (net battery current and Ah per ride)

Status: idea note, not a decision. Nothing here takes effect without a recorded `D-xxx` decision in `DECISIONS.md`.

## Finding: no battery-current signal exists in defs yet

The battery-current sensor (ACS758LCB-200B, +/-200 A Hall sensor, hardware wave W2, D-079 / D-082 item 3) is in the procurement and integration documents only. A search of `uds/`, `dbc/`, `derived/` and `vss/` finds it in two comments (`derived/cl250_derived.yaml`: "ACS758 on rt-core, not defined in defs"; `faults/catalog.yaml`: "needs the planned battery-current sensor") and nowhere as a signal, DID or CAN message. By platform rule 2 no signal is invented until the sensor has a defs entry, so this note proposes the entries instead of adding them.

What defs already has for the charging path: `did.BATTERY_VOLTAGE` (0xF442, from the ECU), `derived.charging_plateau_voltage` and `derived.charging_ripple` (voltage side only), and the parked self-discharge catalog entry (`battery_self_discharge`). None of them says whether the battery is gaining or losing charge.

## Proposed signals (after the sensor exists on the bench)

1. Platform-bus sample (rt-core ADC, not an ECU DID, so not in `uds/vehicle_cl250.yaml`): `BATTERY_CURRENT`, signed, A, positive = into the battery, 1 kHz sampled and reported as a 100 ms mean in `VehicleEngine`-style QM frame (new message through `/signal-change`, MINOR bump). Validity bit like the other samples; calibration offset (zero-current ADC value) stored by rt-core, not in the frame.
2. Derived per window (`derived/cl250_derived.yaml`, same style as `charging_plateau_voltage`):
   - `net_battery_current_idle`: mean `BATTERY_CURRENT` while the engine is at idle (ENGINE_SPEED in the idle band, vehicle stationary).
   - `net_battery_current_riding`: mean `BATTERY_CURRENT` while moving above the plateau RPM.
   - `ah_balance_ride`: integral of `BATTERY_CURRENT` over the ride in Ah (negative = the ride discharged the battery). Reset at ride start by the ride-mark logic (D-133); the starter inrush (60-90 A for about 1 s) is excluded by the cranking gate already used for the plateau voltage.
3. Alert/analysis hooks (data only, PROVISIONAL): a negative idle balance with a healthy plateau voltage points to load above the alternator output at idle (the platform's own worst case is about 2 A, `parked-current.md`); a positive riding balance with a low plateau voltage is an inconsistent pair and a sensor-fault hint.

## Open points

- Alternator output of the CL250 is not in the owner's manual; the figure quoted by an AI tool on 2026-11-28 (about 330-340 W at 5,000 rpm) is UNVERIFIED and must come from the service manual before any threshold uses it.
- Sensor placement (series element in the battery cable), zero-offset drift with temperature and the ADC divider (VOUT x 0.667) are hardware items for the W2 bench.
- rt-core side (ADC driver, window integration) is a follow-up card; the vehicle-server Python reference for the derived signals can follow the existing golden-vector pattern once the defs entries exist.
