# Architecture and Sequence Diagrams

Thesis-ready Mermaid diagrams for the `vehicle-platform` system. Each file contains a short caption, one Mermaid diagram verified against the repository sources, and a **Sources** list tracing every node and arrow to its governing decision or implementation file.

| # | File | Topic | Key Decisions / Sources |
|---|---|---|---|
| 1 | [01-system-context.md](01-system-context.md) | System context: MCUs, vehicle vs. platform CAN, Pi 5, server, mobile app, analyzer | D-009, D-021, D-077, D-081, D-118, `docs/ARCHITECTURE.md` |
| 2 | [02-firmware-layering.md](02-firmware-layering.md) | MCU firmware layering (`features` -> `services` -> `hal`, target vs. host port) | D-012, D-118, `docs/ARCHITECTURE.md` §6, `vehicle-rt-core`, `vehicle-safety-node` |
| 3 | [03-uds-polling-republish.md](03-uds-polling-republish.md) | Read-only UDS polling on the vehicle bus and platform-bus republish | D-019, D-020, D-021, D-027, D-037, `uds_client.c`, `vehicle_republish.c` |
| 4 | [04-in-ride-alert.md](04-in-ride-alert.md) | In-ride alert pipeline from live signal to mobile banner and P1 voice | D-129, D-130, `alerts/service.py`, `alerts_api.py`, `alert_controller.dart` |
| 5 | [05-ride-mark-flow.md](05-ride-mark-flow.md) | Ride event mark with persisted offline queue, backoff retry, and idempotent insert | D-133, `mark_queue.dart`, `marks_api.py`, `marks.py` |
| 6 | [06-assistant-pipeline.md](06-assistant-pipeline.md) | Rider assistant `/chat` pipeline (guard, router, MCP tool, template/LLM, output filter) | D-121, D-127, D-128, `chat/service.py`, `chat/guard.py`, `chat/router.py` |
| 7 | [07-raspi-dataflow.md](07-raspi-dataflow.md) | Raspberry Pi 5 data flow: SocketCAN -> `kuksa-can-provider` -> Databroker (VSS) -> consumers | D-004, D-021, `vehicle-linux-node/docker-compose.yml`, `config/dbc_feeder.ini` |
