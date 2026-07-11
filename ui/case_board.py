r"""PAPER TRAIL case board -- Streamlit UI over the evidence warehouse
(DuckDB analytics.*) and the DataHub review trail.

Run:  .venv\Scripts\python.exe -m streamlit run ui\case_board.py
Requires DataHub GMS at localhost:8080 for live review states
(falls back gracefully if the graph is unreachable).
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # streamlit puts ui/ on sys.path, not the repo root
    sys.path.insert(0, str(ROOT))
DB = ROOT / "data" / "warehouse.duckdb"
DATAHUB_UI = "http://localhost:9002"

HUNTS = {
    "hunt1_comm_spikes": {
        "title": "Hunt 1 - Communication spikes",
        "question": "Did email volume around key entities spike before the restatement?",
        "finding": "Week of Oct 22 2001: z=4.43 volume anomaly, 3 days before the SEC inquiry disclosure.",
    },
    "hunt2_external_leakage": {
        "title": "Hunt 2 - External leakage",
        "question": "Did SPE-related material leave the company before public disclosure?",
        "finding": "120 pre-disclosure emails referencing undisclosed SPEs reached 43 external addresses, "
                   "including personal AOL accounts and ljminvestments.com itself.",
    },
    "hunt3_spe_web": {
        "title": "Hunt 3 - The SPE shadow web",
        "question": "Which vehicles co-travel with known SPEs but are absent from the glossary?",
        "finding": "8 shadow vehicles surfaced (marlin, osprey, talon, yosemite, rawhide, fishtail, "
                   "condor, porcupine) -- all real Enron entities, none in the official glossary.",
    },
    "hunt4_orphaned_ownership": {
        "title": "Hunt 4 - Orphaned ownership",
        "question": "Are financially-material datasets owned by implicated or departed officers?",
        "finding": "3 material datasets owned by implicated, departed officers (Fastow, Causey); "
                   "none certified.",
    },
    "hunt5_provenance_gaps": {
        "title": "Hunt 5 - Provenance gaps",
        "question": "Which material datasets have no documented lineage at all?",
        "finding": "The same 3 datasets have zero documented lineage -- the governance holes "
                   "the metadata graph was hiding in plain sight.",
    },
}

STATE_BADGE = {"confirmed": "CONFIRMED", "pending-review": "PENDING REVIEW",
               "rejected": "REJECTED", "unknown": "STATE UNKNOWN"}
STATE_COLOR = {"confirmed": "green", "pending-review": "orange",
               "rejected": "red", "unknown": "gray"}


@st.cache_resource
def warehouse():
    return duckdb.connect(str(DB), read_only=True)


@st.cache_data(ttl=60)
def review_states():
    """table -> (state, reviewed_by, reviewed_at, note) from the DataHub graph.
    Empty dict if GMS is unreachable (board still renders evidence)."""
    try:
        from datahub.metadata.schema_classes import (DatasetPropertiesClass,
                                                     GlobalTagsClass)
        from agents.tools.metadata import get_graph, table_name
        graph = get_graph()
        out = {}
        for urn in graph.get_urns_by_filter(entity_types=["dataset"], platform="duckdb"):
            tbl = table_name(urn)
            if not tbl.startswith("analytics."):
                continue
            tags = graph.get_aspect(urn, GlobalTagsClass)
            names = [t.tag.split(":")[-1] for t in tags.tags] if tags else []
            state = next((s for s in ("confirmed", "rejected", "pending-review")
                          if s in names), "unknown")
            props = graph.get_aspect(urn, DatasetPropertiesClass)
            cp = (props.customProperties or {}) if props else {}
            out[tbl.removeprefix("analytics.")] = (
                state, cp.get("reviewed_by", ""), cp.get("reviewed_at", ""),
                cp.get("review_note", ""))
        return out
    except Exception:
        return {}


@st.cache_data(ttl=300)
def evidence(table: str) -> pd.DataFrame:
    return warehouse().sql(f'SELECT * FROM analytics."{table}"').df()


def badge(state, by, at):
    color = STATE_COLOR[state]
    label = STATE_BADGE[state]
    line = f":{color}[**{label}**]"
    if by and at:
        line += f" &nbsp;-&nbsp; reviewed by `{by}` at {at}"
    return line


def hunt_chart(key: str, df: pd.DataFrame):
    """One purpose-built visual per hunt; silently skips if columns missing."""
    try:
        if key == "hunt1_comm_spikes":
            st.line_chart(df.set_index("week")[["vol", "zscore"]], height=260)
        elif key == "hunt2_external_leakage":
            top = (df.groupby("external_domain").size().sort_values(ascending=False)
                   .head(12).rename("emails"))
            st.bar_chart(top, height=260, horizontal=True)
            st.caption("Top external recipient domains (pre-disclosure SPE traffic)")
        elif key == "hunt3_spe_web":
            shadow = df[~df["b_known"]] if df["b_known"].dtype == bool else df[df["b_known"] == False]  # noqa: E712
            top = (shadow.groupby("entity_b")["co_mentions"].sum()
                   .sort_values(ascending=False).head(10))
            st.bar_chart(top, height=260, horizontal=True)
            st.caption("Shadow vehicles by total co-mentions with known SPEs")
        elif key in ("hunt4_orphaned_ownership", "hunt5_provenance_gaps"):
            flagged = int(df["flagged"].sum())
            st.metric("Datasets flagged", flagged, help="financially material + governance gap")
    except Exception as e:  # chart must never take down the evidence table
        st.caption(f"(chart unavailable: {e})")


st.set_page_config(page_title="PAPER TRAIL - Case Board", page_icon=":card_index_dividers:",
                   layout="wide")
st.title("PAPER TRAIL")
st.caption("Metadata-driven forensics over the Enron corpus - DuckDB evidence + "
           f"DataHub review trail ([open DataHub]({DATAHUB_UI}))")

states = review_states()
if not states:
    st.warning("DataHub GMS unreachable - showing evidence without live review states.")

confirmed = sum(1 for s in states.values() if s[0] == "confirmed")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hunts", len(HUNTS))
c2.metric("Confirmed", f"{confirmed}/{len(HUNTS)}" if states else "n/a")
c3.metric("Evidence rows", sum(len(evidence(k)) for k in HUNTS))
c4.metric("Corpus", "435K emails")

tabs = st.tabs([h["title"] for h in HUNTS.values()])
for tab, (key, meta) in zip(tabs, HUNTS.items()):
    with tab:
        state, by, at, note = states.get(key, ("unknown", "", "", ""))
        st.markdown(badge(state, by, at))
        if note:
            st.caption(f"Review note: {note}")
        st.markdown(f"**Question:** {meta['question']}")
        st.markdown(f"**Finding:** {meta['finding']}")
        df = evidence(key)
        left, right = st.columns([3, 2])
        with left:
            st.dataframe(df, use_container_width=True, hide_index=True, height=380)
        with right:
            hunt_chart(key, df)
