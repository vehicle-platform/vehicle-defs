# Model Context Protocol (MCP) Server: Architecture, Scenarios & AI Agent Capabilities

> **Idea notes, not decisions** (drafted with Gemini, 2026-10-05; moved here from the workspace root on 2026-10-07; reviewed against `DECISIONS.md`, `ARCHITECTURE.md` and the platform invariants on 2026-10-09). Nothing here overrides `DECISIONS.md` or vehicle-mcp's read-only scope (ARCHITECTURE: "vehicle-linux-node → vehicle-mcp (localhost, read-only) → cloud LLM"). The recorded tool set is the six tools of hardware-architecture §5b.7 (`get_live_snapshot`, `get_recent_stats`, `get_event_log`, `get_anomaly_status`, `get_maintenance_status`, `query_ride_history`); the other tools here are candidates.
>
> **Review (2026-10-09).** Verdicts as in `can-data-expansion.md`: CONTRADICTS (forbidden as written), EDIT (compatible once corrected), DECIDE (needs a decision or the named open question).
>
> | Item | Verdict | Basis |
> |---|---|---|
> | Rule 1 (no actuation or write tools), rule 2 (pre-computed statistics), rule 4 (VSS abstraction) | compatible | Invariant 1 and the read-only repo map (rule 1 now cites invariant 1 and D-114, provisional: vehicle-mcp is read-only for good); invariant 7: tools return computed values, never raw time series; D-028 |
> | Dual-brain voice assistant | compatible | D-044, D-047. Which assistant (templates, a local LLM or the hybrid cloud path) and what may reach a cloud LLM: Q-028 |
> | "System 1: JEV / TinyML reflex engine" | EDIT | "JEV" is not defined anywhere in the platform; the deterministic layer is rt-core / safety-node firmware (EKF, cornering decision), renamed in the diagram. "D-029 Autoencoder Gating" is wrong: D-029 is the polling budget |
> | "ISO 26262 ASIL-D" claims (document header, §5) | CONTRADICTS | D-046: no ASIL has been assigned yet (no HARA) |
> | Fuel pump / ignition isolation (§1 diagram, scenario 5.2) | CONTRADICTS | Invariant 6, feature-pool §15 |
> | Remote `LOCKED_ARMED` immobilizer (5.1) | CONTRADICTS | Invariant 6 (unlocked default, hidden bypass, 10 s unlock); reading the state is fine |
> | Coordinates to the cloud or a cloud LLM: 3.2 (CDN), 5.1, 5.2; crowd data of `query_road_hazards` | CONTRADICTS | Invariant 7 and ARCHITECTURE ("raw GPS is never sent"); in Phase 0 latitude and longitude never leave conn (D-060 item 3) |
> | Local position-derived tools: `estimate_range_and_efficiency(destination)`, rule 3 semantic geofencing; the group-mesh hazard position (6.1) | DECIDE (Q-028) | In Phase 0 only conn has a position (D-060 item 3); where position-derived values could be computed is Q-028 item 3. Sharing positions with other riders has no decision |
> | Scenario 5.2: the LLM dispatches to 112 with medical data | CONTRADICTS | An LLM must not trigger emergency actions; medical data is personal data (D-033); no eCall or cellular decision |
> | Signals not in defs (`MAP_kPa`, `IAT`, tire pressure, odometer, engine hours, rev-limiter strikes, slip ratio, `IMU_CHASSIS_FFT_PEAKS`, `CRASH_LATCH`, `0x380 PACK_HAZARD`) | CONTRADICTS | Invariant 2: only the defs DIDs and VSS paths exist (5 polled DIDs today); new ones go through `/signal-change` |
> | Resale passport (VIN, blockchain, cloud logs; 7.1) | CONTRADICTS | The VIN is never committed, the probe prints the WMI only (D-059, D-033); the data it audits does not exist |
> | Diagnostic triage (1.1) | EDIT | DTC read (0x19) is allowed, clear (0x14) is not (D-020). `safe_to_continue` / `max_recommended_speed_kmh` are safety advice: only deterministic modules may produce them, never the LLM or ML (invariants 3, 7) |
> | Wear, RUL, clutch-slip and brake-pad models (4.1, 4.2), coaching (3.1) | DECIDE | Each needs a deterministic upstream module (invariant 7); friction circle: Q-022 |
> | Acoustic / vibration diagnostics (1.2) | DECIDE (Q-025) | D-044: no raw audio or vibration on CAN or VSS |
> | Pre-ride briefing (2.1): TPMS, weather, the rider's name | DECIDE | TPMS is a pool item; weather is an external source; names are personal data (D-033) |
> | Highlight-reel generation and CDN publishing (3.2); any actuator tool | DECIDE (Q-027) | Producing or publishing artifacts and peripheral actuator writes go beyond today's read-only scope; hardware-architecture §10.2 lists approval-gated peripheral writes for Phase 2 |
> | Exposure to Claude, GPT and other third-party clients | DECIDE (Q-028) | hardware-architecture §5b.7: home-demo mode needs TLS + auth; which telemetry may reach a cloud LLM is open |
> | §5 commercial summary (SaaS pricing) | removed | Commercial planning stays outside the public repo (D-033; user, 2026-10-09) |

