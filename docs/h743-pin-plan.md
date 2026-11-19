# H743 pin plan, rt-core (roadmap S2) — proposal v0.1

**Status:** proposal by Claude, 2026-11-19, **not a decision**. It becomes binding only as a
DECISIONS item after the user checks it in STM32CubeMX (`.ioc` for STM32H743ZITx, board
NUCLEO-H743ZI2, D-118, roadmap T6) and against UM2407 for the header positions and solder
bridges. Firmware CubeMX projects (red zone, invariant 8) follow it only after that.
Companion plan for the safety MCU: [`g474-pin-plan.md`](g474-pin-plan.md). This file replaces
`h755-pin-plan.md` (v0.1, 2026-11-10), which split one dual-core chip between two cores
(D-072); D-118 retired that: rt-core now owns the whole H743 and the safety functions moved
to the separate STM32G474.

**Sources (no pin is from memory):**
- Pin list and alternate functions: ST's open pin data, `STMicroelectronics/STM32_open_pin_data`
  at `7d1f1514ed55`: `mcu/STM32H743ZITx.xml` (LQFP144 pin list) and
  `mcu/IP/GPIO-STM32H747_gpio_v1_0_Modes.xml` (AF numbers, the file that package references).
- Board-reserved pins: the same repository's
  `boards/G73_Nucleo_NUCLEO-H743ZI2_STM32H743ZIT_Board_AllConfig.ioc`.
- Peripheral needs and ownership: D-118 item 2 (rt-core scope unchanged: FDCAN1 vehicle bus as
  the single read-only tester, FDCAN2 platform bus, SDMMC, chassis IMU, GPS, power management),
  D-082 (boards A, B, C2), D-079 (battery sensing), D-112 (bike ESP32 on the platform bus),
  `models/kicad-lib/SCHEMATIC-README.md` (vehicle-workspace) for the signal names.
- Header positions (Zio CN7-CN10, ST morpho CN11/CN12) and solder bridges are **not** taken from
  the open pin data: every line below that depends on them says **VERIFY in CubeMX (T6)**
  (and UM2407).

**Package note:** the single-core LQFP144 (ZIT6, no SMPS pin set) has PF0-PF15 and PG0-PG15 (the
dual-core H745 package of the old plan did not). Every pin below exists in `STM32H743ZITx.xml`.

## 1. Port ownership and DMA

One core, so no port split: rt-core may use every port. The plan keeps the old M7 assignment
(ports A, B, C, D, H) unchanged, so the code and the schematic notes written against it stay
valid, and leaves ports E, F, G free for growth (section 4). The old M4 functions are **not** here:
they moved to the G474 (`g474-pin-plan.md`). DMA: DMA1/DMA2 and BDMA are all rt-core's; the
D-093 rule "BDMA unused because it reaches SRAM4" is retired with the mailbox. DMA request,
stream and DMAMUX allocation: **VERIFY in CubeMX (T6)**.

## 2. Board-reserved pins (NUCLEO-H743ZI2 default configuration)

| Pins | Board use | Plan |
|---|---|---|
| PA1, PA2, PA7, PB13, PC1, PC4, PC5, PG11, PG13 | Ethernet RMII to the on-board PHY (REF_CLK, MDIO, CRS_DV, TXD1, MDC, RXD0, RXD1, TX_EN, TXD0) | not used (no Ethernet in the platform); never assigned. To free them the ETH solder bridges would have to change; this plan does not need that |
| PA8, PA9, PA11, PA12, PD10, PG7 | USB OTG FS (SOF, VBUS, DM, DP, power enable, over-current) | not used; never assigned |
| PA13, PA14, PB3 | SWD + SWO (ST-LINK) | debug only |
| PD8, PD9 | USART3 to the ST-LINK virtual COM port | debug console |
| PB0, PB14, PE1 | LD1 green, LD3 red, LD2 yellow | status LEDs (use LD1 first; LD3/LD2 free if the LED is not wanted) |
| PC13 | B1 user button | input |
| PC14, PC15, PH0, PH1 | LSE / HSE oscillator (HSE is the ST-LINK MCO clock, `RCC_OSC_IN` in the board `.ioc`) | clocks |

Solder bridges: the board `.ioc` lists only the pins above as locked. **VERIFY in UM2407** which
SB must change for any other pin used here; the plan assumes none of them needs a bridge change,
except possibly PC2_C / PC3_C (analog switch pins, see ADC row).

## 3. rt-core pins (STM32H743ZIT6, NUCLEO-H743ZI2)

