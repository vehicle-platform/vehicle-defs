# Derived-signal thresholds: research brief (D-103)

Claude, 2026-11-05. **Status:** the values below are in force as provisional constants (D-103);
this note is the plan to replace them, not a decision. The machine-readable source is
`vehicle/cl250_constants.yaml` (look for `source: "D-103 recommendation: ..."`); this table is a
snapshot of it and loses to it when they differ.

## How to replace a value

1. **Measured on the bike (preferred):** after G1/V1, read the value from the sessions (the
   `source` of each row says which measurement), then `/signal-change`: new `value`,
   `status: measured`, the evidence in `source` (session ids stay out of git if they carry
   position, D-033).
2. **Deep research (when no measurement is possible yet):** a cited range from the CL250 service
   manual, Honda data for the same engine family, or peer-reviewed motorcycle dynamics literature.
   Keep `status: provisional` and replace the `source` text with the citation.
3. A changed value is a defs release; vehicle-server (the Python reference) and later rt-core pick
   it up at their bump without code changes.

## Research questions (grouped)

- **Engine (CL250 manual first):** warm idle speed and band; thermostat opening and fan switch
  temperatures; rev limiter RPM (also needed by the analyzer tach, roadmap A1.1); warm-idle MAP;
  charging plateau start RPM and regulated voltage (CONFIRM values in
  `cl250-technical-baseline.md` section 2).
- **Rider and vehicle dynamics (literature):** braking-event deceleration levels, pitch rate of
  wheelie/stoppie starts versus suspension dive, jerk comfort limits, typical road-riding lateral
  acceleration and lean percentiles (the two aggressiveness references).
- **Sensors:** TPS noise floor at closed throttle, GNSS speed accuracy of the fitted receiver,
  fuel-level sender slosh, battery voltage step of the fan load.
- **Method choices:** road-roughness band versus the IMU rate and engine orders; shift and launch
  detection windows; the equal-weight aggressiveness scores (whether a weighting from literature
  exists).

## Values in force

