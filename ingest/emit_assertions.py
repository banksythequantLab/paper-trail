"""Publish the value gate to DataHub as native custom Assertions.

verify_golden.py re-derives each hunt's headline numbers and checks them against
golden.yaml. This script takes those SAME check results and reports them into
DataHub as custom (external) assertions on the evidence datasets -- one assertion
per evidence set, SUCCESS iff all of that set's golden checks pass, with each
individual check attached as a native result property. So the gate that guards
CI also becomes a first-class Validation signal in DataHub, sitting on the data
it guards. Deterministic assertion URNs make re-runs idempotent.

  python ingest/emit_assertions.py   # -> upserts + reports; prints each assertion
"""
import os
import sys
import time

# Make both the repo root (for agents.*) and ingest/ (for verify_golden) importable
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from datahub.configuration.common import GraphError
from datahub.emitter.mce_builder import make_dataset_urn

from agents.tools.metadata import (get_graph, upsert_custom_assertion,
                                    report_assertion_result)
from verify_golden import run_checks

# check-name prefix -> (evidence table, human label)
GROUPS = [
    ("hunt1.",    "analytics.hunt1_comm_spikes",                 "Restatement-window comm spike"),
    ("exhibits.", "analytics.hunt1_exhibits",                    "Exhibits: the messages behind the spike"),
    ("hunt2.",    "analytics.hunt2_external_leakage",            "Pre-disclosure external leakage"),
    ("hunt3.",    "analytics.hunt3_spe_web",                     "Shadow SPE co-mention web"),
    ("hunt4.",    "analytics.hunt4_orphaned_ownership_evidence", "Orphaned ownership by departed officers"),
    ("hunt5.",    "analytics.hunt5_provenance_gaps_evidence",    "Material data with zero provenance"),
]


def duck_urn(table):
    return make_dataset_urn("duckdb", f"paper_trail.{table}", "PROD")


def _report_with_retry(graph, a_urn, passed, props, tries=5, delay=3):
    """reportAssertionResult can race the async creation of the Asserts
    association; retry a few times before giving up."""
    for i in range(tries):
        try:
            return report_assertion_result(graph, a_urn, passed, properties=props)
        except GraphError:
            if i == tries - 1:
                raise
            time.sleep(delay)


def main():
    checks = run_checks()
    graph = get_graph()
    plan = []
    for prefix, table, label in GROUPS:
        mine = [(n, ok, d) for (n, ok, d) in checks if n.startswith(prefix)]
        if not mine:
            print(f"  [SKIP] {table} (no checks matched {prefix!r})")
            continue
        passed = all(ok for _, ok, _ in mine)
        n_ok = sum(1 for _, ok, _ in mine if ok)
        key = table.split(".", 1)[1]
        a_urn = f"urn:li:assertion:pt-gate-{key}"
        props = {n: ("PASS" if ok else f"FAIL: {d}") for (n, ok, d) in mine}
        desc = (f"Paper Trail value gate -- {label}. {n_ok}/{len(mine)} golden "
                f"values re-derived from the warehouse match ingest/golden.yaml. "
                f"A value regression (e.g. the z-score drifting off 4.43) fails "
                f"this assertion even when the SQL and lineage still look right.")
        upsert_custom_assertion(
            graph, duck_urn(table), a_urn,
            custom_type="Paper Trail Value Gate", description=desc,
            logic="verify_golden.py re-derives these headline numbers from the "
                  "evidence tables and asserts they match ingest/golden.yaml exactly.")
        plan.append((a_urn, table, passed, props, n_ok, len(mine)))

    # Assertion entities are created asynchronously; let the Asserts association
    # index before reporting run results against them.
    time.sleep(6)
    any_fail = False
    for a_urn, table, passed, props, n_ok, n_all in plan:
        _report_with_retry(graph, a_urn, passed, props)
        any_fail = any_fail or not passed
        print(f"  [{'SUCCESS' if passed else 'FAILURE'}] {a_urn}  "
              f"({n_ok}/{n_all}) on {table}")
    print("\nASSERTIONS_" + ("FAIL" if any_fail else "OK"))
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
