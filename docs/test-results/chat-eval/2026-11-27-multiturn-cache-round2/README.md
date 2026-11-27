# 2026-11-27 — Multi-turn prompt-cache measurement, round 2 (T72)

`Provenance: synthetic` (the 8 synthetic demo rides of the local demo data set, `vehicle-server`
mock/demo store; no real ride or position data).

Compares `llama-server` slot configurations **Arm A** (`-np 1 -c 4096`) vs. **Arm B**
(`-np 2 -c 8192`, keeping 4096 tokens per slot) on the ten multi-turn conversations
(`mt-01`..`mt-10`, 35 turns per run) introduced in `vehicle-server#110`, with three separate runs
per arm and locale (`en`, `tr`). Measure only — no prompt, router, template, or server changes.

## Environment and versions

- **`vehicle-server`**: `main` at `e5837a5` (includes `vehicle-server#110` multi-turn eval harness)
- **`vehicle-mcp`**: `853c012` (local `.venv/bin/vehicle-mcp`)
- **`llama-server`**: `version: 1.0.0-dev (build 1, commit b1b770d)`, AppleClang 21.0.0.21000101,
  Darwin arm64
- **Model**: `qwen2.5-1.5b-instruct-q4_k_m.gguf`
- **Server launch** (same `vehicle-server` process across both arms; rate limit raised via env so
  420 sequential turns do not sleep on 429):
  ```sh
  VEHICLE_CHAT_RATE_PER_MIN=600 ./local/run-server.sh
  ```
- **Arm A (`llama-server` restarted fresh before arm A)**:
  ```sh
  ./local/run-llama.sh
  # expands to: llama-server -m local/pi/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  #   --host 127.0.0.1 --port 8081 -c 4096 -np 1
  # startup log: n_slots = 1, n_ctx_slot = 4096, kv_unified = 'false'
  ```
- **Arm B (`llama-server` restarted fresh before arm B)**:
  ```sh
  ./local/llama/build/bin/llama-server \
    -m ./local/pi/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --host 127.0.0.1 --port 8081 -c 8192 -np 2
  # startup log: n_slots = 2, n_ctx_slot = 4096, kv_unified = 'false'
  ```
- **Eval command** (run 3 times sequentially for `en`, then 3 times sequentially for `tr`, within
  each arm without restarting `llama-server` between runs or locales):
  ```sh
  uv run vehicle-server chat-eval \
    --base-url http://127.0.0.1:8000 \
    --token-file <demo-user-token-file> \
    --locale <en|tr> \
    --only mt-01,mt-02,mt-03,mt-04,mt-05,mt-06,mt-07,mt-08,mt-09,mt-10 \
    --timeout 60 \
    --out <out.json> \
    --summary-md <summary.md>
  ```
- Demo user active provider verified before Arm A via `GET /assistant/active`:
  `provider_id=local`, `selected_provider_id=local`, `fallback_reason=null`.

## Step 1: `llama-server` calls per `/chat` turn (code audit)

Audited on `vehicle-server` `e5837a5` in `src/vehicle_server/chat/service.py`, `llm.py`,
`planner.py`, `wiring.py`, and `providers/{openai_compat,factory}.py`.

One `POST /chat` turn makes **0, 1, or 2** calls to `POST {llm_url}/chat/completions` (no other
endpoints are called during `/chat`; memory commands return before `_choose`, and `list_models` is
never called during `/chat`):

| Call | Code path | System prompt source | When it runs | Parameters |
|---|---|---|---|---|
| 1. Tool choice | `ChatService._choose` (`service.py:262`) -> `planner.choose_tool` (`planner.py:196-198`) -> `OpenAICompatibleProvider.choose_tool` (`providers/openai_compat.py:26-38`) -> `OpenAiCompatLlm.complete` (`llm.py:117-151`) | `planner.system_text(tools)` (`planner.py:106-114`): static English instruction + sorted one-line tool menu (~560 tokens). Context (state, memory, recent turns) is appended to the `user` message (`planner.py:125-130`). | Only when `guard.refuses`, `followup.resolve`, `router.route`, and `_symptom_step` (`pre_llm`) all return `None`. | `temperature=0`, `max_tokens=200`, `response_format=json_schema` (falls back to `json_object`/`none` if rejected), `cache_prompt=True` on default local client (`wiring.py:21`). |
| 2. Phrasing | `ChatService._phrase` (`service.py:422-433`) -> `OpenAICompatibleProvider.phrase` (`providers/openai_compat.py:40-41`) -> `OpenAiCompatLlm.complete` (`llm.py:117-151`) | `service._system_prompt(locale)` (`service.py:39-41`) -> `i18n.load_chat(locale)["system_prompt"]` (`chat/locales/<locale>.json`, ~133 tokens in `en`, ~134 tokens in `tr`). Context + question + flattened tool result go in the `user` message (`service.py:418-430`). | Only when a tool ran AND either `answers.uses_llm(plan, result)` is `True` or `answers.render` returns `None`. | `temperature=0`, `max_tokens=answers.MAX_LLM_TOKENS` (`120`), no `response_format`, `cache_prompt=True` on default local client (`wiring.py:21`). |