| Constant | Value | Used by | Why this value / what replaces it |
|---|---|---|---|
| `derived_operating_coolant_degc` | 80.0 degC | cold_engine_abuse, idle_rpm_std, idle_rpm_drift, ride_warmup_time, ride_thermal_cycle_count | W3_WARM_IDLE already uses 80 degC; a liquid-cooled single's thermostat opens at about 80-85 degC (generic); replace by the coolant plateau of the first rides |
| `derived_cold_coolant_degc` | 50.0 degC | ride_thermal_cycle_count | the cold level of a thermal cycle, 30 K below derived_operating_coolant_degc as hysteresis; replace after the first cold starts |
| `derived_idle_rpm_min` | 1000.0 rpm | idle_map_residual, cranking_dip, idle_rpm_std, idle_rpm_drift | the same band as W3_WARM_IDLE (provisional there), around the ~1400 rpm idle of ideas/cl250-technical-baseline.md (CONFIRM); replace by the warm-idle band measured at V1 |
| `derived_idle_rpm_max` | 1800.0 rpm | idle_map_residual, idle_rpm_std, idle_rpm_drift, engine_braking_phase | the same band as W3_WARM_IDLE (provisional there), around the ~1400 rpm idle of ideas/cl250-technical-baseline.md (CONFIRM); replace by the warm-idle band measured at V1 |
| `derived_moving_speed_min_kmh` | 3.0 km/h | clutch_state, neutral_coasting_state, launch_event, pitch_event, road_roughness, idle_rpm_std, idle_rpm_drift, engine_braking_phase, refuel_event | three steps of the ECU speed resolution (1 km/h); below = at rest |
| `derived_throttle_closed_max_pct` | 2.0 % | clutch_state, neutral_coasting_state, idle_map_residual, engine_braking_phase | TPS noise floor at a closed throttle (generic); replace by the closed-throttle spread seen at V1 |
| `derived_throttle_load_min_pct` | 10.0 % | clutch_state | throttle clearly open = driven (clutch slip, launch); generic |
| `derived_gear_ratio_tolerance` | 0.06  | clutch_state, launch_event | half the smallest gear step (gear_ratio_5 / gear_ratio_6 = 1.123, half of 12.3 %); a measured ratio farther than this from every gear = not engaged |
| `derived_steady_speed_spread_kmh` | 4.0 km/h | speedometer_error, effective_tyre_radius, ride_final_drive_ratio | the W4_CRUISE stability band (+-2 km/h) |
| `derived_steady_min_duration_ms` | 10000 ms | speedometer_error, effective_tyre_radius, ride_final_drive_ratio | the W4_CRUISE minimum duration |
| `derived_gnss_speed_accuracy_max_mps` | 0.3 m/s | wheel_slip, speedometer_error, effective_tyre_radius | a good 3D fix of a u-blox class receiver reports 0.05-0.2 m/s speed accuracy; above this the GNSS speed is not a reference |
| `derived_calibration_speed_min_kmh` | 30.0 km/h | speedometer_error, effective_tyre_radius, ride_final_drive_ratio | the 1 km/h ECU speed resolution is 3.3 % at 30 km/h, below that it dominates a speed or radius calibration |
| `shift_event_rpm_step_min_rpm` | 500.0 rpm | shift_event | the smallest gear step (12.3 %) at 4000 rpm is about 490 rpm; smaller RPM changes are throttle, not a shift |
| `shift_event_window_ms` | 500 ms | shift_event | a typical clutch-and-lever shift lasts 200-500 ms (generic); replace after the first rides |
| `shift_event_speed_change_max_kmh` | 3.0 km/h | shift_event | speed stays continuous through a shift; three ECU speed steps |
| `launch_event_end_speed_kmh` | 10.0 km/h | launch_event | by 10 km/h a launch in gear 1 has the clutch engaged (generic) |
| `braking_event_decel_min_mps2` | 3.0 m/s2 | braking_event | about 0.3 g, above engine braking and normal deceleration (generic motorcycle braking literature: normal 2-4, strong above 5 m/s2) |
| `braking_event_min_duration_ms` | 300 ms | braking_event | rejects single-sample accel spikes (3 vehicle_accel periods) |
| `wheel_slip_accel_min_mps2` | 1.5 m/s2 | wheel_slip | wheel slip only counts under clear acceleration or braking |
| `wheel_slip_speed_min_kmh` | 10.0 km/h | wheel_slip | the relative speed difference is noise below 10 km/h |
| `pitch_event_rate_min_dps` | 30.0 deg/s | pitch_event | suspension dive/squat stays well below; wheelie and stoppie starts exceed it (generic); replace from IMU data |
| `road_roughness_band_low_hz` | 5.0 Hz | road_roughness | above the 1-3 Hz sprung-mass body modes |
| `road_roughness_band_high_hz` | 20.0 Hz | road_roughness | below the 50 Hz Nyquist limit of the 10 ms IMU sample and the engine's first order at idle (about 23 Hz at 1400 rpm) |
| `idle_map_residual_expected_kpa` | 35.0 kPa | idle_map_residual | typical warm-idle MAP of a small single, 30-40 kPa (generic); replace by the W3_WARM_IDLE median of the first rides |
| `heat_soak_delta_speed_max_kmh` | 10.0 km/h | heat_soak_delta | below 10 km/h ram air no longer cools the intake (generic) |
| `charging_plateau_rpm_min` | 3000.0 rpm | charging_plateau_voltage | a permanent-magnet alternator reaches the regulator set point above about 2500-3000 rpm (generic; ideas/cl250-technical-baseline.md section 2 gives the 14.0-15.0 V plateau and the 340 W rating at 5000 rpm, CONFIRM); replace by the plateau start seen at V1 |
| `cold_engine_abuse_rpm_max` | 6000.0 rpm | cold_engine_abuse | just below the 6250 rpm torque peak (vehicle-work-plan.md section 2) |
| `cold_engine_abuse_load_max_pct` | 70.0 % | cold_engine_abuse | generic cold-engine guidance; high load before operating temperature |
| `over_rev_rpm_min` | 9500.0 rpm | over_rev | 1000 rpm above the 8500 rpm peak-power point (vehicle-work-plan.md section 2); the CL250 limiter is not in defs: replace by the highest RPM seen at the limiter |
| `lugging_rpm_max` | 3000.0 rpm | lugging | less than half the 6250 rpm torque peak (generic for a single) |
| `lugging_load_min_pct` | 80.0 % | lugging | near-full load at low RPM in gear 2 or above (generic) |
| `engine_braking_phase_fuel_rate_max_lph` | 0.1 L/h | engine_braking_phase | fuel cut = fuel rate near zero (generic; warm idle uses far more) |
| `refuel_event_step_min_pct` | 10.0 % | refuel_event | 1.2 L of the 12 L tank, above sender slosh at rest |
| `fuel_level_filtered_accel_max_mps2` | 0.5 m/s2 | fuel_level_filtered | samples taken above this acceleration are slosh and left out of the average |
| `ride_fan_on_temperature_voltage_step_v` | 0.15 V | ride_fan_on_temperature | a 5-8 A fan load drops the battery voltage by about 0.1-0.3 V at idle (generic); replace by the step seen at the first fan start |
| `ride_fan_on_temperature_coolant_min_degc` | 90.0 degC | ride_fan_on_temperature | fan steps are searched only above this coolant temperature (generic thermoswitch range 95-105 degC) |
| `throttle_torque_lag_step_min_pct` | 20.0 % | throttle_torque_lag | a throttle step = at least 20 % within throttle_torque_lag_step_window_ms |
| `throttle_torque_lag_step_window_ms` | 200 ms | throttle_torque_lag | two THROTTLE_POS poll periods |
| `throttle_torque_lag_search_max_ms` | 1000 ms | throttle_torque_lag | the cross-correlation lag is searched from 0 to this |
| `ride_aggressiveness_score_throttle_rate_ref_pct_s` | 200.0 %/s | ride_aggressiveness_score | the p95 throttle opening rate that scores full (generic); equal weights, see the signal description |
| `ride_aggressiveness_score_jerk_ref_mps3` | 10.0 m/s3 | ride_aggressiveness_score | the p95 absolute jerk that scores full (generic comfort literature: above 2-3 m/s3 is felt as harsh) |
| `ride_aggressiveness_score_decel_ref_mps2` | 6.0 m/s2 | ride_aggressiveness_score | the braking-event peak that scores full (strong braking, about 0.6 g) |
| `ride_aggressiveness_score_shift_rpm_ref` | 7000.0 rpm | ride_aggressiveness_score | the p95 RPM before an upshift that scores full (between the 6250 rpm torque and 8500 rpm power peaks) |
| `ride_cornering_aggressiveness_lat_accel_ref_mps2` | 6.0 m/s2 | ride_cornering_aggressiveness | the p95 lateral acceleration that scores full (about 0.6 g, sporty road riding) |
| `ride_cornering_aggressiveness_lean_ref_deg` | 40.0 deg | ride_cornering_aggressiveness | the p95 lean angle that scores full (a road bike on road tyres, generic) |
