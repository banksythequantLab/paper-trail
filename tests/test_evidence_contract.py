"""Tier-1 regression test: the forgiving materialize_evidence contract.
Reproduces the two blind-run stumbles and asserts they now succeed.
Run: .venv\\Scripts\\python.exe -m pytest tests/test_evidence_contract.py -q
"""
import os
import tempfile
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def _fresh_warehouse():
    fd, path = tempfile.mkstemp(suffix=".duckdb")
    os.close(fd)
    os.remove(path)  # let duckdb create it fresh
    os.environ["PAPER_TRAIL_WAREHOUSE"] = path
    return path


def test_normalize_and_strip():
    from agents.tools import warehouse as w
    assert w.normalize_evidence_table("comm_spikes") == "analytics.comm_spikes"
    assert w.normalize_evidence_table("analytics.comm_spikes") == "analytics.comm_spikes"
    assert w.normalize_evidence_table("  `weird-name` ") == "analytics.weird_name"
    assert w.normalize_evidence_table("other.foo") == "analytics.foo"
    assert w.strip_create_wrapper("SELECT 1 AS a") == "SELECT 1 AS a"
    assert w.strip_create_wrapper("WITH x AS (SELECT 1 AS a) SELECT * FROM x").startswith("WITH")
    assert w.strip_create_wrapper(
        "CREATE OR REPLACE TABLE analytics.comm_spikes AS SELECT 1 AS a").strip() == "SELECT 1 AS a"


def test_stumble1_bare_table_name():
    path = _fresh_warehouse()
    import importlib
    from agents.tools import warehouse as w
    importlib.reload(w)
    try:
        n = w.write_evidence("comm_spikes", "SELECT 1 AS a, 2 AS b")  # bare name, was an assert error
        assert n == 1
        cols, rows = w.query("SELECT * FROM analytics.comm_spikes")
        assert rows == [(1, 2)]
    finally:
        os.remove(path)


def test_stumble2_embedded_create():
    path = _fresh_warehouse()
    import importlib
    from agents.tools import warehouse as w
    importlib.reload(w)
    try:
        # model jammed a full CREATE TABLE into select_sql -> was a SQL error
        n = w.write_evidence("comm_spikes",
                             "CREATE TABLE analytics.comm_spikes AS SELECT 42 AS x")
        assert n == 1
        cols, rows = w.query("SELECT x FROM analytics.comm_spikes")
        assert rows == [(42,)]
    finally:
        os.remove(path)


if __name__ == "__main__":
    test_normalize_and_strip()
    test_stumble1_bare_table_name()
    test_stumble2_embedded_create()
    print("ALL_PASS")