- **Note on `cache_prompt`**: the default local server client in `chat/wiring.py:21` passes
  `cache_prompt=True`. By contrast, `chat/providers/factory.py:33` constructs `OpenAiCompatLlm`
  without `cache_prompt=True` (defaults to `False`) when a user explicitly configures the `local`
  preset through per-user provider settings (fixed in vehicle-server by a Claude follow-up PR; the
  local preset now passes `cache_prompt=True`).
- **Which call's `timings` `/chat` reports**: `OpenAiCompatLlm.complete` (`llm.py:138-142`) parses
  `data["timings"]` (`prompt_n`, `cache_n`, `prompt_ms`, `predicted_ms`) on every call and appends
  it to the per-request `REPORTED_TIMINGS` `ContextVar` list. `ChatService.answer`
  (`service.py:180-193`) sums all entries in that list (`sum(prompt_n)`, `sum(cache_n)`,
  `round(sum(prompt_ms), 3)`, `round(sum(predicted_ms), 3)`). Turns that make 0 LLM calls return
  `timings: null`.

## Results

All 12 runs completed with `0` request errors (`35` turns per run, `105` turns pooled over 3 runs
per arm and locale). Cache shares and `prompt_ms` percentiles below are computed strictly over
LLM-timed turns (`timings != null`), with both total `n` and `timed n` shown.

### Per-run summary (showing cold run 1 vs. warm runs 2–3)

Caption: Run 1 is cold only for the first locale of each arm. The `tr` Run 1 is not fully cold: it ran after the `en` runs on the same `llama-server`, so the shared planner prefix was already cached (finding 3).

| Locale | Arm | Run | n | LLM-timed n | Cached / total prompt tokens | Cached share | `prompt_ms` p50 | `prompt_ms` p95 | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| `en` | A (`-np 1 -c 4096`) | 1 | 35 | 14 | 5222 / 9259 | 56.4% | 123.8 ms | 1598.5 ms | 22.4 s |
| `en` | A (`-np 1 -c 4096`) | 2 | 35 | 14 | 8881 / 9259 | 95.9% | 75.2 ms | 288.2 ms | 13.3 s |
| `en` | A (`-np 1 -c 4096`) | 3 | 35 | 14 | 8881 / 9259 | 95.9% | 75.3 ms | 285.6 ms | 12.7 s |
| `en` | B (`-np 2 -c 8192`) | 1 | 35 | 14 | 5476 / 9259 | 59.1% | 122.5 ms | 1671.8 ms | 24.8 s |
| `en` | B (`-np 2 -c 8192`) | 2 | 35 | 14 | 8881 / 9259 | 95.9% | 93.2 ms | 371.2 ms | 24.8 s |
| `en` | B (`-np 2 -c 8192`) | 3 | 35 | 14 | 8881 / 9259 | 95.9% | 93.8 ms | 333.4 ms | 21.8 s |
| `tr` | A (`-np 1 -c 4096`) | 1 | 35 | 11 | 2787 / 8507 | 32.8% | 1198.3 ms | 1669.7 ms | 32.5 s |
| `tr` | A (`-np 1 -c 4096`) | 2 | 35 | 11 | 8087 / 8507 | 95.1% | 34.8 ms | 423.8 ms | 22.2 s |
| `tr` | A (`-np 1 -c 4096`) | 3 | 35 | 11 | 8087 / 8507 | 95.1% | 40.2 ms | 423.7 ms | 22.7 s |
| `tr` | B (`-np 2 -c 8192`) | 1 | 35 | 11 | 3049 / 8507 | 35.8% | 1265.3 ms | 1820.0 ms | 36.9 s |
| `tr` | B (`-np 2 -c 8192`) | 2 | 35 | 11 | 8087 / 8507 | 95.1% | 59.3 ms | 438.0 ms | 26.6 s |
| `tr` | B (`-np 2 -c 8192`) | 3 | 35 | 11 | 8087 / 8507 | 95.1% | 52.7 ms | 441.5 ms | 29.4 s |

