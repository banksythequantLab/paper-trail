"""Read-only DuckDB access for analyst agents + evidence writer."""
import duckdb

WAREHOUSE = r"B:\paper-trail\data\warehouse.duckdb"

def query(sql: str, params=None):
    """Run read-only SQL, return (columns, rows)."""
    con = duckdb.connect(WAREHOUSE, read_only=True)
    try:
        cur = con.execute(sql, params or [])
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        con.close()

def write_evidence(table: str, create_sql: str):
    """Materialize an evidence table in the analytics schema. Returns row count."""
    assert table.startswith("analytics."), "evidence tables live in analytics schema"
    con = duckdb.connect(WAREHOUSE)
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        con.execute(f"CREATE OR REPLACE TABLE {table} AS {create_sql}")
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        con.close()

def describe(table: str):
    con = duckdb.connect(WAREHOUSE, read_only=True)
    try:
        return con.execute(f"DESCRIBE {table}").fetchall()
    finally:
        con.close()
