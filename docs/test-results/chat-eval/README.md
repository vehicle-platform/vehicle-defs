# Chat evaluation (rider assistant)

Scores the full `POST /chat` pipeline (tool choice, tool call, phrasing, number guard) on a
fixed question set, so every assistant change has a before/after number (TASKS T40-T50).

## Method

- Tool: `vehicle-server chat-eval` (`vehicle-server/src/vehicle_server/chat/eval/`), 44
  questions per locale (en, tr) over 16 topics: last ride, distance, time, stops, idle, coolant
  and overheating, warm-up, battery, speed, rpm, ride comparison, ride history, a ride by id,
  fault catalog, symptoms, out of scope. Single-turn only.
- Per question: tool chosen (name and argument patterns against an accepted set), required facts
  (named result values must appear in the answer; unit conversions such as seconds to minutes
  are accepted), forbidden patterns (internal identifiers, file paths, more than two decimals,
  advice words, a file path as the model name), source, latency.
- Data: the 8 synthetic demo rides of the local demo data set (scenarios baseline, highway,
  city-hot, weak-charging, cold-start). Server on the Mac, vehicle-mcp from main (mcp#30
  result shapes), local `llama-server` with Qwen2.5-1.5B-Instruct Q4_K_M, `-c 4096`, CPU.
- Latency is wall time per request including vehicle-mcp spawn; the Mac was busy with other
  work during the baseline, so absolute latency is only comparable between runs on a quiet
  machine.
- Non-English raw output stays outside the repository (D-125); a Turkish run is stored here as
  aggregate scores and failing question ids only.

## Runs

| Date | Change | Run |
|---|---|---|
| 2026-11-26 | Baseline before T42 (main of server 844c000 + harness) | [2026-11-26-baseline](2026-11-26-baseline/README.md) |
