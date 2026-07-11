"""Hunt #5: Provenance gaps (the meta-hunt).
Method: a dataset has documented provenance iff some DataJob lists it as
an output. Financially-material datasets with NO such producing job have
no walkable derivation -- their figures cannot be traced to source.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.tools.warehouse import write_evidence, query
from agents.tools.ledger import record_finding
from agents.tools.metadata import (
    get_graph, estate, produced_datasets, dataset_facts, table_name, values_sql)

HUNT_ID = "hunt5_provenance_gaps"
EVIDENCE = "analytics.hunt5_provenance_gaps"

COLS = ["dataset", "financially_material", "certified",
        "has_documented_lineage", "flagged", "reason"]

def run():
    graph = get_graph()
    datasets, jobs = estate(graph)
    produced = produced_datasets(graph, jobs)
    print(f"[scout] {len(datasets)} datasets, {len(jobs)} jobs, "
          f"{len(produced)} datasets with documented producers")

    rows, flagged = [], []
    for urn in datasets:
        tbl = table_name(urn)
        if tbl.startswith("analytics."):
            continue  # evidence sets carry their own DataJob lineage
        _, tags, terms = dataset_facts(graph, urn)
        mat = "FinanciallyMaterial" in terms
        cert = "certified" in tags
        lineage = urn in produced
        flag = mat and not lineage
        reason = ("financially material with NO documented lineage path to "
                  "any source" if flag else None)
        if flag:
            flagged.append(tbl)
        rows.append((tbl, mat, cert, lineage, flag, reason))
    sql = values_sql(COLS, rows)

    n = write_evidence(EVIDENCE, sql)
    print(f"[analyst] evidence table {EVIDENCE}: {n} datasets audited")
    for t in flagged:
        print(f"    FLAGGED: {t}")

    if not flagged:
        print("[scribe] no provenance gaps; nothing recorded")
        return
    narrative = (
        f"Provenance audit of the DataHub estate: of the datasets carrying "
        f"the FinanciallyMaterial glossary term, {len(flagged)} have NO "
        f"documented lineage path to any source system: "
        f"{', '.join(flagged)}. Nobody can say where these figures came "
        f"from -- in an audit context an unexplained financially-material "
        f"report is itself a red flag (who compiled finance.spe_entities? "
        f"what feeds the executive summary?). Contrast: every staging and "
        f"curated table walks back to the raw corpus, and every Paper Trail "
        f"evidence set walks back through its producing task. Recommend "
        f"lineage backfill or decommissioning before these are cited."
    )
    ev_urn, job_urn = record_finding(
        hunt_id=HUNT_ID,
        title="Financially-material datasets with no documented provenance",
        narrative=narrative, sql=sql, evidence_table=EVIDENCE,
        input_tables=flagged,
        terms=["FinanciallyMaterial"], confidence="high")
    print(f"[scribe] ledger written:\n  evidence: {ev_urn}\n  task:     {job_urn}")
    print("HUNT5_DONE")

if __name__ == "__main__":
    run()
