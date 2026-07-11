"""Hunt #4: Orphaned ownership.
Method: cross-reference DataHub dataset ownership against corpuser status
and the public-record implicated list. Flag financially-material datasets
whose accountable owner is departed/implicated -- especially those still
uncertified. Ownership metadata IS the evidence here.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.tools.warehouse import write_evidence, query
from agents.tools.ledger import record_finding
from agents.tools.metadata import (
    get_graph, estate, dataset_facts, user_facts, table_name, values_sql)

HUNT_ID = "hunt4_orphaned_ownership"
EVIDENCE = "analytics.hunt4_orphaned_ownership"

# public record: officers indicted or centrally implicated in the fraud
IMPLICATED = {"andrew.fastow", "michael.kopper", "richard.causey",
              "jeffrey.skilling", "kenneth.lay", "ben.glisan"}

COLS = ["dataset", "owner", "owner_title", "owner_active", "implicated",
        "financially_material", "certified", "flagged", "reason"]

def run():
    graph = get_graph()
    datasets, _ = estate(graph)
    rows, flagged_tables = [], []
    for urn in datasets:
        tbl = table_name(urn)
        if tbl.startswith("analytics."):
            continue  # our own evidence sets
        owners, tags, terms = dataset_facts(graph, urn)
        if not owners:
            rows.append((tbl, None, None, None, False, False,
                         "certified" in tags, True, "NO OWNER on record"))
            flagged_tables.append(tbl)
            continue
        for owner in owners:
            _, title, active = user_facts(graph, owner)
            imp = owner in IMPLICATED
            mat = "FinanciallyMaterial" in terms
            cert = "certified" in tags
            flag = (imp or active is False) and not cert
            reason = None
            if flag:
                bits = []
                if imp: bits.append("owner implicated (public record)")
                if active is False: bits.append("owner departed")
                if mat: bits.append("financially material")
                bits.append("not certified")
                reason = "; ".join(bits)
                flagged_tables.append(tbl)
            rows.append((tbl, owner, title, active, imp, mat, cert, flag, reason))
    sql = values_sql(COLS, rows)

    n = write_evidence(EVIDENCE, sql)
    print(f"[analyst] evidence table {EVIDENCE}: {n} ownership records")

    _, flags = query(f"""
        SELECT dataset, owner, reason FROM {EVIDENCE}
        WHERE flagged ORDER BY dataset""")
    print(f"[analyst] flagged: {len(flags)}")
    for tbl, owner, reason in flags:
        print(f"    {tbl}  owner={owner}  ({reason})")

    if not flags:
        print("[scribe] no orphaned ownership; nothing recorded")
        return
    listing = "; ".join(f"{t} (owner: {o or 'NONE'} -- {r})" for t, o, r in flags)
    narrative = (
        f"Ownership forensics over the DataHub estate found {len(flags)} "
        f"dataset(s) whose accountable owner is departed and/or implicated "
        f"in the public record, without certification: {listing}. "
        f"An uncertified, financially-material report owned by an indicted "
        f"officer has no accountable steward -- figures derived from it "
        f"cannot be attested. Recommend ownership transfer to an active "
        f"steward and certification review before any downstream use."
    )
    ev_urn, job_urn = record_finding(
        hunt_id=HUNT_ID,
        title="Financially-material datasets with departed/implicated owners",
        narrative=narrative, sql=sql, evidence_table=EVIDENCE,
        input_tables=sorted(set(flags_t for flags_t, _, _ in flags)),
        terms=["FinanciallyMaterial"], confidence="high")
    print(f"[scribe] ledger written:\n  evidence: {ev_urn}\n  task:     {job_urn}")
    print("HUNT4_DONE")

if __name__ == "__main__":
    run()
