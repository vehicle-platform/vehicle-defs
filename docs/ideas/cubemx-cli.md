# STM32CubeMX Command-Line Reference (T70)

Status: reference note, not a decision (facts observed from workspace `local/cubemx/` scripts and logs on macOS, STM32CubeMX 6.18.0)

This note documents how the platform's two initial `.ioc` files (`rt-core` / `NUCLEO-H743ZI2` and `safety-node` / `NUCLEO-G474RE`) were built headlessly with STM32CubeMX's `-q` script mode, which commands worked or failed, how `check_pins.py` verifies pin assignments, and why firmware package installation stays in the GUI. All paths under `<workspace>/local/cubemx/` are git-ignored local tooling.

---

## 1. Running Headlessly on macOS

### Invocation

On macOS, STM32CubeMX 6.18.0 (Java 21.0.10) runs in script mode via:

```bash
/Applications/STMicroelectronics/STM32CubeMX.app/Contents/MacOs/STM32CubeMX -q <script.txt> > <out.log> 2>&1
```

### Kill Guard (No `timeout` on macOS)

macOS does not ship GNU `timeout` by default, and a headless CubeMX invocation can hang if a modal dialog or background thread fails to exit. The wrapper scripts (`local/cubemx/run.sh` with a fixed 170 s limit; `local/cubemx/runl.sh` with configurable `${3:-170}` s) run CubeMX in the background and enforce a hard timeout:

```bash
/Applications/STMicroelectronics/STM32CubeMX.app/Contents/MacOs/STM32CubeMX -q "$S" > "$O" 2>&1 &
p=$!
for i in $(seq 170); do kill -0 $p 2>/dev/null || exit 0; sleep 1; done
kill -9 $p; pkill -9 -f STM32CubeMX; echo KILLED >> "$O"
```

`local/cubemx/build_ioc.sh` also runs `pkill -9 -f STM32CubeMX || true` before each stage to clear any stray JVM instance.

### Why Every Script Starts with `popupwrapper set`

Even in `-q` headless mode, CubeMX raises Swing popup dialogs (for example, `Board Project Options: NUCLEO-H743ZI2` during `loadboard`, or `Project Manager Settings` during `project generate` when a firmware package is missing). Without `popupwrapper set` as the first line, the dialog blocks indefinitely until the kill guard terminates the process.

With `popupwrapper set`, `MxPopupWrapper` intercepts each dialog, logs:

```text
[INFO] MxPopupWrapper:72 - Popup dialog <title>: ... has been wrapped, default Answer was returned
```

and allows the script to continue to `exit`.

---

## 2. Script Commands: What Works and What Does Not

### Commands Verified to Work

Every command below returned `OK` in the captured `local/cubemx/{rt-core,safety-node}/*.out` logs (or is part of the interactive discovery workflow):

| Command | Purpose / Example | Notes from logs |
|---|---|---|
| `popupwrapper set` | Auto-answer blocking GUI popups with their default choice | Must be line 1 of every script |
| `loadboard <board> nomode` | Load board MCU/pinout without enabling default board peripherals (`NUCLEO-H743ZI2 nomode`, `NUCLEO-G474RE nomode`) | Keeps board-locked pins; logs a benign `OptionalMessage_ERROR` for `VP_RIF_VS_RIF1` |
| `get mode available <IP>` | Query valid mode token strings accepted by `set mode` for `<IP>` | Used to discover exact mode names before scripting |
| `set mode <IP> <mode>` | Enable an IP mode (e.g., `set mode FDCAN1 FDCAN_Activate`, `set mode FREERTOS CMSIS_V2`, `set mode RCC HSE-External-Clock-Source`) | Quote mode names containing spaces, e.g. `set mode TIM3 "PWM Generation1 CH1"` |
| `set pin <PIN> <SIGNAL>` | Assign a pin signal (e.g., `set pin PD0 FDCAN1_RX`, `set pin PD11 GPIO_Output`, `set pin PC2_C ADC3_INP0`) | Returns `OK`; logs `Nominal` for FDCAN pins |
| `project name <name>` | Set CubeMX project name (`rt-core`, `safety-node`) | Returns `OK` |
| `project path <dir>` | Set project output directory | Returns `OK` |
| `project toolchain <tc>` | Set target toolchain (`CMake`) | Returns `OK` |
| `config saveas <file.ioc>` | Write the `.ioc` configuration file | Returns `OK` |
| `config load <file.ioc>` | Reload an existing or patched `.ioc` file | Validates and normalizes patched keys on subsequent `config saveas` |
| `csv pinout <file.csv>` | Export the pinout table as CSV | Board-locked pins can have an empty Signal cell in CSV even when present in `.ioc` |
| `exit` | Terminate the headless session cleanly | Required at the end of every script |

To summarize command outcomes from verbose CubeMX logs (`run*.out`, `load.out`, `gen.out`), `local/cubemx/res.py <log> [all]` extracts each script command alongside its `OK`/`KO` result and non-noise `WARN`/`ERROR` lines.

### Known Limitations and Workarounds

