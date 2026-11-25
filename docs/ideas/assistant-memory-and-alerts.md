# Research brief: assistant memory, efficiency, no-dead-end answers, in-ride alerts

Status: research input, not a decision; adopted parts are D-128 and D-129, which win where they differ (for example D-129 adds no APNs relay now).

Date: 2026-11-25. Method: ~15 web searches/fetches in one pass. Labels: [V] = verified in a fetched/search source with URL; [P] = pattern from general practice, only weakly sourced; [U] = could not verify, treat as a hypothesis to test. Where a search returned only blogs, I say so.

## A. Conversation memory

### A1. Designs in production and in frameworks
| Design | How it works | Cost for a small model | Source |
|---|---|---|---|
| Rolling window (buffer) | Last N turns verbatim, drop older | Zero extra LLM calls, forgets beyond budget | https://dev.to/tomerbendavid/memory-types-in-langchain-4l0n [V, tutorial] |
| Summary buffer | Recent turns verbatim, older turns condensed by an LLM | One extra LLM call per refresh; tune verbatim size vs refresh rate | https://atypicalesper.github.io/dev-atlas/ai/05-agentic-ai/03-memory-systems [V, blog] |
| Entity / structured memory | Extract entities, keep a record per entity, inject when mentioned again (LangChain `ConversationEntityMemory`) | Extraction call per turn unless done deterministically | https://dev.to/tomerbendavid/memory-types-in-langchain-4l0n [V, tutorial] |
| Long-term memory layer (Mem0, MemGPT/Letta) | Extract facts, store, retrieve per query; MemGPT treats context as OS-style tiers with a fixed primary context | Extra LLM + embedding calls; designed for cloud-size models | https://arxiv.org/html/2504.19413v1 [V] |
| Retrieval over past chats | Search tool over stored conversations | Needs embeddings or FTS | see Claude below |

Consensus from the sources: production chat agents combine a short verbatim buffer with a summary or retrieval layer (same dev-atlas / Mem0 pages) [V, blogs].

### A2. What the big apps do and what controls they give
- ChatGPT memory: remembers when asked or when it picks things up itself; since June 2025 also references recent conversations (lighter for free users). Controls: turn memory off, "forget" in chat, view/delete/clear in Settings > Personalization > Manage Memory, ask what it remembers. Temporary Chat: not in history, no memory read/write, not used for training. Deleting a chat does NOT delete its memories; memories must be deleted separately. https://openai.com/index/memory-and-new-controls-for-chatgpt/ [V]
- Claude: memory saved as individual topics while chatting (not post-hoc summaries); per-project memory; chat search is a visible tool call (retrieval, paid plans). Controls: pause memory, reset (permanent delete), per-chat memory off before first message, incognito chats (not saved to history or memory), edit/delete individual topics. Sensitive topics (health, politics, religion) not saved by default; government ID and financial account numbers never saved. Deleting a conversation does not remove memories derived from it. https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context [V]
- Gemini "saved info"/personal context: NOT researched in this pass [U].
- Design lessons usable here: (1) memory entries are separate objects from transcripts, so deletion UX needs both "delete chat" and "delete what was learned" (or cascade, which is simpler and arguably more privacy-friendly than both vendors); (2) a per-chat "don't remember" switch; (3) sensitive categories excluded by default.

### A3. Privacy / GDPR-ish deletion
- No binding EDPB guidance specific to LLM chat history found. The EDPB 2025 coordinated enforcement report on erasure says erasure is not absolute and flags retention periods and backup deletion as hard points. https://www.edpb.europa.eu/system/files/2026-02/edpb_cef-report_2025_right-to-erasure_en.pdf [V, general]
- Academic view: chat history is within data-subject rights scope. https://arxiv.org/pdf/2307.03941 [V via search summary, not opened]
- Practical stance for this project: data stays on the rider's own Pi/phone, so GDPR-style obligations are mostly self-directed; still provide view/export/delete all, per-chat delete cascading to derived memory, and a "temporary chat" mode. Position/GPS in chat text conflicts with platform invariant 7 (never committed; only to user servers + MCP) so chat store must be git-ignored and never synced to third-party cloud unless user opts in [P].
- Cloud-key mode: user-supplied cloud LLMs receive history; the UI must say so per message/mode [P].

