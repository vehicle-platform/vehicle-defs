# 2026-11-25 — Qwen2.5-1.5B-Instruct (first run)

First measurement of the rider-assistant LLM. Two hosts with the same model and prompts:
the Mac as a quick proxy before the Pi was up, then the Raspberry Pi 5 itself.

## Conditions

| | Mac (proxy) | Raspberry Pi 5 |
|---|---|---|
| Hardware | Apple M1, 8 cores; run CPU only (`-ngl 0`), 2 threads | Raspberry Pi 5 Model B Rev 1.1, 8 GB, Raspberry Pi OS Lite 64-bit (trixie, 2026-10-06 image), USB SSD |
| llama.cpp | `llama-server` v1.0.0 (commit b1b770d), built from the pinned tag | same, built on the Pi by `deploy/llama/build-llama.sh` |
| Server settings | `--threads 2 --ctx-size 2048 --parallel 1 --no-webui` | `vehicle-llama.service`: same flags, `CPUQuota=150%`, `CPUWeight=20`, `Nice=10`, `MemoryMax=3G` |
| Model | `qwen2.5-1.5b-instruct-q4_k_m.gguf`, SHA-256 `6a1a2eb6…9407e` (Hugging Face `Qwen/Qwen2.5-1.5B-Instruct-GGUF` @ 91cad511) | same file, hash re-checked on the Pi |
| Power / cooling | mains | non-27 W USB-C adapter; `get_throttled=0x50000` (under-voltage and throttling occurred since boot, not during the run); Active Cooler, fan 2916 rpm, 53.2 °C after the run |
| Bench tool | vehicle-linux-node @ 3a8ddca, `--warmup 1` | same |

## Results

| Metric | Mac (proxy) | Pi 5 |
|---|---|---|
| Prompts / errors | 10 / 0 | 10 / 0 |
| Number-grounded answers | 9/10 | 9/10 |
| TTFT median / p95 (s) | 0.46 / 1.09 | 2.77 / 3.19 |
| Total latency median / p95 (s) | 1.32 / 4.86 | 6.57 / 11.30 |
| Generation speed median (tok/s) | 33.8 | 6.5 |

Raw output: `mac-m1-cpu2t.json|md`, `pi5-cpu2t.json|md`.

## Human review of the Turkish (Claude, 2026-11-25)

Answers that a rider could hear unchanged: about 3-4 of 10 on both hosts. Recurring problems:

- mixed person ("In my last ride … your speed"), broken word order ("Engine heated at most 118 degrees");
- English words and misspelling ("Front tire pressure of yours");
- decimal point instead of the Turkish comma ("112.4");
- an invented explanation of a fault code (#9, "voltage control (fuel trim)") that the number guard cannot catch;
- Pi #8: lean angle phrased as "you made a 38.5-degree high fall" (reads like a crash), a dangerous wording;
- the one "ungrounded" flag (#7, "100" in "litre / 100 km") is a unit, a false positive of the guard.


## Prompts and answers (English translation)

Literal translation for readers; the evaluated output was Turkish text (not committed, D-125).

### Mac (proxy)

| # | Question (EN) | Answer (EN, literal) | Note |
|---|---|---|---|
| 1 | What was my top speed on my last ride? | In my last ride your top speed was 112.4 km/h. |  |
| 2 | How many kilometres was my last ride and how long did it take? | The driver, from his last ride shows 42.8 km distance. | Garbled; no duration |
| 3 | Is the engine temperature normal? | Engine temperature is 92 degrees and oil temperature is 104 degrees. I prefer to recommend checking the engine. | Unsolicited advice |
| 4 | How hot did the engine get at most? | Engine heated at most 118 degrees. | Broken word order |
| 5 | How is the battery voltage? | Battery voltage is 12.6V and loading voltage is 14.2V. |  |
| 6 | What are my tire pressures? | Result: Front tire pressure of yours is 225 kPa and rear tire pressure of yours is 250 kPa. | English words, misspelling |
| 7 | What is my average fuel consumption? | Average fuel consumption of yours is 3.4 litres 100 km. | Unit garbled |
| 8 | How much did I lean at most on this ride? | Sorry, there is no data in this vehicle result. | No answer given |
| 9 | Which fault codes are there? | Fault code is P0171, found as "Fuel trim lean, bank 1". This code shows that the engine's voltage control (fuel trim) is missing in the bank 1 range. | Invented explanation of the code |
| 10 | How many kilometres have I done in total? | You did 12874 kilometres in total. |  |

### Raspberry Pi 5

| # | Question (EN) | Answer (EN, literal) | Note |
|---|---|---|---|
| 1 | What was my top speed on my last ride? | In my last ride your top speed was 112.4 km/h. |  |
| 2 | How many kilometres was my last ride and how long did it take? | My last ride was 42.8 km distance and lasted 51 minutes lasted. | Mixed person, repeated word |
| 3 | Is the engine temperature normal? | Engine temperature is 92°C. |  |
| 4 | How hot did the engine get at most? | Engine heated at most 118 degrees. | Broken word order |
| 5 | How is the battery voltage? | Battery voltage is 12.6V and loading voltage is 14.2V. |  |
| 6 | What are my tire pressures? | Result: Front tire pressure of yours is 225 kPa and rear tire pressure of yours is 250 kPa. | English words, misspelling |
| 7 | What is my average fuel consumption? | Average fuel consumption of yours is 3.4 litres 100 km. | Unit garbled; guard flag is a false positive ("100") |
| 8 | How much did I lean at most on this ride? | The driver, in this ride at most 38.5 degrees high fall you made. | Reads like a crash; dangerous wording |
| 9 | Which fault codes are there? | Fault code is P0171, found as "Fuel trim lean, bank 1". This code means that the engine's voltage control (fuel trim) is missing in the bank 1 range. | Invented explanation of the code |
| 10 | How many kilometres have I done in total? | You did 12874 kilometres in total. |  |

## Conclusions

1. Speed on the Pi: one `/chat` answer makes two LLM calls (tool choice + phrasing), so with this
   model a rider waits about 10-15 s; too long for intercom use.
2. Quality: not acceptable for riders as is; the number guard holds, the wording does not.
3. Next runs: Gemma 3 1B and 4B with the same prompts; keyword-first tool choice (skip the first
   LLM call); a stricter system prompt (second person, decimal comma, no English, no interpretation,
   2-3 examples); cloud providers (D-124) for quality with the local model as fallback.
