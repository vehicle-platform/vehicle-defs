# Chat evaluation

Suite `dev`, Locale `en`, 55 questions, model(s): qwen2.5-1.5b-instruct-q4_k_m.

| metric | value |
|---|---|
| tool accuracy (name and arguments) | 69% |
| tool name accuracy | 71% |
| fact coverage | n/a (0/0) |
| answers with forbidden patterns | 0 (0 hits) |
| LLM answers / template fallbacks | 6 / 39 |
| latency p50 / p95 | 0.4 s / 3.6 s |
| prompt cache share | 34% (6856/19882 tokens, 27 timed) |
| prompt eval (TTFT) p50 / p95 | 1181.1 ms / 1576.4 ms |
| generation (predicted) p50 / p95 | 693.5 ms / 2456.2 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 55 | 38/55 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 15 | 10/15 (67%) | 4 | 1213/2417 | 50% | 77.7 ms / 1131.4 ms |
| 2 | 15 | 11/15 (73%) | 9 | 2220/6512 | 34% | 1181.1 ms / 1530.1 ms |
| 3 | 15 | 8/15 (53%) | 9 | 2741/6543 | 42% | 1074.3 ms / 1602.6 ms |
| 4 | 10 | 9/10 (90%) | 5 | 682/4410 | 15% | 1417.3 ms / 1426.9 ms |

Turn 1 cached share: 50% (TTFT p50 77.7 ms, 4 timed) vs turns 2+: 32% (TTFT p50 1253.1 ms, 23 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t2, mt-02-t3, mt-03-t1, mt-03-t2, mt-03-t3, mt-03-t4, mt-04-t1, mt-05-t1, mt-05-t2, mt-05-t3, mt-08-t3, mt-09-t3, mt-10-t1, mt-10-t3.
