"""Hunt #6 -- RED-TEAM CONTROL: a deliberately naive volume-anomaly detector.

This is NOT a real finding. It is a planted control that tests the review loop.
A naive detector flags the most extreme per-sender weekly volume spike in the
Aug-Dec 2001 disclosure window as a "suspicious communication surge." The top
candidate is no.address@enron.com -- Enron's automated internal-broadcast address
(outage reports, org announcements, training notices) -- which a human reviewer
REJECTS as a false positive. The rejection (who/when/why) is stamped into the
ledger.

The point: the pipeline does not just confirm what it is fed. It flags
candidates and the human filters the false positives -- and the rejection is
itself auditable metadata, exactly like a confirmation. Run this, then:

    python -m agents.reviewer reject hunt6_decoy_volume --note "<why it's benign>"
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.tools.warehouse import write_evidence, query
from agents.tools.ledger import record_finding

HUNT_ID = "hunt6_decoy_volume"
EVIDENCE = "analytics.hunt6_decoy_volume"

# Naive per-sender weekly-volume z-score; flag big spikes in the disclosure
# window. Deliberately unaware that some high-volume senders are automated.
SQL = """
WITH sw AS (
  SELECT sender, date_trunc('week', sent_at) AS week, count(*) AS vol
  FROM staging.emails GROUP BY 1, 2),
     stats AS (
  SELECT sender, avg(vol) AS mu, stddev_samp(vol) AS sigma
  FROM sw GROUP BY 1 HAVING count(*) >= 12 AND stddev_samp(vol) > 0)
SELECT s.sender, s.week, s.vol,
       round((s.vol - t.mu) / t.sigma, 2) AS zscore,
       (SELECT any_value(e.subject) FROM staging.emails e
        WHERE e.sender = s.sender AND date_trunc('week', e.sent_at) = s.week) AS sample_subject
FROM sw s JOIN stats t ON s.sender = t.sender
WHERE s.week BETWEEN DATE '2001-08-01' AND DATE '2001-12-31'
  AND (s.vol - t.mu) / t.sigma >= 5.0
ORDER BY zscore DESC
"""


def run():
    n = write_evidence(EVIDENCE, SQL)
    _, top = query(f"SELECT sender, week::varchar, vol, zscore, sample_subject "
                   f"FROM {EVIDENCE} ORDER BY zscore DESC LIMIT 1")
    s, wk, vol, z, subj = top[0]
    print(f"[decoy] {EVIDENCE}: {n} candidate(s); top = {s} {wk} vol={vol} z={z}")

    narrative = (
        f"RED-TEAM CONTROL (not a confirmed finding). A deliberately naive volume-anomaly "
        f"detector flags {n} sender-week(s) with an outbound-volume z-score >= 5.0 during the "
        f"Aug-Dec 2001 disclosure window. Top candidate: {s}, week of {wk[:10]} -- {vol} messages "
        f"(z = {z}), a surge in the exact week of the SEC inquiry (Oct 22, 2001). On its face this "
        f"looks like coordinated activity; it is planted to test the human review. Sample subject "
        f"for the top candidate: \"{(subj or '')[:60]}\". Awaiting review -- tagged pending-review "
        f"until an investigator confirms or REJECTS it."
    )
    ev_urn, job_urn = record_finding(
        hunt_id=HUNT_ID,
        title="[RED-TEAM] Anomalous communication surge in disclosure window (candidate)",
        narrative=narrative, sql=SQL.strip(), evidence_table=EVIDENCE,
        input_tables=["staging.emails"], confidence="low")
    print(f"[decoy] ledger written (pending-review):\n  evidence: {ev_urn}\n  task:     {job_urn}")
    print("HUNT6_DECOY_DONE")


if __name__ == "__main__":
    run()
