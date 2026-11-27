# Raspberry Pi 5 Data Flow (CAN -> Kuksa VSS -> Consumers)

**Caption:** Data flow inside `vehicle-linux-node` on the Raspberry Pi 5: `kuksa-can-provider` decodes platform-bus SocketCAN frames one-way (`dbc2val = True`, `val2dbc = False`) using `platform.dbc` and `vss_dbc.json` into the loopback Kuksa Databroker (`grpc://127.0.0.1:55555`), which serves read-only gRPC VSS consumers without any consumer touching SocketCAN directly.

```mermaid
flowchart LR
  subgraph Defs["Pinned external/vehicle-defs (mounted :ro)"]
    DBC["/defs/dbc/platform.dbc"]
    VSS["/defs/gen/vss/vss_dbc.json<br/>(VSS 6.0 + Vehicle.Motorcycle.* + dbc2vss)"]
  end

  CAN["Platform CAN Bus<br/>SocketCAN (${CAN_PORT:-vcan0} / can1)<br/>500 kbps classic, 11-bit"]

  subgraph Docker["Docker Compose (network_mode: host, read_only, cap_drop: ALL)"]
    FEEDER["kuksa-can-provider:0.5.1<br/>config/dbc_feeder.ini<br/>--use-socketcan --no-val2dbc<br/>dbc2val=True, val2dbc=False"]
    BROKER["kuksa-databroker:0.7.2<br/>127.0.0.1:55555 (gRPC, --insecure loopback)"]
  end

  subgraph Consumers["vehicle-linux-node Consumers (gRPC VSSClient, never touch CAN)"]
    HEALTH["nodehealth/service.py<br/>Heartbeat & staleness panel"]
    BBOX["blackbox/service.py<br/>Pre/post ring buffer (no position)<br/>trigger file -> event store"]
    LIVE["live/service.py<br/>LivePublisher (10 Hz, backlog queue)<br/>-> MQTT vehicle/{device_id}/live/{vss_path}"]
  end

  SERVER["vehicle-server<br/>MQTT live subscriber + ride ingest"]

  CAN -->|"Platform CAN frames"| FEEDER
  DBC -.->|"decode"| FEEDER
  VSS -.->|"dbc2vss map"| FEEDER
  VSS -.->|"VSS schema"| BROKER
  FEEDER -->|"gRPC publish (127.0.0.1:55555)"| BROKER

  BROKER -->|"subscribe_current_values (gRPC)"| HEALTH
  BROKER -->|"subscribe_current_values (gRPC)"| BBOX
  BROKER -->|"subscribe_current_values (gRPC)"| LIVE
  LIVE -->|"MQTT"| SERVER
```

## Sources
- `vehicle-linux-node/docker-compose.yml` (services `databroker` 0.7.2 on `127.0.0.1:55555` and `can-provider` 0.5.1 with `--no-val2dbc`, `--use-socketcan`, read-only defs mounts, container hardening)
- `vehicle-linux-node/config/dbc_feeder.ini` (`address = grpc://127.0.0.1:55555`, `mapping = /defs/gen/vss/vss_dbc.json`, `dbc2val = True`, `val2dbc = False`, `dbcfile = /defs/dbc/platform.dbc`)
- `vehicle-linux-node/src/vehicle_linux_node/nodehealth/service.py`, `blackbox/service.py`, `live/service.py`
- `vehicle-defs/docs/ARCHITECTURE.md` §5, §7 (VSS and Cloud flows)
- `vehicle-defs/docs/DECISIONS.md`: D-004 (Kuksa CAN->VSS), D-021 (Raspi reads platform bus), D-076 (position excluded by default in blackbox/live)
