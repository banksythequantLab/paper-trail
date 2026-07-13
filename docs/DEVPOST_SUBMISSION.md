# Paper Trail — Devpost Submission Draft

*Paste each section into the Devpost form; fill the video link at the bottom. Rewritten 2026-07-13 to lead with one thesis and one story (per judge feedback), then refreshed with the native DataHub close-the-loop (Assertions + Incident lifecycle) and the offline juror page.*

## Tagline
Paper Trail isn't an AI investigator — it turns AI investigations into **auditable, reviewable metadata with end-to-end chain of custody**, in DataHub.

## Inspiration
"The model flagged it" is not admissible in audit, compliance, or legal work. A **chain of custody** is. A metadata catalog is exactly a chain-of-custody machine — so instead of returning a chat answer, Paper Trail treats every investigation as first-class DataHub metadata: an evidence trail a human can walk, review, challenge, and act on — from an accusation back to the raw email that supports it.

## What it does (one story)
Start with a real email. **Jeffrey McMahon — Enron's Treasurer — wrote to the heads of the trading businesses (Delainey, Kitchen, Lavorato) about "2002 Corporate Allocations," eight days before Enron announced a ~$618M quarterly loss.** Paper Trail finds the statistical anomaly that surfaces that week (a z=4.43 spike in Finance↔Trading communication), and then does the thing a chatbot can't: it writes the finding back into DataHub as a walkable evidence ledger.

Open the finding in the DataHub UI and walk it:
**evidence dataset → the verbatim SQL that produced it → its lineage → the individual messages (`hunt1_exhibits`) → `staging.emails`.** Five clicks from a z-score to the Treasurer's actual email. A human reviewer confirms it — and DataHub **raises a native Incident** on the asset and an **event-driven Action** fires downstream. Every step — who reviewed it, when, why, and the exact SQL — is stamped into the catalog as governed metadata.

## What makes it different from ordinary DataHub
A traditional catalog *describes* data. Paper Trail turns *investigations* into governed metadata that can be reviewed, audited, challenged, and **acted upon**:
- **Chain of custody, literal.** The provenance walk ends on the real messages between named executives — not a summary table.
- **DataHub participates, it doesn't just store.** Confirming a finding raises a native **Incident** — on the *implicated production table* (e.g. `finance.spe_entities`, owned by the departed CAO), not the evidence table — category "Fraud Investigation," idempotent, and **resolved** when the finding is rejected or reopened. A custom **Action** on DataHub's own event stream fires a webhook the moment a review state changes. The investigation *is* the catalog's state.
- **Verification you can trust — as native DataHub Assertions.** `verify_golden.py` re-derives every headline number and asserts it against a checked-in golden — a planted wrong value (z=2.1) **fails** the gate, proving the verifier can reject, not just confirm. That gate is also published *into* DataHub as native **custom Assertions** on each evidence dataset (20/20 green in the Validation tab), so a value regression surfaces on the data itself, next to freshness and volume checks.
- **Verifiable in 60 seconds, no stack.** [`docs/juror.html`](../docs/juror.html) is a self-contained offline page — open it in any browser (no DataHub, no GPU, no network) and read the whole chain top to bottom: the real McMahon emails, the verbatim SQL, the re-derived z=4.43, the 20/20 gate, and the assertion + incident it becomes. Every number is rebuilt from a 3 MB committed fixture that **CI recomputes on every push**.
- **The review has teeth.** A planted red-team decoy — a benign automated-broadcast surge (1,399 messages the week of the SEC inquiry, a *bigger* z-score than the real finding) — is flagged, then **rejected** by a human, with the rejection reason stamped into the ledger like a confirmation. The pipeline doesn't just confirm what it's fed.

## The agent (stated honestly — the honesty is the point)
The **deterministic hunts are the source of truth**: a reproducible verification layer (`verify_hunts.py` for shape, `verify_golden.py` for values) that the evidence ledger depends on. On top of that, a **fully local LLM agent** (qwen3-30b via Ollama, no cloud API) proves the harder claim: an autonomous agent can reproduce the same finding and **pass the same verification gate** (`agents/run_gate.py` — drop the evidence table, run the agent, and it rebuilds a table that passes `verify_golden` 20/20). We don't oversell it: the local model is best-effort, and the gate-passing run is a *directed* investigation. The design point is that a machine-written finding is held to the exact same auditable standard as a human-written one.

## What's real vs. demonstrated (up front, on purpose)
The email corpus is **real and public** (CMU Enron corpus, 435,259 messages). Hunts **1–2 are discoveries on that real data** (the comm-spike and pre-disclosure external leakage). Hunts **3–5 demonstrate the governance-audit capability** — shadow-entity co-mention, orphaned ownership, and provenance gaps — over `finance.*` tables that are **reconstructed from the public Enron record and labeled as such** in DataHub. The contribution is the *auditable pattern*, not the reconstructed tables. Full mapping in `docs/ground_truth.md`.

## How we built it
DataHub OSS quickstart (v1.5.0.6) as the provenance layer; `mcp-server-datahub` as the agent's grounding; a DuckDB warehouse of the parsed corpus; the acryl-datahub SDK for write-back (evidence Datasets + DataJobs with verbatim SQL + lineage + tags/glossary/domains); native **custom Assertions** (`upsertCustomAssertion` / `reportAssertionResult`) that carry the value gate, and a full **Incident lifecycle** (`raiseIncident` on the implicated asset → `updateIncidentStatus` resolve, idempotent) driven by the review workflow; a custom `datahub-actions` pipeline on the Kafka event stream; a Streamlit case board for human review; a local LangGraph ReAct agent on Ollama. A 3 MB committed fixture plus `ingest/build_juror.py` produce the offline juror page, and **green GitHub Actions CI recomputes every headline number and rebuilds the juror page on every push** — no GPU, no DataHub. The pattern is upstreamed as a reusable `datahub-investigate` skill (PR #34 to datahub-project/datahub-skills).

## Accomplishments we're proud of
Five clicks from an accusation to the raw email; a value-level verifier that can *reject* a wrong number, now published as native DataHub **Assertions**; an **Incident lifecycle** that opens *and resolves* on the implicated production asset; a review loop that rejects a plausible false positive; DataHub that *acts* (Incident + Action) rather than just stores; a self-contained **juror page** that lets anyone verify the entire chain of custody offline in a browser; and a fully local agent held to the same audit standard as the deterministic backbone.

## What's next
A live, judge-browsable hosted catalog for the Aug 17–31 window, and landing the `datahub-investigate` skill upstream (PR #34). *(Two earlier "next" items are already shipped: a committed minimal-runnable snapshot — the 3 MB fixture + offline juror page, CI-verified — and a genuinely undirected agent run, logged verbatim in `docs/blind_test_log.md`.)*

## Built with
DataHub (OSS) · mcp-server-datahub · DataHub **Assertions + Incidents + Actions** (Kafka) · LangGraph · Ollama (qwen3-30b-a3b) · DuckDB · acryl-datahub SDK · Streamlit · Python

## Links
- **Repo (public):** https://github.com/banksythequantLab/paper-trail
- **Verify it in 60 seconds (offline):** open [`docs/juror.html`](https://github.com/banksythequantLab/paper-trail/blob/main/docs/juror.html) from the repo — the full chain of custody, no stack required.
- **Demo video:** `<add YouTube/Vimeo link>`
- **OSS skill PR:** https://github.com/datahub-project/datahub-skills/pull/34
