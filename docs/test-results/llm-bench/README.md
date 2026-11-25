# LLM benchmark (rider assistant)

Measures the phrasing step of `POST /chat` (D-121 item 1): the model gets a rider question
plus a synthetic tool result and must answer in at most 3 short Turkish sentences, using only
numbers from the result (invariant 7).

## Method

- Tool: `vehicle-linux-node-llm-bench` (`vehicle-linux-node/src/vehicle_linux_node/llmbench.py`),
  10 fixed Turkish prompts, the same system prompt and message shape as vehicle-server's
  phrasing step, OpenAI-compatible endpoint (llama.cpp `llama-server`).
- Metrics per prompt: time to first token (TTFT), total latency, generation speed,
  number grounding (every number in the answer must occur in the tool result; rounding allowed).
- Turkish quality is judged by a human reading the answers (the tool cannot), see each run.
- Reproduce on the Pi: `uv run vehicle-linux-node-llm-bench --url http://127.0.0.1:8081/v1 --label <name> --out <dir> --warmup 1`.
- Note: the tool's output file name is cut at the first dot of `--label` (`qwen2.5-1.5b` → `qwen2.5-1.json`);
  run folders rename the files.

## Runs

| Date | Model | Host | TTFT median / p95 (s) | Total median / p95 (s) | tok/s | Grounded | Turkish (human) | Run |
|---|---|---|---|---|---|---|---|---|
| 2026-11-25 | Qwen2.5-1.5B-Instruct Q4_K_M | Mac M1, CPU only, 2 threads (proxy) | 0.46 / 1.09 | 1.32 / 4.86 | 33.8 | 9/10 | weak (3-4/10 usable) | [2026-11-25-qwen2.5-1.5b](2026-11-25-qwen2.5-1.5b/README.md) |
| 2026-11-25 | Qwen2.5-1.5B-Instruct Q4_K_M | **Raspberry Pi 5**, vehicle-llama unit, 2 threads | **2.77 / 3.19** | **6.57 / 11.30** | **6.5** | 9/10 | weak (3-4/10 usable) | [2026-11-25-qwen2.5-1.5b](2026-11-25-qwen2.5-1.5b/README.md) |
| 2026-11-25 | Gemma 3 1B IT Q4_K_M | **Raspberry Pi 5**, vehicle-llama unit, 2 threads | **8.46 / 9.00** | **13.14 / 14.19** | **9.9** | 9/10 | weak: unsolicited advice, unit error, prompt leak | [2026-11-25-gemma3-1b](2026-11-25-gemma3-1b/README.md) |

Next: Gemma 3 4B on the Pi with the same prompts.
