"""Paper Trail week-1 milestone: DataHub MCP server smoke test.
Launches mcp-server-datahub over stdio, lists tools, runs a search
for the evidence dataset emitted by smoke_roundtrip.py.
"""
import asyncio, os, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = r"B:\paper-trail\.venv\Scripts\mcp-server-datahub.exe"
ENV = {
    **os.environ,
    "DATAHUB_GMS_URL": "http://localhost:8080",
    "DATAHUB_GMS_TOKEN": "",
    "TOOLS_IS_MUTATION_ENABLED": "true",
    "PYTHONIOENCODING": "utf-8",
}

async def main():
    params = StdioServerParameters(command=SERVER, args=[], env=ENV)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"[1/2] MCP server up. {len(names)} tools:")
            print("  " + ", ".join(names))
            mutation = [n for n in names if n in (
                "add_tags", "update_description", "save_document",
                "create_glossary_term", "add_terms", "add_owners")]
            print(f"  mutation tools enabled: {mutation}")
            try:
                r = await session.call_tool("search", {"query": "smoke_evidence_set"})
                txt = "".join(c.text for c in r.content if hasattr(c, "text"))
                hit = "smoke_evidence_set" in txt
                print(f"[2/2] search executed; found evidence dataset: {hit}")
                if not hit:
                    print("  raw (first 500): " + txt[:500])
            except Exception as e:
                print(f"[2/2] search call failed: {e}")
            print("MCP_SMOKE_DONE")

asyncio.run(main())
