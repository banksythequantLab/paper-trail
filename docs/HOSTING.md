# Paper Trail — Hosting Plan

**Decision (2026-07-11):** For judging, the recorded **video is the primary artifact**. If we provide a live link, we host **only the web tier** (DataHub catalog + Streamlit case board) always-on for the judging window — **no live GPU**. An API-backed agent is an optional add-on for on-demand live runs.

## Judging window (Devpost)

| Period | When (EDT) |
| --- | --- |
| Submissions close | Aug 10, 5:00 pm |
| **Judging** | **Aug 17 → Aug 31** (async) |
| Winners announced | Sep 8 |

Judges review asynchronously across the **two-week** window — we never know the exact moment. So anything "live" must stay up and healthy the whole time, unattended.

## Why no live GPU

The qwen3-30b agent needs ~24 GB VRAM. Keeping a rented GPU up 24/7 for the two-week window is ~$150+ and risks being wedged the one time a judge clicks. Scale-to-zero serverless reloads ~20 GB of weights on cold start (tens of seconds to minutes) — bad for a single click. And the catalog + case board don't need the agent to be **browsable**: the findings are already materialized in DataHub + DuckDB from recorded runs.

## Architecture

- **Tier A — always-on, judge-facing (host this):** DataHub UI (`:9002`) + GMS (`:8080`) + the Streamlit case board (`:8601`), reading pre-materialized findings from `data/warehouse.duckdb`. No GPU. Fronted by a Cloudflare Tunnel for a clean HTTPS URL.
- **Tier B — optional, on-demand agent:** either (default) *pre-recorded* in the video, or *API-backed* (swap Ollama → a hosted Qwen3 endpoint) so a judge can trigger a live run for pennies with no idle cost.

## Cost

| Item | Rough cost |
| --- | --- |
| 16 GB CPU VM (Hetzner/DO/Fly), ~2–3 wks | **$15–50** |
| Cloudflare Tunnel | free |
| Optional: Qwen3-30B API (DeepInfra/OpenRouter) | ~$0.12/M in, ~$0.50/M out → pennies/run |
| (Avoided) A40 GPU 24/7 × 2 wks | ~$150 |

## Deploy — web tier (Tier A)

1. **VM:** Ubuntu 22.04, ≥16 GB RAM (DataHub's Elasticsearch/Kafka are the hogs), Docker + Compose.
2. **DataHub:** bring up the v1.5.0.6 quickstart on the box (`datahub docker quickstart`, or your local compose file). Verify `:9002` (UI) and `:8080` (GMS). **Change the default `datahub/datahub` login before exposing it.**
3. **Load findings:** copy `data/warehouse.duckdb` to the VM, then replay ingestion + the ledger writes **on the box** (so `localhost:8080` = the hosted GMS) — see the `ledger.py` note below.
4. **Case board:** `streamlit run ui/case_board.py --server.headless true --server.port 8601`, pointed at the copied DuckDB (see `warehouse.py` note).
5. **Cloudflare Tunnel:** install `cloudflared`, create a tunnel, route `catalog.<domain>` → `localhost:9002` and `board.<domain>` → `localhost:8601`. Optionally gate with Cloudflare Access so only judges get in.
6. **Verify by Aug 17:** open both URLs in an incognito browser; confirm lineage + case board render with findings.

## Portability (env vars)

These local paths are now **env-overridable**; defaults equal the Windows box, so nothing changes locally. On a Linux host, set:

| Env var | Overrides | Default |
| --- | --- | --- |
| `PAPER_TRAIL_WAREHOUSE` | DuckDB path (`warehouse.py`) | `B:\paper-trail\data\warehouse.duckdb` |
| `DATAHUB_GMS_URL` | GMS URL (`ledger.py` + agent MCP) | `http://localhost:8080` |
| `PAPER_TRAIL_VENV` | venv bin dir (`graph.py`) | `B:\paper-trail\.venv\Scripts` |
| `PAPER_TRAIL_MCP_DATAHUB` | full path to `mcp-server-datahub` (`graph.py`) | `<VENV>\mcp-server-datahub.exe` |

For the always-on catalog you only need `PAPER_TRAIL_WAREHOUSE` (the case board). `PAPER_TRAIL_VENV` / `PAPER_TRAIL_MCP_DATAHUB` matter only if you host the live agent (Tier B) — e.g. `.venv/bin/mcp-server-datahub` on Linux. If the findings replay runs on the box, `DATAHUB_GMS_URL` can stay default.

## Optional — API-backed live agent (Tier B)

Point the model at a hosted Qwen3 endpoint so judges can trigger a live run with no GPU:

```python
# graph.py — swap ChatOllama for an OpenAI-compatible endpoint
from langchain_openai import ChatOpenAI
class RetryingChat(ChatOpenAI):            # keep the x3 retry wrapper
    async def _agenerate(self, *a, **k):
        last = None
        for _ in range(3):
            try: return await super()._agenerate(*a, **k)
            except Exception as e: last = e
        raise last

model = RetryingChat(
    model="qwen/qwen3-30b-a3b",                 # provider's model id
    base_url=os.getenv("OPENAI_BASE_URL"),      # e.g. https://openrouter.ai/api/v1
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.2, max_tokens=2048)
```

Providers: DeepInfra / OpenRouter / Together (~$0.12/M in, ~$0.50/M out). Trade-off: it's a cloud API, so it dents the "fully local" claim — keep that claim in the **video**, which runs on the local Ollama box.

## Pre-submission checklist (with the runbook)

- [ ] Video recorded (local qwen3-30b agent, per `DEMO_RUNBOOK.md`)
- [ ] Repo public; README + this file included
- [ ] (If live link) Tier A up + verified by **Aug 17**; default creds changed; tunnel stable
- [ ] Skill PR datahub-skills#34 linked in the write-up

## References

- Devpost schedule: <https://datahub.devpost.com/details/dates>
- Qwen3-30B-A3B API pricing: <https://openrouter.ai/qwen/qwen3-30b-a3b>
- Cloud GPU price comparison: <https://klymentiev.com/blog/runpod-vs-lambda-vs-vast>
