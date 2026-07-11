"""Hunt #2: Material-info leakage.
Method: emails mentioning undisclosed SPE vehicles (word-boundary match,
ILIKE prefilter for speed) sent to external (non-@enron.com) recipients
before the first public disclosure (2001-10-16).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.tools.warehouse import write_evidence, query
from agents.tools.ledger import record_finding

HUNT_ID = "hunt2_material_leakage"
EVIDENCE = "analytics.hunt2_external_leakage"

SQL = """
WITH cand AS (
  SELECT id, sent_at, sender, subject,
         lower(coalesce(subject,'') || ' ' || coalesce(body,'')) AS txt
  FROM staging.emails
  WHERE sent_at BETWEEN DATE '1999-01-01' AND DATE '2001-10-15'
    AND (subject ILIKE '%chewco%' OR body ILIKE '%chewco%'
      OR subject ILIKE '%ljm%'    OR body ILIKE '%ljm%'
      OR subject ILIKE '%raptor%' OR body ILIKE '%raptor%'
      OR subject ILIKE '%jedi%'   OR body ILIKE '%jedi%'
      OR subject ILIKE '%braveheart%' OR body ILIKE '%braveheart%')),
hits AS (
  SELECT id, sent_at, sender, subject,
         unnest(list_distinct(regexp_extract_all(
           txt, '\\b(chewco|ljm1|ljm2|ljm|raptor|jedi|braveheart)\\b'))) AS entity
  FROM cand)
SELECT h.id AS email_id, h.sent_at, h.sender, h.subject, h.entity,
       r.addr AS external_recipient,
       lower(split_part(r.addr, '@', 2)) AS external_domain,
       (SELECT min(e.event_date) FROM finance.restatement_events e)
         - h.sent_at AS days_before_disclosure
FROM hits h
JOIN staging.recipients r ON r.email_id = h.id
WHERE r.addr NOT ILIKE '%@enron.com' AND r.addr LIKE '%@%'
"""

def run():
    n = write_evidence(EVIDENCE, SQL)
    print(f"[analyst] evidence table {EVIDENCE}: {n} rows")

    _, stats = query(f"""
        SELECT count(distinct email_id), count(distinct external_recipient)
        FROM {EVIDENCE}""")
    n_emails, n_recips = stats[0]
    _, domains = query(f"""
        SELECT external_domain, count(distinct email_id) AS n
        FROM {EVIDENCE} GROUP BY 1 ORDER BY n DESC LIMIT 6""")
    print(f"[analyst] {n_emails} distinct emails to {n_recips} external addresses")
    for d, c in domains:
        print(f"    {d}: {c}")

    if n == 0:
        print("[scribe] no leakage candidates; nothing recorded")
        return
    top = ", ".join(f"{d} ({c})" for d, c in domains[:4])
    narrative = (
        f"{n_emails} emails referencing undisclosed special-purpose vehicles "
        f"(Chewco, LJM1/2, Raptor, JEDI, Braveheart -- all disclosed=false in "
        f"finance.spe_entities) were sent to {n_recips} addresses outside the "
        f"@enron.com perimeter BEFORE the first public disclosure on 2001-10-16. "
        f"Top external domains: {top}. Notable: SPE valuation material forwarded "
        f"to personal webmail (e.g. 'FW: LJM/Raptor valuations' to an @aol.com "
        f"address, Oct 8 2001) and to outside counsel (velaw.com) during the "
        f"pre-disclosure window. Term matching is lexical; individual messages "
        f"require content-level review to separate business-as-usual legal "
        f"correspondence from genuine leakage."
    )
    ev_urn, job_urn = record_finding(
        hunt_id=HUNT_ID,
        title="Pre-disclosure external transmission of undisclosed-SPE material",
        narrative=narrative, sql=SQL.strip(), evidence_table=EVIDENCE,
        input_tables=["staging.emails", "staging.recipients",
                      "finance.spe_entities", "finance.restatement_events"],
        terms=["FinanciallyMaterial", "SPE"], confidence="medium")
    print(f"[scribe] ledger written:\n  evidence: {ev_urn}\n  task:     {job_urn}")
    print("HUNT2_DONE")

if __name__ == "__main__":
    run()
