-- Pre-disclosure external transmission of undisclosed-SPE material
-- producing task: urn:li:dataJob:(urn:li:dataFlow:(paper_trail,investigations,PROD),hunt2_material_leakage)
-- evidence: urn:li:dataset:(urn:li:dataPlatform:duckdb,paper_trail.analytics.hunt2_external_leakage,PROD)

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
           txt, '\b(chewco|ljm1|ljm2|ljm|raptor|jedi|braveheart)\b'))) AS entity
  FROM cand)
SELECT h.id AS email_id, h.sent_at, h.sender, h.subject, h.entity,
       r.addr AS external_recipient,
       lower(split_part(r.addr, '@', 2)) AS external_domain,
       (SELECT min(e.event_date) FROM finance.restatement_events e)
         - h.sent_at AS days_before_disclosure
FROM hits h
JOIN staging.recipients r ON r.email_id = h.id
WHERE r.addr NOT ILIKE '%@enron.com' AND r.addr LIKE '%@%'
