# G6-1 cache round 2 — Arm A (en, run 2)

Suite `dev`, Locale `en`, 35 questions, model(s): qwen2.5-1.5b-instruct-q4_k_m.

| metric | value |
|---|---|
| tool accuracy (name and arguments) | 51% |
| tool name accuracy | 54% |
| fact coverage | n/a (0/0) |
| answers with forbidden patterns | 0 (0 hits) |
| LLM answers / template fallbacks | 2 / 23 |
| latency p50 / p95 | 0.0 s / 1.2 s |
| prompt cache share | 96% (8881/9259 tokens, 14 timed) |
| prompt eval (TTFT) p50 / p95 | 75.2 ms / 288.2 ms |
| generation (predicted) p50 / p95 | 532.8 ms / 1085.5 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 35 | 18/35 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 10 | 5/10 (50%) | 4 | 2366/2417 | 98% | 60.6 ms / 90.2 ms |
| 2 | 10 | 6/10 (60%) | 4 | 2489/2607 | 95% | 122.6 ms / 128.4 ms |
| 3 | 10 | 3/10 (30%) | 6 | 4026/4235 | 95% | 74.1 ms / 288.2 ms |
| 4 | 5 | 4/5 (80%) | 0 | n/a | n/a | n/a / n/a |

Turn 1 cached share: 98% (TTFT p50 60.6 ms, 4 timed) vs turns 2+: 95% (TTFT p50 75.2 ms, 10 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t2, mt-02-t3, mt-03-t1, mt-03-t2, mt-03-t3, mt-03-t4, mt-04-t1, mt-05-t1, mt-05-t2, mt-05-t3, mt-08-t3, mt-09-t3, mt-10-t1, mt-10-t3.
