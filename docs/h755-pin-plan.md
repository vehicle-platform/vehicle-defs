# H755 pin plan (roadmap S2) — proposal v0.1

**Status:** proposal by Claude, 2026-11-10, **not a decision**. It becomes binding only as a
DECISIONS item after the user checks it in STM32CubeMX (`.ioc` for STM32H745ZITx, board
NUCLEO-H745ZI-Q, D-094) and against UM2408 for the header positions and solder bridges.
Firmware CubeMX projects (red zone, invariant 8) follow it only after that.

**Sources (no pin is from memory):**
- Pin list and alternate functions: ST's open pin data, `STMicroelectronics/STM32_open_pin_data`
  at `7d1f1514ed55`: `mcu/STM32H745ZITx.xml` (LQFP144 pin list) and
  `mcu/IP/GPIO-STM32H747_gpio_v1_0_Modes.xml` (AF numbers).
- Board-reserved pins: the same repository's
  `boards/G71_Nucleo_NUCLEO-H745ZI-Q_STM32H745ZI_Board_AllConfig.ioc`.
- Peripheral needs and ownership: D-072 items 2-4 (port-level GPIO split: **no GPIO port is
  shared by the two cores**), D-082 (boards A, B, C1-IO, C1-IMU, C2), D-093 (SRAM4 mailbox,
  HSEM), D-094 (no CRYP/HASH), D-075 item 4 (Q-033 indicator inputs), D-097 (immobilizer),
  `models/fusion-lib/SCHEMATIC-README.md` (vehicle-workspace) for the signal names.

**Note on this package:** the dual-core LQFP144 (SMPS) has no PF0-PF5, PF12, PF13, PG0-PG5 or
PG15. Every pin below exists in `STM32H745ZITx.xml`.

## 1. Port ownership

| Core | GPIO ports | Why |
|---|---|---|
| M7 (rt-core) | A, B, C, D, H (oscillator) | FDCAN1/2, SDMMC1 (PC8-PC12, PD2), the ADC pins, ST-LINK VCP (PD8/PD9), most free pins |
| M4 (safety-node) | E, F, G | SPI4, UART7, USART6, TIM1 and I2C4 all have pins inside E/F/G, so the M4 needs no pin of an M7 port |

The M7 MPU denies the M4 ports E, F, G (D-072 item 4a). DMA: one controller per core is the
proposal (DMA1 = M7, DMA2 = M4; BDMA unused because it reaches SRAM4, D-093 item 3). **CONFIRM**
in the CubeMX DMA/DMAMUX view.

## 2. Board-reserved pins (NUCLEO-H745ZI-Q default configuration)

| Pins | Board use | Plan |
|---|---|---|
| PA1, PA2, PA7, PB13, PC1, PC4, PC5, PG11, PG13 | Ethernet RMII to the on-board PHY | not used (no Ethernet in the platform); never assigned |
| PA8, PA9, PA11, PA12, PD10, PG7 | USB OTG FS (SOF, VBUS, DM, DP, power enable, over-current) | not used; never assigned |
| PA13, PA14, PB3 | SWD + SWO (ST-LINK) | debug only |
| PD8, PD9 | USART3 to the ST-LINK virtual COM port | M7 debug console |
| PB0, PB14 / PE1 | LD1 green, LD3 red / LD2 yellow | M7 status LEDs / M4 status LED |
| PC13 | B1 user button | M7 input |
| PC14, PC15, PH0, PH1 | LSE / HSE oscillator | clocks |

## 3. M7 (rt-core) pins

