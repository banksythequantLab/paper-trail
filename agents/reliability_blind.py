"""N-run reliability harness for the UNDIRECTED (blind) agent, post Tier-1 fixes.

Runs the same blind directive N times against the live warehouse + DataHub,
keeping the model warm (one load). For each run it counts how many governed
write-backs completed (materialize_evidence -> record_finding_tool -> "ledger
written"). A run PASSES if it recorded >= 1 finding. Emits a manifest of every
analytics table + evidence URN it created so the artifacts can be cleaned up.

    set PAPER_TRAIL_MODEL=qwen3:30b-a3b-instruct-2507-q4_K_M
    .venv\\Scripts\\python.exe agents/reliability_blind.py 5
"""
import asyncio
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("PAPER_TRAIL_MODEL", "qwen3:30b-a3b-instruct-2507-q4_K_M")
# Force the "wrap up" nudge (turn 28) to fire well before the recursion budget
# (140 steps ~= 46 turns), so a wandering run is told to summarize instead of
# being cut off mid-exploration by the hard limit (the run-2 failure mode).
os.environ["PAPER_TRAIL_SUMMARY_TURN"] = "28"

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from agents.graph import _arg_coercion_hook, _local_tools
from agents.run_blind import SYSTEM, DIRECTIVE

MANIFEST = pathlib.Path(__file__).resolve().parents[1] / "data" / "blind_reliability_manifest.json"
_CREATED = re.compile(r"created (analytics\.\w+)")
_LEDGER = re.compile(r"ledger written: evidence=(urn:li:dataset:[^\s]+) task=(urn:li:dataJob:[^\s]+)")


def _scan(messages):
    tables, evidence, jobs, findings = set(), set(), set(), 0
    for m in messages:
        if type(m).__name__ != "ToolMessage":
            continue
        c = str(getattr(m, "content", ""))
        tables.update(_CREATED.findall(c))
        for ev, job in _LEDGER.findall(c):
            evidence.add(ev)
            jobs.add(job)
            findings += 1
    return tables, evidence, jobs, findings


async def main(n):
    tools = _local_tools()
    model = ChatOllama(model=os.environ["PAPER_TRAIL_MODEL"], temperature=0.2,
                       num_ctx=8192, num_predict=1536)
    all_tables, all_ev, all_jobs = set(), set(), set()
    passes = 0
    for i in range(1, n + 1):
        agent = create_react_agent(model, tools, prompt=SYSTEM,
                                   post_model_hook=_arg_coercion_hook(tools))
        try:
            r = await agent.ainvoke({"messages": [("user", DIRECTIVE)]},
                                    {"recursion_limit": 140})
            tables, ev, jobs, findings = _scan(r["messages"])
        except Exception as e:  # noqa: BLE001
            print(f"[run {i}/{n}] ERROR: {e}", flush=True)
            continue
        all_tables |= tables
        all_ev |= ev
        all_jobs |= jobs
        ok = findings >= 1
        passes += 1 if ok else 0
        print(f"[run {i}/{n}] findings_recorded={findings} tables={sorted(tables)} "
              f"-> {'PASS' if ok else 'FAIL'}", flush=True)
    MANIFEST.write_text(json.dumps(
        {"tables": sorted(all_tables), "evidence_urns": sorted(all_ev),
         "job_urns": sorted(all_jobs)}, indent=2))
    print(f"\nRELIABILITY: {passes}/{n} runs completed the governed write-back "
          f"(>=1 finding recorded).", flush=True)
    print(f"manifest: {MANIFEST}", flush=True)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 5))
