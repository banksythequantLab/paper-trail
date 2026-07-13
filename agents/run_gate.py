"""Run the LLM agent through the value gate.

Given the hunt-1 investigation brief (the analytical method, in prose -- not the
SQL), the local LLM agent autonomously writes the SQL, materializes the evidence
table (analytics.hunt1_comm_spikes), records the finding to the DataHub ledger,
and reports the result. It reliably identifies the correct anomaly: the week of
2001-10-08, with a z-score around 4.5.

`ingest/verify_golden.py` then gates that output against the canonical numbers.
The agent's self-written SQL derives the baseline slightly differently than the
deterministic hunt (it lands z=4.55 vs the golden 4.43), so the exact-match gate
FLAGS the difference -- which is exactly what a value gate is for. Pin the exact
method (feed the canonical SQL in the brief) and the agent's output matches
golden 20/20 (verified by dropping analytics.hunt1_comm_spikes and having the
agent rebuild it from scratch).

So this proves two things at once: the agent's execute -> write-back ->
self-report loop is reliable and independently verifiable, AND the value gate has
real teeth -- it catches even the agent's own near-miss. It uses the local
warehouse + ledger tools; the full DataHub-MCP-grounded agent is in
agents/graph.py (best-effort on a local 30B). Swap models via PAPER_TRAIL_MODEL.

    python agents/run_gate.py            # then: python ingest/verify_golden.py
"""
import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("PAPER_TRAIL_MODEL", "qwen3:30b-a3b-instruct-2507-q4_K_M")

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from agents.graph import _arg_coercion_hook, _local_tools

SYSTEM = (
    "You are Paper Trail, a forensic data investigator on a DuckDB warehouse. Tools: "
    "run_sql (read-only SELECT), materialize_evidence(table, select_sql) which runs "
    "CREATE TABLE analytics.<table> AS <select_sql>, and record_finding_tool which writes the "
    "finding to the DataHub ledger. Schemas: staging.employees(addr,name,title,dept), "
    "curated.comm_edges(sender,recipient,week,n), finance.restatement_events(event_date,...). "
    "Use schema.table names directly. Work efficiently and never repeat an identical tool call. "
    "Your FINAL message must be a short FINDINGS summary naming the peak week and its z-score."
)

DIRECTIVE = (
    "Investigate whether cross-department email volume between Finance/Accounting and Trading "
    "spiked around Enron's late-2001 disclosure window, and write the result to the ledger.\n"
    "Approach: split addresses by staging.employees.dept into Finance/Accounting vs Trading; for "
    "each week, sum cross-department message volume (curated.comm_edges.n) in BOTH directions; "
    "compute a z-score of each week's volume against a baseline of weeks BETWEEN DATE '2000-01-01' "
    "AND DATE '2001-07-31' using the mean and the SAMPLE standard deviation (stddev_samp); flag "
    "weeks on or after DATE '2001-08-01' with z-score >= 2.0.\n"
    "Materialize the result as analytics.hunt1_comm_spikes with columns (week, vol, zscore, flagged) "
    "covering weeks BETWEEN DATE '2000-01-01' AND DATE '2001-12-31', with zscore ROUNDED to 2 decimals. "
    "Then call record_finding_tool(hunt_id='hunt1_restatement_spikes', title='Anomalous Finance-Trading "
    "communication surge in restatement window', narrative=<one sentence>, sql=<your SQL>, "
    "evidence_table='analytics.hunt1_comm_spikes', input_tables=['curated.comm_edges','staging.employees',"
    "'finance.restatement_events'], confidence='medium'). Report the peak week and its z-score."
)


async def main():
    tools = _local_tools()
    model = ChatOllama(model=os.environ["PAPER_TRAIL_MODEL"], temperature=0.1,
                       num_ctx=8192, num_predict=1536)
    agent = create_react_agent(model, tools, prompt=SYSTEM,
                               post_model_hook=_arg_coercion_hook(tools))
    r = await agent.ainvoke({"messages": [("user", DIRECTIVE)]}, {"recursion_limit": 50})
    print("=== AGENT FINDINGS ===", flush=True)
    print(r["messages"][-1].content, flush=True)
    print("=== AGENT RUN COMPLETE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
