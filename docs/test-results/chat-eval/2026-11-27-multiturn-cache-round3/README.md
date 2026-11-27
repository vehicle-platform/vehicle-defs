# 2026-11-27 — Multi-turn prompt-cache measurement, round 3 (T72)

`Provenance: synthetic` (the 8 synthetic demo rides of the local demo data set, `vehicle-server`
mock/demo store; no real ride or position data).

Compares `llama-server` slot configurations **Arm A** (`-np 1 -c 4096`) vs. **Arm B**
(`-np 2 -c 8192`, keeping 4096 tokens per slot) on all fifteen multi-turn dev conversations
(`mt-01`..`mt-15`, 55 turns per run, including the five new conversations `mt-11`..`mt-15` from
`vehicle-server#117` whose turns 2–4 exercise LLM phrasing). Unlike round 2
([2026-11-27-multiturn-cache-round2](../2026-11-27-multiturn-cache-round2/README.md)),
**`llama-server` was restarted fresh before every single run and every locale** (12 cold restarts
for 12 runs: 2 arms × 2 locales × 3 runs), eliminating cross-run prompt-cache replay. Measure
only — no prompt, router, template, or server-logic changes.

## Environment and versions

- **`vehicle-server`**: branch `ext/gemini-mt-llm-turns` (`vehicle-server#117`) at commit `d4f283b`
  (adds `mt-11`..`mt-15` dev items on top of `main` `273ad67`, which includes `server#115`
  `cache_prompt=True` on the local preset)
- **`vehicle-mcp`**: `main` at `71b1af6` (local `.venv/bin/vehicle-mcp`)
- **`llama-server`**: `version: 1.0.0-dev (build 1, commit b1b770d)`, AppleClang 21.0.0.21000101,
  Darwin arm64
- **Model**: `qwen2.5-1.5b-instruct-q4_k_m.gguf`
- **Server launch** (one `vehicle-server` process across all 12 runs, isolated on local port
  `8010` with the same environment as `local/run-server.sh`, `VEHICLE_CHAT_SELF_URL` pointed at
  port `8010`, and `VEHICLE_CHAT_RATE_PER_MIN=600` so sequential turns do not sleep on 429):
  ```sh
  VEHICLE_CHAT_RATE_PER_MIN=600 \
  VEHICLE_CHAT_SELF_URL=http://127.0.0.1:8010 \
  VEHICLE_LLM_URL=http://127.0.0.1:8081/v1 \
  uv run vehicle-server serve --host 127.0.0.1 --port 8010
  ```
- **Arm A (`llama-server` stopped and restarted fresh before every run and locale)**:
  ```sh
  ./local/run-llama.sh
  # expands to: llama-server -m local/pi/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  #   --host 127.0.0.1 --port 8081 -c 4096 -np 1
  # startup log (verified on each restart): n_slots = 1, n_ctx_slot = 4096, kv_unified = 'false'
  ```
- **Arm B (`llama-server` stopped and restarted fresh before every run and locale)**:
  ```sh
  ./local/llama/build/bin/llama-server \
    -m ./local/pi/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --host 127.0.0.1 --port 8081 -c 8192 -np 2
  # startup log (verified on each restart): n_slots = 2, n_ctx_slot = 4096, kv_unified = 'false'
  ```
- **Eval command** (executed 3 times per arm and locale, with a full `llama-server` shutdown,
  port-close wait, and fresh cold start before every single run):
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
- Demo user active provider verified before the runs via `GET /assistant/active`:
  `provider_id=local`, `selected_provider_id=local`, `fallback_reason=null`.

## Results

All 12 cold-restarted runs (6 paired runs per locale/run-number) completed with `0` request
errors (`55` turns per run, `165` turns pooled over 3 cold runs per arm and locale). Every one of
the 20 new turns (`mt-11`..`mt-15`) achieved `20/20` tool accuracy in both `en` and `tr`, raising
Turn 4 LLM-timed coverage from `0` (round 2) to `5` per run (`15` pooled over 3 runs per arm and
locale). Cache shares and `prompt_ms` percentiles below are computed strictly over LLM-timed turns
(`timings != null`), with both total `n` and `LLM-timed n` reported.

### Per-run summary (every run started on a freshly restarted cold `llama-server`)