### A4. What fits a 4k-context 1.5B model on a Pi
Principles [P unless cited]:
1. Do not feed raw history to the model for tool choice. Carry structured state instead: `{last_ride_id, last_signal, last_metric, last_time_range, last_tool, last_result_digest}` (a few dozen tokens) plus the last 1-2 turns as one-line summaries.
2. Resolve follow-ups ("and the one before that?") in code first: deterministic rules over the carried state (ordinal ride shifts, "same for", pronoun -> last_signal). Only if rules fail, one cheap LLM "rewrite to standalone question" call. Literature supports rewriting as a standard pre-retrieval step and that it is cheap enough per turn with a small model: https://algomaster.io/learn/ai-engineering/conversational-rag-exercise [V, guide]; CHIQ (open models for clarify-then-rewrite): https://web3.arxiv.org/pdf/2406.05013 [V via search]; ZeQR splits coreference vs omission: https://arxiv.org/pdf/2307.09384 [V via search]. Small-model quality numbers: not read, [U].
3. Use the rewrite only for routing; the answer-phrasing call sees only the standalone question + tool result (keeps the number guard trivial: allowed numbers = tool result only).
4. Summary buffer is probably unnecessary at this scale: persistent transcript in SQLite for UI/history, but model context uses structured state. Summarise only for cloud models.
5. Long-term "user memory" (preferred units, nickname, bike name, "ignore tyre pressure alerts") = a small key-value table edited in settings, injected as <=100 tokens. No LLM-extracted memories on the 1.5B model (error-prone) [P].

## B. Efficiency

### B1. llama.cpp server
- `cache_prompt` request field defaults to true; an identical repeat request processed 1 token instead of 43; a request with a shared prefix reused 33 tokens and processed 12. https://github.com/ggml-org/llama.cpp/discussions/13606 [V]
- Slots: `-np N` splits `-c` evenly (`-c 1024 -np 2` = 2 x 512), so with 4k context and `-np 2` each slot gets 2k. Slot selection uses prompt similarity `-sps` (default 0.5); `id_slot` forces a slot. Same source [V]. Implication: use `-np 1` or pin `id_slot` per task so a 4k budget is not halved [P].
- Slot save/restore: `--slot-save-path`; save of 72 tokens = 7.67 MB in 1.4 ms, restore 0.74 ms (same source) [V]. The size is large per token for that model (maintainer warns `--slots` is unsafe for wide exposure), so keep the endpoint bound to localhost. Restoring a prebuilt system-prompt+tool-schema KV state is a possible optimisation but the saved size scales with the model; measure on the Pi [U].
- `--cache-reuse N` (KV shifting for reused chunks, default 0/disabled) is mentioned only in a generated Q&A dataset and a guide; confirm against the official `tools/server` README before relying on it [U]. https://huggingface.co/datasets/ping98k/llama-cpp-server-doc-qa/viewer/default/train?p=16
- Hybrid/recurrent-memory models can force full prompt reprocessing (no partial cache). https://github.com/ggml-org/llama.cpp/issues/17107 [V via search summary]. Matters if Gemma-class or other non-pure-transformer models are chosen; verify per model.
- Stable prefix: keep system prompt + tool schemas first and byte-identical, put volatile state (carried context, user question) last; otherwise prefix cache breaks at the first differing token [P, follows from the prefix-match behaviour above].
- Prefill is the Pi bottleneck at 4k; so every token saved before the question counts. Prefill/decode tokens-per-second for 1.5B on Pi 5: not measured here, use project's own ~6 s figure and profile [U].

### B2. Cloud caching (as per vendor docs fetched today)
- Anthropic: caching minimums by model (docs list 512 tokens for the newest tier including Sonnet 5.5 and Haiku 5.5, 1,024 for Sonnet 5/4.x, 2,048 for Opus 4.7, 4,096 for Opus 4.5/4.6 and Haiku 4.5); 5-minute write 1.25x, 1-hour write 2x, read 0.1x of base input (0.05x for Opus 5.5/Sonnet 5.5, 0.025x for Fable/Mythos 5.1/5.2). TTL 5 min default, each hit refreshes. Check `usage.cache_read_input_tokens`. https://platform.claude.com/docs/en/build-with-claude/prompt-caching [V; the page was only read to the first 100k chars]. For this project a system prompt + tool schemas of roughly 1-2k tokens is cacheable on recent Sonnet/Haiku tiers; on older Haiku 4.5 it is below the 4,096 minimum and would silently not cache [V].
- Gemini: implicit caching on by default for 2.5 and newer; minimums 2,048 (2.5 Flash/Pro) and 4,096 for newer listed models; explicit caching only via generateContent on supported 2.5/3 models. Discount rate and storage pricing not on the page I read [U]. https://aistudio.google.com/docs/caching [V]. A ~1-2k token prompt falls below Gemini's minimums, so assume no caching [V by arithmetic].
- Takeaway: for short prompts, caching is a minor lever on cloud; the larger saving is deterministic routing so that many questions need no LLM call at all.

