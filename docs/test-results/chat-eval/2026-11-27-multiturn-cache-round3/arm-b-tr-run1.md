# Chat evaluation

Suite `dev`, Locale `tr`, 55 questions, model(s): qwen2.5-1.5b-instruct-q4_k_m.

| metric | value |
|---|---|
| tool accuracy (name and arguments) | 84% |
| tool name accuracy | 84% |
| fact coverage | n/a (0/0) |
| answers with forbidden patterns | 0 (0 hits) |
| LLM answers / template fallbacks | 11 / 40 |
| latency p50 / p95 | 0.0 s / 4.7 s |
| prompt cache share | 24% (4790/20110 tokens, 24 timed) |
| prompt eval (TTFT) p50 / p95 | 1390.2 ms / 1690.2 ms |
| generation (predicted) p50 / p95 | 1242.3 ms / 2586.9 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 55 | 46/55 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 15 | 12/15 (80%) | 5 | 964/3400 | 28% | 1191.4 ms / 1252.4 ms |
| 2 | 15 | 13/15 (87%) | 6 | 878/4938 | 18% | 1374.5 ms / 1550.2 ms |
| 3 | 15 | 11/15 (73%) | 8 | 2061/6990 | 29% | 1397.3 ms / 1816.0 ms |
| 4 | 10 | 10/10 (100%) | 5 | 887/4782 | 19% | 1563.2 ms / 1674.6 ms |

Turn 1 cached share: 28% (TTFT p50 1191.4 ms, 5 timed) vs turns 2+: 23% (TTFT p50 1449.4 ms, 19 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t3, mt-05-t3, mt-06-t1, mt-06-t2, mt-06-t3, mt-08-t1.
