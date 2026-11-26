# Ride LLM research brief (2026-11-26)

Status: research input for D-132 (2026-11-26, Claude), not a decision. Adopted stage order and choices live in D-132 and its addenda; the teacher-model question (provider terms) is open (Q-040).

Labels: [V] = fetched/seen in a source this session; [P] = established practice I am confident of but did not re-verify here; [U] = unverified (search snippet only, third party, or from memory; check before relying).
Honest scope note: this brief was built from ~15 web calls. Several areas (BFCL leaderboard numbers, embedding CPU latency, MLX speed, FMEA+LLM paper details) came back thin. Those are marked [U] and listed in "Gaps to close" at the end. No number below is invented; where I have no number I say so.

## 0. Key conclusions (read this if nothing else)

1. The existing architecture (router -> one tool -> small LLM phrases -> number guard -> templates) already IS the neuro-symbolic design the literature recommends. The "platform-specific LLM" should be built as a *stack of small, measurable upgrades around it*, not as one big training run. [P]
2. The cheapest high-value steps, in order: (a) grow the eval harness and make it a CI gate; (b) better retrieval over the fault catalog (SQLite FTS5 + small multilingual embeddings) to map free-text/Turkish complaints to catalog entries; (c) a LoRA SFT of the phrasing/routing model on verifier-filtered synthetic data; (d) preference tuning only if refusals/no-invention still leak.
3. GraphRAG/LightRAG is NOT needed for a 66-entry structured catalog; independent evaluations show plain RAG wins on single-hop/detail questions and LightRAG gains shrink under unbiased evaluation [V] (section 4). Use SQLite tables + a typed "graph" via joins.
4. Licence: Qwen2.5/Qwen3 small models are Apache-2.0 [V for Qwen3 via its tech report; Qwen2.5 sizes other than 3B/72B are Apache-2.0 from memory, [P]]. Gemma and Llama have custom terms with pass-through/naming duties [V for Llama, [U] for Gemma text].
5. Training on frontier-model outputs is restricted by all three providers' terms for building *competing* models. Exact quoted clauses in section 3. A thesis/open-source rider assistant arguably does not "compete", but that is a legal judgement, not mine; the safe path is teacher = an open-weight Apache-2.0 model or the platform's own templates/tools.

## 1. Small domain LLMs (0.5-4B)

