# 2026-11-28 — Multi-turn prompt-cache measurement, round 4 (T72)

`Provenance: synthetic` (the 8 synthetic demo rides of the local demo data set, `vehicle-server`
mock/demo store; no real ride or position data).

Tests the round 3 ([2026-11-27-multiturn-cache-round3](../2026-11-27-multiturn-cache-round3/README.md))
hypothesis by comparing **Arm A** (`VEHICLE_CHAT_HISTORY_MESSAGES=0`, default single `user` message
layout) vs. **Arm C** (`VEHICLE_CHAT_HISTORY_MESSAGES=1`, append-only `user`/`assistant` message
pairs for recent turns with changing state, question, and tool result in the final `user` message,
added in `vehicle-server#124`), both running on identical `llama-server` single-slot settings
(`-np 1 -c 4096` via `local/run-llama.sh`) and identical `budget.LOCAL` defaults (`turn_count = 2`,
`turns = 200`).

Following the round 3 protocol identically, **`llama-server` was stopped, port-close-waited, and
cold-restarted before every single run and every locale** (12 cold restarts for 12 runs: 2 arms ×
2 locales × 3 runs) on all fifteen multi-turn dev conversations (`mt-01`..`mt-15`, 55 turns per
run). Nothing under `local/` was modified. The default switch decision (`VEHICLE_CHAT_HISTORY_MESSAGES`
default off vs. on) is Claude's.

## Environment and versions

- **`vehicle-server`**: branch `ext/gemini-chat-history-messages` (`vehicle-server#124`) at commit
  `bf006d2` (rebased on `main` `976e501`, which includes `vehicle-server#117` `mt-11`..`mt-15` and
  `server#115` `cache_prompt=True`)
- **`vehicle-mcp`**: `main` at `a3520a6` (local `.venv/bin/vehicle-mcp`)
- **`llama-server`**: `version: 1.0.0-dev (build 1, commit b1b770d)`, AppleClang 21.0.0.21000101,
  Darwin arm64
- **Model**: `qwen2.5-1.5b-instruct-q4_k_m.gguf` (D-137)
- **Server launch** (isolated on local port `8010` with the same environment as `local/run-server.sh`,
  restarted once between Arm A and Arm C to flip `VEHICLE_CHAT_HISTORY_MESSAGES`):
  ```sh
  VEHICLE_CHAT_HISTORY_MESSAGES=<0|1> \
  VEHICLE_CHAT_RATE_PER_MIN=600 \
  VEHICLE_CHAT_SELF_URL=http://127.0.0.1:8010 \
  VEHICLE_LLM_URL=http://127.0.0.1:8081/v1 \
  uv run vehicle-server serve --host 127.0.0.1 --port 8010
  ```
- **`llama-server` launch (both Arm A and Arm C; stopped and cold-restarted before every run and
  locale)**:
  ```sh
  ./local/run-llama.sh
  # expands to: llama-server -m local/pi/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  #   --host 127.0.0.1 --port 8081 -c 4096 -np 1
  ```
- **Eval command** (executed 3 times per arm and locale, with a cold `llama-server` restart before
  every run):
  ```sh
  uv run vehicle-server chat-eval \
    --base-url http://127.0.0.1:8010 \
    --token-file <demo-user-token-file> \
    --locale <en|tr> \
    --only mt-01,mt-02,mt-03,mt-04,mt-05,mt-06,mt-07,mt-08,mt-09,mt-10,mt-11,mt-12,mt-13,mt-14,mt-15 \
    --timeout 60 \
    --out <out.json> \
    --summary-md <summary.md>
  ```
- Demo user active provider verified before each arm via `GET /assistant/active`:
  `provider_id=local`, `selected_provider_id=local`, `fallback_reason=null`.

## Results

All 12 cold-restarted runs completed with `0` HTTP/request errors (`55` turns per run, `165` turns
pooled over 3 cold runs per arm and locale). Cache shares and `prompt_ms` percentiles are computed
strictly over LLM-timed turns (`timings != null`), with both total `n` and `LLM-timed n` reported.
Source of every English figure below: committed `arm-{a,c}-en-run{1,2,3}.json` and `.md` files in
this directory; source of Turkish figures: committed `arm-{a,c}-tr-run{1,2,3}.md` summaries and
(marked below) local aggregation of Turkish runs, not committed (Turkish raw JSONs kept in a temporary directory outside the
repository and deleted after aggregation per D-125).

### Quality and answer-source comparison per arm (identical across all 3 runs per arm and locale)

