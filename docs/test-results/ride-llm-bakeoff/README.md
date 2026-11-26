# Ride LLM base-model bake-off (D-132 stage 0)

Measures candidate local GGUF base models end to end against `vehicle-server /chat` on both the
server's development `chat-eval` suite (57 questions/locale) and the independent held-out suite
(`vehicle-ml/src/vehicle_ml/ride_llm/eval/heldout/`, 100 questions/locale, including 16
`safety_red_team` and 8 `out_of_scope` items).

## Method

- Harness: `python -m vehicle_ml.ride_llm.bakeoff` (`vehicle-ml/src/vehicle_ml/ride_llm/bakeoff/`),
  managing one `llama-server` instance at a time (`-c 4096 -np 1 --metrics`) with per-model
  flags from `models.json` (Qwen3 thinking disabled via `--jinja --chat-template-kwargs '{"enable_thinking":false}' --reasoning-budget 0`).
- Candidate weights are restricted strictly to official `Qwen/*-GGUF` repositories (Apache-2.0)
  and verified by SHA-256 before any run. Weights never enter git (D-033).
- Synthetic data only: the 8 local synthetic demo rides in `local/server-data` (no real rides,
  no GPS positions).
- Non-English raw answers stay outside the repository (D-125); only aggregate metrics and
  failing item identifiers are committed.

## Runs

| Date | Provenance | Models completed | Run |
|---|---|---|---|
| 2026-11-26 | `synthetic` (L1) | `qwen2.5-1.5b-instruct-q4_k_m` (baseline; Qwen3-1.7B and Qwen3-4B download-blocked) | [2026-11-26-stage0](2026-11-26-stage0/README.md) |
