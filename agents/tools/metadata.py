"""Read helpers over the DataHub metadata graph for metadata-level hunts
(ownership forensics, provenance gaps). Uses the same SDK surface verified
in ingest/smoke_roundtrip.py and ingest/datahub_bootstrap.py.
"""
import json

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

def _unwrap(res):
    return res["data"] if isinstance(res, dict) and "data" in res else res


def active_incidents(graph, resource_urn):
    """[(urn, title)] of ACTIVE (unresolved) incidents on resource_urn."""
    q = ("query incidents($urn: String!) { dataset(urn: $urn) { "
         "incidents(state: ACTIVE, start: 0, count: 50) "
         "{ incidents { urn title } } } }")
    res = _unwrap(graph.execute_graphql(q, variables={"urn": resource_urn}))
    ds = (res or {}).get("dataset") or {}
    inc = (ds.get("incidents") or {}).get("incidents") or []
    return [(i["urn"], i.get("title")) for i in inc]


def raise_incident(graph, resource_urn, title, description,
                   incident_type="CUSTOM", custom_type="Fraud Investigation",
                   dedupe=True):
    """Raise a native DataHub Incident on resource_urn via the raiseIncident
    GraphQL mutation. Returns the incident urn. Idempotent by default: if an
    ACTIVE incident with the same title already exists on the asset, returns
    that one instead of raising a duplicate (so re-running the reviewer is
    safe). This is how a confirmed finding becomes a first-class 'this asset is
    under investigation' signal in DataHub itself, rather than only a tag."""
    if dedupe:
        for urn, t in active_incidents(graph, resource_urn):
            if t == title:
                return urn
    inp = {"type": incident_type, "title": title,
           "description": description, "resourceUrn": resource_urn}
    if incident_type == "CUSTOM":
        inp["customType"] = custom_type
    q = ("mutation raiseIncident($input: RaiseIncidentInput!) "
         "{ raiseIncident(input: $input) }")
    res = _unwrap(graph.execute_graphql(q, variables={"input": inp}))
    return res["raiseIncident"]


def resolve_incident(graph, incident_urn, message):
    """Resolve (close) an incident via updateIncidentStatus -> RESOLVED. Inlined
    (state is an enum, message JSON-escaped) to avoid input-type coupling.
    Returns True on success."""
    q = ("mutation { updateIncidentStatus(urn: %s, input: "
         "{ state: RESOLVED, message: %s }) }"
         % (json.dumps(incident_urn), json.dumps(message)))
    return _unwrap(graph.execute_graphql(q))["updateIncidentStatus"]


def resolve_incidents_for(graph, resource_urn, title, message):
    """Resolve every ACTIVE incident on resource_urn whose title matches. Returns
    the list of resolved incident urns (idempotent: empty if none are open)."""
    done = []
    for urn, t in active_incidents(graph, resource_urn):
        if t == title:
            resolve_incident(graph, urn, message)
            done.append(urn)
    return done


def upsert_custom_assertion(graph, entity_urn, assertion_urn, custom_type,
                            description, logic=None, external_url=None,
                            platform_name="Paper Trail"):
    """Register/replace a custom (external) assertion on entity_urn via
    upsertCustomAssertion. A deterministic assertion_urn makes it idempotent --
    re-running updates the same assertion instead of creating duplicates.
    Returns the assertion urn."""
    inp = {"entityUrn": entity_urn, "type": custom_type,
           "description": description, "platform": {"name": platform_name}}
    if logic:
        inp["logic"] = logic
    if external_url:
        inp["externalUrl"] = external_url
    q = ("mutation upsert($urn: String, $input: UpsertCustomAssertionInput!) "
         "{ upsertCustomAssertion(urn: $urn, input: $input) { urn } }")
    res = _unwrap(graph.execute_graphql(
        q, variables={"urn": assertion_urn, "input": inp}))
    return res["upsertCustomAssertion"]["urn"]


def report_assertion_result(graph, assertion_urn, success, properties=None,
                            external_url=None):
    """Report a SUCCESS/FAILURE result for a custom assertion via
    reportAssertionResult, so it shows a pass/fail run in DataHub's Validation
    tab. Returns True on success."""
    result = {"type": "SUCCESS" if success else "FAILURE"}
    if properties:
        result["properties"] = [{"key": str(k), "value": str(v)}
                                for k, v in properties.items()]
    if external_url:
        result["externalUrl"] = external_url
    q = ("mutation report($urn: String!, $result: AssertionResultInput!) "
         "{ reportAssertionResult(urn: $urn, result: $result) }")
    res = _unwrap(graph.execute_graphql(
        q, variables={"urn": assertion_urn, "result": result}))
    return res["reportAssertionResult"]


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
