"""Paper Trail: build DuckDB warehouse from existing enron.db (435K parsed emails).
Layers: staging (emails, recipients, employees) -> curated (comm_edges) + finance seeds.
"""
import duckdb

DB = r"B:\paper-trail\data\warehouse.duckdb"
SRC = r"B:\enron-loader\data\enron.db"

con = duckdb.connect(DB)
con.execute("INSTALL sqlite; LOAD sqlite;")
con.execute(f"ATTACH '{SRC}' AS src (TYPE sqlite, READ_ONLY)")
for s in ("staging", "curated", "finance"):
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")

con.execute("""
CREATE OR REPLACE TABLE staging.emails AS
SELECT id, msg_id, sender, TRY_CAST(date AS DATE) AS sent_at,
       subject, body, mailbox, folder
FROM src.emails
""")

con.execute("""
CREATE OR REPLACE TABLE staging.recipients AS
WITH exploded AS (
  SELECT id AS email_id,
         trim(unnest(string_split(recipients, ','))) AS addr
  FROM src.emails WHERE recipients IS NOT NULL
)
SELECT email_id, addr FROM exploded WHERE addr <> '' AND addr LIKE '%@%'
""")

# Key custodians with public-record titles/departments (demo ownership model)
con.execute("""
CREATE OR REPLACE TABLE staging.employees AS
SELECT * FROM (VALUES
 ('kenneth.lay@enron.com','Kenneth Lay','Chairman & CEO','Executive'),
 ('jeff.skilling@enron.com','Jeffrey Skilling','President & CEO','Executive'),
 ('greg.whalley@enron.com','Greg Whalley','President & COO','Executive'),
 ('andrew.fastow@enron.com','Andrew Fastow','CFO','Finance'),
 ('richard.causey@enron.com','Richard Causey','Chief Accounting Officer','Accounting'),
 ('ben.glisan@enron.com','Ben Glisan','Treasurer','Finance'),
 ('jeffrey.mcmahon@enron.com','Jeffrey McMahon','Treasurer','Finance'),
 ('john.lavorato@enron.com','John Lavorato','CEO Enron Americas','Trading'),
 ('david.delainey@enron.com','David Delainey','CEO Enron North America','Trading'),
 ('louise.kitchen@enron.com','Louise Kitchen','President Enron Online','Trading'),
 ('john.arnold@enron.com','John Arnold','Gas Trader','Trading'),
 ('tim.belden@enron.com','Tim Belden','Head of West Power Trading','Trading'),
 ('james.derrick@enron.com','James Derrick','General Counsel','Legal'),
 ('mark.haedicke@enron.com','Mark Haedicke','Managing Director Legal','Legal'),
 ('steven.kean@enron.com','Steven Kean','Chief of Staff','Gov Affairs'),
 ('richard.shapiro@enron.com','Richard Shapiro','VP Regulatory Affairs','Gov Affairs'),
 ('mark.koenig@enron.com','Mark Koenig','Head of Investor Relations','IR'),
 ('paula.rieker@enron.com','Paula Rieker','Corporate Secretary','IR'),
 ('rick.buy@enron.com','Rick Buy','Chief Risk Officer','Risk'),
 ('sally.beck@enron.com','Sally Beck','COO Energy Operations','Operations')
) AS t(addr, name, title, dept)
""")

con.execute("""
CREATE OR REPLACE TABLE curated.comm_edges AS
SELECT e.sender, r.addr AS recipient,
       date_trunc('week', e.sent_at) AS week, count(*) AS n
FROM staging.emails e JOIN staging.recipients r ON r.email_id = e.id
WHERE e.sent_at IS NOT NULL
GROUP BY 1, 2, 3
""")

# Public-record SPE / related-party entities (the fraud vehicles)
con.execute("""
CREATE OR REPLACE TABLE finance.spe_entities AS
SELECT * FROM (VALUES
 ('Chewco', 'SPE', true, false, 'Kopper-run vehicle to keep JEDI off balance sheet'),
 ('JEDI', 'JV', true, false, 'CalPERS JV; deconsolidation trigger'),
 ('LJM1', 'SPE', true, false, 'Fastow partnership; Rhythms hedge'),
 ('LJM2', 'SPE', true, false, 'Fastow partnership; Raptor funding'),
 ('Raptor I', 'SPE', true, false, 'Merchant investment hedge vehicle'),
 ('Raptor II', 'SPE', true, false, 'Merchant investment hedge vehicle'),
 ('Raptor III', 'SPE', true, false, 'New Power hedge vehicle'),
 ('Raptor IV', 'SPE', true, false, 'Merchant investment hedge vehicle'),
 ('Braveheart', 'SPE', true, false, 'Blockbuster VOD revenue vehicle'),
 ('Whitewing', 'SPE', true, true, 'Asset warehouse; partially disclosed')
) AS t(entity, kind, related_party, disclosed, note)
""")

con.execute("""
CREATE OR REPLACE TABLE finance.restatement_events AS
SELECT * FROM (VALUES
 (DATE '2001-10-16', 'Q3 2001 earnings: $618M loss, $1.2B equity writedown'),
 (DATE '2001-10-22', 'SEC inquiry into related-party transactions announced'),
 (DATE '2001-11-08', '8-K restatement: 1997-2001 earnings reduced ~$586M'),
 (DATE '2001-12-02', 'Chapter 11 bankruptcy filing')
) AS t(event_date, event)
""")

for t in ["staging.emails", "staging.recipients", "staging.employees",
          "curated.comm_edges", "finance.spe_entities", "finance.restatement_events"]:
    n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"{t}: {n:,} rows")
con.close()
print("WAREHOUSE_BUILD_DONE")
