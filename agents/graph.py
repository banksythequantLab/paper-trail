"""Paper Trail agent graph. LLM mode runs a LangGraph agent (local Ollama
model) wired to DataHub MCP tools + warehouse SQL. Deterministic mode runs the
scripted hunts (hunts/*.py) with the same scribe write-back.
Model override: PAPER_TRAIL_MODEL env var (default qwen3:30b-a3b-instruct-2507-q4_K_M).
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
   present a finding as confirmed.
6. TOOL CALL HYGIENE: omit optional parameters unless you need them. The
   search tool's `filter` is a DSL STRING, not JSON — e.g.
   entity_type = 'dataset' AND platform = 'duckdb'. `sort_by` is a plain
   field-name string. When a tool errors, change your arguments — never
   repeat the same call."""

def _local_tools():
    """LangChain tools wrapping the warehouse + ledger."""
    from langchain_core.tools import tool
    from agents.tools import warehouse, ledger

    @tool
    def run_sql(sql: str) -> str:
        """Run read-only SQL against the investigation warehouse (DuckDB).
        Schemas: staging.emails/recipients/employees, curated.comm_edges,
        finance.spe_entities/restatement_events, analytics.* (evidence).
        Use schema.table names directly (finance.spe_entities) -- there is
        NO paper_trail catalog prefix in the warehouse."""
        try:
            cols, rows = warehouse.query(sql)
        except Exception as e:
            return f"SQL ERROR (fix the query and retry): {e}"
        head = rows[:50]
        return f"columns: {cols}\nrows ({len(rows)} total, showing {len(head)}):\n" + \
               "\n".join(str(r) for r in head)

    @tool
    def materialize_evidence(table: str, select_sql: str) -> str:
        """Materialize evidence: CREATE TABLE analytics.<table> AS <select_sql>."""
        try:
            n = warehouse.write_evidence(table, select_sql)
        except Exception as e:
            return f"SQL ERROR (fix the query and retry): {e}"
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

def _arg_coercion_hook(tools):
    """Local models often pass dicts where MCP tool schemas want JSON strings.
    Coerce dict/list args to json.dumps(...) when the schema type is string."""
    import json
    schemas = {t.name: (t.args or {}) for t in tools}
    def _is_stringy(spec):
        if spec.get("type") == "string":
            return True
        return any(alt.get("type") == "string"
                   for alt in spec.get("anyOf", []) + spec.get("oneOf", []))
    def hook(state):
        last = state["messages"][-1]
        for tc in getattr(last, "tool_calls", None) or []:
            props = schemas.get(tc["name"], {})
            args = tc.get("args") or {}
            # search.filter wants a DSL string; translate flat dicts.
            if tc["name"] == "search":
                f = args.get("filter")
                if isinstance(f, dict) and all(isinstance(v, str) for v in f.values()):
                    args["filter"] = " AND ".join(f"{k} = '{v}'" for k, v in f.items())
                if isinstance(args.get("sort_by"), (dict, list)):
                    args.pop("sort_by")
            for k, v in list(args.items()):
                spec = props.get(k, {})
                ptype = spec.get("type") or next(
                    (a.get("type") for a in spec.get("anyOf", []) + spec.get("oneOf", [])
                     if a.get("type") not in (None, "null")), None)
                if ptype == "array":
                    if isinstance(v, dict):
                        args[k] = list(v.values())
                    elif isinstance(v, str):
                        args[k] = [v]
                elif isinstance(v, (dict, list)) and _is_stringy(spec):
                    args[k] = json.dumps(v)
        return {"messages": [last]}
    return hook

async def build_agent():
    """LLM-mode agent: Claude + DataHub MCP tools + warehouse tools."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_ollama import ChatOllama
    from langgraph.prebuilt import create_react_agent
    client = MultiServerMCPClient(MCP_CONFIG)
    tools = await client.get_tools() + _local_tools()
    model = ChatOllama(
        model=os.getenv("PAPER_TRAIL_MODEL", "qwen3:30b-a3b-instruct-2507-q4_K_M"),
        temperature=0,
        num_ctx=int(os.getenv("PAPER_TRAIL_NUM_CTX", "32768")),
        num_predict=int(os.getenv("PAPER_TRAIL_NUM_PREDICT", "2048")),
    )
    return create_react_agent(model, tools, prompt=SYSTEM,
                              post_model_hook=_arg_coercion_hook(tools))

async def investigate(directive: str, stream: bool = False):
    import sys
    agent = await build_agent()
    inputs = {"messages": [("user", directive)]}
    config = {"recursion_limit": 40}
    if not stream:
        result = await agent.ainvoke(inputs, config)
        return result["messages"][-1].content
    last = None
    async for update in agent.astream(inputs, config, stream_mode="updates"):
        for node, payload in update.items():
            for msg in (payload or {}).get("messages", []):
                msg.pretty_print()
                sys.stdout.flush()
                last = msg
    return last.content if last is not None else ""

if __name__ == "__main__":
    import sys
    asyncio.run(investigate(" ".join(sys.argv[1:]) or
        "Ground yourself: what financially-material tables exist and who owns them?",
        stream=True))
