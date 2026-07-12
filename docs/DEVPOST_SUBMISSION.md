# Paper Trail — Devpost Submission Draft

*Paste each section into the Devpost project form; fill the repo + video links at the bottom. Written 2026-07-12. Before submitting, reconcile the two doc notes at the end.*

## Tagline
The auditable AI fraud investigator — every conclusion has walkable chain-of-custody lineage in DataHub.

## Inspiration
An AI that flags fraud is useless in audit, compliance, or legal work if it can't show its work. "The model flagged it" is not admissible — a chain of custody is. A metadata graph is exactly a chain-of-custody machine, so we built an agent that treats each investigation as first-class DataHub metadata: not a chat answer, but an evidence trail a human can walk from accusation back to the raw source.

## What it does
Paper Trail works the public Enron email corpus (435,259 messages) like a forensic team and lands five confirmed findings — each written back into DataHub as governed, reviewable metadata:

| # | Hunt | Finding |
|---|------|---------|
| 1 | Restatement-window comm spikes | z=4.43 email-volume anomaly the week of Oct 8 2001 — 8 days before Enron's Oct 16 Q3-loss announcement |
| 2 | Material-info leakage | 120 pre-disclosure emails about undisclosed SPEs reached 43 external addresses (incl. personal AOL accounts and `ljminvestments.com`) |
| 3 | SPE shadow web | 8 off-glossary shadow vehicles (marlin, osprey, talon, yosemite, rawhide, fishtail, condor, porcupine) co-mentioned with known SPEs — all real Enron entities |
| 4 | Orphaned ownership | 3 financially-material datasets owned by departed, implicated officers (Fastow, Causey); none certified |
| 5 | Provenance gaps | those same 3 datasets have zero documented lineage — fraud in the data governance itself |

Every finding terminates in an evidence-provenance ledger entry: an **evidence Dataset** (the finding as a real table, with hypothesis, method, thresholds), a **DataJob** holding the *verbatim* SQL plus input lineage to every source table, and **tags** (`evidence`, `pending-review`). A human reviewer flips pending-review → confirmed/rejected and the verdict is stamped into the entity. The payoff: in the DataHub UI, open a finding → evidence dataset → lineage → DataJob (SQL visible) → staging tables → raw mailbox files. **Five clicks from accusation to evidence.**

## How we built it
- **DataHub OSS quickstart (v1.5.0.6)** as the context + provenance layer; **`mcp-server-datahub`** (mutations enabled) as the agent's hands.
- A **DuckDB** warehouse of the parsed corpus, plus a full metadata model bootstrapped into DataHub — ownership, glossary, domains, lineage, and deliberate governance defects to hunt.
- **Deterministic hunts** (hunt1–5): each grounds in metadata, runs metadata-checked SQL, materializes evidence, and writes the ledger via the **acryl-datahub SDK** (MCP mutations can't create Datasets/DataJobs). `verify_hunts.py` walks every paper trail end-to-end (→ VERIFY_PASS).
- An **LLM investigator** (LangGraph ReAct agent) wired to **18 DataHub MCP tools + 3 warehouse tools** — running on a **fully local open model (qwen3-30b-a3b via Ollama)**, no proprietary API.
- A **Streamlit case board** for the human-in-the-loop review step.

## Challenges we ran into
The hardest part was making a local 30B model reliable at MCP tool-calling. Local models fumble tool schemas — passing dicts where DSL strings belong, invalid enum values, malformed JSON that 400s the server, and death-spiral loops that repeat a zero-result call until the graph hits its recursion limit. We built a layered fix: an **argument-coercion shim** (dict→JSON/DSL/array normalization, enum dropping), a **retry wrapper** so a diverging temperature can recover from bad tool JSON, a **loop-breaker** that redirects repeated identical calls to a "stop and summarize" nudge, and a **turn-budget nudge** that forces the final FINDINGS summary before the step budget runs out. The result is a fully local agent that grounds, queries, self-corrects, and ends with a structured, provenance-backed summary — no cloud model in the loop.

## Accomplishments we're proud of
- **Auditability:** five clicks from an accusation to the raw email that supports it — no black-box verdicts.
- **Governance-as-a-hunt:** hunt 5 finds the fraud *in the data governance itself* — orphaned, unlineaged, financially-material tables owned by departed officers.
- A **fully local** agent reliable enough to run the same investigation end-to-end and land a clean FINDINGS summary.
- The pattern is **reusable and upstreamed** as a DataHub skill (PR #34).

## What we learned
Metadata isn't documentation — it's the substrate for trustworthy AI. When every claim must cite a materialized evidence table and its producing SQL, a "hallucinated finding" stops being expressible. And a mid-size open model, with the right guardrails, can drive a real multi-tool investigation locally.

## What's next for Paper Trail
- A live, judge-browsable catalog (findings + lineage), hosted for the Aug 17–31 judging window.
- More hunt types; generalize beyond the Enron corpus to any DataHub-catalogued warehouse.
- Land the `datahub-investigate` skill upstream.

## Built with
DataHub (OSS) · mcp-server-datahub · LangGraph · Ollama (qwen3-30b-a3b) · DuckDB · acryl-datahub SDK · Streamlit · Python

## Links
- **Repo:** https://github.com/banksythequantLab/paper-trail
- **Demo video:** `<add link>`
- **OSS skill PR:** https://github.com/datahub-project/datahub-skills/pull/34

## Honest labeling (keep this in the submission)
The email corpus is real and public (CMU Enron corpus, May 2015 release). The `finance.*` tables (transactions, SPE entities, restatement events) are reconstructed for the demo from the public record and labeled as such in their DataHub descriptions. Entity names, dates, and disclosure windows follow the historical record.

## Before submitting — one note left (Claude's)
Resolved: the README now says the LLM agent runs on local Ollama (was Claude/Anthropic), and hunt-1 timing is reconciled everywhere to the verified value — **week of Oct 8 2001, 8 days before the Oct 16 Q3-loss announcement, z=4.43** (from the hunt-1 ledger entry; README + `ui/case_board.py` fixed to match).

Still your call: README §Architecture describes a 5-sub-agent supervisor (Intake/Scout/Analyst/Tracer/Scribe), but the LLM `agents/graph.py` is a single ReAct agent — reword (or note the sub-agents are the deterministic hunt pipeline) so a judge reading the code isn't confused.

