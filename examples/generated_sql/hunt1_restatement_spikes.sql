-- Anomalous Finance-Trading communication surge in restatement window
-- producing task: urn:li:dataJob:(urn:li:dataFlow:(paper_trail,investigations,PROD),hunt1_restatement_spikes)
-- evidence: urn:li:dataset:(urn:li:dataPlatform:duckdb,paper_trail.analytics.hunt1_comm_spikes,PROD)

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
