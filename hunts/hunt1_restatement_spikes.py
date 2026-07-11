"""Hunt #1: Restatement-window communication spikes.
Method: weekly Finance/Accounting <-> Trading cross-dept email volume;
z-score vs pre-Aug-2001 baseline; flag anomalous weeks near disclosure events.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.tools.warehouse import write_evidence, query
from agents.tools.ledger import record_finding

HUNT_ID = "hunt1_restatement_spikes"
EVIDENCE = "analytics.hunt1_comm_spikes"

SQL = """
WITH fin AS (SELECT addr FROM staging.employees WHERE dept IN ('Finance','Accounting')),
     trd AS (SELECT addr FROM staging.employees WHERE dept = 'Trading'),
     xdept AS (
       SELECT week, SUM(n) AS vol FROM curated.comm_edges
       WHERE (sender IN (SELECT addr FROM fin) AND recipient IN (SELECT addr FROM trd))
          OR (sender IN (SELECT addr FROM trd) AND recipient IN (SELECT addr FROM fin))
       GROUP BY week),
     base AS (SELECT avg(vol) AS mu, stddev_samp(vol) AS sigma
              FROM xdept WHERE week BETWEEN DATE '2000-01-01' AND DATE '2001-07-31')
SELECT x.week, x.vol,
       round((x.vol - b.mu) / NULLIF(b.sigma, 0), 2) AS zscore,
       (SELECT min(abs(date_diff('day', x.week, e.event_date)))
        FROM finance.restatement_events e) AS days_to_event,
       ((x.vol - b.mu) / NULLIF(b.sigma, 0)) >= 2.0
         AND x.week >= DATE '2001-08-01' AS flagged
FROM xdept x, base b
WHERE x.week BETWEEN DATE '2000-01-01' AND DATE '2001-12-31'
ORDER BY x.week
"""

def run():
    n = write_evidence(EVIDENCE, SQL)
    print(f"[analyst] evidence table {EVIDENCE}: {n} weeks")

    _, flagged = query(f"""
        SELECT week, vol, zscore FROM {EVIDENCE}
        WHERE flagged ORDER BY zscore DESC""")
    _, base = query(f"""
        SELECT round(avg(vol)) FROM {EVIDENCE}
        WHERE week < DATE '2001-08-01'""")
    print(f"[analyst] flagged weeks: {len(flagged)} (baseline avg {base[0][0]}/wk)")
    for wk, vol, z in flagged[:8]:
        print(f"    {wk}  vol={vol}  z={z}")

    if not flagged:
        print("[scribe] no anomalies; nothing recorded")
        return
    top = flagged[0]
    narrative = (
        f"Cross-department email volume between Finance/Accounting and Trading "
        f"shows {len(flagged)} anomalous week(s) (z >= 2.0 vs. Jan-2000..Jul-2001 "
        f"baseline of ~{base[0][0]}/week) during Aug-Dec 2001, the window "
        f"surrounding Enron's Q3 loss announcement (Oct 16), SEC inquiry (Oct 22), "
        f"and restatement 8-K (Nov 8). Peak week {top[0]} reached {top[1]} messages "
        f"(z={top[2]}). Pattern is consistent with coordination between the groups "
        f"ahead of and during the disclosure window. Individual threads in the peak "
        f"weeks warrant content-level review (see hunt #2)."
    )
    ev_urn, job_urn = record_finding(
        hunt_id=HUNT_ID,
        title="Anomalous Finance-Trading communication surge in restatement window",
        narrative=narrative, sql=SQL.strip(), evidence_table=EVIDENCE,
        input_tables=["curated.comm_edges", "staging.employees", "finance.restatement_events"],
        terms=["RestrictedPeriod", "FinanciallyMaterial"], confidence="medium")
    print(f"[scribe] ledger written:\n  evidence: {ev_urn}\n  task:     {job_urn}")
    print("HUNT1_DONE")

if __name__ == "__main__":
    run()