| Function | Peripheral | Pins (AF) | Notes |
|---|---|---|---|
| Vehicle bus (D-021, listen + the one tester) | FDCAN1 | PD0 RX, PD1 TX (AF9) | SN65HVD230 on Board A; no termination. PA11/PA12 and PB8/PB9 are also FDCAN1 but USB / I2C: avoided. Header (Zio CN9 on this board family): **VERIFY in CubeMX (T6)** |
| Platform bus (D-009, D-021) | FDCAN2 | PB5 RX, PB6 TX (AF9) | PB12/PB13 avoided: PB13 is the board's ETH_TXD1. Header position and SB: **VERIFY in CubeMX (T6)** |
| C2 chassis IMU, INA226, MLX90614, BME280, later VL53L1X/AS5600 | I2C1 | PB8 SCL, PB9 SDA (AF4) | pull-ups 2.2-4.7 kΩ at the controller end (proposal, HI §3.4). On the H7 PB8 is not a boot pin (BOOT0 is a dedicated pin) |
| MAX31856 EGT, ADXL345 x2 (Board B) | SPI1 | PA5 SCK, PA6 MISO, PD7 MOSI (AF5) | PA7 (MOSI alternative) is Ethernet |
| SPI1 chip selects | GPIO out | PD11 `CS_EGT`, PD4 `CS_ADXL_ENG`, PD3 `CS_ADXL_ARM` | idle high |
| MAX31856 DRDY / FAULT | GPIO in | PB7 `EGT_DRDY`, PB4 `EGT_FLT` | PB4 = NJTRST, free with SWD |
| GPS NEO-M8N | USART2 | PD5 TX, PD6 RX (AF7) | 3.3 V logic |
| `SPARK_IN`, `WHEEL_F`, `WHEEL_R`, `GPS_PPS` | TIM4 input capture | PD12 CH1, PD13 CH2, PD14 CH3, PD15 CH4 (AF2) | 16-bit: the overflow count extends it in software; TIM2/TIM5 (32-bit) have no four free channels without Ethernet pins |
| microSD logging (D-072 item 2, D-118 item 2) | SDMMC1 4-bit | PC8 D0, PC9 D1, PC10 D2, PC11 D3, PC12 CK, PD2 CMD (AF12) | the HI §3.4 "MicroSD SPI" line is superseded by D-072. Header and SB of the six pins: **VERIFY in CubeMX (T6)** |
| `V_BAT_SENSE` (power management, D-079) | ADC1 | PA3 (ADC1_INP15) | 1 kHz with DMA (D-079, D-082 item 4) |
| `I_BAT_SENSE` (ACS758LCB-200B via divider) | ADC1 | PA4 (ADC1_INP18) | same ADC as the voltage for paired samples |
| `NTC_1`..`NTC_5` | ADC1 / ADC3 | PA0 (ADC1_INP16), PB1 (ADC1_INP5), PC0 (ADC1_INP10), PC2_C (ADC3_INP0), PC3_C (ADC3_INP1) | `_C` pins go through an analog switch (not 5 V tolerant); whether CN-header routing and SB leave them usable: **VERIFY in CubeMX (T6)**. PB0 (LD1) avoided |
| `TAP_CLUTCH`, `TAP_BRAKE`, `TAP_FAN` (PC817, Board B) | GPIO in | PB10, PB11, PB12 | not connected before Q-031(c) |
| Gear / shift-light WS2812B (optional) | TIM3_CH1 + DMA | PC6 (AF2) | separate buffer (SCHEMATIC S2). PC6 is also SDMMC1_D6: only in 8-bit mode, not used |
| Bike ESP32 link (D-112) | none | none reserved | the platform bus (the ESP32's own SN65HVD230), no H743 pin |
| GSM SIM800L (later) | none | none reserved | decide with its wave |
| Power management beyond the battery sensing (D-118 item 2) | none | none reserved | no dedicated pin proposed yet; extra pins come from the free list below |

Debug: SWD PA13/PA14/PB3 (ST-LINK), console on USART3 PD8/PD9 (ST-LINK VCP), status LED LD1 PB0,
button B1 PC13.

Free rt-core pins after this plan: **PA10, PA15, PB2, PB15, PC7** (the old M7 set) plus the whole
of ports E, F, G except the board-reserved PE1 (LD2), PG7 (USB), PG11 and PG13 (ETH): PE0, PE2-PE15,
PF0-PF15, PG0-PG6, PG8-PG10, PG12, PG14, PG15. Their header routing on the board differs per pin
and is not checked: **VERIFY in CubeMX (T6)** before a free pin is promised to a function.

## 4. Assigned twice / board-reserved: none

Checked by script (2026-11-19) against `STM32H743ZITx.xml` and the board `.ioc`:

| Check | Result |
|---|---|
| Pin used by this plan but absent from the LQFP144 pin list | none |
| Pin assigned to two functions | none |
| Pin used by this plan that the board `.ioc` locks (ETH, USB, SWD, VCP, LEDs, button, oscillators) | none |
| Pin assigned here and also in `g474-pin-plan.md` | not applicable: different chips, different boards; the two meet only on the platform bus |

## 5. Checks before this becomes a decision (user)

1. Open the plan in STM32CubeMX for STM32H743ZITx with the NUCLEO-H743ZI2 board selector and
   confirm there is no conflict (pin, AF, DMA request, clock). T6 produces the `.ioc`.
2. UM2407: the header position of each pin (Zio CN7-CN10 or morpho CN11/CN12) and the default
   solder bridges of the pins used (in particular PD0, PD1, PB5, PB6, PA5, PA6, PD7, PC8-PC12,
   PD2, PC2_C, PC3_C).
3. SDMMC1 at the planned clock with the card socket wiring on Board A.
4. Then record it as a DECISIONS item and update `SCHEMATIC-README.md` S2-S4 and
   `hardware-integration.md` §10 item 10 ("H743 + G474 pin maps").
