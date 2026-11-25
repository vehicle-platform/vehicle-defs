# Test results

Measured results of the platform, kept as evidence (thesis) and as the baseline for later
runs. One folder per test family; one dated folder per run inside it. Nothing here is a
decision: a run feeds a decision in `../DECISIONS.md`, which cites the run folder.

| Family | What | Index |
|---|---|---|
| `llm-bench/` | Rider-assistant LLM (D-121, D-124): latency, speed, number grounding, Turkish quality | [llm-bench/README.md](llm-bench/README.md) |

## Rules for every run

- **Synthetic inputs only** (public repo, D-033): no real ride data, position or personal data.
- **Raw output committed next to the write-up** (`*.json`, `*.md` as the tool wrote them).
- **Conditions recorded**: hardware, power supply and `vcgencmd get_throttled`, cooling,
  software versions and commits, model files with SHA-256, service limits.
- **Human review where a tool cannot judge** (for example Turkish quality), marked as such.
- Runs are never edited after the fact; a correction is a new run that links the old one.