| Locale | Arm | Tool accuracy (name + args) | Tool name accuracy | Forbidden hits | Answers with forbidden | Accepted LLM answers | Template fallbacks | Unsupported / error |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `en` | A (`HISTORY_MESSAGES=0`) | 69.1% (38/55) | 70.9% (39/55) | 0 | 0 | 6 | 39 | 10 / 0 |
| `en` | C (`HISTORY_MESSAGES=1`) | 69.1% (38/55) | 70.9% (39/55) | 0 | 0 | 12 | 33 | 10 / 0 |
| `tr` | A (`HISTORY_MESSAGES=0`) | 83.6% (46/55) | 83.6% (46/55) | 0 | 0 | 11 | 40 | 3 / 1 |
| `tr` | C (`HISTORY_MESSAGES=1`) | 83.6% (46/55) | 83.6% (46/55) | 0 | 0 | 13 | 38 | 3 / 1 |

Totals reconcile per run: `en` `6 + 39 + 10 + 0 = 55` (Arm A) and `12 + 33 + 10 + 0 = 55` (Arm C);
`tr` `11 + 40 + 3 + 1 = 55` (Arm A) and `13 + 38 + 3 + 1 = 55` (Arm C). All 20 turns of
`mt-11`..`mt-15` scored `20/20` tool accuracy in both arms and both locales.

### Per-run summary (every run started on a freshly restarted cold `llama-server`)

| Locale | Arm | Run | n | LLM-timed n | Tool acc | Forbidden | Cached / total prompt tokens | Cached share | `prompt_ms` p50 | `prompt_ms` p95 | Wall time |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| `en` | A (`HISTORY_MESSAGES=0`) | 1 | 55 | 27 | 69.1% | 0 | 6856 / 19882 | 34.5% | 1169.1 ms | 1564.2 ms | 59.2 s |
| `en` | A (`HISTORY_MESSAGES=0`) | 2 | 55 | 27 | 69.1% | 0 | 6856 / 19882 | 34.5% | 1160.7 ms | 1552.8 ms | 55.3 s |
| `en` | A (`HISTORY_MESSAGES=0`) | 3 | 55 | 27 | 69.1% | 0 | 6856 / 19882 | 34.5% | 1160.1 ms | 1567.2 ms | 55.7 s |
| `en` | C (`HISTORY_MESSAGES=1`) | 1 | 55 | 27 | 69.1% | 0 | 6438 / 19917 | 32.3% | 1296.5 ms | 1618.7 ms | 61.4 s |
| `en` | C (`HISTORY_MESSAGES=1`) | 2 | 55 | 27 | 69.1% | 0 | 6438 / 19917 | 32.3% | 1318.8 ms | 1703.0 ms | 58.7 s |
| `en` | C (`HISTORY_MESSAGES=1`) | 3 | 55 | 27 | 69.1% | 0 | 6438 / 19917 | 32.3% | 1321.4 ms | 1721.7 ms | 58.5 s |
| `tr` | A (`HISTORY_MESSAGES=0`) | 1 | 55 | 24 | 83.6% | 0 | 4531 / 20110 | 22.5% | 1343.2 ms | 1629.2 ms | 73.2 s |
| `tr` | A (`HISTORY_MESSAGES=0`) | 2 | 55 | 24 | 83.6% | 0 | 4531 / 20110 | 22.5% | 1357.5 ms | 1688.0 ms | 73.7 s |
| `tr` | A (`HISTORY_MESSAGES=0`) | 3 | 55 | 24 | 83.6% | 0 | 4531 / 20110 | 22.5% | 1374.2 ms | 1693.7 ms | 74.2 s |
| `tr` | C (`HISTORY_MESSAGES=1`) | 1 | 55 | 24 | 83.6% | 0 | 4092 / 20330 | 20.1% | 1462.0 ms | 1758.7 ms | 82.4 s |
| `tr` | C (`HISTORY_MESSAGES=1`) | 2 | 55 | 24 | 83.6% | 0 | 4092 / 20330 | 20.1% | 1459.5 ms | 1810.1 ms | 82.9 s |
| `tr` | C (`HISTORY_MESSAGES=1`) | 3 | 55 | 24 | 83.6% | 0 | 4092 / 20330 | 20.1% | 1441.5 ms | 1803.5 ms | 82.4 s |

### Per-turn pooled across 3 cold runs (per arm and locale)

The three runs replay the same deterministic conversations and produced identical token counts on
Runs 1, 2, and 3, so they are repeats of one configuration rather than independent samples: token
figures have `n = 1` per arm and locale with no variance estimate; only the latency timings vary
between runs.

Sources: the `en` rows come from the committed `arm-{a,c}-en-run*.json`. The `tr` token counts are
3 × the per-turn rows of the committed `arm-{a,c}-tr-run*.md`; the pooled `tr` `prompt_ms` p50/p95
(per turn and **All**) are **from a local log, not committed** (the Turkish raw JSONs were deleted),
and so are the `tr` per-item token deltas in finding 3 and the `tr` item ids in finding 4.

