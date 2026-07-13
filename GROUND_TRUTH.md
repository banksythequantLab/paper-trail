# Ground Truth & Limitations

One-page honesty sheet. The detailed finding-by-finding mapping to the documented
Enron record is in [`docs/ground_truth.md`](docs/ground_truth.md).

## Real vs. reconstructed (no overclaiming)

- **Real (public record):** the 435,259-email CMU Enron corpus, and every person,
  SPE codename, date, and disclosure window the hunts surface — Fastow and Causey;
  Chewco, LJM1/2, Raptor, Talon, Porcupine, Marlin, Osprey, Yosemite; the Oct 8 2001
  communication spike, eight days before Enron's **Oct 16 2001 $618M Q3 loss**.
- **Reconstructed (labeled as such in DataHub):** the `finance.*` tables — ownership,
  the SPE registry, restatement events — seeded to mirror the documented case so the
  hunts have a governed warehouse to investigate.
- **Not claimed:** blind discovery of the fraud from scratch. The contribution is the
  **auditable provenance pattern**, which generalizes to any governed data.

## The numbers, and how to check them

- **5 hunts, all confirmed** on the real corpus; **20/20 golden values** re-derived
  from source and asserted on **every CI push** — z=4.43 the week of Oct 8, the 6
  exhibit messages, 120 leaked emails to 43 external addresses, the 8 shadow vehicles,
  the Fastow/Causey datasets.
- Reproduce with no GPU and no DataHub:
  `PAPER_TRAIL_WAREHOUSE=data/fixture_warehouse.duckdb python ingest/verify_golden.py` -> **GOLDEN_PASS (20/20)**.
- The agent path is verified the same way: `agents/run_gate.py` has the local 30B
  rebuild the evidence table from scratch; its output passes `verify_golden` **20/20**.

## The review has teeth — it rejects false positives (a planted control)

`hunts/hunt6_decoy_volume.py` is a deliberate decoy: a naive volume detector that
flags the single biggest surge in the disclosure window — **1,399 messages the week
of the SEC inquiry, z=6.6**. It looks damning, but the sender is
`no.address@enron.com`, Enron's automated internal-broadcast address. A human reviewer
**rejects** it, and the rejection (who, when, and why) is stamped into the ledger
exactly like a confirmation. A pipeline that can only confirm what it's fed isn't
auditable; this one says *no*, on the record.

## Honest limitations

- **The LLM agent is best-effort.** A local 30B (qwen3-30b-a3b) slows and varies under
  sustained load. It passes the golden gate on a warm, directed run (`run_gate.py`,
  20/20) and surfaces real, un-planted issues undirected (`run_blind.py` — corrupted
  timestamps, a top sender missing from the employee registry) but does not always
  complete the governed write-back. The full trace, stumbles included, is in
  [`docs/blind_test_log.md`](docs/blind_test_log.md). The deterministic hunts plus the
  golden gate are the guardrail that makes the agent's autonomy safe for audit use —
  *guided autonomy with deterministic guardrails.*
- **`finance.*` is reconstructed**, not primary-source financials (labeled in DataHub).
- **Single corpus.** Validated on the Enron dataset; no live client matter or modern
  channels (Slack, Teams) yet.

## Sources

- DOJ — Fastow indictment (2002): <https://www.justice.gov/archive/opa/pr/2002/October/02_crm_627.htm>
- SEC — Causey / Skilling litigation release: <https://www.sec.gov/enforcement-litigation/litigation-releases/lr-18582>
- Corpus — CMU Enron Email Dataset (public, May 2015 release).
