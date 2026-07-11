# PAPER TRAIL — Demo Runbook (Devpost, deadline Aug 10 2026)

One page: what to check, what to show, what to say. All commands verified 2026-07-11.

## Pre-flight (15 min before recording)

1. Docker Desktop running (launch via `explorer.exe` shortcut, NOT a bare shell — env gets stripped).
2. DataHub healthy: `Invoke-WebRequest http://localhost:9002/health` → 200. Login datahub/datahub.
3. Free the GPU: `nvidia-smi` — kill anything holding VRAM (watch for stray python
   processes ~8GB). Agent needs ~20GB for qwen3-30b at 32k ctx.
4. Warm the model so the demo doesn't stall on load (~90s):
   `ollama run qwen3:30b-a3b-instruct-2507-q4_K_M "ready" --keepalive 60m`
5. Case board up: check http://localhost:8601 (streamlit, usually already running).
6. Kill stale agent runs: `Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
   Where-Object {$_.CommandLine -like '*agents.graph*'} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`

## Shot list (~3 min video)

**Shot 1 — The hook (30s).** DataHub UI (localhost:9002), open
`analytics.hunt1_comm_spikes`. Say: "Eight days before Enron announced the
$618M loss, exec email traffic between Finance and Trading spiked to 3.6x
baseline — z-score 4.43. An agent found this, and everything it found is
sitting in the catalog as governed metadata."

**Shot 2 — Provenance walk (45s).** From the evidence dataset, click Lineage.
Walk: evidence table → producing task (exact SQL in custom properties) →
comm_edges → staging → raw corpus. Say: "Every claim traces to raw evidence.
No black box."

**Shot 3 — Live agent (60s).** Terminal:
`cd B:\paper-trail; .\.venv\Scripts\python.exe -m agents.graph "Ground yourself: what financially-material tables exist and who owns them?"`
Runs on a LOCAL qwen3-30b via Ollama — no API, no cloud. It searches the
catalog, reads entities, walks lineage, queries the warehouse, self-corrects
SQL errors, ends with a FINDINGS summary naming Fastow/Causey-owned
uncertified tables. (Full run ~15-20 min: pre-record and time-lapse, or cut
between the 3 best exchanges from agent_run.log.)

**Shot 4 — Human in the loop (30s).** Case board (localhost:8601): five hunt
tabs, review states. Show a finding flip pending-review → confirmed; point at
the reviewed_by/review_note properties landing in DataHub.

**Shot 5 — Close (15s).** PR datahub-skills#34: "The investigation pattern is
upstreamed as a reusable skill."

## Talking points / numbers

- 435K emails, DuckDB warehouse, DataHub v1.5.0.6 quickstart (OSS)
- 5 hunts, all findings ledgered with lineage + producing SQL
- Hunt 1: z=4.43 spike week of 2001-10-08, 8 days pre-announcement
- Agent: LangGraph + 18 DataHub MCP tools + 3 warehouse tools, fully local
- Coercion shim makes a 30B local model reliable at MCP tool calls

## Known quirks

- First model load ~90s; each agent turn 1-3 min. Never demo cold.
- qwen3-coder:30b does NOT work as backend (text tool calls) — a3b only.
- CLI emoji crash: set PYTHONIOENCODING=utf-8 first.
- Agent transcripts land in agent_run.log (gitignored).