| Locale | Arm | Turn | n | LLM-timed n | Cached / total prompt tokens | Cached share | `prompt_ms` p50 | `prompt_ms` p95 |
|---|---|---|---:|---:|---|---:|---:|---:|
| `en` | A | 1 | 45 | 12 | 3639 / 7251 | 50.2% | 592.9 ms | 1108.4 ms |
| `en` | A | 2 | 45 | 27 | 6660 / 19536 | 34.1% | 1167.0 ms | 1510.7 ms |
| `en` | A | 3 | 45 | 27 | 8223 / 19629 | 41.9% | 1051.0 ms | 1566.7 ms |
| `en` | A | 4 | 30 | 15 | 2046 / 13230 | 15.5% | 1398.8 ms | 1414.9 ms |
| `en` | A | **All** | **165** | **81** | **20568 / 59646** | **34.5%** | **1167.0 ms** | **1557.8 ms** |
| `en` | C | 1 | 45 | 12 | 3639 / 7251 | 50.2% | 594.8 ms | 1170.3 ms |
| `en` | C | 2 | 45 | 27 | 6180 / 19641 | 31.5% | 1363.2 ms | 1620.4 ms |
| `en` | C | 3 | 45 | 27 | 8100 / 19722 | 41.1% | 1200.7 ms | 1718.7 ms |
| `en` | C | 4 | 30 | 15 | 1395 / 13137 | 10.6% | 1525.7 ms | 1586.1 ms |
| `en` | C | **All** | **165** | **81** | **19314 / 59751** | **32.3%** | **1319.9 ms** | **1659.7 ms** |
| `tr` | A | 1 | 45 | 15 | 2499 / 10200 | 24.5% | 1131.5 ms | 1357.6 ms |
| `tr` | A | 2 | 45 | 18 | 2643 / 14814 | 17.8% | 1335.1 ms | 1447.0 ms |
| `tr` | A | 3 | 45 | 24 | 5790 / 20970 | 27.6% | 1377.3 ms | 1699.9 ms |
| `tr` | A | 4 | 30 | 15 | 2661 / 14346 | 18.5% | 1506.4 ms | 1630.0 ms |
| `tr` | A | **All** | **165** | **72** | **13593 / 60330** | **22.5%** | **1362.6 ms** | **1666.0 ms** |
| `tr` | C | 1 | 45 | 15 | 2499 / 10200 | 24.5% | 1184.2 ms | 1406.5 ms |
| `tr` | C | 2 | 45 | 18 | 2019 / 14925 | 13.5% | 1464.9 ms | 1542.3 ms |
| `tr` | C | 3 | 45 | 24 | 5748 / 21267 | 27.0% | 1460.7 ms | 1815.9 ms |
| `tr` | C | 4 | 30 | 15 | 2010 / 14598 | 13.8% | 1726.2 ms | 1762.5 ms |
| `tr` | C | **All** | **165** | **72** | **12276 / 60990** | **20.1%** | **1463.1 ms** | **1798.3 ms** |

## Findings and conclusions

1. **Exact Arm A reproducibility vs. round 3 (shown):**
   Arm A (`VEHICLE_CHAT_HISTORY_MESSAGES=0`) reproduced round 3 Arm A's exact token counts on every
   single run and turn (`6856 / 19882` = `34.5%` in `en`, `4531 / 20110` = `22.5%` in `tr`),
   confirming zero prompt drift when the setting is off.
2. **Round 3 hypothesis (higher prompt-cache share and lower TTFT from append-only history messages
   under `budget.LOCAL`): NOT shown — measured regression.**
   Arm C (`VEHICLE_CHAT_HISTORY_MESSAGES=1`) reduced overall cached share by `-2.2 pp` in `en`
   (`32.3%` vs. `34.5%`, `-418` cached tokens/run) and `-2.4 pp` in `tr` (`20.1%` vs. `22.5%`,
   `-439` cached tokens/run), and increased pooled `prompt_ms` p50 (`1319.9 ms` vs. `1167.0 ms` in
   `en`; `1463.1 ms` vs. `1362.6 ms` in `tr`) and wall time (`58.5–61.4 s` vs. `55.3–59.2 s` in
   `en`; `82.4–82.9 s` vs. `73.2–74.2 s` in `tr`).
