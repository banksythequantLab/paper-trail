-- Financially-material datasets with no documented provenance
-- producing task: urn:li:dataJob:(urn:li:dataFlow:(paper_trail,investigations,PROD),hunt5_provenance_gaps)
-- evidence: urn:li:dataset:(urn:li:dataPlatform:duckdb,paper_trail.analytics.hunt5_provenance_gaps,PROD)

SELECT * FROM (VALUES
  ('curated.comm_edges', FALSE, TRUE, TRUE, FALSE, NULL),
  ('staging.emails', FALSE, TRUE, TRUE, FALSE, NULL),
  ('staging.employees', FALSE, TRUE, TRUE, FALSE, NULL),
  ('staging.recipients', FALSE, TRUE, TRUE, FALSE, NULL),
  ('finance.executive_summary_report', TRUE, FALSE, FALSE, TRUE, 'financially material with NO documented lineage path to any source'),
  ('finance.restatement_events', TRUE, FALSE, FALSE, TRUE, 'financially material with NO documented lineage path to any source'),
  ('finance.spe_entities', TRUE, FALSE, FALSE, TRUE, 'financially material with NO documented lineage path to any source')
) AS t(dataset, financially_material, certified, has_documented_lineage, flagged, reason)
