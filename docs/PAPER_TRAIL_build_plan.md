# PAPER TRAIL — The Auditable AI Fraud Investigator
### Build Plan — "Build with DataHub: The Agent Hackathon" (deadline Aug 10, 2026 @ 5pm EDT)

**One-line pitch:** A LangGraph multi-agent fraud investigator that works the Enron dataset like a forensic team — and every conclusion it reaches has walkable chain-of-custody lineage in DataHub. No black-box verdicts: click any finding and trace it back through the exact SQL, intermediate datasets, and source tables to the raw evidence.

**Track:** Open/Wildcard (regulatory automation is name-checked in the brief), with the codegen judges satisfied via an `examples/` folder of generated SQL artifacts.

**Decisions locked (Jul 10):** Name = **Paper Trail**. Solo build. Project root = **B:\paper-trail** (Docker volumes and corpus on B:, nothing on C:). MaiVid narrated summary video **is in scope** as the week-4 garnish.

---

## 1. Why this wins (judging criteria map)

| Criterion | How we hit it |
|---|---|
| **Use of DataHub** | Reads: search, schemas, lineage, ownership, tags, real query context. Writes back: investigation documents, risk tags, glossary taxonomy, new Dataset entities for evidence sets, DataJob entities recording every analysis (= lineage of findings). Uses the governed **proposals workflow** for human sign-off. Few submissions will touch mutation tools at all. |
| **Technical Execution** | End-to-end runnable: `docker compose up` → ingest → investigate → walk lineage in DataHub UI. |
| **Originality** | Doesn't rebuild text-to-SQL (Analytics Agent exists) or stewardship (datahub-enrich exists). The novel artifact is the **evidence-provenance ledger** — investigations as first-class metadata. |
| **Real-World Usefulness** | AI findings are useless in audit/legal contexts without provenance. Compliance, internal audit, and e-discovery teams face this today. (Nota.Lawyer domain credibility in the write-up.) |
| **Submission Quality** | Real fraud story = memorable 3-min video. Judges walk the lineage themselves on the hosted/demo instance. |
| **Bonus: OSS contribution** | PR a `datahub-investigate` skill to `datahub-project/datahub-skills` (week 3). |

**Positioning guardrail:** SQL generation is internal plumbing, never the headline. The headline is: *every AI conclusion is admissible because its full derivation lives in the metadata graph.*

---

## 2. Architecture

```
                        ┌─────────────────────────────────────────┐
                        │        LangGraph Supervisor              │
                        │  (case state machine, routing, memory)   │
                        └──┬───────┬────────┬────────┬────────┬───┘
                           │       │        │        │        │
                    ┌──────▼─┐ ┌───▼────┐ ┌─▼──────┐ ┌▼──────┐ ┌▼────────┐
                    │ Intake │ │Context │ │Analyst │ │Lineage│ │ Scribe  │
                    │ agent  │ │ Scout  │ │ agent  │ │Tracer │ │ agent   │
                    └────────┘ └───┬────┘ └─┬───┬──┘ └──┬────┘ └──┬──────┘
                                   │        │   │       │         │
                          DataHub MCP    DuckDB │  DataHub MCP  DataHub MCP
                          (read tools)  (SQL    │  (get_lineage, (mutations) +
                                        exec)   │  paths_between) Python SDK
                                                │                (DataJob/Dataset
                                        draft_sql_for_tables      emission)
                                                          ┌──────────────┐
                                                          │ Reviewer/HITL │
                                                          │ (proposals +  │
                                                          │ accept/reject)│
                                                          └──────────────┘
```

### Agents (LangGraph StateGraph nodes)

