"""Paper Trail agent graph. LLM mode (ANTHROPIC_API_KEY set) runs a LangGraph
agent wired to DataHub MCP tools + warehouse SQL. Deterministic mode runs the
scripted hunts (hunts/*.py) with the same scribe write-back.
"""
import os, asyncio, pathlib
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

VENV = r"B:\paper-trail\.venv\Scripts"
MCP_CONFIG = {
    "datahub": {
        "transport": "stdio",
        "command": rf"{VENV}\mcp-server-datahub.exe",
        "args": [],
        "env": {
            "DATAHUB_GMS_URL": os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"),
            "DATAHUB_GMS_TOKEN": os.getenv("DATAHUB_GMS_TOKEN", ""),
            "TOOLS_IS_MUTATION_ENABLED": "true",
        },
    }
}

SYSTEM = """You are Paper Trail, a forensic data investigator. Rules:
1. GROUND FIRST: before any analysis, use DataHub tools (search, get_entities,
   list_schema_fields, get_lineage) to understand tables, ownership, sensitivity
   terms, and quality caveats. Never guess a schema.
2. RESPECT SENSITIVITY: note when you touch PII / RestrictedPeriod /
   FinanciallyMaterial data; explain why it was necessary.
3. EVIDENCE OR SILENCE: every claim must cite an evidence table you materialized
   and the exact SQL that produced it.
4. WRITE BACK: record findings via the ledger (record_finding) and update_description /
   add_tags so the next investigator inherits your work.
5. Findings are tagged pending-review; a human confirms or rejects. Never
   present a finding as confirmed."""

def _local_tools():
    """LangChain tools wrapping the warehouse + ledger."""
    from langchain_core.tools import tool
    from agents.tools import warehouse, ledger

    @tool
    def run_sql(sql: str) -> str:
        """Run read-only SQL against the investigation warehouse (DuckDB).
        Schemas: staging.emails/recipients/employees, curated.comm_edges,
        finance.spe_entities/restatement_events, analytics.* (evidence)."""
        cols, rows = warehouse.query(sql)
        head = rows[:50]
        return f"columns: {cols}\nrows ({len(rows)} total, showing {len(head)}):\n" + \
               "\n".join(str(r) for r in head)

    @tool
    def materialize_evidence(table: str, select_sql: str) -> str:
        """Materialize evidence: CREATE TABLE analytics.<table> AS <select_sql>."""
        n = warehouse.write_evidence(table, select_sql)
        return f"created {table} with {n} rows"

    @tool
    def record_finding_tool(hunt_id: str, title: str, narrative: str, sql: str,
                            evidence_table: str, input_tables: list[str],
                            confidence: str) -> str:
        """Record a finding in the DataHub ledger with lineage. input_tables are
        warehouse tables the SQL read from. confidence: low|medium|high."""
        ev, job = ledger.record_finding(hunt_id, title, narrative, sql,
                                        evidence_table, input_tables, confidence=confidence)
        return f"ledger written: evidence={ev} task={job}"

    return [run_sql, materialize_evidence, record_finding_tool]

async def build_agent():
    """LLM-mode agent: Claude + DataHub MCP tools + warehouse tools."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_anthropic import ChatAnthropic
    from langgraph.prebuilt import create_react_agent
    client = MultiServerMCPClient(MCP_CONFIG)
    tools = await client.get_tools() + _local_tools()
    model = ChatAnthropic(model=os.getenv("PAPER_TRAIL_MODEL", "claude-sonnet-5"))
    return create_react_agent(model, tools, prompt=SYSTEM)

async def investigate(directive: str):
    agent = await build_agent()
    result = await agent.ainvoke({"messages": [("user", directive)]})
    return result["messages"][-1].content

if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("LLM mode needs ANTHROPIC_API_KEY in B:\\paper-trail\\.env; "
                         "deterministic hunts run via hunts/*.py")
    import sys
    print(asyncio.run(investigate(" ".join(sys.argv[1:]) or
        "Ground yourself: what financially-material tables exist and who owns them?")))
