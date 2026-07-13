# Paper Trail — 3:00 Demo Video Script

Target: 3:00 flat. Screen recording + voiceover (MaiVid narrated garnish
optional as B-roll). Every on-screen beat is listed with what to have open
BEFORE recording.

**Prep checklist (before recording):**

- DataHub UI at localhost:9002, logged in, hunt3 evidence dataset bookmarked
- Case board running at localhost:8601, all tabs pre-loaded once (warm cache)
- Terminal with venv active, font large, `agents.reviewer list` in history
- Second terminal ready to run hunt3 live (it completes in seconds)

---

## 0:00–0:20 — Hook

**Screen:** black title card → slow zoom on a raw Enron email file.

> In 2001, Enron collapsed. Half a million of their internal emails are
> public record. We gave them to an AI investigator — with one rule:
> every conclusion must have a paper trail.

## 0:20–0:45 — Problem

**Screen:** split: a chat window saying "the model flagged it" vs. a DataHub
lineage graph.

> AI findings are worthless to auditors and courts without provenance.
> "The model said so" is not admissible. But chain of custody is exactly
> what a metadata graph provides — if the investigation itself becomes
> metadata. That's Paper Trail: findings as first-class DataHub entities.

## 0:45–1:10 — Architecture flash

**Screen:** architecture diagram (15 seconds max on boxes and arrows).

> Two ways to run the same investigation. Five deterministic hunts are the
> reproducible backbone — grounded in the catalog, they run metadata-checked
> SQL and write everything back. On top, a single local ReAct agent (qwen3-30b,
> no cloud) runs the same loop autonomously: ground, query, self-correct, and
> scribe the results — evidence datasets, DataJobs holding the exact SQL,
> lineage to every source touched. Humans review; nothing confirms itself.

## 1:10–1:50 — Live hunt

**Screen:** terminal. Run hunt #3 (SPE web) live; show the ledger output
lines as they emit.

> Watch hunt three: mapping Enron's web of special-purpose entities. The
> agent builds a co-mention graph from four hundred thousand emails and
> finds eight vehicles that pattern-match known SPEs but were never
> classified in the glossary — marlin, osprey, talon, raptors' cousins,
> all real Enron entities. It doesn't just claim this. It materializes the
> evidence, registers it in DataHub, and proposes the classification —
> tagged pending review.

## 1:50–2:30 — THE MONEY SHOT

**Screen:** DataHub UI. Slow, deliberate clicks. This is the whole video.

> Here's the finding in DataHub. Click the evidence dataset… lineage tab…
> there's the DataJob — and inside it, the exact SQL that ran, character
> for character. Keep walking: the curated co-mention graph… staging
> emails… the raw mailbox file. Five clicks from accusation to evidence.
> Every verdict in this system can make that walk.

## 2:30–2:50 — Governance

**Screen:** terminal `agents.reviewer list` showing confirmed states, then
the case board with review badges and reviewer stamps.

> Findings stay pending until a human investigator accepts or rejects —
> and the review itself becomes metadata: who, when, why, stamped on the
> entity. Cases are cumulative: run two reads run one's ledger. This is
> what governed AI investigation looks like.

## 2:50–3:00 — Close

**Screen:** case board full view → repo URL card.

> Built on DataHub. Every verdict has a paper trail.

---

## Cut-priority if over 3:00

1. Trim architecture (0:45–1:10) to 15s — judges have seen boxes before
2. Trim hook zoom
3. Never cut the money shot — it is the submission
