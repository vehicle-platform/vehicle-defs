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

- mixed person ("Son sürüşümde … hızınız"), broken word order ("Motor ısındı en fazla 118 derece");
- English words and misspelling ("Front lastik basınçınız");
- decimal point instead of the Turkish comma ("112.4");
- an invented explanation of a fault code (#9, "gerilim kontrolü (fuel trim)") that the number guard cannot catch;
- Pi #8: lean angle phrased as "38.5 derece yüksek düşme yaptınız" (reads like a crash), a dangerous wording;
- the one "ungrounded" flag (#7, "100" in "litre / 100 km") is a unit, a false positive of the guard.

## Conclusions

1. Speed on the Pi: one `/chat` answer makes two LLM calls (tool choice + phrasing), so with this
   model a rider waits about 10-15 s; too long for intercom use.
2. Quality: not acceptable for riders as is; the number guard holds, the wording does not.
3. Next runs: Gemma 3 1B and 4B with the same prompts; keyword-first tool choice (skip the first
   LLM call); a stricter system prompt (second person, decimal comma, no English, no interpretation,
   2-3 examples); cloud providers (D-124) for quality with the local model as fallback.
