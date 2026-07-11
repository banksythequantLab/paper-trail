-- Financially-material datasets with departed/implicated owners
-- producing task: urn:li:dataJob:(urn:li:dataFlow:(paper_trail,investigations,PROD),hunt4_orphaned_ownership)
-- evidence: urn:li:dataset:(urn:li:dataPlatform:duckdb,paper_trail.analytics.hunt4_orphaned_ownership,PROD)

SELECT * FROM (VALUES
  ('curated.comm_edges', 'sally.beck', 'COO Energy Operations (Operations)', FALSE, FALSE, FALSE, TRUE, FALSE, NULL),
  ('staging.emails', 'sally.beck', 'COO Energy Operations (Operations)', FALSE, FALSE, FALSE, TRUE, FALSE, NULL),
  ('staging.employees', 'sally.beck', 'COO Energy Operations (Operations)', FALSE, FALSE, FALSE, TRUE, FALSE, NULL),
  ('staging.recipients', 'sally.beck', 'COO Energy Operations (Operations)', FALSE, FALSE, FALSE, TRUE, FALSE, NULL),
  ('finance.executive_summary_report', 'andrew.fastow', 'CFO (Finance)', FALSE, TRUE, TRUE, FALSE, TRUE, 'owner implicated (public record); owner departed; financially material; not certified'),
  ('finance.restatement_events', 'richard.causey', 'Chief Accounting Officer (Accounting)', FALSE, TRUE, TRUE, FALSE, TRUE, 'owner implicated (public record); owner departed; financially material; not certified'),
  ('finance.spe_entities', 'richard.causey', 'Chief Accounting Officer (Accounting)', FALSE, TRUE, TRUE, FALSE, TRUE, 'owner implicated (public record); owner departed; financially material; not certified')
) AS t(dataset, owner, owner_title, owner_active, implicated, financially_material, certified, flagged, reason)
