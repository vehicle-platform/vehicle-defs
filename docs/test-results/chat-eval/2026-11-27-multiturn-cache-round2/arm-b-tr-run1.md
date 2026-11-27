# G6-1 cache round 2 — Arm B (tr, run 1)

Suite `dev`, Locale `tr`, 35 questions, model(s): qwen2.5-1.5b-instruct-q4_k_m.

| metric | value |
|---|---|
| tool accuracy (name and arguments) | 74% |
| tool name accuracy | 74% |
| fact coverage | n/a (0/0) |
| answers with forbidden patterns | 0 (0 hits) |
| LLM answers / template fallbacks | 5 / 26 |
| latency p50 / p95 | 0.0 s / 4.8 s |
| prompt cache share | 36% (3049/8507 tokens, 11 timed) |
| prompt eval (TTFT) p50 / p95 | 1265.3 ms / 1820.0 ms |
| generation (predicted) p50 / p95 | 1414.7 ms / 2721.8 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 35 | 26/35 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 10 | 7/10 (70%) | 5 | 1524/3400 | 45% | 1262.0 ms / 1266.2 ms |
| 2 | 10 | 8/10 (80%) | 1 | 3/776 | 0% | 1636.3 ms / 1636.3 ms |
| 3 | 10 | 6/10 (60%) | 5 | 1522/4331 | 35% | 1591.6 ms / 1820.0 ms |
| 4 | 5 | 5/5 (100%) | 0 | n/a | n/a | n/a / n/a |

Turn 1 cached share: 45% (TTFT p50 1262.0 ms, 5 timed) vs turns 2+: 30% (TTFT p50 1591.6 ms, 6 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t3, mt-05-t3, mt-06-t1, mt-06-t2, mt-06-t3, mt-08-t1.
