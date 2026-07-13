"""Build a self-contained, offline evidence page for a judge ("juror mode").

Reads ONLY the committed 3 MB fixture (data/fixture_warehouse.duckdb) plus the
committed screenshots, and renders the full chain of custody for the headline
finding into one dependency-free docs/juror.html: the real emails behind the
spike, the verbatim SQL, the re-derived numbers, the 20/20 value gate, and the
native DataHub assertion + incident the finding becomes. No DataHub, no GPU, no
network -- open the file in any browser. Rebuilt deterministically; CI recomputes
the same numbers from the same fixture on every push.

  python ingest/build_juror.py     # -> writes docs/juror.html, prints JUROR_BUILT
"""
import base64
import os
import re
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from verify_golden import run_checks  # noqa: E402

FIX = os.path.join(ROOT, "data", "fixture_warehouse.duckdb")
IMG = os.path.join(ROOT, "docs", "img")
OUT = os.path.join(ROOT, "docs", "juror.html")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def data_uri(name):
    p = os.path.join(IMG, name)
    if not os.path.exists(p):
        return None
    b = base64.b64encode(open(p, "rb").read()).decode()
    return f"data:image/png;base64,{b}"


CSS = """
:root{--ink:#1a1b25;--mut:#5b6072;--line:#e5e7f0;--bg:#f7f8fc;--card:#fff;
--grn:#12855a;--grnbg:#e7f6ee;--red:#b3341f;--redbg:#fbe9e6;--accent:#3b3f8f;--code:#f4f5fb}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:40px 22px 80px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.3px}
h2{font-size:21px;margin:44px 0 12px;padding-top:16px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:20px 0 6px}
p{margin:10px 0}
.sub{color:var(--mut);font-size:15px;margin:0 0 20px}
.lead{font-size:18px;background:var(--card);border:1px solid var(--line);
border-left:4px solid var(--accent);border-radius:8px;padding:16px 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.stat{display:inline-block;background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:10px 14px;margin:6px 8px 6px 0}
.stat b{display:block;font-size:24px;color:var(--accent)}
.stat span{font-size:13px;color:var(--mut)}
.mono,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;
padding:14px;overflow:auto;font-size:13px;line-height:1.5}
.mail{border:1px solid var(--line);border-radius:8px;margin:10px 0;overflow:hidden}
.mail .hd{background:#fbfbff;padding:10px 14px;border-bottom:1px solid var(--line);font-size:14px}
.mail .hd .fromto{font-weight:600}
.mail .hd .subj{color:var(--accent);margin-top:2px}
.mail .bd{padding:10px 14px;color:#3a3d4c;font-size:14px}
.mail .mid{color:var(--mut);font-size:12px;padding:0 14px 10px}
.gate{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px}
.chk{font-size:13.5px;padding:3px 0;border-bottom:1px dashed var(--line)}
.pass{color:var(--grn);font-weight:700}
.badge{display:inline-block;background:var(--grnbg);color:var(--grn);border-radius:20px;
padding:3px 12px;font-size:13px;font-weight:700}
.badge.red{background:var(--redbg);color:var(--red)}
figure{margin:14px 0}
figure img{width:100%;border:1px solid var(--line);border-radius:8px;display:block}
figcaption{color:var(--mut);font-size:13px;margin-top:6px}
a{color:var(--accent)}
.foot{color:var(--mut);font-size:13px;margin-top:40px;border-top:1px solid var(--line);padding-top:16px}
"""


