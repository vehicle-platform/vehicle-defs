# 2026-11-25 — Gemma 3 1B IT (second run)

Same prompts, tool and Pi as [the first run](../2026-11-25-qwen2.5-1.5b/README.md); only the model changed.

## Conditions

| | Raspberry Pi 5 |
|---|---|
| Hardware / OS / llama.cpp / unit | as in the first run (Pi 5 8 GB, trixie, llama-server v1.0.0 b1b770d, `vehicle-llama.service` with `CPUQuota=150%`, 2 threads, ctx 2048) |
| Model | `gemma-3-1b-it-Q4_K_M.gguf`, SHA-256 `8ccc5cd1…eb75a135` (Hugging Face `ggml-org/gemma-3-1b-it-GGUF` @ f9c28bcd), Gemma terms of use |
| Power / cooling | non-27 W adapter, `get_throttled=0x50000` since boot; Active Cooler, fan 2896 rpm, 56.0 °C after the run |
| Bench tool | vehicle-linux-node @ 3a8ddca, `--warmup 1` |

## Results

| Metric | Gemma 3 1B (Pi 5) | Qwen2.5-1.5B (Pi 5, run 1) |
|---|---|---|
| Prompts / errors | 10 / 0 | 10 / 0 |
| Number-grounded answers | 9/10 | 9/10 |
| TTFT median / p95 (s) | 8.46 / 9.00 | 2.77 / 3.19 |
| Total latency median / p95 (s) | 13.14 / 14.19 | 6.57 / 11.30 |
| Generation speed median (tok/s) | 9.9 | 6.5 |

The raw outputs (Turkish answers) are kept outside the public repository (D-125); the evaluated language was Turkish. Numeric summaries: see the `*.metrics.json` files in this folder.

## Human review of the Turkish (Claude, 2026-11-25)

More fluent sentences than Qwen, but worse for riders:

- unsolicited safety advice in most answers ("stop somewhere safe", "have the engine checked"), against the system prompt and alarming for the rider;
- a unit error that changes the value a thousandfold ("225 and 250 pa", the result is kPa);
- prompt leakage: an internal field name read out ("If result_stop is true", #8);
- a vague, alarming fault answer without the code (#9);
- decimal point instead of comma; English word "lean" (#8);
- the one "ungrounded" flag (#7, "100" in "litre/100km") is the same unit false positive as in run 1.


## Prompts and answers (English translation)

Literal translation for readers; the evaluated output was Turkish text (not committed, D-125).

| # | Question (EN) | Answer (EN, literal) | Note |
|---|---|---|---|
| 1 | What was my top speed on my last ride? | In your ride your top speed was 112.4 km/h. |  |
| 2 | How many kilometres was my last ride and how long did it take? | Your ride reached 42.8 kilometres. You lasted about 51 minutes. For your safety, it is recommended that you check the check of your engine. | Unsolicited advice; garbled |
| 3 | Is the engine temperature normal? | Engine temperature is normal. The temperature value is around 92 degrees. The heating of the engine is a normal situation. If the temperature is too high, please check the engine and stop at a safe place. | Unsolicited advice |
| 4 | How hot did the engine get at most? | Your engine reached 118 degrees. The highest temperature is 121 degrees. For your safety, do not forget to have the engine checked. | Unsolicited advice |
| 5 | How is the battery voltage? | Battery voltage is between 12.6 volts and 14.2 volts. These values are within normal limits. If the voltage is dropping, there may be a problem in the battery. I recommend moving to a safe place and checking the engine. | Unsolicited advice |
| 6 | What are my tire pressures? | "Your tire pressure is between 225 and 250 pa." | Unit error: result is kPa, not Pa |
| 7 | What is my average fuel consumption? | Your fuel consumption is around 3.4 litres/100km. This value occurred in the last 42.8 km trip. I recommend having your fuel consumption checked. | Unsolicited advice; guard flag ("100") is a unit false positive |
| 8 | How much did I lean at most on this ride? | In your ride there is 38.5 degrees lean. Make sure to check your engine and stop at a safe place. If result_stop is true, stop at a safe place. | Advice; internal field name leaked; English word "lean" |
| 9 | Which fault codes are there? | "There seems to be a problem with your engine. There may be a problem in bank 1 in particular. I recommend having the engine checked. If the problem continues, it would be best to stop at a safe place and check the engine." | Vague, alarming; fault code not given |
| 10 | How many kilometres have I done in total? | You set out on 12874 kilometres of road. |  |

## Conclusions

1. Slower than Qwen end to end on the Pi: generation is faster, but the time to first token is about 3x
   longer (prompt processing), so the rider waits longer.
2. Not acceptable for riders: unsolicited advice, a unit error and prompt leakage are worse than Qwen's wording problems.
3. A small local model needs a much stricter prompt and output check (no advice sentences, no internal names,
   units copied verbatim) whichever model is chosen.
