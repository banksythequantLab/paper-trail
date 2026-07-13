"""CI / offline reproducibility check — no DataHub, no GPU.

Reads the *canonical* hunt-1 SQL straight out of hunts/hunt1_restatement_spikes.py
(so it can't drift from the real hunt), runs it against the fixture warehouse's
SOURCE tables (curated.comm_edges + staging.employees + finance.restatement_events),
and asserts it reproduces the golden peak: week 2001-10-08, vol 18, z = 4.43.

Proves the flagship number is *derived from data*, not merely a stored table.

  python ingest/recompute_hunt1.py     # -> RECOMPUTE_PASS
"""
import os
import pathlib
import re
import sys

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
WAREHOUSE = os.getenv("PAPER_TRAIL_WAREHOUSE", str(ROOT / "data" / "fixture_warehouse.duckdb"))

src = (ROOT / "hunts" / "hunt1_restatement_spikes.py").read_text(encoding="utf-8")
m = re.search(r'SQL\s*=\s*"""(.*?)"""', src, re.S)
if not m:
    print("FAIL: could not extract hunt-1 SQL from hunts/hunt1_restatement_spikes.py")
    sys.exit(1)
SQL = m.group(1)

con = duckdb.connect(WAREHOUSE, read_only=True)
rows = con.execute(SQL).fetchall()
cols = [d[0] for d in con.description]
fi = cols.index("flagged")
flagged = [r for r in rows if r[fi]]

if len(flagged) != 1:
    print(f"FAIL: expected exactly 1 flagged week, got {len(flagged)}: {flagged}")
    sys.exit(1)

wk, vol, z = flagged[0][0], flagged[0][1], round(float(flagged[0][2]), 2)
print(f"recomputed hunt-1 from fixture source: week={str(wk)[:10]} vol={int(vol)} zscore={z}")

ok = str(wk)[:10] == "2001-10-08" and int(vol) == 18 and z == 4.43
if not ok:
    print("RECOMPUTE_FAIL: does not match golden (2001-10-08, 18, 4.43)")
    sys.exit(1)
print("RECOMPUTE_PASS: hunt-1 z=4.43 reproduced from source data (no DataHub, no GPU)")