### Per-turn pooled across 3 runs (per arm and locale)

The pooled rows mix the cold Run 1 with the replay-dominated Runs 2-3 (finding 3), so they do not measure within-conversation reuse; use the Run 1 rows for that.

| Locale | Arm | Turn | n | LLM-timed n | Cached / total prompt tokens | Cached share | `prompt_ms` p50 | `prompt_ms` p95 |
|---|---|---|---|---|---|---|---|---|
| `en` | A | 1 | 30 | 12 | 5945 / 7251 | 82.0% | 79.1 ms | 1148.3 ms |
| `en` | A | 2 | 30 | 12 | 6662 / 7821 | 85.2% | 122.6 ms | 764.1 ms |
| `en` | A | 3 | 30 | 18 | 10377 / 12705 | 81.7% | 75.4 ms | 1590.9 ms |
| `en` | A | 4 | 15 | 0 | n/a | n/a | n/a | n/a |
| `en` | A | **All** | **105** | **42** | **22984 / 27777** | **82.7%** | **88.5 ms** | **1521.5 ms** |
| `en` | B | 1 | 30 | 12 | 5945 / 7251 | 82.0% | 93.5 ms | 1217.7 ms |
| `en` | B | 2 | 30 | 12 | 6658 / 7821 | 85.1% | 139.9 ms | 769.4 ms |
| `en` | B | 3 | 30 | 18 | 10635 / 12705 | 83.7% | 104.1 ms | 1461.8 ms |
| `en` | B | 4 | 15 | 0 | n/a | n/a | n/a | n/a |
| `en` | B | **All** | **105** | **42** | **23238 / 27777** | **83.7%** | **115.0 ms** | **1421.4 ms** |
| `tr` | A | 1 | 30 | 15 | 8115 / 10200 | 79.6% | 67.4 ms | 1250.5 ms |
| `tr` | A | 2 | 30 | 3 | 1553 / 2328 | 66.7% | 43.0 ms | 1329.8 ms |
| `tr` | A | 3 | 30 | 15 | 9293 / 12993 | 71.5% | 368.9 ms | 1617.5 ms |
| `tr` | A | 4 | 15 | 0 | n/a | n/a | n/a | n/a |
| `tr` | A | **All** | **105** | **33** | **18961 / 25521** | **74.3%** | **68.9 ms** | **1560.8 ms** |
| `tr` | B | 1 | 30 | 15 | 8246 / 10200 | 80.8% | 79.4 ms | 1265.5 ms |
| `tr` | B | 2 | 30 | 3 | 1553 / 2328 | 66.7% | 67.8 ms | 1479.5 ms |
| `tr` | B | 3 | 30 | 15 | 9424 / 12993 | 72.5% | 388.5 ms | 1734.8 ms |
| `tr` | B | 4 | 15 | 0 | n/a | n/a | n/a | n/a |
| `tr` | B | **All** | **105** | **33** | **19223 / 25521** | **75.3%** | **82.3 ms** | **1661.1 ms** |

## Findings and conclusions

1. **Two-slot phrasing-prefix retention in cold alternating traffic (shown in Run 1, small effect):**
   When `llama-server` starts cold (Run 1), alternating between tool-choice calls (`planner.system_text`,
   ~560 tokens) and phrasing calls (`locales/<locale>.json:system_prompt`, ~133–134 tokens) evicted
   the phrasing system prompt from Arm A's single slot (`mt-04-t3` and `mt-06-t3` in `en`: `cache_n=4`
   in Arm A vs. `133` in Arm B; `mt-03-t3` and `mt-07-t1` in `tr`: `cache_n=3` in Arm A vs. `134` in
   Arm B). Across Run 1, Arm B cached `+254` more tokens in `en` (`59.1%` vs. `56.4%`, `n=14` timed)
   and `+262` more tokens in `tr` (`35.8%` vs. `32.8%`, `n=11` timed).
