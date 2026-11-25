# 2026-11-26 — baseline before T42

First run of the chat evaluation harness on the unmodified assistant (vehicle-server main at
844c000 plus the harness; vehicle-mcp main with the mcp#30 result shapes; defs v0.31.0 data).

## Results

| Metric | en | tr |
|---|---|---|
| Questions / request errors | 44 / 0 | 44 / 0 |
| Tool accuracy (name and arguments) | 45% | 43% |
| Fact coverage | 46% (17/37) | 35% (13/37) |
| Answers with forbidden patterns | 19 (22 hits) | 14 (23 hits) |
| LLM answers / template fallbacks / unsupported | 18 / 3 / 22 | 13 / 9 / 22 |
| Latency p50 / p95 | 3.7 s / 21.2 s | 4.2 s / 29.2 s |

Raw output: `en.json` (English). The Turkish run is kept as `tr-scores.json` (aggregates and
failing ids only; raw Turkish answers stay outside the repository).

## Findings

- Half of the questions end as "unsupported": battery, speed, rpm, comparison, history by date,
  ride by id and every symptom question are not routed to a tool by either the LLM or the
  keyword matcher (the keyword table only knows faults, overheating, summary and sessions).
- The model is reported as a file path (`pi/models/...gguf`) in every answer: it is the one
  forbidden hit that appears in every row.
- Excess precision (`20.6458 km`) reaches the rider in the Turkish run, and the comparison
  question leaks internal names (`did.COOLANT_TEMP`) through the template fallback.
- Facts are lost mainly because the wrong tool or no tool ran; where the right tool ran, the
  facts mostly appear (last-ride 5/6, idle 2/2 in en).

## Next

T42 optimisations (template-first phrasing, tool routing for the new `get_data_card` and
`check_symptom` tools, session pool, compact router prompt) are measured against this baseline.
