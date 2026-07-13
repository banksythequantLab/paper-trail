"""UNDIRECTED (blind) agent run — the honesty test.

Unlike agents/run_gate.py (a directed run where the brief specifies the method),
this hands the agent only the schema and a generic goal: "inspect the stack for
anomalies or governance failures — no hypothesis, no method." The agent decides
what to look at, writes its own SQL, materializes evidence, and records findings.
It dumps the full message trace (every tool call + result) so the run can be
logged verbatim in docs/blind_test_log.md — successes and stumbles alike.

    python agents/run_blind.py > docs/blind_test_log.txt 2>&1
"""
import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("PAPER_TRAIL_MODEL", "qwen3:30b-a3b-instruct-2507-q4_K_M")
os.environ.setdefault("PAPER_TRAIL_SUMMARY_TURN", "30")  # let it explore before summarizing

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from agents.graph import _arg_coercion_hook, _local_tools

SYSTEM = (
    "You are Paper Trail, a forensic data investigator with tools on a DuckDB warehouse: "
    "run_sql (read-only SELECT), materialize_evidence(table, select_sql) which runs "
    "CREATE TABLE analytics.<table> AS <select_sql>, and record_finding_tool(hunt_id, title, "
    "narrative, sql, evidence_table, input_tables, confidence) which writes a finding to the "
    "DataHub ledger (evidence_table must already exist — materialize it first). Schemas: "
    "staging.emails(id,msg_id,sender,sent_at,subject,body,mailbox,folder), "
    "staging.recipients(email_id,addr), staging.employees(addr,name,title,dept), "
    "curated.comm_edges(sender,recipient,week,n), finance.spe_entities(name,...), "
    "finance.restatement_events(event_date,...), analytics.* (your outputs). Use schema.table "
    "names directly. Explore the data yourself and decide what is worth investigating. When a "
    "tool errors, fix the arguments; never repeat an identical call. End with a FINDINGS summary "
    "of what you actually found and how confident you are."
)

DIRECTIVE = (
    "Inspect this data stack for anomalies, suspicious patterns, or data-governance failures. "
    "You are given NO hypothesis and NO method — decide for yourself what to look at. Start by "
    "exploring the tables with run_sql, then investigate whatever looks off. Materialize anything "
    "notable as an analytics.<name> table and record real findings with record_finding_tool. "
    "Then report what you found and how confident you are."
)


def _dump(messages):
    for m in messages:
        t = type(m).__name__
        tcs = getattr(m, "tool_calls", None)
        if tcs:
            for tc in tcs:
                print(f"\n[AGENT -> {tc['name']}]  {str(tc.get('args'))[:600]}", flush=True)
        elif t == "ToolMessage":
            print(f"[TOOL RESULT]  {str(getattr(m, 'content', ''))[:600]}", flush=True)
        elif t == "HumanMessage":
            print(f"[DIRECTIVE]  {str(m.content)[:400]}", flush=True)
        elif t == "AIMessage" and getattr(m, "content", ""):
            print(f"\n=== AGENT FINAL / MESSAGE ===\n{m.content}", flush=True)


async def main():
    tools = _local_tools()
    model = ChatOllama(model=os.environ["PAPER_TRAIL_MODEL"], temperature=0.2,
                       num_ctx=8192, num_predict=1536)
    agent = create_react_agent(model, tools, prompt=SYSTEM,
                               post_model_hook=_arg_coercion_hook(tools))
    r = await agent.ainvoke({"messages": [("user", DIRECTIVE)]}, {"recursion_limit": 60})
    print("\n\n########## FULL BLIND-RUN TRACE ##########", flush=True)
    _dump(r["messages"])
    print("\n########## END TRACE ##########", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