**Document:** `docs/ideas/mcp-scenarios.md` (originally `MCP_SCENARIOS_AND_AGENT_ARCHITECTURE.md` at the workspace root)  
**Target Repository:** `vehicle-mcp` (Exposed to Claude, GPT, and Local LLMs)  
**Standard Compliance:** Anthropic Model Context Protocol (MCP) v1.0, COVESA Vehicle Signal Specification (VSS v4.0), ISO 14229 (UDS), ISO 26262 ASIL-D Safe Read-Only Boundary.

---

## 1. Executive Summary & Architectural Philosophy

The `vehicle-mcp` service transforms the motorcycle from an opaque mechanical asset into an **Intelligent Conversational Agent**. By exposing high-cadence vehicle telemetry, UDS diagnostics, and edge anomaly states through the open **Model Context Protocol (MCP)**, large language models (LLMs) can reason across live physics, historical baselines, and maintenance manuals.

### The Dual-Brain Paradigm: System 1 vs. System 2

```
========================================================================================
[ VEHICLE EDGE SENSORS & CAN NETWORK (FDCAN1 / FDCAN2) ]
========================================================================================
           │
           ├──► [ SYSTEM 1: DETERMINISTIC REFLEX LAYER, rt-core / safety-node (<10 ms) ]
           │      ├── Real-Time Roll/Pitch Lean Angle (EKF @ 100 Hz)
           │      ├── Tank-Slapper / Resonance Bandpass Filter (6–9 Hz)
           │      ├── Fast-Gate Anomaly Triage (D-029 Autoencoder Gating)
           │      └── Active Actuation: Strobe Lights, Haptic Grips, Fuel Isolation
           │
           └──► [ SYSTEM 2: VEHICLE-MCP & CLOUD LLM (Contextual Reasoning & Dialogue) ]
                  ├── Conversational Voice Assistant (Helmet Intercom / Mobile App)
                  ├── Predictive Maintenance & Root-Cause Failure Diagnostics
                  ├── AR Cornering & Performance Coaching
                  └── Cryptographic Resale Dossiers & Pre-Ride Briefings
========================================================================================
```

### Safety & Isolation Boundary (The 4 Inviolable Rules)
1. **Strict Read-Only Enforcement (invariant 1, D-114):** `vehicle-mcp` exposes zero actuation or write tools. An LLM can never manipulate throttle, braking, fuel, or ignition.
2. **Pre-Computed Statistics (No LLM Math Hallucinations):** Tools never return raw 100,000-point time-series. Python/PyArrow pre-computes mean, standard deviation, percentiles, and anomaly scores, delivering pre-digested domain summaries.
3. **Location Privacy (Semantic Geofencing):** Raw GPS coordinates are masked into high-level semantic tags (`"Mountain Pass"`, `"Urban Congestion"`, `"15 km from Garage"`).
4. **VSS Abstraction (Vehicle-Agnostic):** Internal tool mappings utilize standard COVESA VSS signal paths (`Vehicle.Powertrain.CombustionEngine.Speed`) rather than OEM-specific CAN IDs, ensuring 100% portability to any car, van, or motorcycle.

---

## 2. Comprehensive MCP Tool Catalog

The `vehicle-mcp` server implements 12 dedicated tools categorized into four functional groups:

