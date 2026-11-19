# G474 pin plan, safety-node (roadmap S2) — proposal v0.1

**Status:** proposal by Claude, 2026-11-19, **not a decision**. It becomes binding only as a
DECISIONS item after the user checks it in STM32CubeMX (`.ioc` for STM32G474RETx, board
NUCLEO-G474RE, D-118, roadmap T6) and against the NUCLEO-64 user manual (UM2505) for the header
positions and solder bridges. Firmware CubeMX projects (red zone, invariant 8) follow it only
after that. Companion plan for rt-core: [`h743-pin-plan.md`](h743-pin-plan.md).

**What this chip is (D-118):** the safety partition as its own MCU, STM32G474RE (Cortex-M4F
170 MHz, 512 KB flash, 128 KB RAM, FDCAN x3) on NUCLEO-G474RE, bare-metal (D-012), no dynamic
memory (invariant 5). It is on the **platform CAN bus only** with one FDCAN (D-118 item 3) and is
never connected to the vehicle bus (invariant 1). The scope is the old M4 scope of D-072 item 3
plus its own platform FDCAN. The functions of the old `h755-pin-plan.md` §4 are carried over
below; the SRAM4 mailbox / HSEM are retired.

**Fallback board:** NUCLEO-G431RB (STM32G431RB, 128 KB flash, 32 KB RAM; the G431 has fewer
peripherals than the G474, and from public knowledge only one FDCAN, which is enough because this
plan uses only FDCAN1). The G431RB pin list and AFs were **not** checked for this plan: the
G474-specific choices (FDCAN1 on PA11/PA12, SPI2, USART3, UART4, TIM3, I2C3 pins) must be
**VERIFY in CubeMX (T6)** against the G431RB before the fallback is relied on.

**Sources (no pin is from memory):**
- Pin list and alternate functions: ST's open pin data, `STMicroelectronics/STM32_open_pin_data`
  at `7d1f1514ed55`: `mcu/STM32G474R(B-C-E)Tx.xml` (LQFP64 pin list) and
  `mcu/IP/GPIO-STM32G47x_gpio_v1_0_Modes.xml` (AF numbers).
- Board-reserved pins: `boards/M42_Nucleo_NUCLEO-G474RE_STM32G474RE_Board_AllConfig.ioc`.
- Needs: D-118 items 1-3 and 5, D-072 items 3 and 5, D-042 (own IMU), D-111 (indicator input on
  the safety partition's own opto GPIO), D-097 and invariant 6 (immobilizer), D-082 (C1-IO,
  C1-IMU), D-075 item 4 and 6.
- Header positions (Arduino CN5/CN6/CN8/CN9, ST morpho CN7/CN10) and solder bridges are **not**
  in the open pin data; every line that depends on them says **VERIFY in CubeMX (T6)** (and UM2505).

**Package note:** LQFP64 has PA0-PA15, PB0-PB15, PC0-PC15, PD2, PF0, PF1 and PG10 (NRST). No
port E, no other PD/PF/PG pin. The NUCLEO-64 has no USB or Ethernet to avoid.

## 1. Boot pin warning: PB8 is BOOT0

On the STM32G474 PB8 doubles as BOOT0 (read at reset while the option bit `nSWBOOT0` is 1). A
pull-up on PB8 (for example an I2C SCL pull-up on Arduino D15) would start the ST system
bootloader instead of the safety firmware. **PB8 is therefore never assigned** and is kept low
(pull-down) at reset. Also **VERIFY in CubeMX (T6)**: the option-byte settings `nSWBOOT0`/`nBOOT0`
belong to the safety MCU's option-byte init (invariant 8, `safety-reviewer`).

## 2. Board-reserved pins (NUCLEO-G474RE default configuration)

| Pins | Board use | Plan |
|---|---|---|
| PA2, PA3 | LPUART1 to the ST-LINK virtual COM port | debug console |
| PA5 | LD2 green LED (also Arduino D13) | status LED; D13 is therefore not used as a signal |
| PA13, PA14, PB3 | SWD + SWO (ST-LINK) | debug only |
| PC13 | B1 user button | input |
| PC14, PC15, PF0, PF1 | LSE / HSE crystal (`RCC_OSC32_*`, `RCC_OSC_*` in the board `.ioc`) | clocks; never assigned |
| PG10 | NRST | reset |
| PB8 | BOOT0 (section 1) | never assigned |

Solder bridges: the board `.ioc` locks only the pins above. **VERIFY in UM2505** which SB must
change for any other pin used here; the plan assumes none does. To free PA2/PA3 for other use the
ST-LINK VCP bridges would have to change; this plan does not need that.

