# G6-1 cache round 2 — Arm A (en, run 1)

Suite `dev`, Locale `en`, 35 questions, model(s): qwen2.5-1.5b-instruct-q4_k_m.

| metric | value |
|---|---|
| tool accuracy (name and arguments) | 51% |
| tool name accuracy | 54% |
| fact coverage | n/a (0/0) |
| answers with forbidden patterns | 0 (0 hits) |
| LLM answers / template fallbacks | 2 / 23 |
| latency p50 / p95 | 0.2 s / 2.9 s |
| prompt cache share | 56% (5222/9259 tokens, 14 timed) |
| prompt eval (TTFT) p50 / p95 | 123.8 ms / 1598.5 ms |
| generation (predicted) p50 / p95 | 570.5 ms / 1099.2 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 35 | 18/35 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 10 | 5/10 (50%) | 4 | 1213/2417 | 50% | 79.5 ms / 1149.0 ms |
| 2 | 10 | 6/10 (60%) | 4 | 1684/2607 | 65% | 122.9 ms / 1541.1 ms |
| 3 | 10 | 3/10 (30%) | 6 | 2325/4235 | 55% | 123.8 ms / 1598.5 ms |
| 4 | 5 | 4/5 (80%) | 0 | n/a | n/a | n/a / n/a |

Turn 1 cached share: 50% (TTFT p50 79.5 ms, 4 timed) vs turns 2+: 59% (TTFT p50 123.8 ms, 10 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t2, mt-02-t3, mt-03-t1, mt-03-t2, mt-03-t3, mt-03-t4, mt-04-t1, mt-05-t1, mt-05-t2, mt-05-t3, mt-08-t3, mt-09-t3, mt-10-t1, mt-10-t3.