| Tool Identifier | Category | Input Arguments | Output Description |
|---|---|---|---|
| `get_live_telemetry_snapshot` | Diagnostics | `attributes: list[str]` | Instantaneous engine state, thermodynamic metrics, and electrical health. |
| `get_component_health_status` | Maintenance | `component: str` | Remaining useful life (RUL) for clutch, brake pads, battery, or intake. |
| `run_diagnostic_triage` | Diagnostics | `dtc_code: str (opt)` | Root-cause analysis combining active DTCs, UDS DIDs, and anomaly history. |
| `get_pre_ride_briefing` | Safety | `planned_distance_km: float` | Autonomous pre-ride inspection, tire pressure status, and weather risks. |
| `query_ride_coaching` | Performance | `session_id: str` | Deep cornering review, Kamm friction circle margins, and apex analysis. |
| `generate_telemetry_reel` | Media/Social | `session_id: str, criteria: str` | Slices top-3 dynamic cornering events with burned-in telemetry overlay. |
| `get_sentry_incident_report` | Security | `incident_id: str (opt)` | Tampering timeline, IMU impact magnitude, and captured video links. |
| `verify_resale_passport` | Commercial | `vin: str` | Cryptographic audit of original mileage, rev-limiter history, and crashes. |
| `query_road_hazards` | Crowd Intel | `corridor_bounds: dict` | Verified pothole clusters, low-friction road wear, and road surface index. |
| `get_pack_telemetry_status` | Community | `group_id: str` | Live mesh status of riding companions, separation alerts, and leader warnings. |
| `estimate_range_and_efficiency` | Energy | `destination: str` | Fuel range calculation factoring gradient, ambient temperature, and rider pace. |
| `get_fatigue_and_ergonomics` | Safety | `session_id: str` | Rider cognitive fatigue score, reaction time degradation, and rest advice. |

---

## 3. Deep-Dive Operational Scenarios

### Domain 1: Conversational Pocket Mechanic & Live Diagnostics

#### Scenario 1.1: Spontaneous Engine Misfire & Vacuum Leak Triage
* **Context:** While riding on a highway, the rider feels a slight hesitation under acceleration. The yellow "Check Engine" indicator illuminates.
* **Rider Voice Query:** *"Engine feels sluggish and the check engine light just came on. What is happening?"*
* **Agent Tool Execution:**
  ```json
  // Call 1: Fetch active trouble codes
  run_diagnostic_triage({ "dtc_code": "P0171" })
  // Call 2: Inspect real-time vacuum and intake parameters
  get_live_telemetry_snapshot({ "attributes": ["MAP_kPa", "ENGINE_SPEED_rpm", "THROTTLE_pos", "IAT_celsius"] })
  ```
* **Tool Response Payload:**
  ```json
  {
    "dtc": "P0171 - System Too Lean (Bank 1)",
    "telemetry_anomaly": {
      "MAP_actual_kPa": 48.2,
      "MAP_expected_baseline_kPa": 34.0,
      "discrepancy_percent": "+41.7%",
      "throttle_position_pct": 14.2,
      "engine_speed_rpm": 3850
    },
    "root_cause_probability": [
      { "cause": "Intake manifold rubber boot air leak / loose clamp", "confidence": 0.88 },
      { "cause": "Clogged fuel injector nozzle", "confidence": 0.09 },
      { "cause": "Failing oxygen sensor", "confidence": 0.03 }
    ],
    "safe_to_continue": true,
    "max_recommended_speed_kmh": 80
  }
  ```
* **LLM Audio Synthesis to Helmet:**
  > *"Diagnostic code P-0-1-7-1 is active: your fuel mixture is running lean. Manifold vacuum is reading 48 kPa instead of the normal 34 kPa at this throttle opening. This strongly indicates an intake air leak around the throttle-body rubber boot. It is safe to ride home, but avoid hard acceleration to prevent exhaust valve overheating."*

---

#### Scenario 1.2: Acoustic Sound Analysis & Cold Knocking Diagnostic
* **Context:** After starting the motorcycle on a cold winter morning, the rider hears an unfamiliar metallic ticking sound from the cylinder head.
* **Rider Voice Query:** *"The engine is making a ticking noise on idle. Should I be worried?"*
* **Agent Tool Execution:**
  ```json
  get_live_telemetry_snapshot({ "attributes": ["COOLANT_TEMP_celsius", "ENGINE_SPEED_rpm", "BATTERY_VOLT", "IMU_CHASSIS_FFT_PEAKS"] })
  ```
* **Tool Response Payload:**
  ```json
  {
    "coolant_temp_celsius": 14.0,
    "oil_viscosity_state": "High Viscosity / Cold Start",
    "primary_vibration_peak_hz": 11.25,
    "valve_train_harmonic_match": true,
    "harmonic_damping_rate": "Active thermal normalization observed",
    "conclusion": "Hydraulic / valve clearance lash prior to thermal expansion"
  }
  ```