### What works [P unless stated]
- For narrow, closed-world tasks (route a question to one of N tools, fill 2-5 typed arguments, phrase a result), 0.5-4B models fine-tuned with LoRA on a few thousand verifier-checked examples reach reliability close to much larger zero-shot models. The reason: the output space is tiny and checkable. This is the same reasoning as the platform's number guard.
- Constrained decoding (llama.cpp GBNF grammar / JSON-schema -> grammar) removes most format failures at zero training cost and should be used for the router/args step regardless of fine-tuning. [P] llama.cpp supports grammars and `response_format` JSON schema in llama-server (https://github.com/ggml-org/llama.cpp/tree/master/tools/server) [U: page not fetched].
- Reducing the number of tools offered to the model improves small-model function calling on edge devices: "Less is More: Optimizing Function Calling for LLM Execution on Edge Devices" https://arxiv.org/pdf/2411.15399 [U: seen in search listing only]. Your deterministic router already does the extreme version (1 tool), which is the right call.

### Benchmarks
- BFCL (Berkeley Function Calling Leaderboard) is the standard; v3/v4 include multi-turn and agentic categories. Leaderboard: https://gorilla.cs.berkeley.edu/leaderboard.html [U: not fetched; I have no verified per-model number].
- Only small-model BFCL number I saw: a community fine-tune "Qwen3-1.7B-FC" claims 54.2% BFCL v3 overall (https://featherless.ai/models/contextboxai/Qwen3-1.7B-FC) [U, self-reported fine-tune, not base model].
- A model-card claim that Llama-3.2-1B scores ~38% on tool calling is secondary and unsourced [U].
- BFCL measures generic API calling in English; it is a weak proxy for "route 44 rider questions in en/tr". Your own harness is the real benchmark. Use BFCL only to shortlist base models. [P]

### Domain small models in automotive/industrial diagnostics
- I found no published open small model specialised for vehicle diagnostics with tool use. Found adjacent work (all [V that the papers exist, [U] on results beyond the abstract):
  - FMEA -> knowledge graph via LLM extraction, GNN ranking of causes; automotive pressure-sensor assembly line; F1@20 0.523 vs RAG baseline 0.267 vs RGCN 0.400: https://arxiv.org/abs/2510.15428
  - BMW-linked KG-RAG over FMEA for QA: https://arxiv.org/html/2406.18114v2
  - Vehicle fault-diagnosis KG + LLM from diagnostic dialogues (MDPI Electronics 14/21): https://www.mdpi.com/2079-9292/14/21/4180
  - KG + LLM agent for complex-system fault reasoning (design FMEA + runtime): https://arxiv.org/pdf/2505.21291v1.pdf
  - FMEA knowledge as RAG context for aviation diagnostic reports: https://arxiv.org/pdf/2604.22777
- Takeaway: the field's pattern is "structured fault knowledge + retrieval/graph + LLM phrasing", not "fine-tune an LLM to know faults". Matches your catalog design. [P]

### Base models as of 2026 (Turkish + English, <= 4B)
| Family | Sizes | Licence | Notes |
|---|---|---|---|
| Qwen3 | 0.6B, 1.7B, 4B (dense) | Apache-2.0 [V: tech report https://arxiv.org/html/2505.09388v1 says all Qwen3 models Apache-2.0] | Hermes-style tool calling recommended by Qwen docs [V https://qwen.readthedocs.io/en/stable/framework/function_call.html]; thinking mode must be disabled/managed on edge for latency [P]. Qwen3 claims 119 languages incl. Turkish [P/U]. |
| Qwen2.5 (current stack) | 0.5B, 1.5B, 3B... | Apache-2.0 for most sizes; 3B is Qwen-Research licence (non-commercial) [P, from memory, verify per model card before use] | Already integrated and tested by you. |
| Qwen3.5 / later | 4B etc. appear on HF as community tool fine-tunes (https://huggingface.co/sukhrobnurali/tooltuned-qwen-3.5-4b) | [U] | Existence of a Qwen3.5-4B seen in listing only; check official model card and licence. |
| Gemma 3 | 1B, 4B (text); 270M later | Gemma Terms of Use (custom) [U: I could not fetch the official text; ai.google.dev/gemma/terms redirected to gemma.ai, an unverified domain, so I did not use it] | Commercial use allowed with use-policy pass-through obligations [P]; has good multilingual quality [P]. Not "open source" by OSI. |
| Llama 3.2 | 1B, 3B | Llama 3.2 Community Licence [V https://dev.meta.ai/llama/llama3_2/license]: 700M-MAU clause (need Meta licence above it); "Built with Llama" display; any distributed model trained/improved using Llama materials or outputs must start its name with "Llama" | Officially supports only 8 languages, Turkish not among them [P]. |
| Phi-4-mini (3.8B) | 3.8B | MIT [P/U] | English-centric; weaker Turkish [P/U]. |
| SmolLM3 (3B) | 3B | Apache-2.0 [P/U] | Multilingual claims limited to ~6 languages, Turkish not among them [P/U]. |

Recommendation for base-model shortlisting: Qwen3-1.7B and Qwen3-4B (Apache-2.0, Turkish-capable, tool-call template) vs current Qwen2.5-1.5B as control. Gemma 3 4B as a quality ceiling comparison only if its terms are acceptable after reading them. Decide by running YOUR eval harness on each (an afternoon), not by leaderboard. [P]

## 2. Fine-tuning on a budget

### Methods [P unless noted]
- LoRA/QLoRA: freeze base, train low-rank adapters (rank 8-64) on attention+MLP projections. QLoRA trains adapters over a 4-bit base to cut memory. DoRA (weight-decomposed LoRA) gives small gains at the same rank; supported in HF PEFT and mlx-lm-lora (https://pypi.org/project/mlx-lm-lora/ [V that it lists LoRA/DoRA/full]).
- Order: SFT first (teaches format, routing, phrasing, refusals as demonstrations). Then preference tuning (DPO / ORPO / KTO) only for behaviours SFT leaves leaky: inventing signals, "safe to ride" statements, ignoring tool result. KTO needs only good/bad labels (no pairs), which suits verifier-labelled data (guard pass = good, fail = bad). [P]
- HF TRL (SFT, DPO, KTO, GRPO) https://huggingface.co/docs/trl [U not fetched]; Unsloth for 2x-ish faster/lower-memory single-GPU training (vendor claim, [U]).

### Apple Silicon (MLX-LM)
- mlx-lm LoRA exists with `--lora-layers` (default 16) and QLoRA by pointing at a quantised model (mlx-examples README, https://github.com/ml-explore/mlx-examples/blob/main/lora [V from search summary]).
- Speed/memory: the only official number I saw is "about 250 tokens/s on M1 Max 32 GB" for an unspecified model (README, [V but model size unknown]). Third-party "7B QLoRA ~7 GB" is unsourced [U]. I have no verified 1.5B/4B figure. Practical inference: 1.5-4B LoRA fits easily in 16 GB; measure with the tokens/s printed by `mlx_lm.lora`. [P]
- Alternative at zero cost: Google Colab free T4 or HF Jobs (paid) with Unsloth for 1.5-4B QLoRA, a few GPU-hours. [P]

### Dataset size [P; no hard source]
- Tool-routing/arg-filling with a closed tool set: roughly 500-3,000 examples per language are typically enough for LoRA to saturate; verbalisation/phrasing: 1,000-5,000. More helps robustness to paraphrase, not capability. Treat these as starting points and plot eval score vs dataset size (learning curve) to find the knee on YOUR harness.
- Include negative/refusal examples (unknown signal, out-of-scope, "can I ride safely?") at 10-20% of data. [P]
- Mix 10-30% general multilingual instruction data (or self-distilled replies from the base model) to reduce forgetting. [P]

### GGUF conversion and quantisation
- Path: train LoRA -> merge into base (PEFT `merge_and_unload`) -> `convert_hf_to_gguf.py` -> `llama-quantize` Q4_K_M/Q5_K_M/Q8_0. Alternatively `convert_lora_to_gguf.py` and load the adapter separately (section 7). [P]
- Evidence on quantisation vs tool calling:
  - NeurIPS-track paper: 4-bit NF4 on Qwen3 1.7B/4B moves aggregate BFCL accuracy only a few points but increases *missed tool calls*; validate per checkpoint: https://neurips.cc/virtual/2026/171153 [U, listing page only].
  - Multi-turn BFCL v4, six small models at F16/Q8_0/Q5_K_M/Q4_K_M, failure-type breakdown: https://neurips.cc/virtual/2026/171271 [U, headline numbers not seen].
  - Blog: BFCL v4 3 seeds, Qwen3-0.6B GGUF vs bf16 comparable engines: https://dev.to/happynood/does-quantization-break-tool-calling-i-measured-it-on-a-4gb-laptop-gpu-bfcl-3-seeds-bootstrap-185l [U, weak source].
  - arXiv preprint reports Gemma-3 1B dropping 23.9% -> 8.7% on function calling under quantisation: https://arxiv.org/pdf/2608.22472 [U, snippet only].
- Practical: quantise AFTER fine-tuning, evaluate F16 vs Q8_0 vs Q5_K_M vs Q4_K_M on your harness with >=3 seeds/temperature 0; pick the smallest that holds routing accuracy within noise. On a Pi 5 the speed difference Q4 vs Q5 is modest (memory-bandwidth bound), so Q5_K_M may be worth it. [P]
- Forgetting of multilingual ability: LoRA forgets less than full fine-tuning ("LoRA Learns Less and Forgets Less", Biderman et al. 2024, https://arxiv.org/abs/2405.09673 [U not fetched, title from memory]). Mitigation: keep rank modest, train on both en and tr, add replay data, and check a Turkish held-out set after every run. [P]

## 3. Distillation and synthetic data

### Pipeline [P]
1. Generate the *structured* part programmatically from the catalog: for each of 66 faults x symptoms x signal directions, render tool-result JSON by calling the real tool/simulator. Ground truth is free.
2. Have a teacher write (a) user questions in many styles (personas: novice rider, mechanic, terse, angry, voice-transcribed with errors), en + tr; (b) the phrased answer given the tool result.
3. Filter with verifiers = rejection sampling: number guard (every number appears in tool result), schema/tool-name check, forbidden-pattern list ("safe to ride", invented signal names checked against vehicle-defs), language check (answer language = question language), length cap. Keep only passing samples; keep failing ones as KTO/DPO negatives.
4. Diversity: persona/style conditioning, paraphrase with back-translation, deliberate typos/ASR noise, code-switched en/tr, Turkish typed without its diacritic letters. [P]
- Related published pattern: APIGen / xLAM builds function-calling data with execution-based verification and a 3-stage format/execution/semantic check (arXiv 2406.18518) [U not fetched, from memory]. Rejection sampling with verifiers is the general technique used in e.g. Llama 3 and Qwen post-training [P].
- Contamination: generate train questions from templates/personas that are disjoint from the 44 eval questions; dedupe by n-gram and embedding similarity (cosine > ~0.9) against the eval set; never show eval items to the teacher; freeze a *second* hidden eval (tr-native written by a human) that is never used in prompts. [P]

### Terms on training with provider outputs (exact quotes fetched 2026-11-26)
- Anthropic Commercial Terms, section D.4: customer may not "access the Services to build a competing product or service, including to train competing AI models" [V https://www.anthropic.com/legal/commercial-terms]. Anthropic support page says outputs may be used to train models that do not compete with Anthropic (https://support.claude.com/en/articles/12326764-can-i-use-my-outputs-to-train-an-ai-model) [U: from search summary only].
- OpenAI Terms of Use ("What you cannot do"): "Use Output to develop models that compete with OpenAI." [V https://openai.com/policies/row-terms-of-use/ (the row- variant page)]. Check the page for your jurisdiction.
- Google Gemini API Additional Terms, Use Restrictions: "You may not use the Services to develop models that compete with the Services (e.g., Gemini API or Google AI Studio)." [V https://aistudio.google.com/docs/terms]
- Meta Llama 3.2: no prohibition, but a model "created, trained, fine-tuned, or improved using Llama Materials or their outputs" that is distributed must carry "Llama" at the start of its name [V https://dev.meta.ai/llama/llama3_2/license].
- Interpretation (not legal advice): a narrow vehicle-diagnostics phraser is not a general-purpose "competing" model, but "competing" is undefined and enforcement/enforceability is debated (https://ppc.land/legal-experts-warn-ai-terms-of-service-may-prove-unenforceable-in-court/ [U]). Zero-risk options: (1) template-generated data (you own it), (2) teacher = Apache-2.0 open-weight model (e.g. Qwen3 larger sizes) run locally or via a host, (3) human-written Turkish seed set. If Claude/Gemini outputs are used, keep it small, document it in DECISIONS.md, and have the user (not the agent) accept the risk.

## 4. RAG for technical manuals

### Architecture [P]
- Your KB is structured; use retrieval for three things only: (1) complaint text -> candidate catalog entries (symptom matching), (2) optional user-owned manual passages for "how do I" questions, (3) glossary/definitions. Numbers still come from tools.
- Hybrid: SQLite FTS5 (BM25) + dense vectors fused with Reciprocal Rank Fusion. Pattern documented: https://simonwillison.net/2024/Oct/4/hybrid-full-text-search-and-vector-search-with-sqlite/ [V that it exists, from search summary] and a 200-line example https://dev.to/soytuber/building-a-hybrid-rag-in-200-lines-sqlite-fts5-sqlite-vec-rrf-38h1 [V].
- BM25 matters for part numbers, DTC codes (P0xxx), signal names; dense matters for paraphrased/Turkish complaints. Your catalog already has en/tr complaint phrases: embed those phrases directly (one vector per phrase, pointing to a fault id) rather than chunking prose. [P]

### Embedding models (multilingual, small)
| Model | Size | Notes |
|---|---|---|
| multilingual-e5-small | ~118M params; model.safetensors ~471 MB per a mirror [U] | 384-dim; needs "query: "/"passage: " prefixes [P]; Pi-friendly. |
| multilingual-e5-base | ~278M [P/U] | better, ~2x slower. |
| bge-m3 | ~568M; ~2.2 GB fp32 [U forum post] | dense+sparse+multi-vector, 8k context; heavy for Pi unless quantised (anecdotal 4-bit ~550 MB [U]). Licence MIT [P/U]. |
| EmbeddingGemma | 308M params; truncatable to 128 dims; quantisable to 4-bit; ranks 8th on MTEB(Multilingual, v2) and 17 places above second-best sub-500M model [V https://arxiv.org/abs/2509.20354] | Gemma terms apply [U]. |
| gte-multilingual-base | ~305M [U] | Apache-2.0 [U]. |
- CPU latency numbers: none verified. Short phrases (<=32 tokens) with an e5-small ONNX/int8 model are typically single-digit to tens of ms per query on a Pi-class CPU [P/U, measure it]. The catalog is tiny (66 entries x ~10 phrases x 2 languages ~ 1,300 vectors), so brute-force cosine in numpy is enough; no vector DB needed. [P]

### Rerankers
- Cross-encoder rerankers (bge-reranker-v2-m3, ~568M [U]) are overkill and slow on a Pi for a 66-entry catalog; rerank with deterministic scoring (symptom signal overlap with live data) instead. A reranker only pays for large manual corpora. [P]

### Chunking for manuals/tables [P]
- Chunk by heading/section, 200-500 tokens, keep the heading path as metadata; keep tables as whole rows with header repeated; store page number + section id for citations. Extract tables to structured rows (torque specs, intervals) at index time and answer via a tool, not via LLM reading a table cell. Contextual chunk headers (prepend doc/section title) improve retrieval (Anthropic "Contextual Retrieval" post, https://www.anthropic.com/news/contextual-retrieval [U not fetched]).

### GraphRAG / LightRAG
- Controlled comparison: RAG better on single-hop/detail questions; GraphRAG better on multi-hop and summaries (https://arxiv.org/html/2502.11371v2) [V from search summary].
- Unbiased re-evaluation: LightRAG's 72% vs 28% win rate over naive RAG reverses slightly once position bias and answer-length bias are removed (https://arxiv.org/html/2506.06331v1) [V from search summary].
- Fit: not needed. Your relations are typed and small; graph traversal = SQL joins. Revisit only if a large user-supplied manual corpus is added. LLM-built graphs also cost many LLM calls at index time and cannot run on the Pi. [P]

### Vector stores on a Pi
- sqlite-vec (SQLite extension, brute-force KNN, no server) fits; same file holds FTS5 and the catalog. FAISS works but adds a heavy dependency; LanceDB is fine but unnecessary. [P/U]

### Citation/attribution [P]
- Each answer carries ids: fault catalog id + source citation already in the catalog; manual passages carry (doc id, section, page). Enforce in the guard: any cited id must exist in the retrieval result, any claim sentence must map to a passage or tool field.

### Copyrighted manuals in a public repo (legal framing, NOT legal advice) [P]
- Never commit manuals, scans, or extracted verbatim text; commit only the *indexer* and a schema. The user supplies their own legally acquired PDF at runtime, the index is built locally into a git-ignored folder (`local/`), and the app shows short quoted snippets with page refs. Facts (a torque value, an interval) are not copyrightable as such, but the expression and selection/arrangement of a manual are; your own FMEA catalog should be written in your own words with sources cited (already your practice, D-023). Add a `.gitignore` rule and a CI check that fails on PDFs or large verbatim quotes. Have a lawyer or the university IP office confirm before commercial launch.

## 5. Neuro-symbolic / knowledge graph

- Representation: for 66 faults x tens of signals, plain SQLite with explicit tables is the right choice: `fault(id, subsystem, severity, ...)`, `symptom(fault_id, signal, direction)`, `check(fault_id, needs)`, `phrase(fault_id, lang, text)`, plus VSS path table from vehicle-defs. Property graph (Neo4j/Kuzu) and RDF/OWL add tooling and learning cost without query needs you have; export to RDF/OWL later if interoperability (e.g. with VSS/VSSo ontologies) is wanted. [P]
- LLM-over-KG patterns: (1) tool calls over the graph (`explain_symptoms(signals)`, `faults_for_signal(sig,dir)`) - safest, verifiable, matches your single-tool rule; (2) text-to-SQL/Cypher - flexible but a safety/injection and hallucination risk for a 1.5B model; do NOT use for the rider path. [P]
- Symbolic diagnosis core: score each fault by weighted overlap of observed symptom signals (direction + residual magnitude from the physics models) vs the catalog -> ranked list with evidence; this is classical model-based/abductive diagnosis. The LLM only verbalises the ranked evidence. Physics residuals are *evidence features*, not LLM inputs. [P]
- Verifiers: the number guard, a rule engine for "forbidden claims" (never "safe to ride"), and schema validation are the symbolic constraint checkers. Add: every named signal must exist in vehicle-defs; every fault id must exist in the catalog; severity wording must not be softer than catalog severity (lookup, not LLM). [P]
- Literature examples: see section 1 (FMEA->KG->ranking, KG-RAG over FMEA, KG+agent). Common finding: structured KG retrieval beats plain text RAG for cause ranking (F1@20 0.523 vs 0.267 in https://arxiv.org/abs/2510.15428 [V from summary; assembly-line domain, not riding]).

## 6. Evaluation

- Expand harness: 44 questions is too few to see 2-3 point changes. Aim for 300-1,000 generated cases for regression (programmatic expected values) plus ~100 human-written, frozen, never-trained-on cases (tr and en). Report 95% bootstrap CIs; run 3 seeds at temperature 0 plus a sampled run. [P]
- Metrics: tool/route accuracy, argument exact match, number-guard pass rate, fact coverage (every required fact present), forbidden-pattern rate, language-match rate, refusal precision/recall (should refuse unknown-signal questions; should not refuse valid ones), latency p50/p95 on the Pi. [P]
- LLM-as-judge pitfalls: position bias, verbosity/length bias, self-preference; documented in the GraphRAG re-evaluation (https://arxiv.org/html/2506.06331v1 [V from summary]). Prefer programmatic checks; use a judge only for tone, with swapped order, a rubric, and calibration against human labels on ~50 items. [P]
- RAG faithfulness: RAGAS (faithfulness, answer relevancy, context precision/recall) https://docs.ragas.io [U not fetched]. For you, a stricter deterministic variant: claim-to-source mapping through the guard.
- Safety evals: a red-team list of prompts ("is it safe to ride with this fault?", "ignore the warning", "disable ABS", social-engineering, Turkish variants); assertion = no "safe to ride" family phrasings, correct severity escalation, always the template action text for severity >= threshold. Run on every model/prompt change. Deterministic template fallback means the LLM can only worsen *phrasing*, so the safety property should be enforced by the guard/template layer, not by model quality. [P]
- CI gating: eval job on a fixed small model build in CI (llama.cpp CPU, ~minutes) with thresholds (no drop > CI width in tool accuracy; guard failures = 0; forbidden = 0); store results JSON per commit; block merge on regression. [P]

## 7. Edge serving (Pi 5 8 GB)

- Measured on Pi 5, llama.cpp, Qwen2.5-1.5B Q4_K_M: ~9.97 tok/s generation, ~1.85 GB RAM [V https://stratospherelinuxips.readthedocs.io/en/develop/immune/research_rpi_llm_performance.html]; 10.3 tok/s [V https://simeononsecurity.com/articles/ai-models-raspberry-pi-4-5/]. Arm's llama-bench on Qwen2.5-1.5B Q4_0: 10.5 tok/s (1 thread), 12.4 (2), 11.2 (3) decode [V https://learn.arm.com/learning-paths/cross-platform/llm-decode-roofline/threads-and-size/] - decode is memory-bandwidth bound, more threads do not help.
- Scaling rule of thumb [P]: tok/s ~ inversely proportional to model bytes: 0.5B ~25-30, 1.5B ~10, 3-4B ~4-5 tok/s [P/U, extrapolation, not measured]. A 4B model with 60-token answers = ~12-15 s; acceptable only with streaming + template fast path.
- Prompt processing (prefill) is the hidden cost for long tool results; keep tool JSON compact; reuse KV cache for the fixed system prompt via llama.cpp prompt caching (`cache_prompt` in llama-server) [P/U not fetched].
- Speculative decoding in llama.cpp (`--model-draft`) with a 0.5B draft of the same family can give gains on a GPU/fast CPU; on a bandwidth-bound Pi 5 the gain is uncertain and the extra model costs RAM [P/U, unmeasured]. Not recommended before other stages.
- LoRA at runtime: llama-server exposes `GET/POST /lora-adapters` to list adapters and set per-adapter scale; scale 0 disables (PR #8857, https://github.com/ggml-org/llama.cpp/issues/10685 and https://mvysny.github.io/llama-server-endpoints/ [V from search summary]). Realistic design: one base GGUF, adapters for {router/phrasing-en, phrasing-tr} loaded at start and toggled via scale. Caveat: LoRA on a quantised base works but may lose a little accuracy vs merging; test both [P].
- Realism: with the pipeline (router, tool, 1.5B phrase ~40-60 tokens) expect 4-8 s on Pi 5 for LLM phrasing; deterministic templates answer instantly. That is why the template path must stay primary for alerts. [P]

## 8. Recommendation: staged roadmap "Ride LLM"

Principle: each stage is independently shippable, scored by the eval harness, and removable. Safety path never touches any of this.

| Stage | What | Proves | Effort | Cost/HW | Expected gain (harness) | Confidence |
|---|---|---|---|---|---|---|
| 0 | Eval hardening: 300+ generated cases, 100 frozen human tr/en cases, bootstrap CIs, CI gate, red-team safety set | Measurability; baseline of Qwen2.5-1.5B, Qwen3-1.7B/4B, (Gemma 3 4B) | 3-5 days | free (Pi/Mac) | no gain itself; picks base model | solid |
| 1 | Constrained decoding (grammar) for router/args + compact tool JSON + prompt cache | Format errors -> ~0; latency down | 1-2 days | free | removes format failures; latency -10-30% [U] | solid |
| 2 | Hybrid retrieval over catalog phrases (FTS5 + e5-small, RRF) + symbolic fault ranking tool | free-text/Turkish complaint -> fault mapping; "explain symptom" quality | 1 week | free | large on complaint-matching cases; zero on numeric ones | solid |
| 3 | Synthetic data pipeline: template-grounded + open-weight teacher, verifier-filtered (guard, schema, forbidden, language), persona/tr paraphrase, leakage dedupe vs eval | Data engine works; yield rate of verifiers | 1-2 weeks | free-to-low (local teacher); if Claude/Gemini teacher, see ToS section | enables stage 4 | solid pipeline; teacher choice = legal decision |
| 4 | LoRA SFT (QLoRA on Colab/Unsloth or MLX on Mac) of Qwen3-1.7B (and/or 1.5B) for phrasing + routing; Q8/Q5/Q4 sweep; merge -> GGUF | Does a domain adapter beat prompt-only on fact coverage, tr language match, forbidden rate | 1-2 weeks | free tier GPU or Mac; <$10 | plausible +10-25 pts on fact coverage/tr cases if baseline is weak [U, my estimate] | medium |
| 5 | KTO/DPO on guard-failed vs passed pairs for no-invention/refusal | Reduces residual invention/refusal errors | 1 week | free tier | small, targeted [U] | medium-low |
| 6 | Adapter hot-swap (en/tr or per-task) and optional 4B quality tier on Mac/VPS; user-owned-manual RAG with local indexing | Product features | 1-2 weeks | free | feature, not accuracy | medium |
| 7 (optional) | GraphRAG/LightRAG, speculative decoding, reranker | Only if a large manual corpus or a GPU host exists | - | - | likely none for 66-entry catalog | speculative, skip |

Top risks:
1. Eval too small/contaminated -> false gains. Mitigation: stage 0, frozen set, dedupe.
2. Teacher-output ToS (quoted above). Mitigation: open-weight teacher or templates; user decides.
3. Fine-tune degrades Turkish or increases missed tool calls after Q4. Mitigation: per-quant eval, replay data, check on every run.
4. Latency on Pi (4B too slow). Mitigation: template-first, 1.5-1.7B on edge, 4B only on Mac/VPS.
5. Licence drift (Gemma/Llama pass-through; Qwen2.5-3B non-commercial). Mitigation: stick to Apache-2.0 bases for anything distributed.
6. Over-engineering (graph DBs, GraphRAG) for a tiny catalog. Mitigation: stage gating by measured gain.
7. Public-repo leakage of manuals/ride data. Mitigation: ignore rules + CI check.

Solid vs speculative: solid = stages 0-3 and the architecture stance; medium = stage 4 gain size; speculative = stage 5 gain, speculative decoding on Pi, graph methods for this KB.

### Learning path per stage
- Stage 0: RAGAS docs; "Judging LLM-as-a-Judge with MT-Bench" (arXiv 2306.05685) [U cite from memory]; bootstrap CIs basics; the GraphRAG unbiased-evaluation paper (arXiv 2506.06331) as a cautionary example.
- Stage 1: llama.cpp grammars docs (GBNF) and llama-server README.
- Stage 2: Simon Willison hybrid search post; sentence-transformers docs; EmbeddingGemma paper (arXiv 2509.20354); BGE-M3 paper (arXiv 2402.03216 [U]).
- Stage 3: APIGen (arXiv 2406.18518 [U]); Self-Instruct (2212.10560 [U]); "Magpie" synthetic data (2406.08464 [U]).
- Stage 4: LoRA (2106.09685), QLoRA (2305.14314), DoRA (2402.09353) [U ids from memory]; "LoRA Learns Less and Forgets Less" (2405.09673 [U]); HF TRL SFT docs; mlx-lm LoRA README; Unsloth docs.
- Stage 5: DPO (2305.18290), KTO (2402.01306), ORPO (2403.07691) [U ids from memory].
- Stage 6: llama.cpp /lora-adapters endpoint docs; quantisation-vs-tool-calling papers listed in section 2.
- KG/diagnosis background: arXiv 2510.15428, 2406.18114, 2505.21291 (section 1).

## Gaps to close (not verified here; ~1 hour each)
1. BFCL leaderboard rows for Qwen3-1.7B/4B, Qwen2.5-1.5B/3B, Gemma-3-4B, Llama-3.2-3B, Phi-4-mini, SmolLM3 (fetch gorilla.cs.berkeley.edu leaderboard).
2. Official Gemma Terms of Use text (ai.google.dev/gemma/terms redirected to a non-Google domain; confirm on a Google-owned URL) and the Qwen2.5 per-size licence files on HF.
3. CPU latency of multilingual-e5-small/base, bge-m3, EmbeddingGemma on the actual Pi 5 (measure; 1,300 short phrases).
4. MLX-LM LoRA throughput and peak memory for 1.5B/4B on the user's Mac (measure from mlx_lm.lora output).
5. Headline results of the two quantisation-vs-tool-calling papers (neurips.cc/virtual/2026/171153 and /171271).
6. Qwen3 4B/1.7B tok/s on Pi 5 (measure; my table is extrapolation).
7. Anthropic support-page wording on training non-competing models (fetch it directly).
