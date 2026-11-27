# In-Ride Alert Pipeline (Signal to App Banner and Voice)

**Caption:** End-to-end flow for P1/P2 in-ride alerts (D-129): live telemetry samples enter `LiveHub`, are evaluated against `vehicle-defs` alert rules in `AlertEngine`, persisted as `anomaly` notifications, streamed over `GET /alerts/stream` (SSE) and `/ws/live`, and rendered by `vehicle-mobile` as a timed banner plus optional P1 intercom voice (P0 safety warnings stay on `vehicle-safety-node`).

```mermaid
sequenceDiagram
  autonumber
  participant Source as Live Source<br/>(MQTT VSS / MockCanStreamer)
  participant Hub as LiveHub<br/>(stream.py)
  participant Svc as AlertService & AlertEngine<br/>(alerts/service.py, engine.py)
  participant DB as Notifications DB<br/>(notifications.py)
  participant SSE as GET /alerts/stream (SSE)<br/>& /ws/live
  participant Mobile as AlertController<br/>(alert_controller.dart)
  participant UI as Ride Banner & AlertPrefs<br/>(P1 30 s / P2 12 s)
  participant Voice as CriticalAnnouncer / HFP Intercom<br/>(voice/)

  Source->>Hub: publish(StreamBatchDto)
  Hub->>Svc: on_batch(batch)
  Note over Svc: Evaluate vehicle-defs alert_rules.yaml<br/>(threshold, debounce, hysteresis, cooldown, per-ride cap)<br/>+ periodic tick(1.0 s) for staleness/ride end

  alt Rule fires (P1 critical or P2 warning)
    Svc->>DB: store anomaly notification (session_id=null)
    Svc->>SSE: push event "alert" (rule_id, class, severity, value, unit, speak)
    SSE-->>Mobile: SSE frame (event: alert, data: JSON)
    Mobile->>UI: show banner (P1 always shown; P2 respects per-rule mute)
    alt P1 alert & speak=true & voice not muted
      Mobile->>Voice: speak short alert text via phone HFP intercom
    end
  else Rule clears (recovered / gate / ride_end)
    Svc->>SSE: push event "clear" (speak=false, reason)
    SSE-->>Mobile: SSE frame (event: clear, data: JSON)
    Mobile->>UI: dismiss active banner early
  end

  Note over SSE,Mobile: No SSE replay on disconnect:<br/>reconnect triggers backoff (1..30 s) + GET /notifications pull
  Note over Svc,DB: After upload, alerts/replay.py runs the same engine over the stored ride<br/>(anomaly notifications with session_id set; an alert already raised live is not stored twice)
```

## Sources
- `vehicle-defs/docs/DECISIONS.md`: D-129 (in-ride alert classes P0/P1/P2, debounce/hysteresis/cooldown, SSE stream, per-type mutes), D-130 item 4 (banner max display time)
- `vehicle-defs/docs/ARCHITECTURE.md` §7 (Rider accounts and notifications)
- `vehicle-server/src/vehicle_server/alerts/service.py` (`AlertService`, `on_batch`, `tick`, `TICK_PERIOD_S = 1.0`)
- `vehicle-server/src/vehicle_server/alerts/replay.py` (post-ride replay, D-129 item 3)
- `vehicle-server/src/vehicle_server/alerts_api.py` (`GET /alerts/stream`, `sse_frame`, `HEARTBEAT_PERIOD_S = 15.0`)
- `vehicle-mobile/lib/services/alerts/alert_controller.dart` (`AlertController`, `p1BannerMaxDisplay = 30s`, `p2BannerMaxDisplay = 12s`, `alertBackoff`)
- `vehicle-mobile/lib/services/alerts/alert_prefs.dart` (`AlertPrefs`: P1 voice-only mute, P2 banner+voice mute)