### B3. Other efficiency levers
- Deterministic routing before the LLM: regex/keyword/embedding-free intent table for the top N questions ("last ride distance", "max lean") -> tool directly; LLM only on miss [P].
- Per-ride tool-result cache: rides are immutable once closed, so cache key = (tool, args, ride_id, defs/tool version); invalidate on schema/tool version bump only [P]. Also cache the phrased answer text keyed the same way (zero-LLM repeat answers) [P].
- Streaming: stream tokens to the UI; but the number guard needs the full text, so either stream a template-rendered answer (numbers inserted by code) or guard incrementally per sentence [P].
- Constrained decoding: GBNF/JSON-schema grammar in llama.cpp forces valid JSON; one blog reports on Llama 3.2 3B ~80-85% valid JSON prompt-only vs 100% with grammar at ~5-8% decode overhead (single anecdotal source). https://dev.to/software_mvp-factory/structured-output-and-tool-calling-with-on-device-llms-on-android-3e9j [V, anecdotal]. Grammar guarantees syntax, not that the chosen tool/argument is correct; make tool name an enum so only real tools are possible. Known limits: some JSON-Schema features (anyOf/oneOf) unsupported, `x?{N}` repetition can be very slow. https://raw.githubusercontent.com/ggml-org/llama.cpp/HEAD/grammars/README.md [V].
- Tool-choice accuracy of Qwen2.5-1.5B / Gemma 3 1B-4B on a BFCL-style benchmark: not found [U]. Recommendation: build a 100-200 question eval of the project's own tool set and measure routing accuracy per model before choosing; a router that outputs one enum from <=12 tools is far easier than free-form function calling [P].

## C. "Never a dead end" patterns
Evidence gathered is thin; most of this is design practice [P].
- Mercedes MBUX: ChatGPT integration (Azure OpenAI) was added to handle requests beyond the pre-programmed command set, beta June 2023, later rolled out to ~3M vehicles; sources do not say what happens when it also cannot answer. https://group.mercedes-benz.com/innovation/digitalisation/connectivity/car-voice-control-with-chatgpt.html , https://www.neowin.net/amp/mercedesbenz-is-rolling-out-chatgpt-powered-mbux-voice-assistant-to-three-million-vehicles/ [V]. Pattern = tiered: scripted domain commands first, general LLM as fallback.
- BMW Intelligent Personal Assistant, Garmin, Whoop, Strava AI coaches: not researched in this pass [U].
Recommended patterns for this system [P]:
1. Tiered answer ladder: exact tool -> nearest tool with relaxed args (e.g. asked "tyre wear", not available -> offer ride distance/lean-angle stats that relate) -> data card (raw table/chart of the closest signals for the asked ride) -> clarifying question with 2-3 chips -> only then an honest "I don't have that signal" that names what IS available.
2. Retrieval-style fallback without LLM math: map the question to signals/catalog entries by keyword/embedding over the signal catalogue (from vehicle-defs, not hand-typed) and return a card. This satisfies "hand over relevant data" and keeps the number guard intact because the numbers come from a tool.
3. Follow-up chips generated by code from the tool that just ran (e.g. after "max lean": "Compare with previous ride", "Show on map", "Lean angle distribution") so users see the vocabulary the system understands.
4. Honest uncertainty: say what was assumed ("I used your last ride from Tuesday").
5. Log every fallback (locally) to drive which tools to add next.

## D. Real-time in-ride alerts