1. **Case Intake** — turns a directive ("investigate undisclosed related-party entities") into an investigation plan; loads prior ledger entries via `search_documents` / `grep_documents` so cases are **cumulative** — run 2 inherits run 1's findings.
2. **Context Scout** — grounds everything before analysis: `search`, `get_entities`, `list_schema_fields`, `get_dataset_queries`, `find_sql_context`. Knows `body` can be null, knows which tables carry `financially-material` tags, refuses to touch `restricted-period` data without logging it.
3. **Analyst** — `draft_sql_for_tables` (DataHub-grounded SQL) → executes against DuckDB → statistical checks (spike detection, graph metrics). Every query it runs is captured verbatim for the ledger.
4. **Lineage Tracer** — `get_lineage`, `get_lineage_paths_between` for blast-radius and provenance verification (e.g., "does this report have documented lineage to source?").
5. **Scribe** — the differentiator. Writes back to DataHub:
   - `save_document` → investigation ledger entry (structured: hypothesis, method, evidence URNs, confidence, SQL)
   - `add_tags` → `risk-flagged`, `evidence`, `under-investigation` on implicated assets
   - `create_glossary_term` / `add_related_terms` → risk taxonomy (SPE, Related-Party, Round-Trip-Trade…)
   - **Python SDK emitter** (not MCP) → new Dataset entity per evidence set + DataJob entity recording the exact SQL with input/output lineage. ⚠️ *MCP mutation tools cannot create Datasets/DataJobs/lineage — this requires `acryl-datahub` SDK direct emission. Key implementation detail.*
6. **Reviewer (HITL)** — findings surface as DataHub **proposals** (`propose_lifecycle_stage`, `propose_create_glossary_term`); human investigator approves/rejects via `accept_or_reject_proposals` or the DataHub UI. Governed AI = the compliance story judges will remember.

### Stack

| Layer | Choice | Notes |
|---|---|---|
| Agents | **LangGraph** (Python 3.11) | StateGraph supervisor pattern; checkpointing for resumable cases |
| MCP bridge | `langchain-mcp-adapters` (`MultiServerMCPClient`) | ⚠️ verify current API via Context7 before coding — moves fast |
| DataHub | OSS quickstart (Docker) | `datahub docker quickstart`; needs ~8GB RAM for Docker |
| MCP server | `mcp-server-datahub` (self-hosted, `uvx mcp-server-datahub@latest`) | `DATAHUB_GMS_URL` + `DATAHUB_GMS_TOKEN`; **`TOOLS_IS_MUTATION_ENABLED=true`** (mutations need v0.5.0+) |
| Write-back | `acryl-datahub` Python SDK | Dataset/DataJob emission, lineage edges |
| Warehouse | **DuckDB** | zero-ops, fast over Parquet, has a DataHub ingestion path |
| LLM | Claude via `langchain-anthropic` (make provider swappable — judges may lack Anthropic keys) | |
| Case board UI | Streamlit (thin) | Optional polish; DataHub UI itself is the real demo surface |
| License | **Apache 2.0, visible in repo About section** | Hard submission requirement |

---

## 3. Data layer: Enron as a data ecosystem

### Sources (all public)
- **CMU Enron corpus** (May 2015 release, ~500K emails, ~1.7GB) — https://www.cs.cmu.edu/~enron/
- **Enron employee roles list** (public annotations mapping ~150 custodians to titles/departments) — becomes the org chart / ownership model
- **Public-record financials** — quarterly statements, restatement dates (Oct–Nov 2001), and the famous SPEs (Chewco, LJM1/LJM2, Raptors). Synthesize a `transactions` table modeled on the public record; clearly label as reconstructed-for-demo.

### Warehouse tables (DuckDB)
```
raw:      email_files (path, mailbox, raw_text)
staging:  emails (id, sender, sent_at, subject, body), recipients (email_id, addr, type),
          employees (addr, name, title, dept), entities_mentioned (email_id, entity, type)
curated:  threads, comm_edges (sender, recipient, week, n), entity_comention_graph
finance:  transactions, spe_entities, restatement_events
analytics: <created by the agent at runtime — the evidence sets>
```

