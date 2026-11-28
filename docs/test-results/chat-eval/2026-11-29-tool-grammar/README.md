# 2026-11-29 — T59 Tool-Choice GBNF Grammar Measurement (`off` vs. `on`)

`Provenance: synthetic` (8 synthetic demo rides in the local demo data set; no real ride or GPS
position data, D-033).

Measures the effect of the closed per-tool JSON-schema grammar compiled by `llama-server`
(`planner.build_grammar_schema`, merged in `vehicle-server#125`, switch and telemetry added in
`vehicle-server#129` / G9-1a) compared against the name-only schema (`planner.build_schema`), across
both locales (`en`, `tr`) and both evaluation splits (**dev**, 160 items/locale, and frozen
**held-out**, 100 items/locale; held-out is scored only, never tuned on).

**Observation only:** this report states the measured effect with numbers; choosing the default
setting of `VEHICLE_LLM_TOOL_GRAMMAR` is Claude's decision.

---

## Setup and Commands

| Item | Value |
|---|---|
| Host | Apple M1 MacBook Air (`arm64`, 8 GB RAM, macOS) |
| Model | `qwen2.5-1.5b-instruct-q4_k_m.gguf` (`Q4_K_M`, Apache-2.0, D-137) |
| `llama-server` | `version: 1.0.0-dev (build 1, commit b1b770d)`, flags `-c 4096 -np 1` (`./local/run-llama.sh`) |
| `vehicle-server` | `ext/gemini-tool-grammar-setting` (`vehicle-server#129`, commit `fef2cfd`, based on `main` `6b91c9e`) |
| `vehicle-mcp` | `main` at `7c1eb32` |
| Held-out split | `vehicle-ml/src/vehicle_ml/ride_llm/eval/heldout/` (`spec.json` SHA-256 `26721f1930e85067c5543e12edd19e3b21775f1c1c278d6b67e18acc7c0ad891`, 100 items/locale) |
| Arms | **`off`** (`VEHICLE_LLM_TOOL_GRAMMAR=off`, sends `build_schema`) vs. **`on`** (`VEHICLE_LLM_TOOL_GRAMMAR=on`, sends `build_grammar_schema`) |
| Repeats | **3 cold runs** per arm and locale (12 runs total: 2 arms × 2 locales × 3 runs); `llama-server` was stopped and cold-restarted before every single run and between arms, and `vehicle-server` was restarted between arms. |

Exact server and eval commands:

```sh
# Per arm (off / on):
VEHICLE_CHAT_ENABLED=1 VEHICLE_CHAT_RATE_PER_MIN=600 \
VEHICLE_CHAT_SELF_URL=http://127.0.0.1:8010 \
VEHICLE_LLM_URL=http://127.0.0.1:8081/v1 \
VEHICLE_LLM_TOOL_GRAMMAR=<off|on> \
uv run vehicle-server serve --host 127.0.0.1 --port 8010

# Fresh cold llama-server before each run:
./local/run-llama.sh

# Eval command (dev + held-out together, 3 runs per arm and locale):
uv run vehicle-server chat-eval \
  --base-url http://127.0.0.1:8010 \
  --token-file <demo-user-token-file> \
  --locale <en|tr> \
  --spec ../vehicle-ml/src/vehicle_ml/ride_llm/eval/heldout/spec.json \
  --locales-dir ../vehicle-ml/src/vehicle_ml/ride_llm/eval/heldout/locales \
  --include-dev \
  --timeout 60 \
  --out <local-tmp.json> \
  --summary-md <local-tmp.md>
```

Compact aggregate JSON (no raw `answer` fields, no held-out item text): [`summary.json`](summary.json).
Raw per-run JSONs and Turkish logs were kept in `/tmp` outside git and deleted after aggregation (D-125).

---

## Pooled Results Across 3 Cold Runs (Per Suite, Arm, and Locale)

Because `temperature=0` is deterministic, all 3 runs in each `(arm, locale, suite)` cell produced
identical tool choices, accuracy, argument-validity counts, forbidden hits, and token totals: these
are **n = 1 configuration, repeated k = 3 times** (no variance estimate on accuracy/tokens; only
latencies vary across the 3 repeats). All 12 runs exited 0 with **0** request errors.

