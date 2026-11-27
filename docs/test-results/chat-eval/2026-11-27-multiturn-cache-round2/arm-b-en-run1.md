# G6-1 cache round 2 — Arm B (en, run 1)

Suite `dev`, Locale `en`, 35 questions, model(s): qwen2.5-1.5b-instruct-q4_k_m.

| metric | value |
|---|---|
| tool accuracy (name and arguments) | 51% |
| tool name accuracy | 54% |
| fact coverage | n/a (0/0) |
| answers with forbidden patterns | 0 (0 hits) |
| LLM answers / template fallbacks | 2 / 23 |
| latency p50 / p95 | 0.1 s / 3.0 s |
| prompt cache share | 59% (5476/9259 tokens, 14 timed) |
| prompt eval (TTFT) p50 / p95 | 122.5 ms / 1671.8 ms |
| generation (predicted) p50 / p95 | 671.7 ms / 2423.2 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 35 | 18/35 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 10 | 5/10 (50%) | 4 | 1213/2417 | 50% | 105.1 ms / 1359.3 ms |
| 2 | 10 | 6/10 (60%) | 4 | 1680/2607 | 64% | 122.5 ms / 1513.6 ms |
| 3 | 10 | 3/10 (30%) | 6 | 2583/4235 | 61% | 122.0 ms / 1671.8 ms |
| 4 | 5 | 4/5 (80%) | 0 | n/a | n/a | n/a / n/a |

Turn 1 cached share: 50% (TTFT p50 105.1 ms, 4 timed) vs turns 2+: 62% (TTFT p50 122.5 ms, 10 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t2, mt-02-t3, mt-03-t1, mt-03-t2, mt-03-t3, mt-03-t4, mt-04-t1, mt-05-t1, mt-05-t2, mt-05-t3, mt-08-t3, mt-09-t3, mt-10-t1, mt-10-t3.
