# Ride Event Mark Flow (Offline Queue, Backoff Retry, Idempotent Insert)

**Caption:** Sequence for recording a timestamped, position-free rider event mark (D-133) in `vehicle-mobile` through the serialized `SharedPreferences` offline queue, exponential backoff retry, and race-free `INSERT OR IGNORE` idempotent handling in `vehicle-server`.

```mermaid
sequenceDiagram
  autonumber
  participant Rider as Rider (Live Screen)
  participant Queue as MarkQueue<br/>(mark_queue.dart)
  participant Prefs as SharedPreferences<br/>(ride_mark_queue_v1)
  participant Client as MarksClient<br/>(marks_client.dart)
  participant API as POST /marks<br/>(marks_api.py)
  participant DB as index.sqlite<br/>(marks.py: ride_marks)

  Rider->>Queue: recordAndSend(kind, note?)
  Note over Queue: Generates client id m_{utc_ms}_{hex}<br/>No GPS/position fields (D-076)
  Queue->>Prefs: _locked(): read, deduplicate by id, save
  Queue->>Client: flush() -> POST /marks {id, t_utc, kind, note}
  Client->>API: HTTPS POST /marks (Bearer token)
  API->>API: Validate MarkCreate (extra="forbid", note <= 200)

  alt Fresh mark
    API->>DB: INSERT OR IGNORE INTO ride_marks (owner, id, ...)
    DB-->>API: rowcount == 1 (created=True)
    API-->>Client: 201 Created (MarkOut)
    Client-->>Queue: delivered
    Queue->>Prefs: _locked(): remove id from queue
    Queue-->>Rider: MarkSendOutcome.sent
  else Identical retry (network drop after prior insert)
    API->>DB: INSERT OR IGNORE -> rowcount == 0; SELECT existing
    DB-->>API: payload matches (t_utc, kind, note)
    API-->>Client: 200 OK (existing MarkOut)
    Client-->>Queue: delivered (idempotent)
    Queue->>Prefs: _locked(): remove id from queue
    Queue-->>Rider: MarkSendOutcome.sent
  else Permanent error (422 invalid / 409 id conflict)
    API-->>Client: 409 Conflict or 422 Unprocessable Entity
    Client-->>Queue: permanent rejection
    Queue->>Prefs: _locked(): drop mark, increment rejectedCount
    Queue-->>Rider: MarkSendOutcome.rejected (UI surfaces error)
  else Offline / transient failure (network / 5xx)
    Client-->>Queue: transient failure
    Note over Queue: Keep mark persisted;<br/>schedule retry timer (5 s doubling up to 5 min)
    Queue-->>Rider: MarkSendOutcome.queued
  end
```

## Sources
- `vehicle-defs/docs/DECISIONS.md`: D-133 (ride event marks model, server endpoints, mobile offline queue, no position), D-076 (position rule)
- `vehicle-mobile/lib/services/mark_queue.dart` (`MarkQueue`, `_locked`, `newId`, `recordAndSend`, `enqueue`, `retryBase = 5s`, `retryMax = 5m`, `MarkSendOutcome`)
- `vehicle-server/src/vehicle_server/marks_api.py` (`MarkCreate` with `extra="forbid"`, `POST /marks` 201/200/409/422)
- `vehicle-server/src/vehicle_server/marks.py` (`create_mark` using `INSERT OR IGNORE` + re-read check)
