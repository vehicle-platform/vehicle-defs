# 2026-11-25 — Gemma 3 4B IT (third run)

Same prompts, tool and Pi as [run 1](../2026-11-25-qwen2.5-1.5b/README.md) and [run 2](../2026-11-25-gemma3-1b/README.md); only the model changed.

## Conditions

| | Raspberry Pi 5 |
|---|---|
| Hardware / OS / llama.cpp / unit | as in run 1 (Pi 5 8 GB, trixie, llama-server v1.0.0 b1b770d, `vehicle-llama.service` with `CPUQuota=150%`, 2 threads, ctx 2048) |
| Model | `gemma-3-4b-it-Q4_K_M.gguf`, SHA-256 `882e8d2d…21a0863` (Hugging Face `ggml-org/gemma-3-4b-it-GGUF` @ d0976223), Gemma terms of use |
| Power / cooling | non-27 W adapter, `get_throttled=0x50000` since boot; Active Cooler, fan 4869 rpm, 58.2 °C after the run |
| Bench tool | vehicle-linux-node @ 3a8ddca, `--warmup 1 --timeout 180` |

## Results

| Metric (Pi 5) | Qwen2.5-1.5B (run 1) | Gemma 3 1B (run 2) | Gemma 3 4B (this run) |
|---|---|---|---|
| Number-grounded answers | 9/10 | 9/10 | 9/10 |
| TTFT median / p95 (s) | 2.77 / 3.19 | 8.46 / 9.00 | 16.45 / 17.51 |
| Total latency median / p95 (s) | 6.57 / 11.30 | 13.14 / 14.19 | 29.90 / 35.90 |
| Generation speed median (tok/s) | 6.5 | 9.9 | 3.6 |

Raw output: `gemma3-4b-pi5.json|md`.

## Human review of the Turkish (Claude, 2026-11-25)

The most natural Turkish of the three (correct grammar, units kept: "Ön lastikleriniz 225 kPa"), but:

- it computes on its own: "42.8 km'lik bir yolculukta 1.46 litre yakıt harcadın" (#7), against invariant 7; the number guard did not flag it;
- a false claim from a number in the result: "Servis yapmanız gerekiyor, 14000 kilometrelere ulaştınız" at 12874 km (#10);
- unsolicited service/stop advice in nearly every answer; internal field names read out ("advise_stop true", #7, #9);
- decimal point instead of comma in most answers.

## Conclusions

1. Too slow on the Pi 5: about 30 s per phrasing call, about a minute per `/chat` answer with the tool-choice call.
2. Better wording does not make it safe: own arithmetic and a false service claim slip past the number guard.
3. Across runs 1-3 no local model is fit for riders as is. Next steps for the assistant: keyword-first tool
   choice, deterministic templates for the frequent questions, an output filter (advice sentences, internal names,
   numbers not copied from the result), cloud providers (D-124) for quality with the local model as fallback,
   and newer small models measured with this same set.
