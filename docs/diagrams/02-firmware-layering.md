# MCU Firmware Layering (Target vs. Host Port)

**Caption:** One-way layered architecture (`features -> services -> hal`) shared by `vehicle-rt-core` (STM32H743ZI, FreeRTOS) and `vehicle-safety-node` (STM32G474RE, bare-metal), showing how pure logic and services compile identically against either CubeMX target HAL or host simulation ports for unit and SIL testing.

```mermaid
flowchart TB
  DEFS["external/vehicle-defs/gen/c/{node}/<br/>Generated DBC pack/unpack, E2E, DID tables, tester policy gates"]

  subgraph App["Application Wiring (src/app/)"]
    APP["Target init & scheduler (rt-core FreeRTOS / safety-node super-loop)<br/>or Host SIL entrypoint (src/app/host/main.c)"]
  end

  subgraph Features["Features Layer (src/features/) — SWC equivalent (no cross-feature includes)"]
    F_RT["rt-core features:<br/>uds/, vehicle_republish/, cornering/, derived/, heartbeat/, safety_hb/"]
    F_SAF["safety-node features:<br/>cornering/, indicator/"]
  end

  subgraph Services["Services Layer (src/services/) — BSW equivalent"]
    S_RT["rt-core services:<br/>can_if, can_sm, com, diag, vehicle_signals, imu,<br/>snapshot, alive, timebase, ride_records, derived_inputs, lean_health"]
    S_SAF["safety-node services:<br/>platform_link (E2E RX/TX filtering)"]
  end

  subgraph HalIf["HAL Abstraction Headers (src/hal/) — MCAL interface"]
    HAL_H["rt-core: can_port.h, can_frame.c, imu.h, hal_time.h, hal_atomic.h<br/>safety-node: can.h, indicator_gpio.h"]
  end

  subgraph TargetPort["Target Build (STM32 CubeMX)"]
    CUBEMX["cubemx/ (generated Core/Drivers)<br/>STM32H7 / STM32G4 FDCAN, SPI, UART, TIM, GPIO"]
  end

  subgraph HostPort["Host Build (CMake host-tests / ASan+UBSan / TSan)"]
    HOST["src/hal/host/ & tests/host/ (Unity)<br/>rt-core: vbus.c, can_port_host.c, imu_host.c, hal_time_host.c, hal_atomic_host.c<br/>safety-node: can_host.c, indicator_gpio_host.c"]
  end

  APP --> Features
  APP --> Services
  Features --> Services
  Services --> HalIf
  DEFS --> Features
  DEFS --> Services
  HalIf -->|"Target preset (ARM GCC)"| TargetPort
  HalIf -->|"Host preset (host-tests / host-tsan)"| HostPort
```

## Sources
- `vehicle-defs/docs/ARCHITECTURE.md` §5 (Signal definition pipeline), §6 (Software layers — AUTOSAR concept mapping)
- `vehicle-defs/docs/DECISIONS.md`: D-012 (FreeRTOS on rt-core, bare-metal on safety-node), D-027 (per-node filtered `gen/c/<node>/`), D-118 (separate H743 and G474 MCUs)
- `vehicle-rt-core/src/` directory layout (`src/app/`, `src/features/`, `src/services/`, `src/hal/`, `src/hal/host/`)
- `vehicle-safety-node/src/` directory layout (`src/app/`, `src/features/`, `src/services/`, `src/hal/`, `src/hal/host/`)
