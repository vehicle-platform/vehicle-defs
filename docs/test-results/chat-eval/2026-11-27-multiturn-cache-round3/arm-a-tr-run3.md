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
| prompt cache share | 23% (4531/20110 tokens, 24 timed) |
| prompt eval (TTFT) p50 / p95 | 1415.6 ms / 1799.8 ms |
| generation (predicted) p50 / p95 | 1223.8 ms / 2569.2 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 55 | 46/55 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 15 | 12/15 (80%) | 5 | 833/3400 | 24% | 1213.7 ms / 1415.6 ms |
| 2 | 15 | 13/15 (87%) | 6 | 881/4938 | 18% | 1357.8 ms / 1541.2 ms |
| 3 | 15 | 11/15 (73%) | 8 | 1930/6990 | 28% | 1436.9 ms / 1809.3 ms |
| 4 | 10 | 10/10 (100%) | 5 | 887/4782 | 19% | 1572.6 ms / 1733.3 ms |

Turn 1 cached share: 24% (TTFT p50 1213.7 ms, 5 timed) vs turns 2+: 22% (TTFT p50 1488.4 ms, 19 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t3, mt-05-t3, mt-06-t1, mt-06-t2, mt-06-t3, mt-08-t1.
