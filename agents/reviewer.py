"""Human-in-the-loop reviewer (app-layer proposals, per build plan sec 10).
Findings land tagged pending-review; a human investigator confirms or
rejects. The review itself becomes metadata: tag swap + audit trail in
the dataset's custom properties.

Usage:
  python -m agents.reviewer list
  python -m agents.reviewer accept <hunt_id|evidence_table> [--note "..."]
  python -m agents.reviewer reject <hunt_id|evidence_table> [--note "..."]
"""
import argparse, getpass, sys, time
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.mce_builder import make_dataset_urn, make_tag_urn
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass, GlobalTagsClass, TagAssociationClass)
from agents.tools.metadata import (
    get_graph, table_name, raise_incident, resolve_incidents_for)
from agents.tools.warehouse import query, describe

PENDING = make_tag_urn("pending-review")


def duck_urn(table):
    return make_dataset_urn("duckdb", f"paper_trail.{table}", "PROD")


def incident_title(tbl):
    return f"Paper Trail investigation: {tbl}"


def implicated_assets(tbl):
    """Production datasets a finding points at. hunt4/5 evidence rows name the
    implicated finance datasets in a 'dataset' column -> return those URNs so the
    Incident lands on the *real asset under investigation*, not just the evidence
    table. Other hunts stand on their own evidence set -> return [] and the caller
    falls back to the evidence dataset."""
    cols = [c[0] for c in describe(tbl)]
    if "dataset" not in cols:
        return []
    _, rows = query(f"SELECT DISTINCT dataset FROM {tbl}")
    return [duck_urn(r[0]) for r in rows if r[0]]

def evidence_sets(graph):
    urns = graph.get_urns_by_filter(entity_types=["dataset"], platform="duckdb")
    for urn in urns:
        if not table_name(urn).startswith("analytics."):
            continue
        tags = graph.get_aspect(urn, GlobalTagsClass)
        yield urn, [t.tag for t in tags.tags] if tags else []

def cmd_list(graph):
    print("evidence sets (analytics.*):")
    for urn, tags in evidence_sets(graph):
        state = ("PENDING" if PENDING in tags else
                 "confirmed" if make_tag_urn("confirmed") in tags else
                 "rejected" if make_tag_urn("rejected") in tags else "-")
        print(f"  [{state:9}] {table_name(urn)}")

def resolve(graph, key):
    matches = [urn for urn, _ in evidence_sets(graph) if key in table_name(urn)]
    if len(matches) != 1:
        sys.exit(f"'{key}' matched {len(matches)} evidence sets: "
                 f"{[table_name(m) for m in matches]}")
    return matches[0]

def cmd_review(graph, key, verdict, note):
    urn = resolve(graph, key)
    tbl = table_name(urn)
    tags = graph.get_aspect(urn, GlobalTagsClass) or GlobalTagsClass(tags=[])
    if PENDING not in [t.tag for t in tags.tags]:
        sys.exit(f"{tbl} is not pending-review")
    kept = [t for t in tags.tags if t.tag != PENDING]
    kept.append(TagAssociationClass(tag=make_tag_urn(verdict)))
    reviewer = getpass.getuser()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    props = graph.get_aspect(urn, DatasetPropertiesClass) or \
        DatasetPropertiesClass(name=tbl)
    cp = dict(props.customProperties or {})
    cp.update({"review_verdict": verdict, "reviewed_by": reviewer,
               "reviewed_at": stamp, "review_note": note or ""})
    props.customProperties = cp
    emitter = graph  # DataHubGraph is itself an emitter
    for aspect in (GlobalTagsClass(tags=kept), props):
        emitter.emit_mcp(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))
    print(f"[reviewer] {tbl}: {verdict} by {reviewer} at {stamp}"
          + (f' -- "{note}"' if note else ""))
    # Incident lifecycle: raise on the implicated production asset when the
    # finding names one (hunt4/5 -> the finance datasets), else on the evidence
    # set. Reject closes whatever this finding had opened. Both are idempotent.
    title = incident_title(tbl)
    targets = implicated_assets(tbl) or [urn]
    if verdict == "confirmed":
        for t_urn in targets:
            inc = raise_incident(
                graph, t_urn, title=title,
                description=(f"Investigator {reviewer} confirmed the finding "
                             f"{tbl} on {stamp}."
                             + (f' Note: {note}.' if note else "")
                             + " Raised by the Paper Trail review workflow; this"
                               " asset is now under investigation in DataHub."))
            print(f"[reviewer] incident on {table_name(t_urn)}: {inc}")
    else:  # rejected -> resolve any incident this finding had opened
        msg = (f"Finding {tbl} rejected by {reviewer} on {stamp}."
               + (f' Note: {note}.' if note else ""))
        for t_urn in targets:
            for c in resolve_incidents_for(graph, t_urn, title, msg):
                print(f"[reviewer] resolved incident {c} on {table_name(t_urn)}")

def cmd_reopen(graph, key):
    """Reopen a reviewed finding: swap confirmed/rejected back to pending-review
    so it can be re-examined (a normal audit action)."""
    urn = resolve(graph, key)
    tbl = table_name(urn)
    for t_urn in (implicated_assets(tbl) or [urn]):
        for c in resolve_incidents_for(
                graph, t_urn, incident_title(tbl),
                f"Finding {tbl} reopened for re-examination by {getpass.getuser()}."):
            print(f"[reviewer] resolved incident {c} on {table_name(t_urn)}")
    tags = graph.get_aspect(urn, GlobalTagsClass) or GlobalTagsClass(tags=[])
    verdicts = {make_tag_urn("confirmed"), make_tag_urn("rejected")}
    kept = [t for t in tags.tags if t.tag not in verdicts]
    if PENDING not in [t.tag for t in kept]:
        kept.append(TagAssociationClass(tag=PENDING))
    graph.emit_mcp(MetadataChangeProposalWrapper(
        entityUrn=urn, aspect=GlobalTagsClass(tags=kept)))
    print(f"[reviewer] {tbl}: reopened -> pending-review")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["list", "accept", "reject", "reopen"])
    p.add_argument("key", nargs="?", help="hunt id or evidence table substring")
    p.add_argument("--note", default="")
    a = p.parse_args()
    graph = get_graph()
    if a.action == "list":
        cmd_list(graph)
    elif a.action == "reopen":
        if not a.key:
            sys.exit("reopen needs a hunt id or table substring")
        cmd_reopen(graph, a.key)
    else:
        if not a.key:
            sys.exit("accept/reject need a hunt id or table substring")
        cmd_review(graph, a.key, "confirmed" if a.action == "accept" else "rejected",
                   a.note)

if __name__ == "__main__":
    main()