### Dev Split (160 items / run; 3 cold runs pooled)

| Arm | Locale | Tool acc | LLM tool-choice calls / run | Arg validity (`args_unchanged`) | Invalid / fallback | Forbidden hits | Tool-choice latency p50 / p95 (`k=3` pooled) | Tool-choice tokens / run (prompt + cached / completion) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `off` | `en` | 86.9% (139/160) | 17 | **23.5%** (4/17) | 0 / 0 (0.0%) | 0 | 684.8 / 2404.5 ms (`n=51`) | 1224 + 9054 / **442** |
| `on` | `en` | 86.9% (139/160) | 17 | **100.0%** (17/17) | 0 / 0 (0.0%) | 0 | 541.9 / 2659.4 ms (`n=51`) | 1224 + 9054 / **250** |
| `off` | `tr` | 88.1% (141/160) | 15 | **13.3%** (2/15) | 0 / 0 (0.0%) | 0 | 701.6 / 2132.6 ms (`n=45`) | 1174 + 7843 / **445** |
| `on` | `tr` | 88.1% (141/160) | 15 | **93.3%** (14/15) | 0 / 0 (0.0%) | 0 | 649.5 / 2771.1 ms (`n=45`) | 1174 + 7843 / **241** |

### Frozen Held-Out Split (100 items / run; 3 cold runs pooled; scored only)

| Arm | Locale | Tool acc | LLM tool-choice calls / run | Arg validity (`args_unchanged`) | Invalid / fallback | Forbidden hits | Tool-choice latency p50 / p95 (`k=3` pooled) | Tool-choice tokens / run (prompt + cached / completion) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `off` | `en` | 61.0% (61/100) | 13 | **7.7%** (1/13) | 0 / 0 (0.0%) | 0 | 626.1 / 1336.1 ms (`n=39`) | 217 + 7282 / **309** |
| `on` | `en` | 61.0% (61/100) | 13 | **100.0%** (13/13) | 0 / 0 (0.0%) | 0 | 387.8 / 519.2 ms (`n=39`) | 217 + 7282 / **147** |
| `off` | `tr` | 58.0% (58/100) | 7 | **28.6%** (2/7) | 0 / 0 (0.0%) | 0 | 669.6 / 1728.6 ms (`n=21`) | 184 + 3921 / **186** |
| `on` | `tr` | 58.0% (58/100) | 7 | **100.0%** (7/7) | 0 / 0 (0.0%) | 0 | 547.3 / 736.7 ms (`n=21`) | 184 + 3921 / **80** |

### Per-Run Latency Summary (All 12 Runs, Source: `summary.json`)

| Arm | Locale | Run | Dev tool-choice p50 / p95 (ms) | Held-out tool-choice p50 / p95 (ms) | Dev full-turn p50 / p95 (ms) | Held-out full-turn p50 / p95 (ms) |
|---|---|---:|---:|---:|---:|---:|
| `off` | `en` | 1 | 702.6 / 2404.5 | 665.5 / 1519.6 | 53.0 / 3828.0 | 29.0 / 3218.0 |
| `off` | `en` | 2 | 721.7 / 2447.1 | 650.0 / 858.7 | 21.0 / 3764.0 | 26.0 / 3214.0 |
| `off` | `en` | 3 | 646.7 / 2491.5 | 596.9 / 767.4 | 22.0 / 3587.0 | 22.0 / 3095.0 |
| `off` | `tr` | 1 | 673.3 / 2287.9 | 608.0 / 1532.5 | 25.0 / 4568.0 | 33.0 / 4261.0 |
| `off` | `tr` | 2 | 699.6 / 2132.6 | 692.6 / 1728.6 | 37.0 / 4463.0 | 29.0 / 5180.0 |
| `off` | `tr` | 3 | 983.6 / 2334.4 | 986.9 / 2116.9 | 22.0 / 5419.0 | 29.0 / 5513.0 |
| `on` | `en` | 1 | 429.5 / 2332.1 | 381.0 / 480.6 | 35.0 / 4669.0 | 16.0 / 3896.0 |
| `on` | `en` | 2 | 560.9 / 3729.6 | 414.0 / 567.7 | 20.0 / 5193.0 | 29.0 / 4468.0 |
| `on` | `en` | 3 | 650.8 / 3655.1 | 399.1 / 480.8 | 12.0 / 5865.0 | 30.0 / 4070.0 |
| `on` | `tr` | 1 | 627.6 / 2830.5 | 562.8 / 736.7 | 16.0 / 6277.0 | 24.0 / 6360.0 |
| `on` | `tr` | 2 | 649.5 / 2714.7 | 545.1 / 576.3 | 20.0 / 6479.0 | 21.0 / 6277.0 |
| `on` | `tr` | 3 | 664.9 / 2771.1 | 538.6 / 802.4 | 33.0 / 7216.0 | 72.0 / 6950.0 |

