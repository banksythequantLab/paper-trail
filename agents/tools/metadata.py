"""Read helpers over the DataHub metadata graph for metadata-level hunts
(ownership forensics, provenance gaps). Uses the same SDK surface verified
in ingest/smoke_roundtrip.py and ingest/datahub_bootstrap.py.
"""
from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
from datahub.metadata.schema_classes import (
    CorpUserInfoClass, DataJobInputOutputClass, GlobalTagsClass,
    GlossaryTermsClass, OwnershipClass,
)

GMS = "http://localhost:8080"

def get_graph():
    return DataHubGraph(DatahubClientConfig(server=GMS))

def estate(graph, platform="duckdb"):
    """All dataset urns for the platform + all datajob urns."""
    datasets = list(graph.get_urns_by_filter(entity_types=["dataset"], platform=platform))
    jobs = list(graph.get_urns_by_filter(entity_types=["dataJob"]))
    return datasets, jobs

def produced_datasets(graph, jobs):
    """Set of dataset urns that are the documented output of some DataJob
    (i.e. datasets WITH provenance). Anything absent has no lineage."""
    out = set()
    for j in jobs:
        io = graph.get_aspect(j, DataJobInputOutputClass)
        if io and io.outputDatasets:
            out |= set(io.outputDatasets)
    return out

def dataset_facts(graph, urn):
    """(owners, tags, terms) short names for one dataset."""
    own = graph.get_aspect(urn, OwnershipClass)
    tags = graph.get_aspect(urn, GlobalTagsClass)
    terms = graph.get_aspect(urn, GlossaryTermsClass)
    return ([o.owner.split(":")[-1] for o in own.owners] if own else [],
            [t.tag.split(":")[-1] for t in tags.tags] if tags else [],
            [t.urn.split(":")[-1].split(".")[-1] for t in terms.terms] if terms else [])

def user_facts(graph, username):
    """(display_name, title, active) for a corpuser."""
    info = graph.get_aspect(f"urn:li:corpuser:{username}", CorpUserInfoClass)
    if not info:
        return username, None, None
    return info.displayName or username, info.title, info.active

def table_name(urn):
    """'paper_trail.finance.spe_entities' -> 'finance.spe_entities'"""
    return urn.split(",")[1].removeprefix("paper_trail.")

def raise_incident(graph, resource_urn, title, description,
                   incident_type="CUSTOM", custom_type="Fraud Investigation"):
    """Raise a native DataHub Incident on resource_urn via the raiseIncident
    GraphQL mutation. Returns the new incident urn. This is how a confirmed
    finding becomes a first-class 'this asset is under investigation' signal in
    DataHub itself, rather than only a tag."""
    inp = {"type": incident_type, "title": title,
           "description": description, "resourceUrn": resource_urn}
    if incident_type == "CUSTOM":
        inp["customType"] = custom_type
    q = ("mutation raiseIncident($input: RaiseIncidentInput!) "
         "{ raiseIncident(input: $input) }")
    res = graph.execute_graphql(q, variables={"input": inp})
    if isinstance(res, dict) and "data" in res:
        res = res["data"]
    return res["raiseIncident"]


def values_sql(columns, rows):
    """Render rows into a SELECT ... FROM (VALUES ...) statement so
    metadata-derived evidence is still materialized via captured SQL."""
    def lit(v):
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, (int, float)):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"
    vals = ",\n  ".join("(" + ", ".join(lit(v) for v in r) + ")" for r in rows)
    cols = ", ".join(columns)
    return f"SELECT * FROM (VALUES\n  {vals}\n) AS t({cols})"
