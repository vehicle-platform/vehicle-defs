# RAG Turkish → English Retrieval Tune Pass (G8-3b, T60 follow-up)

- **Date:** 2026-11-28
- **Provenance:** synthetic (authored fault-catalog and `docs/ideas/*.md` queries from `vehicle-mcp/tests/retrieval_eval/`, no real ride data or personal data, D-033)
- **Baseline reference:** `vehicle-mcp/tests/retrieval_eval/README.md` ("Measured results (`test` split, current retrieval, measure only)", 2026-11-27: EN R@1 0.583 / R@5 0.917 / MRR 0.734; TR R@1 0.194 / R@5 0.417 / MRR 0.279 on n = 36 per locale)
- **Code & model:** `vehicle-mcp` commit `ac65438` (branch `ext/gemini-rag-tr-tune`, PR vehicle-mcp#43, exposing `RetrievalSettings` without changing defaults), embedding model `intfloat/multilingual-e5-small@614241f622f5` (ONNX Runtime CPU; `model.onnx` SHA-256 `ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665`, `tokenizer.json` SHA-256 `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39`), corpus = fault catalog served by `vehicle-server` (defs v0.33.0, 319 catalog chunks with `--exclude-holdout`) + `vehicle-defs/docs/ideas/` (325 Markdown chunks; 644 chunks total).
- **Committed source files:** [dev-grid.json](dev-grid.json), [test-once.json](test-once.json), [unconfirmed-rank1-tr-tune.json](unconfirmed-rank1-tr-tune.json). Every figure below comes from these committed files (n = 1 deterministic evaluation per setting).

## What the embedder sends today

In `vehicle-mcp/src/vehicle_mcp/knowledge/embedder.py` (lines 31–32 and 147–151), `OnnxE5Embedder` **already prepends** `QUERY_PREFIX = "query: "` in `embed_queries()` and `PASSAGE_PREFIX = "passage: "` in `embed_passages()` by default. The ablation below compares prefixes **on** (two indexes built with `--rebuild --exclude-holdout`: default vs. `--no-prefixes`) alongside RRF `k`, arm weights, `lexical_top_n`, and `min_similarity`.

## 1. Dev (`tune`) split grid (n = 76 answerable + 10 weak per locale)

All parameter comparisons were run strictly on the `tune` split (`dev-grid.json`).

| Setting | Prefixes | `rrf_k` | `fts_w` | `vec_w` | `lex_top_n` | `min_sim` | EN R@1 | EN R@5 | EN MRR | EN weak | TR R@1 | TR R@5 | TR MRR | TR weak |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pref_on_hybrid_k60_default` (baseline) | on | 60 | 1.0 | 1.0 | 2 | 0.83 | 0.855 | 0.987 | 0.907 | 1.80 | 0.395 | 0.671 | 0.499 | 1.30 |
| `pref_on_hybrid_k30` | on | 30 | 1.0 | 1.0 | 2 | 0.83 | 0.855 | 0.987 | 0.907 | 1.80 | 0.395 | 0.671 | 0.499 | 1.30 |
| `pref_on_hybrid_k10` | on | 10 | 1.0 | 1.0 | 2 | 0.83 | 0.855 | 0.987 | 0.907 | 1.80 | 0.395 | 0.671 | 0.499 | 1.30 |
| `pref_on_vector_only` | on | 60 | 0.0 | 1.0 | 0 | 0.83 | 0.803 | 0.947 | 0.859 | 0.50 | 0.368 | 0.487 | 0.416 | 0.90 |
| `pref_on_fts_only_top2` | on | 60 | 1.0 | 0.0 | 2 | 0.83 | 0.763 | 0.895 | 0.829 | 1.30 | 0.447 | 0.579 | 0.513 | 0.40 |
| `pref_on_fts_only_top5` | on | 60 | 1.0 | 0.0 | 5 | 0.83 | 0.763 | 0.974 | 0.854 | 2.60 | 0.447 | 0.711 | 0.550 | 1.00 |
| `pref_on_hybrid_k60_vec2x` | on | 60 | 0.5 | 1.0 | 2 | 0.83 | 0.829 | 0.974 | 0.888 | 1.80 | 0.382 | 0.645 | 0.483 | 1.30 |
| `pref_on_hybrid_k10_vec2x` | on | 10 | 0.5 | 1.0 | 2 | 0.83 | 0.829 | 0.974 | 0.888 | 1.80 | 0.382 | 0.645 | 0.483 | 1.30 |
| `pref_on_vector_only_sim80` | on | 60 | 0.0 | 1.0 | 0 | 0.80 | 0.803 | 0.947 | 0.859 | 1.80 | 0.382 | 0.513 | 0.434 | 1.60 |
| `pref_on_hybrid_k60_sim80` | on | 60 | 1.0 | 1.0 | 2 | 0.80 | 0.842 | 0.987 | 0.900 | 3.00 | 0.421 | 0.684 | 0.522 | 2.00 |
| `pref_on_hybrid_k60_lex5` | on | 60 | 1.0 | 1.0 | 5 | 0.83 | 0.868 | 1.000 | 0.920 | 3.10 | 0.382 | 0.711 | 0.501 | 1.90 |
| `pref_on_hybrid_k30_lex5` | on | 30 | 1.0 | 1.0 | 5 | 0.83 | 0.868 | 1.000 | 0.920 | 3.10 | 0.382 | 0.711 | 0.501 | 1.90 |
| `pref_on_hybrid_k10_lex5` | on | 10 | 1.0 | 1.0 | 5 | 0.83 | 0.868 | 1.000 | 0.920 | 3.10 | 0.382 | 0.711 | 0.501 | 1.90 |
| `pref_on_hybrid_k60_fts2x_lex5` | on | 60 | 2.0 | 1.0 | 5 | 0.83 | 0.803 | 0.987 | 0.877 | 3.10 | 0.434 | 0.724 | 0.547 | 1.90 |
| `pref_on_hybrid_k10_fts2x_lex5` | on | 10 | 2.0 | 1.0 | 5 | 0.83 | 0.803 | 0.987 | 0.877 | 3.10 | 0.434 | 0.724 | 0.547 | 1.90 |
| **`pref_on_hybrid_k60_fts2x_lex2`** (dev pick) | **on** | **60** | **2.0** | **1.0** | **2** | **0.83** | **0.816** | **0.987** | **0.885** | **1.80** | **0.474** | **0.671** | **0.555** | **1.30** |
| `pref_off_hybrid_k60` | off | 60 | 1.0 | 1.0 | 2 | 0.83 | 0.829 | 1.000 | 0.896 | 1.80 | 0.408 | 0.711 | 0.516 | 2.60 |
| `pref_off_hybrid_k30` | off | 30 | 1.0 | 1.0 | 2 | 0.83 | 0.829 | 1.000 | 0.896 | 1.80 | 0.408 | 0.711 | 0.516 | 2.60 |
| `pref_off_hybrid_k10` | off | 10 | 1.0 | 1.0 | 2 | 0.83 | 0.829 | 1.000 | 0.896 | 1.80 | 0.408 | 0.711 | 0.516 | 2.60 |
| `pref_off_vector_only` | off | 60 | 0.0 | 1.0 | 0 | 0.83 | 0.737 | 0.947 | 0.820 | 0.50 | 0.382 | 0.526 | 0.438 | 2.20 |
| `pref_off_fts_only_top5` | off | 60 | 1.0 | 0.0 | 5 | 0.83 | 0.763 | 0.974 | 0.854 | 2.60 | 0.447 | 0.711 | 0.550 | 1.00 |

### Observations on `tune`

1. **RRF `k` ∈ {10, 30, 60} produces identical rankings** across every prefix and `lexical_top_n` setting (`0.000` delta on EN and TR): with `lexical_top_n` capped at 2 (or 5), hits appearing in both arms always beat single-arm hits regardless of `k ∈ {10, 30, 60}`.
2. **Disabling e5 prefixes hurts English R@1 (`0.855 -> 0.829`; vector-only `0.803 -> 0.737`) and doubles Turkish weak-query noise (`1.30 -> 2.60`; vector-only `0.90 -> 2.20`)**, while Turkish R@5 and MRR rise slightly (`0.671 -> 0.711`, `0.499 -> 0.516`). Hypothesis, not measured here: unprefixed e5 embeddings sit closer together, so more chunks pass the `0.83` cosine floor.
3. **Vector-only underperforms hybrid on both locales** (TR R@5 `0.487` vs. `0.671`, EN R@5 `0.947` vs. `0.987`), while FTS-only (`lex_top_n=5`) improves TR MRR (`0.550` vs. `0.499`) at the cost of EN R@1 (`0.763` vs. `0.855`) and EN weak noise (`2.60` vs. `1.80`).
4. **Dev selection:** `pref_on_hybrid_k60_fts2x_lex2` (`use_prefixes=True, rrf_k=60, fts_weight=2.0, vector_weight=1.0, lexical_top_n=2`) achieved the highest Turkish MRR (`0.555`, +0.056 over baseline) and Turkish R@1 (`0.474`, +0.079) among all settings that kept weak-query noise at the baseline level (`1.80` EN / `1.30` TR), trading -0.039 EN R@1 (`0.855 -> 0.816`) with EN R@5 unchanged (`0.987`).

## 2. Single `test` split evaluation (n = 36 answerable + 4 weak per locale)

The selected dev setting was evaluated **once** on the frozen `test` split alongside the baseline default (`test-once.json`). Note: baseline EN R@1 is `0.639` vs. `0.583` on 2026-11-27 most likely because `vehicle-defs/docs/ideas/` grew by 4 Markdown files in runs 6–7 (325 doc chunks vs. the earlier index; the earlier chunk count was not recorded, so this is not verified); baseline TR metrics match `tests/retrieval_eval/README.md` identically (`0.194 / 0.417 / 0.279`).

| Setting | EN R@1 | EN R@5 | EN MRR | EN weak | TR R@1 | TR R@5 | TR MRR | TR weak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_default` (`fts_w=1.0, vec_w=1.0, rrf_k=60`) | 0.639 | 0.917 | 0.769 | 2.25 | 0.194 | 0.417 | 0.279 | 2.00 |
| `best_dev_fts2x_lex2` (`fts_w=2.0, vec_w=1.0, rrf_k=60`) | 0.694 | 0.917 | 0.792 | 2.25 | 0.194 | 0.417 | 0.283 | 2.00 |

On the frozen `test` split (n = 36 per locale), `fts_weight=2.0` produced **no improvement in Turkish R@1 (`0.194`) or R@5 (`0.417`)** and only `+0.004` in Turkish MRR (`0.279 -> 0.283`, within n = 36 noise). Parameter tuning alone does not resolve the Turkish → English retrieval gap.

## 3. Why `faults/unconfirmed` chunks rank first on Turkish queries (`tune` diagnostic)

Under the baseline default on the Turkish `tune` split (`unconfirmed-rank1-tr-tune.json`), **`faults/unconfirmed#data only` (`ref="unconfirmed"`) ranked #1 on 27 of 76 queries (35.5%)**. Every single winning chunk had `chunk_locale = "tr"` (Turkish unconfirmed complaint phrases indexed by `sources.py:_unconfirmed()`). Breakdown by expected target stratum and retrieval arm:

| Target stratum | Rank-1 `faults/unconfirmed` count | Both FTS + vector | Vector-only (`bm25_rank = null`) | FTS-only (`vector_rank = null`) |
|---|---:|---:|---:|---:|
| Catalog faults | 12 | 12 | 0 | 0 |
| English-only `docs/ideas/*.md` | 15 | 5 | 10 | 0 |
| **Total (of 76 TR `tune` queries)** | **27** | **17** | **10** | **0** |

Two mechanisms explain why `faults/unconfirmed` dominates Turkish rank 1:

1. **Single-group pooling (`ref="unconfirmed"`) in `store.py`:** `sources.py:139` assigns every unconfirmed catalog entry's complaint chunks (across all subsystems) the single group key `ref = "unconfirmed"`. During RRF fusion (`store.py:380-390`), `ref="unconfirmed"` inherits the **best BM25 rank** AND the **best vector rank** across the entire pool of unconfirmed Turkish phrases, even when the winning BM25 chunk and winning vector chunk belong to different unconfirmed faults. For all 12 affected Turkish catalog queries (e.g., `tr-05`, `tr-07`, `tr-18`, `tr-23`, `tr-31`), `ref="unconfirmed"` entered both arms and beat the intended displayable fault entry (which only pools its own 2–4 phrases).
2. **Same-language cosine bias on Turkish → English doc queries (`10/15` vector-only):** `docs/ideas/*.md` chunks are English-only, so Turkish queries rarely match them via FTS. In `multilingual-e5-small`, short Turkish unconfirmed complaint chunks (`chunk_id`s `74` (3×), `222` (3×), `204` (2×), `45` (2×), plus `50`, `144`, `114`, `10`, `215`, `6`, etc. in `unconfirmed-rank1-tr-tune.json`) score cosine similarity `0.836–0.895` against unrelated Turkish engineering doc queries — higher than the cross-lingual English Markdown passages — placing `faults/unconfirmed` at `vector_rank = 1` with `bm25_rank = null`.

## 4. Proposed recommendations (default change is Claude's decision)

- **Proposed — keep existing defaults (`use_prefixes=True`, `rrf_k=60`, `fts_weight=1.0`, `vector_weight=1.0`, `lexical_top_n=2`):**
  - `use_prefixes=True` is supported by the `tune` data (turning prefixes off degrades EN R@1 and doubles TR weak-query noise).
  - `rrf_k ∈ {10, 30, 60}` shows zero effect on `tune`; keep `60`.
  - Raising `fts_weight` to `2.0` improved TR `tune` MRR (+0.056) but did not transfer to the frozen `test` split (TR R@1 `0.194`, R@5 `0.417`, MRR `+0.004`), so changing the default is **not** justified by these measurements.
- **Proposed follow-up investigations (beyond parameter tuning, for Claude):**
  1. Separate or demote `ref="unconfirmed"` (`kind="data_only"`) chunks so the pooled unconfirmed bucket cannot combine BM25 + vector ranks across unrelated unconfirmed entries or outrank displayable faults and docs (35.5% of TR `tune` rank-1 hits).
  2. Address Turkish → English doc retrieval structurally (e.g., separate doc/catalog pools or bilingual headings/summaries) rather than via RRF weights alone.
