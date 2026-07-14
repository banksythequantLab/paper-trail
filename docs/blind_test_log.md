# Blind (undirected) agent run — honest log

`agents/run_gate.py` is a **directed** run: the brief hands the agent the method, so
its output passes `verify_golden` exactly. A fair critique is that a directed run
looks like "a script with an LLM parser." This log is the answer: an **undirected**
run (`agents/run_blind.py`) where the agent gets only the schema and a generic goal —
*"inspect the stack for anomalies or governance failures; no hypothesis, no method"* —
and we report exactly what it did, stumbles included.

**Model:** local `qwen3:30b-a3b-instruct-2507-q4_K_M` (Ollama), local warehouse+ledger
tools only. Reproduce with `python agents/run_blind.py`.

## What the agent did, on its own
With no guidance it explored the warehouse autonomously — ~20 `run_sql` queries:
row counts per table (435,259 emails; 20 employees), date ranges, top senders and
recipients, department distribution — then drilled into what looked off. It surfaced
**two genuine issues that are NOT any of the five scripted hunts** — i.e. things it
found itself:

1. **Corrupted timestamps (real data-quality defect).** It noticed `sent_at` ranges
   from **1979-12-31 to 2044-01-04** — impossible for a 1999–2002 corpus — and
   isolated senders with pre-1980 dates (e.g. 5 emails from `phillip.allen@enron.com`
   dated 1979-12-31). It correctly called this an ingestion/timestamp-validation
   failure. (This is a real artifact of the corpus, not something we planted.)
2. **A power-sender missing from the employee registry (governance gap).**
   `vince.kaminski@enron.com` is the **#1 sender (14,367 emails)** yet does not appear
   in `staging.employees` (a 20-person modeled subset). It flagged this as a
   registry-completeness / "ghost account" governance failure.

Its verbatim FINDINGS summary:

> After thorough investigation, I found the following anomalies:
> 1. **Vince Kaminski's Email Anomaly (High Confidence):** … the top sender … does not
>    appear in the `staging.employees` table … a potential data governance failure: an
>    active email sender is not recognized in the employee registry …
> 2. **Invalid Date Anomalies (High Confidence):** … emails … before 1980 or after
>    2044 … 5 emails from `phillip.allen@enron.com` dated December 31, 1979 … a data
>    quality failure in the ingestion pipeline …
> 3. **Recipient-Email Mismatch (Medium Confidence):** … Kaminski appears as a recipient
>    11,944 times but is not listed in `staging.employees` …
>
> These findings point to a critical data governance failure: the employee registry is
> not synchronized with the email system, and timestamp validation is missing.

## Honest assessment
**What worked — genuine, un-briefed investigation.** Nobody told it what to look for or
handed it any SQL. It formed its own hypotheses (timestamp integrity, sender-vs-registry
consistency), wrote its own queries, and reported two *real* defects that are not among
our five hunts. That directly answers "the agent doesn't really investigate."

**What didn't — the write-back, exactly as documented.** It never completed the
auditable ledger write. It fumbled the `materialize_evidence` argument contract
(passed a bare table name, then tried to embed `CREATE TABLE …` in the `select_sql`,
instead of `table='analytics.<name>'`), our repeat-call **loop-breaker guardrail** fired
correctly, and it ended with a narrative summary — **no evidence table materialized, no
finding recorded**. So this blind run produced *analysis*, not a *provenance-backed
ledger entry*.

**Why this is the honest conclusion, not a bug we're hiding.** This is precisely why the
repo's stance is "the deterministic hunts are the source of truth; the LLM agent is
best-effort." Bounded by the two runs:
- **Directed** (`run_gate.py`): the agent can reliably execute a specified investigation
  and produce output that passes the exact value gate (`verify_golden` 20/20).
- **Undirected** (this log): the agent genuinely investigates and finds real issues, but
  does not reliably complete the governed write-back on a local 30B.

The evidence ledger a human audits is therefore written by the reproducible hunts; the
agent is a real, improving capability shown here without a highlight reel.

## Update — Tier-1 fixes: the write-back now completes, locally, no cloud

The failure above was **tool ergonomics, not model capability.** The agent reasoned
fine; it tripped on the `materialize_evidence` contract. Three local fixes (no bigger
model, no cloud):

1. **Forgiving contract** (`agents/tools/warehouse.py`) — `materialize_evidence` now
   accepts a bare table name (normalized to `analytics.<name>`) and strips an embedded
   `CREATE ... AS` if the model puts one in `select_sql`. Both original stumbles are
   removed. Regression test: `tests/test_evidence_contract.py`.
2. **Repair loop** (`agents/graph.py`) — a stuck write call is handed the exact correct
   call shape instead of being forced into an early summary, and the two write tools are
   allowed through even near the step budget so the ledger entry can complete.
3. **Worked one-shot example** in the blind system prompt showing run_sql →
   materialize_evidence (bare name, plain SELECT) → record_finding_tool.

**Result (verified live, same local hardware, RTX 3090, 19.4 / 24 GB VRAM):** the same
undirected blind run now **completes the governed write-back** — evidence materialized
*and* the finding recorded to the DataHub ledger (real `urn:li:dataJob` / `urn:li:dataset`
URNs). Confirmed on the **original `qwen3:30b-a3b` model** (2–3 findings) and on
`qwen3-coder:30b` (3 findings).

**Reliability this session:** across **7 blind runs** with the Tier-1 fixes active, **6
completed the governed write-back** (recorded ≥1 finding with a real ledger URN). The
single miss was a step-budget misconfiguration (the recursion limit was hit before the
"wrap up" nudge fired) — a harness bug, not a contract failure; it is fixed
(`agents/reliability_blind.py`), and both runs after the fix passed.

**Honest caveats that stay.** This is a handful of runs, not a large-N distribution. The
undirected findings are surface-level data-quality / governance items (skewed top
senders, external addresses, a curated-pipeline gap) — **none is a fraud discovery**,
consistent with GROUND_TRUTH.md. The directed run still passes the gate 20/20, and the
reproducible hunts remain the source of truth. What changed is narrow and real: on local
hardware, the undirected agent now reliably closes the loop it previously couldn't.