---

## Reading: Does the Grammar Help, Hurt, or Do Nothing?

The measured effect of `VEHICLE_LLM_TOOL_GRAMMAR=on` vs. `off` on `qwen2.5-1.5b-instruct-q4_k_m` is
**mixed — strongly positive on argument cleanliness, completion tokens, and warm tool-choice latency,
neutral on tool accuracy and invalid/fallback rate, with a small cold-start p95 overhead on the
first call after `llama-server` startup**:

1. **Helps — Argument validity rises from 17.3% (9/52) to 98.1% (51/52) across all suites/locales.**
   With `off`, the 1.5B model frequently emits invented or null-valued argument keys that
   `sanitize_arguments` has to strip silently (`dev en`: 4/17 -> 17/17; `dev tr`: 2/15 -> 14/15;
   `heldout en`: 1/13 -> 13/13; `heldout tr`: 2/7 -> 7/7). The single remaining `args_unchanged=False`
   case with `on` (`dev tr` `scope-2`) was a malformed optional `session_id` string rejected by
   `SESSION_ID_RE` (which a length-bounded JSON schema does not regex-constrain).
2. **Helps — Tool-choice completion tokens drop by 43%–57% with identical prompt tokens.**
   Because the closed grammar forbids extra keys and restricts `tool=null` to `arguments={}`,
   completion tokens per run fall from `442 -> 250` (`dev en`, -43.4%), `445 -> 241` (`dev tr`,
   -45.8%), `309 -> 147` (`heldout en`, -52.4%), and `186 -> 80` (`heldout tr`, -57.0%). Prompt and
   cache tokens are byte-identical (`1224+9054`, `1174+7843`, `217+7282`, `184+3921`).
3. **Helps on warm tool-choice latency; slight cold-start p95 overhead on dev.**
   - Median (`p50`) tool-choice latency improved in all four cells: `dev en` `684.8 -> 541.9 ms`
     (-20.9%), `dev tr` `701.6 -> 649.5 ms` (-7.4%), `heldout en` `626.1 -> 387.8 ms` (-38.1%),
     `heldout tr` `669.6 -> 547.3 ms` (-18.3%).
   - On `heldout` (which ran after `dev` on the same warmed slot), tool-choice `p95` dropped by
     `61.1%` in `en` (`1336.1 -> 519.2 ms`) and `57.4%` in `tr` (`1728.6 -> 736.7 ms`).
   - On `dev` (which ran immediately after cold `llama-server` startup), tool-choice `p95` increased
     from `2404.5 -> 2659.4 ms` (`en`, +10.6%) and `2132.6 -> 2771.1 ms` (`tr`, +29.9%), reflecting
     the first-call cost of compiling/applying the closed per-tool GBNF grammar (note also that
     full-turn `p95`, dominated by phrasing turns rather than tool choice, drifted higher during
     later runs as the fanless M1 Air warmed up over the ~55-minute run sequence).
4. **Neutral on tool accuracy, invalid-choice / fallback rate, and forbidden hits.**
   Tool accuracy was identical between `off` and `on` in every cell (`dev`: 86.9% `en`, 88.1% `tr`;
   `heldout`: 61.0% `en`, 58.0% `tr`). Invalid choices (`0/52`), keyword fallbacks (`0/52`), and
   forbidden hits (`0`) were zero in both arms because `off` already uses `build_schema` (validating
   tool names as JSON) and `sanitize_arguments` silently strips bad keys instead of rejecting them.
   The default setting of `VEHICLE_LLM_TOOL_GRAMMAR` remains Claude's decision.
