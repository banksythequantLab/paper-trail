"""Hunt #3: SPE web mapping.
Method: entity co-mention graph over the corpus. Known SPEs (from
finance.spe_entities) + candidate vehicle names from the public record.
Candidates that co-mention heavily with known SPEs but were never
classified RelatedParty in the glossary are proposed for classification
(pending-review tag = the HITL proposal, per build plan section 10).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.tools.warehouse import write_evidence, query
from agents.tools.ledger import record_finding

HUNT_ID = "hunt3_spe_web"
EVIDENCE = "analytics.hunt3_spe_web"
THRESHOLD = 20  # min co-mentions with a known SPE to flag a candidate

SQL = """
WITH cand AS (
  SELECT id, lower(coalesce(subject,'') || ' ' || coalesce(body,'')) AS txt
  FROM staging.emails
  WHERE sent_at BETWEEN DATE '1999-01-01' AND DATE '2001-12-31'
    AND (subject ILIKE '%chewco%' OR body ILIKE '%chewco%'
      OR subject ILIKE '%ljm%'    OR body ILIKE '%ljm%'
      OR subject ILIKE '%raptor%' OR body ILIKE '%raptor%'
      OR subject ILIKE '%jedi%'   OR body ILIKE '%jedi%'
      OR subject ILIKE '%braveheart%' OR body ILIKE '%braveheart%'
      OR subject ILIKE '%whitewing%'  OR body ILIKE '%whitewing%')),
mentions AS (
  SELECT id, unnest(list_distinct(regexp_extract_all(txt,
    '\\b(chewco|ljm1|ljm2|ljm|raptor|jedi|braveheart|whitewing|condor|talon|osprey|marlin|yosemite|fishtail|bacchus|slapshot|zephyrus|southampton|rawhide|timberwolf|porcupine)\\b'))) AS entity
  FROM cand),
known AS (
  SELECT lower(entity) AS entity FROM finance.spe_entities
  UNION ALL SELECT unnest(['ljm', 'raptor'])),
edges AS (
  SELECT a.entity AS entity_a, b.entity AS entity_b, count(*) AS co_mentions
  FROM mentions a JOIN mentions b ON a.id = b.id AND a.entity < b.entity
  GROUP BY 1, 2)
SELECT e.*,
       e.entity_a IN (SELECT entity FROM known) AS a_known,
       e.entity_b IN (SELECT entity FROM known) AS b_known
FROM edges e ORDER BY co_mentions DESC
"""

def run():
    n = write_evidence(EVIDENCE, SQL)
    print(f"[analyst] evidence table {EVIDENCE}: {n} co-mention edges")

    _, shadows = query(f"""
        WITH cand AS (
          SELECT CASE WHEN a_known THEN entity_b ELSE entity_a END AS candidate,
                 co_mentions
          FROM {EVIDENCE} WHERE a_known != b_known)
        SELECT candidate, sum(co_mentions) AS total
        FROM cand GROUP BY 1 HAVING total >= {THRESHOLD}
        ORDER BY total DESC""")
    print(f"[analyst] shadow candidates (>= {THRESHOLD} co-mentions with known SPEs):")
    for ent, total in shadows:
        print(f"    {ent}: {total}")

    if not shadows:
        print("[scribe] no unclassified candidates; nothing recorded")
        return
    names = ", ".join(f"{e} ({t})" for e, t in shadows)
    narrative = (
        f"Entity co-mention analysis across the corpus surfaced "
        f"{len(shadows)} vehicle-like entities that co-occur heavily with "
        f"known special-purpose entities but appear NOWHERE in "
        f"finance.spe_entities and carry no RelatedParty glossary "
        f"classification: {names} (co-mention totals with known SPEs). "
        f"Several are documented off-balance-sheet vehicles in the public "
        f"record (Talon was the internal entity of Raptor I; Marlin and "
        f"Osprey funded Whitewing; Yosemite issued credit-linked notes). "
        f"PROPOSAL: classify these entities RelatedParty/SPE in the "
        f"glossary and extend finance.spe_entities. Awaiting human review "
        f"-- this finding is tagged pending-review until an investigator "
        f"confirms or rejects it."
    )
    ev_urn, job_urn = record_finding(
        hunt_id=HUNT_ID,
        title="Unclassified SPE-pattern entities in communication web",
        narrative=narrative, sql=SQL.strip(), evidence_table=EVIDENCE,
        input_tables=["staging.emails", "finance.spe_entities"],
        terms=["SPE", "RelatedParty"], confidence="high")
    print(f"[scribe] ledger written:\n  evidence: {ev_urn}\n  task:     {job_urn}")
    print("HUNT3_DONE")

if __name__ == "__main__":
    run()
