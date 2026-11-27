# G6-1 cache round 2 — Arm A (tr, run 1)

Suite `dev`, Locale `tr`, 35 questions, model(s): qwen2.5-1.5b-instruct-q4_k_m.

| metric | value |
|---|---|
| tool accuracy (name and arguments) | 74% |
| tool name accuracy | 74% |
| fact coverage | n/a (0/0) |
| answers with forbidden patterns | 0 (0 hits) |
| LLM answers / template fallbacks | 5 / 26 |
| latency p50 / p95 | 0.0 s / 4.1 s |
| prompt cache share | 33% (2787/8507 tokens, 11 timed) |
| prompt eval (TTFT) p50 / p95 | 1198.3 ms / 1669.7 ms |
| generation (predicted) p50 / p95 | 1228.9 ms / 2528.3 ms |
| request errors | 0 |

| topic | questions | tool ok | facts hit |
|---|---|---|---|
| multiturn | 35 | 26/35 | - |

### Multi-turn per-turn metrics

| turn | n | tool ok | timed | cached / prompt tokens | cached share | prompt eval (TTFT) p50 / p95 |
|---|---|---|---|---|---|---|
| 1 | 10 | 7/10 (70%) | 5 | 1393/3400 | 41% | 1129.1 ms / 1372.5 ms |
| 2 | 10 | 8/10 (80%) | 1 | 3/776 | 0% | 1472.8 ms / 1472.8 ms |
| 3 | 10 | 6/10 (60%) | 5 | 1391/4331 | 32% | 1537.8 ms / 1669.7 ms |
| 4 | 5 | 5/5 (100%) | 0 | n/a | n/a | n/a / n/a |

Turn 1 cached share: 41% (TTFT p50 1129.1 ms, 5 timed) vs turns 2+: 27% (TTFT p50 1472.8 ms, 6 timed).

Wrong tool or arguments: mt-01-t1, mt-01-t2, mt-01-t3, mt-02-t3, mt-05-t3, mt-06-t1, mt-06-t2, mt-06-t3, mt-08-t1.