* **LLM Audio Synthesis:**
  > *"Coolant temperature is currently 14°C. The vibration frequency matches normal valve lash prior to thermal expansion. As the engine reaches 60°C over the next 3 minutes, oil viscosity will thin and the ticking will subside. No mechanical fault detected."*

---

### Domain 2: Pre-Ride Autonomous Flight Briefing

#### Scenario 2.1: Pre-Departure Health, Tire Pressure & Cold-Road Grip Audit
* **Context:** The rider turns on the ignition key at 07:30 AM before a 180 km weekend ride.
* **Autonomous Trigger:** `vehicle-connectivity-node` detects Key-ON and invokes `get_pre_ride_briefing`.
* **Agent Tool Execution:**
  ```json
  get_pre_ride_briefing({ "planned_distance_km": 180.0 })
  ```
* **Tool Response Payload:**
  ```json
  {
    "battery": { "voltage_v": 12.62, "crank_health_pct": 98, "status": "EXCELLENT" },
    "tires": {
      "front_psi": 28.5, "front_target_psi": 32.0, "front_status": "LOW_WARNING",
      "rear_psi": 36.1, "rear_target_psi": 36.0, "rear_status": "OPTIMAL"
    },
    "ambient": { "temperature_c": 6.8, "road_surface_risk": "Cold asphalt / Reduced friction coefficient (mu ~ 0.55)" },
    "clutch_brake_status": "Nominal",
    "pothole_alerts_on_route": 3
  }
  ```
* **LLM Audio Synthesis to Helmet:**
  > *"Good morning Alihan. Pre-ride check complete: Battery voltage is healthy at 12.6V. Notice: your front tire is at 28.5 PSI—3.5 PSI below recommendation. Top it up at the first station. Ambient temperature is 7°C; expect reduced asphalt grip for the first 15 kilometers. Safe ride!"*

---

### Domain 3: Track Day & AR Performance Coaching

#### Scenario 3.1: Post-Session Cornering Telemetry & Apex Analysis
* **Context:** Rider completes a 20-minute track session and reviews lap performance on their smartphone app.
* **Rider Voice Query:** *"Analyze my cornering in Turn 4 and tell me why my lap time was 0.8 seconds slower."*
* **Agent Tool Execution:**
  ```json
  query_ride_coaching({ "session_id": "sess_20261005_shile_loop" })
  ```
* **Tool Response Payload:**
  ```json
  {
    "turn_id": "Turn 4 (Right-hand Sweeper, R=42m)",
    "entry_speed_kmh": 84.2,
    "apex_speed_kmh": 68.1,
    "max_lean_angle_deg": 41.8,
    "kamm_friction_circle_usage_pct": 89.4,
    "trail_braking_duration_s": 1.4,
    "telemetry_flaw": "Early turn-in detected by 2.2 meters relative to optimal geometric vanishing point. Rider saturated available front tire traction at apex, delaying roll-on throttle by 450 ms."
  }
  ```
* **LLM Interactive Feedback:**
  > *"In Turn 4, you initiated turn-in approximately 2.2 meters too early. This forced a tighter line mid-corner where you leaned to 41.8°, consuming 89% of your friction circle. Because the bike was on its side for too long, you could not roll on throttle until late on the exit rumble strip. Delay your turn-in point by two bike lengths to carry 5 km/h more corner-exit speed."*

---

#### Scenario 3.2: Automated Viral Highlight Reel Generation
* **Context:** Rider arrives at a coffee stop after carving canyon roads and wants to post on social media.
* **Rider Voice Query:** *"Generate my best knee-down clip from today's ride with telemetry overlay."*
* **Agent Tool Execution:**
  ```json
  generate_telemetry_reel({
    "session_id": "sess_current",
    "criteria": "max_lean_angle"
  })
  ```
* **Tool Response Payload:**
  ```json
  {
    "clip_id": "clip_20261005_apex_master.mp4",
    "duration_s": 15.0,
    "peak_metrics": { "lean_angle_deg": 43.6, "speed_kmh": 92.4, "lateral_g": 0.94 },
    "overlay_elements": ["Dynamic Tachometer", "Lean Dial with Peak Hold", "Throttle Position Bar", "Friction Circle"],
    "download_url": "https://cdn.vehicle-server.local/reels/clip_20261005_apex_master.mp4",
    "ready_for_sharing": true
  }
  ```
