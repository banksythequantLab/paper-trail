"""Hunt #1 exhibits: the individual messages behind the z=4.43 spike.

Materializes the actual Finance/Accounting <-> Trading emails in the flagged
week (2001-10-08) and registers them in DataHub as the raw-evidence leaf of the
chain of custody:

    finding (analytics.hunt1_comm_spikes)
      -> exhibit task (verbatim selection SQL)
        -> analytics.hunt1_exhibits  (the actual messages)
          -> staging.emails          (the raw public corpus)

This makes "five clicks from accusation to the raw email" literally true: the
walk ends on real messages between named Enron executives, not an aggregate.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.tools.warehouse import write_evidence, query
from agents.tools.ledger import record_exhibits

HUNT_ID = "hunt1_restatement_spikes"
FINDING = "analytics.hunt1_comm_spikes"
EXHIBITS = "analytics.hunt1_exhibits"

# The individual cross-department messages that make up the flagged week.
# date_trunc('week', ...) matches the weekly bucket used by curated.comm_edges,
# so these rows reconcile exactly to the finding's vol for 2001-10-08.
SQL = r"""
WITH fin AS (SELECT addr FROM staging.employees WHERE dept IN ('Finance','Accounting')),
     trd AS (SELECT addr FROM staging.employees WHERE dept = 'Trading')
SELECT
  e.msg_id,
  e.sent_at,
  e.sender,
  r.addr                                              AS recipient,
  CASE WHEN e.sender IN (SELECT addr FROM fin)
       THEN 'Finance/Accounting -> Trading'
       ELSE 'Trading -> Finance/Accounting' END       AS direction,
  e.subject,
  substr(regexp_replace(e.body, '\s+', ' ', 'g'), 1, 500) AS excerpt,
  e.mailbox,
  e.folder
FROM staging.emails e
JOIN staging.recipients r ON r.email_id = e.id
WHERE date_trunc('week', e.sent_at) = DATE '2001-10-08'
  AND ( (e.sender IN (SELECT addr FROM fin) AND r.addr IN (SELECT addr FROM trd))
     OR (e.sender IN (SELECT addr FROM trd) AND r.addr IN (SELECT addr FROM fin)) )
ORDER BY e.sent_at, e.msg_id, r.addr
"""


def run():
    n = write_evidence(EXHIBITS, SQL)
    _, uniq = query(f"SELECT count(DISTINCT msg_id) FROM {EXHIBITS}")
    n_emails = uniq[0][0]
    print(f"[exhibits] {EXHIBITS}: {n} message-edges across {n_emails} distinct emails")

    description = (
        f"**EXHIBITS - the messages behind the finding.** The {n} "
        f"Finance/Accounting <-> Trading message-edges ({n_emails} distinct emails, each to "
        f"three Trading-side recipients) that constitute the z=4.43 communication spike in the "
        f"week of 2001-10-08 (finding: `{FINDING}`).\n\n"
        f"Real messages from the public CMU Enron corpus: sender **Jeffrey McMahon (Treasurer)** "
        f"to **David Delainey (CEO Enron North America)**, **Louise Kitchen (President Enron "
        f"Online)**, and **John Lavorato (CEO Enron Americas)** - subject *'2002 Corporate "
        f"Allocations to EIM'* - eight days before Enron's Oct-16 Q3-loss announcement.\n\n"
        f"This is the raw-evidence leaf of the chain of custody: finding -> producing task -> "
        f"**these messages** -> `staging.emails`."
    )

    ex_urn, job_urn = record_exhibits(
        hunt_id=HUNT_ID,
        finding_table=FINDING,
        exhibits_table=EXHIBITS,
        title="Hunt-1 exhibits: the messages behind the spike",
        description=description,
        sql=SQL.strip(),
        input_tables=["staging.emails", "staging.recipients", "staging.employees", FINDING],
    )
    print(f"[exhibits] ledger written:\n  exhibits: {ex_urn}\n  task:     {job_urn}")
    print("HUNT1_EXHIBITS_DONE")


if __name__ == "__main__":
    run()
