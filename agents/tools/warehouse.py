"""Read-only DuckDB access for analyst agents + evidence writer."""
import os
import re
import duckdb

WAREHOUSE = os.getenv("PAPER_TRAIL_WAREHOUSE", r"B:\paper-trail\data\warehouse.duckdb")

_IDENT = re.compile(r"[^A-Za-z0-9_]")
_CREATE_AS = re.compile(r"(?is)^\s*create\s+(?:or\s+replace\s+)?(?:table|view)\b.*?\bas\b\s+(.*)$")

def normalize_evidence_table(table: str) -> str:
    """Forgiving: accept a bare name ('comm_spikes'), a wrong-schema name, or a
    quoted/backticked name, and always return 'analytics.<safe_name>'. The blind
    agent's #1 stumble was passing a bare table name; this removes that footgun."""
    t = (table or "").strip().strip('`"[]').strip()
    name = t.split(".")[-1].strip().strip('`"[]')  # drop any schema prefix
    name = _IDENT.sub("_", name).strip("_")
    if not name:
        raise ValueError(f"could not derive a table name from {table!r}")
    return f"analytics.{name}"

def strip_create_wrapper(create_sql: str) -> str:
    """Forgiving: if the model embeds a full 'CREATE [OR REPLACE] TABLE x AS <select>'
    into select_sql (blind agent's #2 stumble), keep only the trailing SELECT/CTE.
    A plain SELECT or 'WITH ... SELECT' passes through unchanged."""
    s = (create_sql or "").strip().rstrip(";").strip()
    m = _CREATE_AS.match(s)
    if m:
        s = m.group(1).strip().rstrip(";").strip()
    return s

def query(sql: str, params=None):
    """Run read-only SQL, return (columns, rows)."""
    con = duckdb.connect(WAREHOUSE, read_only=True)
    try:
        cur = con.execute(sql, params or [])
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        con.close()

def write_evidence(table: str, create_sql: str):
    """Materialize an evidence table in the analytics schema. Accepts a bare or
    prefixed table name and a plain SELECT or a full CREATE...AS statement.
    Returns row_count (back-compatible with the deterministic hunts)."""
    table = normalize_evidence_table(table)
    select_sql = strip_create_wrapper(create_sql)
    con = duckdb.connect(WAREHOUSE)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        con.execute(f"CREATE OR REPLACE TABLE {table} AS {select_sql}")
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        con.close()

def describe(table: str):
    con = duckdb.connect(WAREHOUSE, read_only=True)
    try:
        return con.execute(f"DESCRIBE {table}").fetchall()
    finally:
        con.close()
