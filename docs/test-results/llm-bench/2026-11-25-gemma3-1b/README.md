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

Raw output: `gemma3-1b-pi5.json|md`.

## Human review of the Turkish (Claude, 2026-11-25)

More fluent sentences than Qwen, but worse for riders:

- unsolicited safety advice in most answers ("güvenli bir yere durun", "motoru kontrol ettirin"), against the system prompt and alarming for the rider;
- a unit error that changes the value a thousandfold ("225 ve 250 pa", the result is kPa);
- prompt leakage: an internal field name read out ("Eğer sonuçta_stop doğruysa", #8);
- a vague, alarming fault answer without the code (#9);
- decimal point instead of comma; English word "lean" (#8);
- the one "ungrounded" flag (#7, "100" in "litre/100km") is the same unit false positive as in run 1.

## Conclusions

1. Slower than Qwen end to end on the Pi: generation is faster, but the time to first token is about 3x
   longer (prompt processing), so the rider waits longer.
2. Not acceptable for riders: unsolicited advice, a unit error and prompt leakage are worse than Qwen's wording problems.
3. A small local model needs a much stricter prompt and output check (no advice sentences, no internal names,
   units copied verbatim) whichever model is chosen.