* **LLM Audio Synthesis:**
  > *"I've created a 15-second reel of your 43.6° lean in Turn 7 with full MotoGP-style gauges and G-force friction overlays. The video has been synced to your phone and is ready to share."*

---

### Domain 4: Predictive Component Health & Micro-Wear Modeling

#### Scenario 4.1: Clutch Slip Index & Transmission Degradation
* **Context:** The motorcycle has accumulated 18,000 km.
* **Agent Tool Execution:**
  ```json
  get_component_health_status({ "component": "clutch_pack" })
  ```
* **Tool Response Payload:**
  ```json
  {
    "component": "Clutch Friction Plates",
    "slip_ratio_drift": "+7.4% under wide-open throttle in 4th/5th gear",
    "baseline_engine_wheel_rpm_ratio": 1.428,
    "observed_peak_rpm_divergence_ms": 320,
    "remaining_useful_life_km": 1500,
    "severity": "WARNING",
    "recommendation": "Friction plates approaching minimum thickness specification. Order clutch kit prior to long tours."
  }
  ```
* **LLM Audio Synthesis:**
  > *"Telemetry indicates micro-slippage in your clutch plates during hard acceleration in 4th gear. Slippage has increased by 7% over the last 1,000 km. You have roughly 1,500 km of service life remaining before full mechanical slippage occurs."*

---

#### Scenario 4.2: Brake Rotor & Pad Thermal Cumulative Wear
* **Context:** Rider requests maintenance status before a long mountain tour.
* **Agent Tool Execution:**
  ```json
  get_component_health_status({ "component": "braking_system" })
  ```
* **Tool Response Payload:**
  ```json
  {
    "front_pads_estimated_thickness_mm": 2.4,
    "pad_minimum_limit_mm": 1.5,
    "cumulative_kinetic_energy_dissipated_MJ": 412.8,
    "hard_stops_above_08g": 47,
    "front_rotor_thermal_stress_index": "NOMINAL",
    "estimated_remaining_pad_km": 3200
  }
  ```

---

### Domain 5: Anti-Theft, Sentry Security & Emergency Dispatch

#### Scenario 5.1: Sentry Mode Incident Review
* **Context:** Rider is sitting in an office; their phone vibrates with a high-priority push notification: *"Physical tampering detected on motorcycle!"*.
* **Rider Voice Query:** *"Show me what happened to my bike right now."*
* **Agent Tool Execution:**
  ```json
  get_sentry_incident_report({ "incident_id": "latest" })
  ```
* **Tool Response Payload:**
  ```json
  {
    "timestamp_utc": "2026-10-05T14:22:18Z",
    "trigger_source": "Chassis IMU Z-axis shock (delta_a = 0.42g) - Side-stand lift attempt",
    "coordinates_approx": "Corner of Bagdat Avenue, Kadikoy",
    "camera_clips": {
      "front_1080p_mp4": "https://cdn.vehicle-server.local/sentry/clip_front_142218.mp4",
      "rear_1080p_mp4": "https://cdn.vehicle-server.local/sentry/clip_rear_142218.mp4"
    },
    "starter_immobilizer_state": "LOCKED_ARMED",
    "tampering_persists": false
  }
  ```
* **LLM Interactive Response:**
  > *"At 2:22 PM, a physical shock of 0.42g was detected consistent with someone sitting on the seat or lifting the bike off its side-stand. Both front and rear 5-second video clips are streaming to your screen now. The remote starter immobilizer is actively locked. The motorcycle has returned to stationary status."*

---

#### Scenario 5.2: Autonomous Post-Crash Emergency Dispatch Dossier
* **Context:** A motorcycle low-sides into a rural embankment at night. The rider is disoriented and unable to reach their phone.
* **Autonomous Trigger:** `rt-core` transitions to `CRASH_LATCH` (lean $>70^\circ$, impact $>3.5\text{ g}$). After the 15-second abort window expires, the cloud agent synthesizes an emergency rescue dossier.
* **LLM Automated Dispatch Payload sent to 112 / Emergency Medical Services:**
  > *"CRITICAL MOTORCYCLE CRASH REPORT: Incident at 41.1284 N, 29.3491 E (Shile Coastal Highway, KM 18). Vehicle: Honda CL250. Rider impact severity: 4.2g lateral deceleration. Speed prior to impact: 72 km/h. Fuel pump and ignition isolated. Automatic eCall protocol active. Registered blood type: A Rh(+). Emergency contact notified."*