| Locale | Arm | Run | n | LLM-timed n | Cached / total prompt tokens | Cached share | `prompt_ms` p50 | `prompt_ms` p95 | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| `en` | A (`-np 1 -c 4096`) | 1 | 55 | 27 | 6856 / 19882 | 34.5% | 1181.1 ms | 1576.4 ms | 60.7 s |
| `en` | A (`-np 1 -c 4096`) | 2 | 55 | 27 | 6856 / 19882 | 34.5% | 1242.8 ms | 1627.4 ms | 59.9 s |
| `en` | A (`-np 1 -c 4096`) | 3 | 55 | 27 | 6856 / 19882 | 34.5% | 1251.7 ms | 1646.0 ms | 60.4 s |
| `en` | B (`-np 2 -c 8192`) | 1 | 55 | 27 | 7199 / 19882 | 36.2% | 1307.4 ms | 1589.2 ms | 62.5 s |
| `en` | B (`-np 2 -c 8192`) | 2 | 55 | 27 | 7199 / 19882 | 36.2% | 1289.7 ms | 1597.6 ms | 61.3 s |
| `en` | B (`-np 2 -c 8192`) | 3 | 55 | 27 | 7199 / 19882 | 36.2% | 1261.6 ms | 1554.5 ms | 61.9 s |
| `tr` | A (`-np 1 -c 4096`) | 1 | 55 | 24 | 4531 / 20110 | 22.5% | 1327.1 ms | 1723.3 ms | 81.2 s |
| `tr` | A (`-np 1 -c 4096`) | 2 | 55 | 24 | 4531 / 20110 | 22.5% | 1445.0 ms | 1774.4 ms | 84.1 s |
| `tr` | A (`-np 1 -c 4096`) | 3 | 55 | 24 | 4531 / 20110 | 22.5% | 1415.6 ms | 1799.8 ms | 78.7 s |
| `tr` | B (`-np 2 -c 8192`) | 1 | 55 | 24 | 4790 / 20110 | 23.8% | 1390.2 ms | 1690.2 ms | 77.6 s |
| `tr` | B (`-np 2 -c 8192`) | 2 | 55 | 24 | 4790 / 20110 | 23.8% | 1387.2 ms | 1706.1 ms | 75.2 s |
| `tr` | B (`-np 2 -c 8192`) | 3 | 55 | 24 | 4790 / 20110 | 23.8% | 1396.5 ms | 1675.0 ms | 76.1 s |

### Per-turn pooled across 3 independent cold runs (per arm and locale)

Because `llama-server` was restarted before every run and every locale, all 3 runs in each pool
are identically cold starts (exact same token totals and cached token counts on Runs 1, 2, and 3).

| Locale | Arm | Turn | n | LLM-timed n | Cached / total prompt tokens | Cached share | `prompt_ms` p50 | `prompt_ms` p95 |
|---|---|---|---|---|---|---|---|---|
| `en` | A | 1 | 45 | 12 | 3639 / 7251 | 50.2% | 89.0 ms | 1172.1 ms |
| `en` | A | 2 | 45 | 27 | 6660 / 19536 | 34.1% | 1242.8 ms | 1627.4 ms |
| `en` | A | 3 | 45 | 27 | 8223 / 19629 | 41.9% | 1171.2 ms | 1676.7 ms |
| `en` | A | 4 | 30 | 15 | 2046 / 13230 | 15.5% | 1455.3 ms | 1547.7 ms |
| `en` | A | **All** | **165** | **81** | **20568 / 59646** | **34.5%** | **1242.8 ms** | **1627.4 ms** |
| `en` | B | 1 | 45 | 12 | 3639 / 7251 | 50.2% | 92.5 ms | 1221.9 ms |
| `en` | B | 2 | 45 | 27 | 6915 / 19536 | 35.4% | 1289.7 ms | 1631.9 ms |
| `en` | B | 3 | 45 | 27 | 8997 / 19629 | 45.8% | 1164.0 ms | 1475.6 ms |
| `en` | B | 4 | 30 | 15 | 2046 / 13230 | 15.5% | 1508.8 ms | 1597.6 ms |
| `en` | B | **All** | **165** | **81** | **21597 / 59646** | **36.2%** | **1289.7 ms** | **1589.2 ms** |
| `tr` | A | 1 | 45 | 15 | 2499 / 10200 | 24.5% | 1189.2 ms | 1502.0 ms |
| `tr` | A | 2 | 45 | 18 | 2643 / 14814 | 17.8% | 1354.1 ms | 1735.9 ms |
| `tr` | A | 3 | 45 | 24 | 5790 / 20970 | 27.6% | 1445.0 ms | 1809.3 ms |
| `tr` | A | 4 | 30 | 15 | 2661 / 14346 | 18.5% | 1560.8 ms | 1733.3 ms |
| `tr` | A | **All** | **165** | **72** | **13593 / 60330** | **22.5%** | **1421.8 ms** | **1774.4 ms** |
| `tr` | B | 1 | 45 | 15 | 2892 / 10200 | 28.4% | 1176.1 ms | 1252.4 ms |
| `tr` | B | 2 | 45 | 18 | 2634 / 14814 | 17.8% | 1387.2 ms | 1550.2 ms |
| `tr` | B | 3 | 45 | 24 | 6183 / 20970 | 29.5% | 1397.3 ms | 1775.3 ms |
| `tr` | B | 4 | 30 | 15 | 2661 / 14346 | 18.5% | 1563.2 ms | 1706.1 ms |
| `tr` | B | **All** | **165** | **72** | **14370 / 60330** | **23.8%** | **1393.5 ms** | **1706.1 ms** |

