"""Build a tiny, committable fixture warehouse for CI / offline reproduction.

The full warehouse (435,259 emails) is too big and GPU/DataHub-adjacent to ship.
This exports just what's needed to (a) recompute hunt-1's flagship z-score from
SOURCE data and (b) run the full value gate:

  - analytics.*                : the evidence ledger (small) -> verify_golden.py
  - staging.employees          : the 20 modeled custodians (dept lens for hunt-1)
  - curated.comm_edges (subset): only the Finance/Accounting <-> Trading edges,
                                 which is all hunt-1's SQL reads -> reproduces z=4.43
  - finance.restatement_events, finance.spe_entities : small reconstructed tables

Result is a few hundred KB. Regenerate with:  python ingest/build_fixture.py
"""
import os

import duckdb

SRC = os.getenv("PAPER_TRAIL_WAREHOUSE", r"B:\paper-trail\data\warehouse.duckdb")
DST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "fixture_warehouse.duckdb")

if os.path.exists(DST):
    os.remove(DST)

c = duckdb.connect(DST)
c.execute(f"ATTACH '{SRC}' AS src (READ_ONLY)")
for s in ("analytics", "staging", "curated", "finance"):
    c.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")

# The whole evidence ledger (small) -> lets verify_golden run all 20 checks.
for t in ("hunt1_comm_spikes", "hunt1_exhibits", "hunt2_external_leakage",
          "hunt3_spe_web", "hunt4_orphaned_ownership",
          "hunt4_orphaned_ownership_evidence", "hunt5_provenance_gaps",
          "hunt5_provenance_gaps_evidence"):
    c.execute(f"CREATE TABLE analytics.{t} AS SELECT * FROM src.analytics.{t}")

# Small source tables needed to RECOMPUTE hunt-1 from scratch.
c.execute("CREATE TABLE staging.employees AS SELECT * FROM src.staging.employees")
c.execute("CREATE TABLE finance.restatement_events AS SELECT * FROM src.finance.restatement_events")
c.execute("CREATE TABLE finance.spe_entities AS SELECT * FROM src.finance.spe_entities")

# curated.comm_edges filtered to exactly the cross-department edges hunt-1 reads
# (both directions). This is a tiny subset that still reproduces z=4.43.
c.execute("""
CREATE TABLE curated.comm_edges AS
SELECT e.* FROM src.curated.comm_edges e
WHERE (e.sender IN (SELECT addr FROM src.staging.employees WHERE dept IN ('Finance','Accounting'))
       AND e.recipient IN (SELECT addr FROM src.staging.employees WHERE dept = 'Trading'))
   OR (e.sender IN (SELECT addr FROM src.staging.employees WHERE dept = 'Trading')
       AND e.recipient IN (SELECT addr FROM src.staging.employees WHERE dept IN ('Finance','Accounting')))
""")

n_edges = c.execute("SELECT count(*) FROM curated.comm_edges").fetchone()[0]
c.close()
size = os.path.getsize(DST)
print(f"fixture built: {DST}")
print(f"  cross-dept comm_edges rows: {n_edges}")
print(f"  size: {size/1024:.0f} KB")