---

### Domain 6: Group Riding Mesh & Swarm Intelligence

#### Scenario 6.1: Pack Leader Hazard Broadcast
* **Context:** A group of 8 riders are traveling in formation. The lead rider hits a patch of diesel fuel or loose gravel mid-corner.
* **Autonomous Trigger:** Lead bike detects rear wheel slip ratio divergence ($\Delta v_{\text{wheel}} > 18\%$) coincident with lean angle ($\theta_{\text{lean}} = 36^\circ$).
* **Mesh Network Action:** Lead bike broadcasts localized C-V2X / Wi-Fi Mesh beacon packet `0x380 PACK_HAZARD`.
* **Agent Tool Execution on Trailing Bikes:**
  ```json
  get_pack_telemetry_status({ "group_id": "istanbul_riders_club" })
  ```
* **HUD Action on Trailing Riders' Visors:**
  > Flashes prominent amber alert with directional chevron: *"WARNING: TRACTION LOSS DETECTED BY LEAD BIKE 150M AHEAD IN RIGHT TRACK - EASE LEAN"*.

---

### Domain 7: Cryptographic Resale Dossier & Anti-Fraud Audit

#### Scenario 7.1: Pre-Purchase Inspection & Anti-Odometer Fraud Verification
* **Context:** A potential buyer inspects a used motorcycle equipped with `vehicle-platform`.
* **Buyer Voice Query:** *"Verify the authenticity and mechanical history of this vehicle."*
* **Agent Tool Execution:**
  ```json
  verify_resale_passport({ "vin": "MLHMC55A1P5000123" })
  ```
* **Tool Response Payload:**
  ```json
  {
    "vin": "MLHMC55A1P5000123",
    "verified_odometer_km": 14258.4,
    "odometer_tamper_detected": false,
    "engine_hours_total": 312.4,
    "rev_limiter_strikes": { "count": 4, "cumulative_duration_s": 3.8 },
    "thermal_stress_events": { "overheating_above_110c": 0, "cold_revving_above_6000rpm": 2 },
    "crash_records": { "fall_events_detected": 0, "max_recorded_lateral_g": 1.18 },
    "mechanical_health_index": 96.2,
    "blockchain_signature": "0x4f8a...e91b"
  }
  ```
* **LLM Audio Synthesis:**
  > *"Digital Passport verified against cloud cryptographic logs. The odometer reading of 14,258 km is 100% authentic. The engine has spent only 3.8 seconds at rev-limiter over its entire lifespan. Zero crash or drop events have ever been recorded. Overall vehicle health score is 96 out of 100."*

---

## 4. Implementation Blueprint: FastMCP Python Architecture

The `vehicle-mcp` service is built on the official **Anthropic FastMCP Python SDK**, exposing asynchronous decorators backed by VSS telemetry adapters:

```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("Vehicle-Platform Vehicle Intelligence Core")

class TelemetrySnapshot(BaseModel):
    engine_speed_rpm: float = Field(description="Engine rotational velocity")
    vehicle_speed_kmh: float = Field(description="True wheel speed from ABS sensor")
    manifold_pressure_kpa: float = Field(description="Intake vacuum pressure")
    coolant_temp_celsius: float = Field(description="Engine thermal state")
    lean_angle_deg: float = Field(description="EKF roll angle from real-time core")

@mcp.tool()
async def get_live_telemetry_snapshot(attributes: list[str]) -> TelemetrySnapshot:
    """Fetch instantaneous vehicle operating parameters via COVESA VSS broker."""
    # Queries the local Kuksa Databroker / PyArrow memory buffer
    ...

@mcp.tool()
async def run_diagnostic_triage(dtc_code: str | None = None) -> dict:
    """Perform expert automotive root-cause failure triage combining UDS DIDs and anomalies."""
    ...

@mcp.tool()
async def get_pre_ride_briefing(planned_distance_km: float) -> dict:
    """Execute automated pre-ride airworthiness inspection for tire, battery, and road grip."""
    ...
```

---

## 5. Summary: Academic Impact

1. **For the Academic Thesis:** Demonstrates a groundbreaking bridge between hard real-time ISO 26262 automotive systems and cloud-native Large Language Models via modern open protocols (MCP).