2. **TTFT (`prompt_ms`) improvement from Arm B (`-np 2 -c 8192`): not shown.**
   Despite caching `+254`/`+262` more tokens in Run 1, Arm B did not lower `prompt_ms` p50 or p95:
   - Cold Run 1: `en` p50 `122.5 ms` vs. `123.8 ms`, p95 `1671.8 ms` vs. `1598.5 ms`; `tr` p50
     `1265.3 ms` vs. `1198.3 ms`, p95 `1820.0 ms` vs. `1669.7 ms`.
   - Warm Runs 2–3: Arm B was slower than Arm A on every warm run (`en` p50 `93.2–93.8 ms` vs.
     `75.2–75.3 ms`, `tr` p50 `52.7–59.3 ms` vs. `34.8–40.2 ms`), and total run wall time was higher
     in Arm B on all 6 paired runs (same locale and run number) (`21.8–24.8 s` vs. `12.7–22.4 s` in `en`; `26.6–36.9 s` vs.
     `22.2–32.5 s` in `tr`).
   - **Next hypothesis**: the two-slot allocation (`-np 2 -c 8192`) adds per-request slot/cache
     overhead on this Mac CPU/Metal build that outweighs saving ~133 phrasing system-prompt tokens.
     Check `llama-server` slot-restore / KV-cache overhead with `-np 2` and test whether a smaller
     per-slot context or keeping `-np 1` is preferable on single-rider hardware.
3. **Cross-run exact-prompt memorization dominates Runs 2 and 3 (confounder identified):**
   In Runs 2 and 3, both arms reached identical `95.9%` (`8881/9259`) cached share in `en` and
   `95.1%` (`8087/8507`) in `tr`, with repeated phrasing calls (`mt-02-t2`, `mt-04-t3`, `mt-06-t3`,
   `mt-07-t1` in `en`) dropping to `prompt_n = 1` token. Because `llama-server` (`b1b770d`) keeps
   evicted prompt checkpoints in RAM across sequential runs of the same deterministic questions and
   static demo rides, Runs 2 and 3 measure exact-prompt replay rather than within-conversation
   multi-turn prefix reuse. Additionally, running `tr` immediately after `en` left the shared
   English `planner.system_text` (560 tokens) already warm on `tr` Run 1 `mt-01-t1`.
   - **Next hypothesis**: to isolate within-conversation multi-turn caching from cross-run exact
     repetition, either restart `llama-server` (or disable RAM prompt caching via `--cache-ram 0`)
     between runs and between locales, or vary ride data/question wording per run.
4. **Turn-4 multi-turn caching: not shown.**
   All 5 turn-4 items (`n=15` across 3 runs per arm/locale) resolved deterministically via follow-up
   routing and templates (`LLM-timed n = 0` on turn 4 in all 12 runs).
   - **Next hypothesis**: add multi-turn conversations whose turns 2–4 intentionally exercise LLM
     phrasing (for example `compare_sessions` or multi-match `check_symptom` follow-ups) if turn-4
     LLM prompt-cache behavior needs to be measured.

**Outcome for T72:** keep `-np 1`; no TTFT gain from `-np 2` was shown. A round 3 needs a
`llama-server` restart (or `--cache-ram 0`) between every run and locale, plus conversations whose
later turns use LLM phrasing.

## Artifacts in this directory

- English summary Markdown files (aggregate scores and failing ids only, no raw answers):
  - Arm A: `arm-a-en-run1.md`, `arm-a-en-run2.md`, `arm-a-en-run3.md`, `arm-a-tr-run1.md`,
    `arm-a-tr-run2.md`, `arm-a-tr-run3.md`
  - Arm B: `arm-b-en-run1.md`, `arm-b-en-run2.md`, `arm-b-en-run3.md`, `arm-b-tr-run1.md`,
    `arm-b-tr-run2.md`, `arm-b-tr-run3.md`
- Raw JSON results (English runs only; raw Turkish answers were written to `/tmp` outside the
  repository per D-125):
  - Arm A: `arm-a-en-run1.json`, `arm-a-en-run2.json`, `arm-a-en-run3.json`
  - Arm B: `arm-b-en-run1.json`, `arm-b-en-run2.json`, `arm-b-en-run3.json`
