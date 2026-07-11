-- Unclassified SPE-pattern entities in communication web
-- producing task: urn:li:dataJob:(urn:li:dataFlow:(paper_trail,investigations,PROD),hunt3_spe_web)
-- evidence: urn:li:dataset:(urn:li:dataPlatform:duckdb,paper_trail.analytics.hunt3_spe_web,PROD)

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
    '\b(chewco|ljm1|ljm2|ljm|raptor|jedi|braveheart|whitewing|condor|talon|osprey|marlin|yosemite|fishtail|bacchus|slapshot|zephyrus|southampton|rawhide|timberwolf|porcupine)\b'))) AS entity
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