| Function | Peripheral | Pins (AF) | Notes |
|---|---|---|---|
| Vehicle bus (D-021, listen + the one tester) | FDCAN1 | PD0 RX, PD1 TX (AF9) | SN65HVD230 on Board A; no termination |
| Platform bus | FDCAN2 | PB5 RX, PB6 TX (AF9) | PB12/PB13 avoided: PB13 is the board's ETH_TXD1 |
| C2 chassis IMU, INA226, MLX90614, BME280, later VL53L1X/AS5600 | I2C1 | PB8 SCL, PB9 SDA (AF4) | pull-ups 2.2-4.7 kΩ at the controller end (proposal, HI §3.4) |
| MAX31856 EGT, ADXL345 x2 (Board B) | SPI1 | PA5 SCK, PA6 MISO, PD7 MOSI (AF5) | PA7 (MOSI alternative) is Ethernet |
| SPI1 chip selects | GPIO out | PD11 `CS_EGT`, PD4 `CS_ADXL_ENG`, PD3 `CS_ADXL_ARM` | idle high |
| MAX31856 DRDY / FAULT | GPIO in | PB7 `EGT_DRDY`, PB4 `EGT_FLT` | PB4 = NJTRST, free with SWD |
| GPS NEO-M8N (H755 build) | USART2 | PD5 TX, PD6 RX (AF7) | 3.3 V logic |
| `SPARK_IN`, `WHEEL_F`, `WHEEL_R`, `GPS_PPS` | TIM4 input capture | PD12 CH1, PD13 CH2, PD14 CH3, PD15 CH4 (AF2) | 16-bit: the overflow count extends it in software; TIM2/TIM5 (32-bit) have no four free channels on M7 ports without Ethernet pins |
| microSD logging (D-072 item 2) | SDMMC1 4-bit | PC8 D0, PC9 D1, PC10 D2, PC11 D3, PC12 CK, PD2 CMD (AF12) | the HI §3.4 "MicroSD SPI" line is superseded by D-072 (authority order) |
| `V_BAT_SENSE` | ADC1 | PA3 (ADC1_INP15) | 1 kHz with DMA (D-079, D-082 item 4) |
| `I_BAT_SENSE` (ACS758LCB-200B via divider) | ADC1 | PA4 (ADC1_INP18) | same ADC as the voltage for paired samples |
| `NTC_1`..`NTC_5` | ADC1 / ADC3 | PA0 (ADC1_INP16), PB1 (ADC1_INP5), PC0 (ADC1_INP10), PC2_C (ADC3_INP0), PC3_C (ADC3_INP1) | `_C` pins: analog switch, not 5 V tolerant; PB0 (LD1) avoided |
| `TAP_CLUTCH`, `TAP_BRAKE`, `TAP_FAN` (PC817, Board B) | GPIO in | PB10, PB11, PB12 | not connected before Q-031(c) |
| Gear / shift-light WS2812B (optional) | TIM3_CH1 + DMA | PC6 (AF2) | separate buffer (SCHEMATIC S2) |
| Bike ESP32 link (Q-004 open) | — | none reserved | recommendation: the platform bus (its own SN65HVD230, no H755 pin); a UART would need USART1 PB14/PB15 and the LD3 LED removed |
| GSM SIM800L (later) | — | none reserved | decide with its wave |

Free M7 pins after this plan: PA10, PA15, PB2, PB15, PC7 (checked by script against the pin list
and the board-reserved pins: no pin is assigned twice, none is board-reserved).

## 4. M4 (safety-node) pins

| Function | Peripheral | Pins (AF) | Notes |
|---|---|---|---|
| Own IMU MPU-6500 (C1-IMU, D-042, D-075 item 6) | SPI4 | PE12 SCK, PE13 MISO, PE14 MOSI (AF5) | 33-100 Ω series resistors (D-082 item 2) |
| IMU chip select / interrupt | GPIO | PE10 `CS_IMU_M4` out, PE15 `IMU_INT_M4` in | |
| Radar left HLK-LD2451 | UART7 | PE7 RX, PE8 TX (AF7) | supply and UART level **CONFIRM** (SCHEMATIC §7) |
| Radar right HLK-LD2451 | USART6 | PG9 RX, PG14 TX (AF7) | UART8 (PE0/PE1) avoided: PE1 is LD2 |
| LED ring left / right DIN | TIM1_CH1 / TIM1_CH2 + DMA | PE9, PE11 (AF1) | through the 74AHCT125 on C1-IO; ring DMA must not touch SRAM4 (D-093 item 3) |
| Mirror LEDs left / right | GPIO out | PF8, PF9 | logic-level N-MOSFET |
| Dead-man retrigger `DEADMAN_KICK` (D-072 item 5) | GPIO out | PF10 | an edge from the main loop after each decision step; never a timer, PWM or DMA; external pull-down |
| Indicator inputs `IND_L`, `IND_R` (Q-033, D-075 item 4) | GPIO in | PE2, PE3 | PC817; a dead input reads "not signalling" |
| Immobilizer `IMMO_SET`, `IMMO_RESET` (D-072 item 3, D-097) | GPIO out | PE4, PE5 | pulse only; external gate pull-downs; never SET at boot |
| PN532 NFC (D-072 item 3) | I2C4 | PF14 SCL, PF15 SDA (AF4) | interface TBD in SCHEMATIC S4; I2C proposed |
| PIN input | GPIO in | PG10, PG12 | hardware TBD |
| Status LED | GPIO out | PE1 (LD2) | board LED |

Free M4 pins: PE0, PE6, PF6, PF7, PF11, PG6, PG8 (PG7, PG11, PG13 stay unused: board USB/ETH).

## 5. Checks before this becomes a decision (user)

1. Open the plan in STM32CubeMX for STM32H745ZITx with the NUCLEO-H745ZI-Q board selector and
   confirm there is no conflict (pin, AF, DMA request, clock) and each core's peripheral
   assignment (Pinout -> Runtime contexts M7/M4).
2. UM2408: the header position of each pin (Zio CN7-CN10 or morpho CN11/CN12) and the default
   solder bridges / jumpers of the pins used (in particular PB5, PB6, PA5, PA6, PD7, PC8-PC12,
   PD2).
3. SDMMC1 at the planned clock with the card socket wiring on Board A.
4. Then record it as a DECISIONS item and update `SCHEMATIC-README.md` S2-S4 and
   `hardware-integration.md` §10 item 10 ("H755 pin map").