### DataHub modeling (the part judges grade)
- **Schemas** ingested from DuckDB; every column documented.
- **Ownership**: employees own their mailbox-derived slices; depts own domains (Trading Desk, Accounting, Executive, Legal).
- **Glossary**: `PII`, `Financially-Material`, `Restricted-Period`, `SPE`, `Related-Party`, `Attorney-Client` — agent behavior branches on these.
- **Lineage**: full DAG raw → staging → curated → finance emitted at ingest, so the agent has a real graph to traverse *and* extend.
- **Deliberate defects** (the agent's prey): one report with missing lineage, one dataset owned by a departed employee, quality gaps on `body`.

---

## 4. The five hunts (the "real work")

1. **Restatement-window comm spikes** — anomalous communication volume between Accounting and Trading domains in weeks preceding restatement events (baseline + z-score on `comm_edges`).
2. **Material-info leakage** — content referencing `Financially-Material`-tagged tables appearing in emails to external domains before disclosure dates.
3. **SPE web mapping** — entity co-mention graph → cluster detection → flag entities that pattern-match SPEs but were never tagged `Related-Party` in the glossary. Agent **proposes** the glossary classification (HITL approves).
4. **Orphaned ownership** — datasets and reports whose owner left/was implicated but which kept receiving writes (ownership metadata × activity).
5. **Provenance gaps** — reports with no documented lineage path to certified sources (`get_lineage_paths_between` returns nothing = red flag). The meta-hunt: the tool that finds fraud in data *governance* itself.

Each hunt terminates in a **ledger entry**: document + evidence Dataset + DataJob with lineage + tags + (where classification changes) a proposal awaiting human review.

**Demo money shot:** open finding #3 in DataHub UI → click the evidence dataset → lineage tab → walk backward through the DataJob (SQL visible) → curated graph table → staging emails → raw mailbox file. Accusation to evidence in five clicks.

---

## 5. Repo structure

```
paper-trail/
├── LICENSE                      # Apache 2.0 (must show in GitHub About)
├── README.md                    # what/why/quickstart/architecture diagram
├── docker-compose.yml           # DataHub quickstart + one-command bring-up
├── pyproject.toml
├── ingest/
│   ├── download_corpus.py       # fetch + verify CMU corpus
│   ├── parse_emails.py          # → Parquet
│   ├── build_warehouse.py       # DuckDB tables
│   └── datahub_bootstrap.py     # schemas, owners, glossary, domains, lineage, defects
├── agents/
│   ├── graph.py                 # LangGraph supervisor + state
│   ├── intake.py  scout.py  analyst.py  tracer.py  scribe.py
│   └── tools/                   # MCP client setup, SDK emitters, DuckDB exec
├── hunts/                       # the five hunt definitions (prompt + method + thresholds)
├── ui/case_board.py             # Streamlit (optional)
├── examples/                    # ★ generated SQL, sample ledger docs, screenshots
│   ├── generated_sql/
│   ├── ledger_entries/
│   └── lineage_screenshots/
├── skill/                       # datahub-investigate skill (OSS contribution PR)
└── docs/demo_script.md
```

---

## 6. Timeline (4 weeks, Jul 13 → Aug 10)

Given you turn hackathon submissions in 3 days, this is padded — front-load the risky integration, spend the surplus on polish and the OSS contribution.

**Week 1 (Jul 13–19) — Foundation. Kill all integration risk here.**
- DataHub quickstart running with data on B:\paper-trail (Docker Desktop; keep volumes off C:)
- Corpus downloaded, parsed, DuckDB warehouse built
- `datahub_bootstrap.py`: full metadata model + lineage + deliberate defects
- MCP server up **with mutations enabled**; LangGraph skeleton calling DataHub tools round-trip
- **Milestone:** agent answers "what tables hold financially-material data?" via MCP, and SDK emits one test DataJob with lineage. If both work, everything else is app logic.

**Week 2 (Jul 20–26) — First blood.**
- Context Scout + Analyst + DuckDB execution loop
- Hunt #1 end-to-end including full Scribe write-back (document, tags, evidence Dataset, DataJob lineage)
- **Milestone:** the lineage money-shot works — finding → raw file, clickable in DataHub UI.

**Week 3 (Jul 27–Aug 2) — Full scope.**
- Hunts #2–5; Lineage Tracer; cumulative case memory (ledger read-back at intake)
- HITL proposals flow; Streamlit case board
- OSS contribution: `datahub-investigate` skill PR to `datahub-project/datahub-skills`
- **Milestone:** fresh-clone `docker compose up` → full investigation on a clean machine.

**Week 4 (Aug 3–10) — Ship.**
- README, `examples/` populated, license visible, provider-swappable LLM config
- Record + edit 3-min video; write Devpost submission; opt into feedback survey ($50 bonus prize)
- **Submit Aug 7–8** (buffer). Deadline Aug 10, 5pm EDT.

---

## 7. Demo video outline (3:00)

| Time | Beat |
|---|---|
| 0:00–0:20 | Hook: "In 2001, Enron collapsed. 500,000 of their emails are public. We gave them to an AI investigator — with one rule: every conclusion must have a paper trail." |
| 0:20–0:45 | Problem: AI findings are worthless to auditors/courts without provenance. Chain of custody is exactly what a metadata graph provides. |
| 0:45–1:10 | Architecture flash: LangGraph team + DataHub MCP read/write + proposals. 15 seconds max on boxes and arrows. |
| 1:10–1:50 | Live: kick off hunt #3 (SPE web). Show Scout grounding in metadata, Analyst running grounded SQL, Scribe writing the ledger. |
| 1:50–2:30 | **Money shot:** DataHub UI — finding → evidence dataset → lineage walk → SQL in the DataJob → raw email. "Five clicks from accusation to evidence." |
| 2:30–2:50 | Governance: the proposal awaiting human approval; cumulative ledger; second run inheriting the first. |
| 2:50–3:00 | Close: "Built on DataHub. Every verdict has a paper trail." Repo URL. |

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| DataHub quickstart is resource-hungry (~8GB Docker RAM) | Run on Vesper/Johnson (E: drive); trim corpus to top-50 custodians if ingest is slow — story unaffected |
| Mutation tools need `mcp-server-datahub` v0.5.0+ and env flag | Pin version; verify in week-1 milestone |
| MCP can't create Datasets/DataJobs/lineage | Known: Python SDK emitter handles it; prototype in week 1 |
| `langchain-mcp-adapters` API churn | **Context7 check before writing code** (per your standing rule — these libs ship faster than any model's training data) |
| Enron corpus encoding/dedup mess | Known problem, known fixes; budget one day in parsing |
| Judges can't run Anthropic models | Provider-swappable via env; include recorded fallback + hosted demo |
| Scope creep (5 hunts + UI + skill PR) | Hunts #1 and #3 + money shot are the MVP; everything else is additive and cuttable |

---

## 9. Decisions

1. **Name:** Paper Trail. ✔
2. **Solo build.** ✔ Hunts #1 and #3 + money shot remain the MVP cut line.
3. **Location:** B:\paper-trail — corpus, DuckDB file, Docker volumes, repo clone. Nothing on C:.
4. **MaiVid garnish: IN.** Auto-generated narrated investigation-summary video, produced from the ledger entries, shipped in `examples/`. Also doubles as B-roll for the 3-min Devpost video. Scheduled week 4, cut first if timeline slips.
5. **Still open:** hosted demo vs. docker-compose-only (~$20 VPS, decide start of week 4).


---

## 10. Week-1 verification findings (Jul 10 — infra VERIFIED WORKING)

- DataHub v1.5.0.6 quickstart healthy on Docker 28.4.0; UI at http://localhost:9002 (datahub/datahub).
- SDK round-trip PASS (`ingest/smoke_roundtrip.py`): emitted 2 datasets + dataflow + datajob with input/output lineage, read back verified. Evidence-ledger write path confirmed.
- MCP server PASS (`ingest/mcp_smoke.py`): mcp-server-datahub over stdio, **18 tools** with mutations enabled; search found the smoke dataset.
- **OSS tool list (actual):** search, get_entities, get_lineage, get_lineage_paths_between, list_schema_fields, get_dataset_queries, add/remove tags/terms/owners, set/remove_domains, update_description, add/remove_structured_properties, save_document.
- **Cloud-only (NOT available):** proposals workflow, create_glossary_term via MCP, draft_sql_for_tables, find_sql_context. PLAN CHANGES:
  1. HITL approval moves to app layer: findings tagged `pending-review`; Reviewer flips to `confirmed`/`rejected` via add_tags/remove_tags. Same governance story, our implementation — arguably better for "originality."
  2. SQL generation is our own agent using list_schema_fields + get_dataset_queries context (no draft_sql crutch).
  3. Glossary terms created via Python SDK emitter instead of MCP.
- No token needed against quickstart (metadata service auth off). Use PAT env var for any hosted demo.
- Reusing `B:\enron-loader\data\enron.db` (435,259 parsed emails, FTS-indexed) — corpus parsing step deleted from week 1.