3. **Measured root causes of the Arm C cache drop (per-item token deltas, `n = 1` per locale):**
   - **Turn 4 rolling-window eviction (`budget.LOCAL.turn_count = 2`):** On Turn 4 of `mt-11`..`mt-15`,
     `budget.LOCAL` keeps only the last 2 exchanges (`turns[-2:]`), evicting `(U1, A1)` and shifting
     `(U2, A2)` right after the system prompt. That invalidates the entire history KV prefix down
     to the bare system prompt (`93` tokens in `en`, `134` tokens in `tr`), losing `-40` to `-46`
     cached tokens on every Turn 4 (`mt-11-t4`, `mt-12-t4`, `mt-13-t4`, `mt-14-t4`, `mt-15-t4`)
     compared to Arm A (`133–139` tokens in `en`, `174–180` in `tr`).
   - **Loss of Arm A's accidental cross-conversation `Conversation state` prefix on Turn 2:** In
     Arm A, the single `user` message starts with `Conversation state: ride <latest-date> (<id>)...`,
     which happened to match across consecutive conversations on the same latest demo ride
     (`mt-12-t2`, `mt-13-t2`, `mt-14-t2`, `mt-15-t2`: `133` vs. `93` in `en`, `174` vs. `134` in
     `tr`; `-40` tokens each). In Arm C, each new conversation's Turn-1 question follows the system
     prompt immediately, so cross-conversation prefix sharing stops at the system prompt.
   - **Within-conversation Turn 3 cache hit was genuine but short:** On Turn 3 (`mt-11-t3`,
     `mt-12-t3`, `mt-15-t3`), Arm C **did** reuse Turn 1's `(U1, A1)` messages (`93 -> 125`, `+32`
     tokens in `en`; `134 -> 171..180`, `+37..+46` tokens in `tr`), but because Turn 1 was a short
     template-answered query, `U1 + A1` was slightly shorter than Arm A's `Conversation state`
     prefix (`-13` to `-14` tokens in `en`, `-8` to `0` tokens in `tr`).
4. **No quality loss — accepted LLM phrasing answers increased in Arm C (measured):**
   - Tool accuracy was **identical** in both arms (`69.1%` / `38/55` in `en`, `83.6%` / `46/55` in
     `tr`), and forbidden-pattern hits were **`0`** in all 12 runs.
   - Accepted LLM phrasing answers (drafts passing `answers.output_ok` and `numbers_grounded`)
     increased from **`6/55` to `12/55`** in `en` (`+6`: `mt-02-t2`, `mt-04-t3`, `mt-11-t2`,
     `mt-13-t2`, `mt-14-t2`, `mt-15-t3`, `mt-15-t4` gained LLM answers; `mt-06-t3` fell back to
     template) and from **`11/55` to `13/55`** in `tr` (`+2`: `mt-03-t3`, `mt-11-t3`, `mt-12-t4`,
     `mt-15-t2`, `mt-15-t3` gained LLM answers; `mt-10-t3`, `mt-11-t2`, `mt-12-t2` fell back to
     template).
   - **Hypothesis:** Separating previous turns into explicit `user`/`assistant` chat roles reduced
     number confusion in Qwen2.5-1.5B compared to flattening `Recent turns:` into the same `user`
     block as the current tool result.
5. **Proposed next steps (default switch is Claude's decision):**
   - **Proposed:** Keep `VEHICLE_CHAT_HISTORY_MESSAGES=0` as the default if TTFT / prompt-cache
     efficiency under `turn_count = 2` is the priority, because Arm C regressed cached share
     (`-2.2 pp` `en` / `-2.4 pp` `tr`) and `prompt_ms` p50 (`+152.9 ms` `en` / `+100.5 ms` `tr`).
   - **Proposed follow-up hypothesis (not tested here):** Testing Arm C with `VEHICLE_CHAT_BUDGET_LOCAL`
     set to `turn_count=4,turns=400` would avoid Turn-4 rolling eviction of `(U1, A1)` and test
     whether preserving Turn 1–3 history reverses the Turn-4 cache regression while retaining the
     `+6` EN / `+2` TR LLM-phrasing acceptance gain.

## Artifacts in this directory

- English and Turkish summary Markdown files (aggregate scores and failing ids only, no raw
  answers):
  - Arm A: `arm-a-en-run1.md`, `arm-a-en-run2.md`, `arm-a-en-run3.md`, `arm-a-tr-run1.md`,
    `arm-a-tr-run2.md`, `arm-a-tr-run3.md`
  - Arm C: `arm-c-en-run1.md`, `arm-c-en-run2.md`, `arm-c-en-run3.md`, `arm-c-tr-run1.md`,
    `arm-c-tr-run2.md`, `arm-c-tr-run3.md`
- Raw JSON results (English runs only, with every `answer` field removed prior to commit per the
  public results rule; Turkish raw JSONs were kept in a temporary directory outside the repository
  and deleted after aggregation per D-125):
  - Arm A: `arm-a-en-run1.json`, `arm-a-en-run2.json`, `arm-a-en-run3.json`
  - Arm C: `arm-c-en-run1.json`, `arm-c-en-run2.json`, `arm-c-en-run3.json`