## Findings and conclusions

1. **Cross-run cache confounder eliminated (shown):**
   Restarting `llama-server` before every run and locale produced identical token totals and cached
   token counts across Runs 1, 2, and 3 in every arm and locale (`6856/19882` and `7199/19882` in
   `en`; `4531/20110` and `4790/20110` in `tr`), confirming zero cross-run or cross-locale
   prompt-cache leakage.
2. **Small two-slot prefix retention in alternating tool-choice / phrasing traffic (shown, +1.7 pp
   `en` / +1.3 pp `tr`):**
   Arm B (`-np 2 -c 8192`) cached `+343` more tokens per run in `en` (`36.2%` vs. `34.5%`) and
   `+259` more tokens per run in `tr` (`23.8%` vs. `22.5%`). All gains came from turns where a
   phrasing call immediately followed a tool-choice call (evicting the phrasing system prompt in
   Arm A's single slot): `mt-04-t3` (`+129`), `mt-06-t3` (`+129`), and `mt-11-t2` (`+89`, offset by
   `-4` on `mt-02-t2`) in `en`; `mt-03-t3` (`+131`) and `mt-07-t1` (`+131`, offset by `-3` on
   `mt-01-t2`) in `tr`.
3. **Turn-4 caching gain from `-np 2`: not shown (`0` extra cached tokens on Turn 4).**
   With `mt-11`..`mt-15` providing 15 pooled LLM-timed Turn-4 turns per arm and locale, Arm A and
   Arm B produced identical Turn-4 cached shares (`15.5%`, `2046/13230` in `en`; `18.5%`,
   `2661/14346` in `tr`). In `mt-11`..`mt-15`, deterministic routing avoids tool-choice LLM calls
   so consecutive phrasing calls already retain the phrasing system prompt (~133–139 tokens in
   `en`, ~174–180 tokens in `tr`) in Arm A's single slot, while the remaining ~550–800 tokens per
   turn (conversation state, recent turns, and flattened tool result) sit inside the single `user`
   message and change on every turn.
4. **Consistent TTFT (`prompt_ms`) or wall-time improvement from Arm B (`-np 2 -c 8192`): not
   shown (locale-split, small magnitudes).**
   - In `en`, Arm A was faster than Arm B on `prompt_ms` p50 in all 3 paired runs (`1181.1–1251.7 ms`
     vs. `1261.6–1307.4 ms`; pooled p50 `1242.8 ms` vs. `1289.7 ms`) and on wall time in all 3
     paired runs (`59.9–60.7 s` vs. `61.3–62.5 s`); Arm B was slightly lower only on pooled p95
     (`1589.2 ms` vs. `1627.4 ms`, driven by Turn 3 `1475.6 ms` vs. `1676.7 ms`).
   - In `tr`, Arm B was slightly faster on pooled `prompt_ms` p50 (`1393.5 ms` vs. `1421.8 ms`),
     pooled p95 (`1706.1 ms` vs. `1774.4 ms`), and wall time (`75.2–77.6 s` vs. `78.7–84.1 s`),
     though Run 1 p50 favored Arm A (`1327.1 ms` vs. `1390.2 ms`).
   - **Next hypothesis:** Doubling the KV-cache allocation (`-np 2 -c 8192`) does not yield a
     consistent TTFT gain because only ~1.3–1.7% of prompt tokens benefit from a second slot while
     81–85% of Turn-4 prompt tokens remain uncached inside the changing `user` message. Keeping
     `-np 1` and testing whether formatting multi-turn history as append-only `user`/`assistant`
     messages (or placing stable ride context ahead of changing turn text) increases Turn 2–4
     cached share is the next hypothesis to evaluate.

## Artifacts in this directory

- English summary Markdown files (aggregate scores and failing ids only, no raw answers):
  - Arm A: `arm-a-en-run1.md`, `arm-a-en-run2.md`, `arm-a-en-run3.md`, `arm-a-tr-run1.md`,
    `arm-a-tr-run2.md`, `arm-a-tr-run3.md`
  - Arm B: `arm-b-en-run1.md`, `arm-b-en-run2.md`, `arm-b-en-run3.md`, `arm-b-tr-run1.md`,
    `arm-b-tr-run2.md`, `arm-b-tr-run3.md`
- Raw JSON results (English runs only; Turkish raw JSONs were kept in a temporary directory
  outside the repository and deleted after aggregation per D-125):
  - Arm A: `arm-a-en-run1.json`, `arm-a-en-run2.json`, `arm-a-en-run3.json`
  - Arm B: `arm-b-en-run1.json`, `arm-b-en-run2.json`, `arm-b-en-run3.json`