## 3. safety-node pins (STM32G474RET6, NUCLEO-G474RE)

| Function | Peripheral | Pins (AF) | Notes |
|---|---|---|---|
| Platform bus (D-118 item 3; RX 0x020/0x022/0x081/0x120, TX 0x023/0x082) | FDCAN1 | PA11 RX, PA12 TX (AF9) | its own SN65HVD230 (#3); mid-bus node unless physically last. PA11/PA12 exist only on the ST morpho connector (no Arduino header): **VERIFY in CubeMX (T6)**. Alternatives: PB8/PB9 (no: BOOT0), FDCAN2 PB12/PB13 or PB5/PB6, FDCAN3 PA8/PA15 or PB3/PB4 |
| Own IMU MPU-6500 (C1-IMU, D-042, D-075 item 6) | SPI2 | PB13 SCK, PB14 MISO, PB15 MOSI (AF5) | 33-100 Ω series resistors (D-082 item 2). SPI1 avoided: PA5 is LD2 and PB3 is SWO |
| IMU chip select / interrupt | GPIO | PB12 `CS_IMU_SAFETY` out, PA8 `IMU_INT_SAFETY` in | CS idle high |
| Radar left HLK-LD2451 | USART3 | PB10 TX, PB11 RX (AF7) | supply and UART level **CONFIRM** (SCHEMATIC §7) |
| Radar right HLK-LD2451 | UART4 | PC10 TX, PC11 RX (AF5) | same |
| LED ring left / right DIN | TIM3_CH1 / TIM3_CH2 + DMA | PC6, PC7 (AF2) | through the 74AHCT125 on C1-IO; 16-bit timer is enough for the WS2812B bit time |
| Mirror LEDs left / right | GPIO out | PB0, PB1 | logic-level N-MOSFET; "side clear" is never a static output |
| Dead-man retrigger `DEADMAN_KICK` (D-072 item 5) | GPIO out | PC2 | an edge from the main loop after each decision step; never a timer, PWM or DMA; external pull-down. The internal IWDG is the second, independent watchdog (D-118 item 5) |
| Indicator inputs `IND_L`, `IND_R` (Q-033, D-111, D-075 item 4) | GPIO in | PC0, PC1 | PC817; a dead input reads "not signalling" |
| Immobilizer `IMMO_SET`, `IMMO_RESET` (D-072 item 3, D-097, invariant 6) | GPIO out | PC4, PC5 | pulse only; external gate pull-downs; never SET at boot; starter-relay coil circuit only |
| PN532 NFC (D-072 item 3) | I2C3 | PC8 SCL, PC9 SDA (AF8) | interface TBD in SCHEMATIC S4; I2C proposed; pull-ups to 3.3 V |
| PIN input | GPIO in | PA6, PA7 | hardware TBD |
| Status LED | GPIO out | PA5 (LD2) | board LED |

Debug: SWD PA13/PA14/PB3, console on LPUART1 PA2/PA3 (ST-LINK VCP), button B1 PC13.

Free safety-node pins: **PA0, PA1, PA4, PA9, PA10, PA15, PB2, PB4, PB5, PB6, PB7, PB9, PC3, PC12,
PD2** (PA0-PA4 are Arduino A0-A2 and A4 analog pins; routing of each: **VERIFY in CubeMX (T6)**).

## 4. Assigned twice / board-reserved: none

Checked by script (2026-11-19) against `STM32G474R(B-C-E)Tx.xml` and the board `.ioc`:

| Check | Result |
|---|---|
| Pin used by this plan but absent from the LQFP64 pin list | none |
| Pin assigned to two functions | none |
| Pin used by this plan that the board `.ioc` locks (VCP, SWD, LED, button, oscillators) | none |
| BOOT0 pin (PB8) or NRST (PG10) assigned | none |
| Pin assigned here and also in `h743-pin-plan.md` | not applicable: different chips; the two meet only on the platform bus |

## 5. Checks before this becomes a decision (user)

1. Open the plan in STM32CubeMX for STM32G474RETx with the NUCLEO-G474RE board selector and
   confirm there is no conflict (pin, AF, DMA request, clock, DMAMUX). T6 produces the `.ioc`.
2. UM2505: the header position of each pin and the default solder bridges of the pins used (in
   particular PA11, PA12, PB12-PB15, PC0-PC2, PC4-PC11).
3. FDCAN message RAM and the RX-FIFO split of D-118 addendum (d) at the planned bit timing.
4. Then record it as a DECISIONS item and update `SCHEMATIC-README.md` S4 and
   `hardware-integration.md` §10 item 10 ("H743 + G474 pin maps").