### D1. HMI / distraction guidance
- NHTSA visual-manual guidelines (Phase 1, 2013, voluntary): average single glance away from road <= 2 s, total <= 12 s per task; Phase 2 proposed extending to portable/aftermarket devices (finalisation status not verified). https://www.govinfo.gov/link/fr/78/24861 , https://www.transportation.gov/briefing-room/us-dot-releases-guidelines-minimize-vehicle-distractions [V]. Written for cars; these numbers are a ceiling reference, not a motorcycle standard.
- ISO/TS 16951:2021: two methods to rank priority of on-board messages (criticality x urgency -> priority index/matrix); covers TICS and non-TICS messages incl. telephone, warnings, telltales; excludes legally mandatory messages; gives no guidance on how to present ranked messages. https://www.iso.org/standard/81103.html [V, abstract]. Paid standard; I did not read the body.
- ISO 15005 (dialogue management principles) and ISO 15008 (visual presentation): the search found nothing; contents here are from memory [U]. Do not cite the clauses without reading them.
- Motorcycle-specific: Connected Motorcycle Consortium (BMW, Honda, Yamaha, KTM, Suzuki, Triumph) has an HMI task group developing application-independent HMI specs starting from automotive guidelines, plus simulator studies (RRT I/II) on rider reaction to visual collision warnings. No published HMI spec text found. https://www.rideapart.com/news/482772/six-oem-consortium-improve-connectivity-safety/ , ACEM position that HMI must minimise rider distraction: https://acem.eu/wp-content/uploads/2015/01/Intelligent-transport-systems.pdf [V via search summaries]. An Australian connected-motorcycle pilot concluded a rider-suited HMI is likely different from car HMI: https://imoveaustralia.com/project/motorcyclist-safety-connected-motorcycle-pilot [V via summary]. ISO 26022 does not appear in results; I could not confirm what it covers [U].
- Implication: no motorcycle-specific numeric limit found, so adopt the NHTSA 2 s/12 s as conservative upper bound and prefer audio-only/glanceable alerts while moving [P].

### D2. Priority, interruption, fatigue [P unless cited]
Suggested classes:
| Class | Example | While moving | Channel |
|---|---|---|---|
| P0 safety-critical | handled by safety-node (LED ring, mirror LEDs), NOT this assistant | n/a | hardware only (invariant 3) |
| P1 urgent, actionable | overheating, battery/voltage fault, oil pressure/DTC from read-only UDS | speak now (short earcon + 1 sentence), one repeat max | intercom audio + glanceable banner |
| P2 advisory | tyre pressure low trend, chain-lube due, data quality | queue; deliver when speed ~0 for >N s or at ride end | in-app card, notification after stop |
| P3 info | ride summary, outlook | after ride | notification/digest |
Alert-fatigue controls (generic monitoring practice): hysteresis margins, debounce windows requiring sustained breach before firing and clearing, rate-of-change over static thresholds, digests for low severity, review noisiest alerts. Sources: https://docs.datadoghq.com/fr/monitors/guide/reduce-alert-flapping/ , https://www.capitalone.com/tech/software-engineering/what-is-alert-fatigue-3-steps-to-tackle-it/ , https://pulsegeek.com/articles/set-thresholds-and-avoid-alert-fatigue-in-monitoring/ [V, web-ops sources not automotive]. Add per-alert cooldown, max N spoken alerts per ride, user mute per alert type, and "why this alert" detail on tap.
The anomaly detector lives in linux-node/rt-core; the assistant only phrases alerts using a template with numbers from the event record (same number-guard principle).
Examples from BMW Motorrad Connected, Harley app, Ducati Link, Tesla: NOT researched [U].

### D3. Transport without a paid push provider
| Option | Works when | Limits |
|---|---|---|
| BLE notify from bike gateway to phone | phone near bike, app connected | iOS needs background BLE mode and a running app; range tiny; ESP32 connectivity-node could host GATT [P] |
| WebSocket / SSE from local edge server (Pi) | phone on same network/hotspot, app foregrounded | app suspended in background on iOS and heavily limited on Android [P] |
| MQTT (e.g. Mosquitto on Pi) | same as above | needs persistent connection, same background limits [P] |
| ntfy / UnifiedPush self-hosted | Android: works without Google (UnifiedPush; ntfy Android uses Firebase only for ntfy.sh, never for self-hosted, never in F-Droid flavour) | iOS: UnifiedPush not supported; instant delivery on iOS requires the self-hosted server to forward poll requests to ntfy.sh (upstream-base-url), which then signals via APNs (no message content over APNs). https://docs.ntfy.sh/subscribe/phone , https://noted.lol/ntfy/ , https://github.com/binwiederhier/ntfy/issues/1124 [V, community + docs] |
| FCM / APNs directly | unavoidable for reliable iOS background delivery | free to use but need Apple developer account ($99/yr, not verified here [U]) and a relay server; payload can be a content-free wake-up |
Android periodic background work: WorkManager minimum 15 min (matches current design), not a real-time path. https://developer.android.com/reference/androidx/work/PeriodicWorkRequest [V]. For real-time in-ride on Android, a foreground service with persistent connection is the usual route (docs not fetched [U]).
Key point: in-ride, the phone is usually in a pocket/mount with the app open or a foreground service, and voice goes to the intercom, so the primary channel can be the app's own live connection (SSE/WebSocket to the Pi, or BLE) and the OS push path is only needed for "ride ended / app closed" cases [P].