1. **No CLI command for DMA configuration:**
   CubeMX `-q` mode has no command to create DMA requests, streams, or channels. `local/cubemx/build_ioc.sh` uses a two-stage workaround:
   - **Stage 1:** Run `<board>.txt` (`loadboard <board> nomode`, `set mode`, `set pin`, `config saveas`) to produce `stage1.ioc`.
   - **Stage 2:** Generate `IP:DMA`, `Dma.Request<n>`, `Dma.<REQ>.<n>.*`, and `Dma.RequestsNb` lines with `local/cubemx/dma_args.py <board>` (for `rt-core`, also `ADC1`/`ADC3` `ConversionDataManagement=ADC_CONVERSIONDATA_DMA_CIRCULAR`), patch `stage1.ioc` into `stage2.ioc` with `local/cubemx/patch_ioc.py` (which updates `Mcu.IP0..N` and `Mcu.IPNb`), then reload `stage2.ioc` via `config load` and re-export via `config saveas` + `csv pinout`.
   - During `config load` of the patched `.ioc`, CubeMX logs `OptionalMessage_ERROR` lines such as `IP (DMA) : Parameter (Instance) has Id (ADC1) currently not set` (and `TIM3_CH1` on G474), plus `Unable to find key (Mcu.IP<n>)` / `Unknown IP (dummy)`, yet retains the DMA entries in the saved `.ioc`.

2. **Board VCP UART `set mode` returns `KO`:**
   - On `NUCLEO-H743ZI2` (`rt-core/run4.out`): `set pin PD8 USART3_TX` and `set pin PD9 USART3_RX` both return `OK`, while `set mode USART3 Asynchronous` returns `KO`.
   - On `NUCLEO-G474RE` (`safety-node/run1.out`): `set mode LPUART1 Asynchronous` returns `KO`.
   - The pins remain recorded in the `.ioc` (`PD8`/`PD9` for `USART3`, `PA2`/`PA3` for `LPUART1`); enabling the VCP UART peripheral mode (along with the H743 clock tree) is completed in the CubeMX GUI.

3. **Empty CSV cells for board-locked pins:**
   `csv pinout` can leave the `Signal` column blank for board-locked pins even though `<PIN>.Signal=...` is present in the `.ioc`. Any automated check must fall back to the `.ioc` file when a CSV cell is empty.

---

## 3. Pin Diff Verification (`check_pins.py`)

`local/cubemx/check_pins.py` cross-checks the generated CubeMX outputs against the platform pin plans (`vehicle-defs/docs/h743-pin-plan.md` and `vehicle-defs/docs/g474-pin-plan.md`).

### How to Run

From the workspace root:

```bash
python3 local/cubemx/check_pins.py rt-core
python3 local/cubemx/check_pins.py safety-node
```

Exit code is `0` when there are zero mismatches and `1` on any mismatch.

### Inputs Read

- `<board>/<board>.csv` (exported by `csv pinout`)
- `<board>/<board>.ioc` (fallback for board-locked pins whose CSV `Signal` cell is empty)
- First available CubeMX stdout log in `<board>/` (`load.out`, `run4.out`, or `run1.out`) to parse the `Traitement de la pin : <N> - <PIN>` / `Key = AF<n> // Value = <SIG>` alternate-function listing
- The board's Markdown pin plan section 3 table (`## 3.` through `## 4.`)

### What It Checks

1. **Plan table vs. script expectation table:** Every pin in section 3 of the Markdown pin plan matches the script's `RT`/`G4` expectation dictionary in both directions.
2. **Exact signal and AF match:** Every planned pin carries its exact expected signal (after stripping any leading `S_` prefix) and, for alternate-function signals, its AF number matches CubeMX's console listing.
3. **No unplanned assignments:** Every non-empty pin in the CSV/`.ioc` must belong to either the planned table or the board-reserved table.
4. **Board-reserved pin protection:** Board-reserved pins (e.g., ETH/USB pins on `NUCLEO-H743ZI2`; `PG10`/NRST and `PB8`/BOOT0 on `NUCLEO-G474RE`) cannot appear in the planned table and may only carry their explicitly allowed board signals (or none when mapped to `None`).
5. **No duplicates:** No non-GPIO, non-Reset signal may appear on two pins, and no pin may carry multiple signals.

### Measured Results (2026-11-27)

```text
$ python3 local/cubemx/check_pins.py rt-core
rt-core: 45 pins with a signal in CSV, 37 planned, 0 mismatches

$ python3 local/cubemx/check_pins.py safety-node
safety-node: 34 pins with a signal in CSV, 25 planned, 0 mismatches
```

---

## 4. Code Generation and Firmware Package Licenses

Running `project generate` in script mode requires the matching STM32Cube firmware package to be installed in the local CubeMX repository:

- `rt-core` (`NUCLEO-H743ZI2`): `STM32Cube FW_H7 V1.13.0` (`ProjectManager.FirmwarePackage=STM32Cube FW_H7 V1.13.0`)
- `safety-node` (`NUCLEO-G474RE`): `STM32Cube FW_G4 V1.6.3` (`ProjectManager.FirmwarePackage=STM32Cube FW_G4 V1.6.3`)

When a package is not installed, `project generate` triggers a popup (`The Firmware Package (...) or one of its dependencies required by the Project is not available in your STM32CubeMX Repository`) and `AnalyticsPlugin` logs an empty `Accepted Firmware Licenses:` list. Under `popupwrapper set`, CubeMX returns the default answer and cannot complete full project generation.

Installing a firmware package requires an interactive license acceptance in the STM32CubeMX GUI:

1. Open STM32CubeMX GUI.
2. Go to **Help > Manage embedded software packages**.
3. Install `STM32Cube FW_H7 V1.13.0` (can be loaded from a locally downloaded archive if present) and `STM32Cube FW_G4 V1.6.3`, accepting ST's license dialog manually.

**Rule:** A headless script must **never** accept or bypass firmware license dialogs on the user's behalf.