def main():
    con = duckdb.connect(FIX, read_only=True)
    wk, vol, z, dte = con.execute(
        "SELECT week::varchar, vol, zscore, days_to_event "
        "FROM analytics.hunt1_comm_spikes WHERE flagged").fetchone()
    base = con.execute("SELECT round(avg(vol)) FROM analytics.hunt1_comm_spikes "
                       "WHERE week < DATE '2001-08-01'").fetchone()[0]
    msgs = con.execute(
        "SELECT msg_id, min(sent_at)::varchar, min(sender), "
        "string_agg(DISTINCT recipient, ', '), min(subject), min(excerpt) "
        "FROM analytics.hunt1_exhibits GROUP BY msg_id ORDER BY 2, 1").fetchall()
    n_edges = con.execute("SELECT count(*) FROM analytics.hunt1_exhibits").fetchone()[0]
    con.close()

    src = open(os.path.join(ROOT, "hunts", "hunt1_restatement_spikes.py"),
               encoding="utf-8").read()
    sql = re.search(r'SQL\s*=\s*"""(.*?)"""', src, re.S).group(1).strip()

    checks = run_checks(warehouse=FIX)
    n_ok = sum(1 for _, ok, _ in checks if ok)

    wk10 = wk[:10]
    mail_html = ""
    for mid, dt, sender, recips, subj, exc in msgs:
        mail_html += (
            '<div class="mail"><div class="hd">'
            f'<div class="fromto">{esc(sender)} &rarr; {esc(recips)}</div>'
            f'<div class="subj">Subject: {esc(subj)}</div></div>'
            f'<div class="bd">&ldquo;{esc(exc)}&hellip;&rdquo;</div>'
            f'<div class="mid">{esc(dt)} &middot; message-id {esc(mid)}</div></div>')

    gate_html = ""
    for name, ok, detail in checks:
        b = ('<span class="pass">PASS</span>' if ok
             else '<span style="color:var(--red);font-weight:700">FAIL</span>')
        gate_html += f'<div class="chk">{b} &nbsp;{esc(name)}</div>'

    def figure(name, cap):
        uri = data_uri(name)
        if not uri:
            return ""
        return f'<figure><img src="{uri}" alt="{esc(cap)}"><figcaption>{esc(cap)}</figcaption></figure>'

    stats = (
        f'<div class="stat"><b>z = {z}</b><span>vs a ~{int(base)}/week baseline</span></div>'
        f'<div class="stat"><b>{int(vol)} messages</b><span>week of {wk10}</span></div>'
        f'<div class="stat"><b>{len(msgs)} emails</b><span>{n_edges} sender&rarr;recipient edges</span></div>'
        f'<div class="stat"><b>{int(dte)} days</b><span>to the nearest disclosure event</span></div>')

    body = f"""
<div class="wrap">
<h1>Paper Trail &mdash; juror mode</h1>
<p class="sub">The complete chain of custody for the headline finding, rebuilt offline from the
committed 3&nbsp;MB fixture. No DataHub, no GPU, no network. &nbsp;
<a href="https://github.com/banksythequantLab/paper-trail">github.com/banksythequantLab/paper-trail</a></p>

<p class="lead">A metadata catalog is a chain-of-custody machine. Start with a real email:
<b>Jeffrey McMahon</b>, Enron's Treasurer, wrote to the heads of the trading businesses about
&ldquo;2002 Corporate Allocations,&rdquo; eight days before Enron announced a ~$618M Q3 loss
(Oct&nbsp;16&nbsp;2001). Paper Trail finds the statistical anomaly that surfaces that week, then
writes the finding back into DataHub as a walkable evidence ledger &mdash; and everything below is
re-derived, right now, from data committed to the repo.</p>

<div style="margin:18px 0">{stats}</div>

<h2>1 &middot; The finding</h2>
<p>Weekly Finance/Accounting&nbsp;&harr;&nbsp;Trading cross-department email volume, z-scored against a
Jan&nbsp;2000&ndash;Jul&nbsp;2001 baseline of ~{int(base)}/week. One week in the Aug&ndash;Dec&nbsp;2001
disclosure window breaches the threshold: <b>{wk10}</b>, {int(vol)} messages, <b>z&nbsp;=&nbsp;{z}</b>
&mdash; the window around Enron's Q3 loss announcement (Oct&nbsp;16), SEC inquiry (Oct&nbsp;22), and
restatement 8-K (Nov&nbsp;8).</p>

<h2>2 &middot; The emails behind the number</h2>
<p>The spike isn't a black-box verdict. These are the actual messages from the real, public CMU Enron
corpus that constitute that week's cross-department traffic &mdash; the leaf of the chain of custody:</p>
{mail_html}

<h2>3 &middot; The derivation (verbatim SQL)</h2>
<p>The exact query that produced the evidence table, captured as the producing task's definition in
DataHub. Run against the fixture it re-derives {int(vol)} messages / z&nbsp;=&nbsp;{z} for {wk10}:</p>
<pre>{esc(sql)}</pre>

<h2>4 &middot; The value gate ({n_ok}/{len(checks)} passing)</h2>
<p>Every headline number across all five hunts, re-derived from this fixture and checked against the
committed <span class="mono">ingest/golden.yaml</span>. A value regression (the z-score silently drifting
off {z}) fails the gate even when the SQL and lineage still look right. <span class="badge">{n_ok}/{len(checks)} PASS</span></p>
<div class="gate">{gate_html}</div>

<h2>5 &middot; What it becomes in DataHub</h2>
<p>The same gate is published as a native custom <b>Assertion</b> on the evidence dataset, and confirming
a finding raises a native <b>Incident</b> on the <i>implicated production table</i> &mdash; not the
evidence table &mdash; resolvable in the UI. These are DataHub's own primitives, driven by the review workflow:</p>
{figure("10-assertion.png", "The value gate as a passing native DataHub assertion in the evidence dataset's Validation tab.")}
{figure("11-incident-finance.png", "A confirmed finding raises a Fraud-Investigation Incident on finance.spe_entities (owned by the departed CAO), resolvable in the UI.")}
{figure("06-exhibits-lineage.png", "Lineage: the finding and staging.emails both feed the exhibit task, so the walk ends on the raw corpus.")}

<h2>6 &middot; Honest labeling</h2>
<p>Paper Trail runs on a <b>faithful reconstruction</b> of the Enron case, not a blind rediscovery of it.
The email corpus is the real, public CMU Enron dataset (435,259 messages). The <span class="mono">finance.*</span>
tables (ownership, the SPE registry, restatement events) are reconstructed from the public record and labeled
as such in DataHub. The contribution is the <b>auditable investigation pattern</b> &mdash; every conclusion
carried as walkable, reviewable evidence metadata &mdash; which generalizes to any governed warehouse. We do
<b>not</b> claim an agent discovered the fraud from scratch; an undirected agent run is logged honestly in
<span class="mono">docs/blind_test_log.md</span>.</p>

<h2>7 &middot; Reproduce this page</h2>
<p>Everything above is built from <span class="mono">data/fixture_warehouse.duckdb</span> (3&nbsp;MB, committed) and
recomputed by CI on every push &mdash; no GPU, no DataHub:</p>
<pre>pip install duckdb pyyaml
PAPER_TRAIL_WAREHOUSE=data/fixture_warehouse.duckdb python ingest/recompute_hunt1.py   # z={z} re-derived
PAPER_TRAIL_WAREHOUSE=data/fixture_warehouse.duckdb python ingest/verify_golden.py      # {n_ok}/{len(checks)} gate
python ingest/build_juror.py                                                            # rebuilds this page</pre>

<div class="foot">Generated by <span class="mono">ingest/build_juror.py</span> from the committed fixture.
Numbers on this page are re-derived at build time, not hand-written.</div>
</div>
"""

    html = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Paper Trail &mdash; juror mode</title><style>" + CSS
            + "</style></head><body>" + body + "</body></html>")
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"JUROR_BUILT {OUT} ({len(html)} bytes)")
    print(f"  finding: week={wk10} vol={int(vol)} z={z} days_to_event={int(dte)} baseline={int(base)}")
    print(f"  exhibits: {len(msgs)} messages / {n_edges} edges")
    print(f"  gate: {n_ok}/{len(checks)} checks pass")
    assert n_ok == len(checks), "gate not fully passing on fixture"
    assert round(float(z), 2) == 4.43, f"unexpected z {z}"


if __name__ == "__main__":
    main()