## E. Recommendation (layered design)

### E1. Storage
- SQLite on the edge server: `conversations(id, started, mode{normal,temporary}, source)`, `messages(id, conv_id, role, text, tool_name, tool_args_json, tool_result_ref, ts)`, `session_state(conv_id, last_ride_id, last_signal, last_metric, last_range)`, `user_prefs(key, value)` (units, nickname, muted alert types), `tool_cache(key, result_json, tool_version)`, `alerts(id, ride_id, class, ts, payload, delivered_via, acked)`.
- Temporary chat = no rows written. "Delete chat" cascades to its state; "Delete all" wipes everything; export as JSON.
- Chat DB is user data: git-ignored, excluded from any server sync by default.

### E2. Memory tiers and token budgets
| Tier | Content | Local 4k model | Cloud model |
|---|---|---|---|
| 0 Static prefix | system prompt + tool enum/schema | ~600-900 | ~1-2k (cacheable) |
| 1 Carried state | last ride/signal/metric/range, 1-line last-turn digest | ~80-150 | ~150 |
| 2 Recent turns | last 1-2 exchanges, each trimmed to one line | ~100-200 | last 6-10 turns verbatim, ~1-2k |
| 3 User prefs | KV facts | ~50-100 | ~100-300 |
| 4 Retrieval over old chats | none by default; explicit "what did I ask about X" via FTS5 | off | optional tool |
| Question + tool result | | ~200-500 | ~500 |
| Output reserve | | ~150-250 | ~300 |
Local total stays well under 4k; numbers are design targets, not measurements [U].

### E3. Routing order
1. Alert/ack commands and slash-style shortcuts.
2. Deterministic follow-up resolution against carried state.
3. Rule/keyword intent table -> tool (no LLM).
4. Small LLM with grammar-constrained enum tool choice (+ optional rewrite call if step 2 flagged an unresolved reference).
5. No tool matched: catalogue lookup -> data card + clarifying question + chips (never a bare refusal).
6. Tool result -> cache -> template or LLM phrasing -> number guard -> reply + code-generated chips.
Cloud mode: same pipeline, only steps 4 and 6 swap models; history can be longer.

### E4. Alerts
Classes P1-P3 as in D2 (P0 stays in safety-node). Channels: P1 = live connection (BLE or SSE/WebSocket) -> intercom audio earcon + one sentence, app banner; fallback ntfy/UnifiedPush on Android, FCM/APNs relay only if iOS background is a hard requirement. P2 = queued until stationary. P3 = existing post-ride notifications. Debounce 3-10 s sustained breach (tune), hysteresis band on clear, per-type cooldown, per-ride cap, user mutes.

### E5. Five biggest risks
1. Follow-up resolution errors silently answer the wrong ride/signal; a plausible wrong answer passes the number guard. Mitigation: always state the assumed ride/signal in the answer, and make chips explicit.
2. 1.5B router accuracy and context pressure: grammar fixes syntax not semantics; slot splitting (`-np`) can halve the 4k budget; non-pure-transformer models may defeat prefix caching. Mitigation: own eval set, `-np 1`, pin slot, measure.
3. "Never dead end" can blur into guessing or implied authority (LLM improvising bike diagnoses); keep fallbacks to data cards from tools and avoid unsourced diagnostic claims.
4. In-ride alert distraction/liability and alert fatigue: no motorcycle numeric standard; false positives will lead riders to disable everything. Keep spoken alerts rare, audio-first, user-controllable; safety decisions stay on the safety MCU.
5. Privacy and platform limits: stored chats contain ride/position-derived content (invariant 7, public repos), memory-vs-chat deletion mismatch seen in ChatGPT/Claude, and iOS background delivery cannot be fully zero-cost (needs APNs via a relay or foregrounded app). Decide an explicit iOS stance early.

## Not verified / suggested follow-ups
Gemini saved info; BMW/Garmin/Whoop/Strava out-of-scope behaviour; BMW Motorrad/Harley/Ducati/Tesla alert channels; ISO 15005/15008/26022 text; CMC RRT whitepapers; official llama.cpp server README for `--cache-reuse`; Gemini cache pricing; BFCL/tool-choice accuracy for Qwen2.5-1.5B and Gemma 3; Pi 5 prefill/decode speeds; Android foreground-service docs; Apple developer fee.
