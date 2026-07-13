"""Value-level verification gate.

Re-derives each hunt's headline numbers from the warehouse and asserts they
EXACTLY match the checked-in golden (ingest/golden.yaml). Unlike verify_hunts.py
-- which checks that each paper trail is *shaped* right (evidence dataset +
DataJob with SQL + lineage) -- this gate catches VALUE regressions: if a hunt's
logic drifted and the z-score silently changed from 4.43, verify_hunts would
still pass but this FAILS.

Because the evidence tables are produced the same way whether the deterministic
hunts or the LLM agent wrote them, this gate verifies BOTH modes: run an agent
investigation, then run this -- a passing agent must reproduce the golden trail.

  python ingest/verify_golden.py     # -> GOLDEN_PASS / GOLDEN_FAIL (exit 1)
"""
import os
import sys

import duckdb
import yaml

WAREHOUSE = os.getenv("PAPER_TRAIL_WAREHOUSE", r"B:\paper-trail\data\warehouse.duckdb")
GOLDEN = os.getenv("PAPER_TRAIL_GOLDEN",
                   os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden.yaml"))

con = duckdb.connect(WAREHOUSE, read_only=True)
q = lambda s: con.execute(s).fetchall()
g = yaml.safe_load(open(GOLDEN, encoding="utf-8"))

checks = []


def check(name, got, want):
    checks.append((name, got == want, "" if got == want else f"got {got!r} want {want!r}"))


# --- hunt1: restatement-window comm spike ---
h = g["hunt1_restatement_spikes"]
rows = q("SELECT week::varchar, vol, zscore FROM analytics.hunt1_comm_spikes WHERE flagged")
check("hunt1.flagged_weeks", len(rows), h["flagged_weeks"])
if rows:
    wk, vol, z = rows[0]
    check("hunt1.peak_week", wk[:10], h["peak_week"])
    check("hunt1.peak_volume", int(vol), h["peak_volume"])
    check("hunt1.peak_zscore", round(float(z), 2), h["peak_zscore"])

# --- hunt1 exhibits: the actual messages behind the spike ---
h = g["hunt1_exhibits"]
edges, msgs, _recips, _senders = q(
    "SELECT count(*), count(DISTINCT msg_id), count(DISTINCT recipient), "
    "count(DISTINCT sender) FROM analytics.hunt1_exhibits")[0]
check("exhibits.edges", edges, h["edges"])
check("exhibits.distinct_messages", msgs, h["distinct_messages"])
check("exhibits.sender", q("SELECT DISTINCT sender FROM analytics.hunt1_exhibits")[0][0], h["sender"])
check("exhibits.recipients",
      sorted(x[0] for x in q("SELECT DISTINCT recipient FROM analytics.hunt1_exhibits")),
      sorted(h["recipients"]))

# --- hunt2: pre-disclosure external leakage ---
h = g["hunt2_external_leakage"]
emails, addrs = q("SELECT count(DISTINCT email_id), count(DISTINCT external_recipient) "
                  "FROM analytics.hunt2_external_leakage WHERE days_before_disclosure > 0")[0]
check("hunt2.predisclosure_emails", emails, h["distinct_predisclosure_emails"])
check("hunt2.external_addresses", addrs, h["distinct_external_addresses"])
top = q("SELECT external_domain FROM analytics.hunt2_external_leakage GROUP BY 1 "
        "ORDER BY count(DISTINCT email_id) DESC, external_domain LIMIT 1")[0][0]
check("hunt2.top_domain", top, h["top_domain"])
domains = {x[0] for x in q("SELECT DISTINCT external_domain FROM analytics.hunt2_external_leakage")}
for d in h["must_include_domains"]:
    check(f"hunt2.domain[{d}]", d in domains, True)

# --- hunt3: shadow SPE web (mirror the hunt's threshold derivation) ---
h = g["hunt3_spe_web"]
thr = h["co_mention_threshold"]
shadow = [x[0] for x in q(
    "WITH cand AS (SELECT CASE WHEN a_known THEN entity_b ELSE entity_a END AS candidate, "
    "co_mentions FROM analytics.hunt3_spe_web WHERE a_known != b_known) "
    f"SELECT candidate FROM cand GROUP BY 1 HAVING sum(co_mentions) >= {thr}")]
check("hunt3.shadow_vehicles", sorted(shadow), sorted(h["shadow_vehicles"]))

# --- hunt4: orphaned ownership by implicated departed officers ---
h = g["hunt4_orphaned_ownership"]
rows = q("SELECT dataset, owner FROM analytics.hunt4_orphaned_ownership_evidence")
check("hunt4.flagged_datasets", len(rows), h["flagged_datasets"])
check("hunt4.datasets", sorted(x[0] for x in rows), sorted(h["datasets"]))
check("hunt4.owners", sorted({x[1] for x in rows}), sorted(h["owners"]))

# --- hunt5: provenance gaps (material data, zero lineage) ---
h = g["hunt5_provenance_gaps"]
rows = q("SELECT dataset FROM analytics.hunt5_provenance_gaps_evidence")
check("hunt5.flagged_datasets", len(rows), h["flagged_datasets"])
check("hunt5.datasets", sorted(x[0] for x in rows), sorted(h["datasets"]))

# --- report ---
fails = [c for c in checks if not c[1]]
for name, ok, detail in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
print(f"\n{len(checks) - len(fails)}/{len(checks)} value checks passed")
if fails:
    print("GOLDEN_FAIL")
    sys.exit(1)
print("GOLDEN_PASS")
