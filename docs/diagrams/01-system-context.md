# System Context

**Caption:** Top-level hardware and software topology of `vehicle-platform`, showing physical isolation between the OEM vehicle CAN bus (single read-only tester: rt-core, or the bike ESP32 until rt-core runs, D-023; never both) and the dedicated platform CAN bus, the separate Cortex-M4F safety MCU, the Raspberry Pi 5 HPC, edge/remote servers, the companion app, and the listen-only analyzer.

```mermaid
flowchart LR
  subgraph Bike["Motorcycle (CL250)"]
    ECU["CL250 OEM ECU<br/>(UDS 0x18DA10F1 / 0x18DAF110)"]
    VBUS(("Vehicle CAN Bus<br/>500 kbps classic, 29-bit UDS"))
    RTCORE["vehicle-rt-core<br/>STM32H743ZI Cortex-M7<br/>FDCAN1 + FDCAN2"]
    PBUS(("Platform CAN Bus<br/>500 kbps classic, 11-bit, E2E"))
    SAFETY["vehicle-safety-node<br/>STM32G474RE Cortex-M4F<br/>Own IMU, 2x radar, LEDs, immobilizer"]
    CONN["vehicle-connectivity-node<br/>ESP32-S3 (bike)<br/>TWAI + BLE/Wi-Fi"]
    HELMET["vehicle-connectivity-node<br/>ESP32-S3 (helmet)<br/>HUD only"]
    PI["vehicle-linux-node + vehicle-mcp<br/>Raspberry Pi 5<br/>Kuksa VSS, blackbox, live uplink, local server"]
  end

  subgraph HostCloud["Off-Bike / Host & User Servers"]
    SERVER["vehicle-server<br/>Edge Pi & Remote FastAPI<br/>Rides, Marks, Alerts SSE, /ws/live, /chat"]
    MOBILE["vehicle-mobile<br/>Flutter (Phone & Web)<br/>Ride, Garage, Logbook, Assistant, HFP Voice"]
    ANALYZER["vehicle-analyzer<br/>Web / Tauri Host<br/>Listen-only CAN & Log Analysis"]
  end

  ECU <-->|"UDS read-only"| VBUS
  VBUS <-->|"FDCAN1 (sole tester)"| RTCORE
  VBUS -.->|"can0 optional (listen-only)"| PI
  VBUS -.->|"USB-CAN (listen-only)"| ANALYZER

  RTCORE <-->|"FDCAN2 (0x020/0x021/0x022/0x081/0x110/0x120)"| PBUS
  SAFETY <-->|"FDCAN (0x020/0x022/0x081/0x120 in; 0x023/0x082 out)"| PBUS
  CONN -.->|"TWAI: temporary sole tester until rt-core (D-023)"| VBUS
  CONN <-->|"TWAI (after rt-core: platform bus to BLE bridge)"| PBUS
  PI <-->|"can1 SocketCAN"| PBUS
  PBUS -.->|"USB-CAN (listen-only)"| ANALYZER

  CONN <-->|"BLE"| HELMET
  CONN <-->|"BLE (telemetry + riderInput)"| MOBILE
  PI -->|"MQTT live + HTTP ride sync"| SERVER
  SERVER <-->|"HTTPS / SSE / /chat / /marks"| MOBILE
  SERVER -->|"WebSocket /ws/live"| ANALYZER
```

## Sources
- `vehicle-defs/docs/ARCHITECTURE.md` §2 (Units), §3 (Bus topology — two separate CAN buses), §4 (Platform CAN ID plan), §7 (Data flows)
- `vehicle-defs/docs/DECISIONS.md`: D-009 (two separate CAN buses), D-019 (CL250 poll-based UDS 500 kbps), D-021 (rt-core sole vehicle-bus tester and republisher), D-023 (connectivity-node temporary sole tester), D-073 (helmet ESP32 HUD over BLE), D-077 (edge Pi + remote server), D-081 (listen-only vehicle-analyzer), D-118 (two chips: H743 rt-core + separate G474 safety-node), D-121 (rider assistant & phone HFP intercom voice)
