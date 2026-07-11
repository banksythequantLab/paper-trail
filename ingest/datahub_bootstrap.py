"""Paper Trail: bootstrap the DataHub metadata model for the Enron estate.
Emits: domains, glossary, corpusers, datasets w/ schemas+owners+terms+tags,
pipeline lineage (raw -> staging -> curated), and deliberate defects.
Idempotent: safe to re-run.
"""
import time
import duckdb
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.emitter.mce_builder import (
    make_dataset_urn, make_data_flow_urn, make_data_job_urn,
    make_user_urn, make_tag_urn, make_term_urn, make_domain_urn,
)
from datahub.metadata.schema_classes import (
    AuditStampClass, CorpUserInfoClass, DataFlowInfoClass, DataJobInfoClass,
    DataJobInputOutputClass, DatasetPropertiesClass, DomainPropertiesClass,
    DomainsClass, GlobalTagsClass, GlossaryTermAssociationClass,
    GlossaryTermInfoClass, GlossaryTermsClass, NumberTypeClass, OtherSchemaClass,
    OwnerClass, OwnershipClass, OwnershipTypeClass, SchemaFieldClass,
    SchemaFieldDataTypeClass, SchemaMetadataClass, StringTypeClass,
    BooleanTypeClass, DateTypeClass, TagAssociationClass,
)

GMS = "http://localhost:8080"
WAREHOUSE = r"B:\paper-trail\data\warehouse.duckdb"
NOW = AuditStampClass(time=int(time.time() * 1000), actor="urn:li:corpuser:paper-trail-bootstrap")
emitter = DatahubRestEmitter(gms_server=GMS)
emitter.test_connection()
mcps = []

# ---------- domains ----------
DOMAINS = {
    "communications": "Corporate email and messaging data",
    "finance": "Financial entities, events, and reporting",
    "trading": "Trading desk data",
    "investigations": "Paper Trail investigation outputs (evidence ledger)",
}
for dom_id, desc in DOMAINS.items():
    mcps.append(MetadataChangeProposalWrapper(
        entityUrn=make_domain_urn(dom_id),
        aspect=DomainPropertiesClass(name=dom_id.title(), description=desc)))

# ---------- glossary ----------
TERMS = {
    "PII": "Personally identifiable information (names, emails, personal content).",
    "FinanciallyMaterial": "Data with potential impact on reported financials or stock price.",
    "RestrictedPeriod": "Data touching the Oct-Dec 2001 restatement window; heightened handling.",
    "SPE": "Special Purpose Entity - off-balance-sheet vehicle.",
    "RelatedParty": "Entity with undisclosed or conflicted insider relationship.",
}
def term_urn(name):
    return make_term_urn(f"PaperTrail.{name}")
for name, definition in TERMS.items():
    mcps.append(MetadataChangeProposalWrapper(
        entityUrn=term_urn(name),
        aspect=GlossaryTermInfoClass(definition=definition, termSource="INTERNAL", name=name)))

# ---------- corpusers from employees table ----------
con = duckdb.connect(WAREHOUSE, read_only=True)
for addr, name, title, dept in con.execute("SELECT * FROM staging.employees").fetchall():
    user = addr.split("@")[0]
    mcps.append(MetadataChangeProposalWrapper(
        entityUrn=make_user_urn(user),
        aspect=CorpUserInfoClass(active=False, displayName=name, title=f"{title} ({dept})", email=addr)))

# ---------- datasets ----------
TYPEMAP = {"VARCHAR": StringTypeClass, "BIGINT": NumberTypeClass, "INTEGER": NumberTypeClass,
           "DATE": DateTypeClass, "BOOLEAN": BooleanTypeClass, "TIMESTAMP": DateTypeClass}

def duck_urn(table):
    return make_dataset_urn("duckdb", f"paper_trail.{table}", "PROD")

def schema_fields(table):
    fields = []
    for col, typ, *_ in con.execute(f"DESCRIBE {table}").fetchall():
        cls = TYPEMAP.get(typ.split("(")[0].upper(), StringTypeClass)
        fields.append(SchemaFieldClass(
            fieldPath=col, nativeDataType=typ,
            type=SchemaFieldDataTypeClass(type=cls())))
    return fields

# table -> (description, domain, owner_user, terms, tags)
CATALOG = {
    "staging.emails": ("Parsed Enron corpus emails. NOTE: body may be null for some messages.",
        "communications", "sally.beck", ["PII"], ["certified"]),
    "staging.recipients": ("Exploded email recipients (one row per addressee).",
        "communications", "sally.beck", ["PII"], ["certified"]),
    "staging.employees": ("Key custodians with public-record titles and departments.",
        "communications", "sally.beck", ["PII"], ["certified"]),
    "curated.comm_edges": ("Weekly sender->recipient communication volumes.",
        "communications", "sally.beck", ["PII"], ["certified"]),
    "finance.spe_entities": ("Special purpose entities and JVs from the public record.",
        "finance", "richard.causey", ["SPE", "RelatedParty", "FinanciallyMaterial"], []),
    "finance.restatement_events": ("Key 2001 disclosure and restatement events.",
        "finance", "richard.causey", ["FinanciallyMaterial", "RestrictedPeriod"], []),
}

def dataset_mcps(urn, name, desc, domain, owner, terms, tags, fields=None):
    out = [MetadataChangeProposalWrapper(entityUrn=urn,
            aspect=DatasetPropertiesClass(name=name, description=desc))]
    if fields:
        out.append(MetadataChangeProposalWrapper(entityUrn=urn, aspect=SchemaMetadataClass(
            schemaName=name, platform="urn:li:dataPlatform:duckdb", version=0, hash="",
            platformSchema=OtherSchemaClass(rawSchema=""), fields=fields)))
    if domain:
        out.append(MetadataChangeProposalWrapper(entityUrn=urn,
            aspect=DomainsClass(domains=[make_domain_urn(domain)])))
    if owner:
        out.append(MetadataChangeProposalWrapper(entityUrn=urn, aspect=OwnershipClass(
            owners=[OwnerClass(owner=make_user_urn(owner), type=OwnershipTypeClass.DATAOWNER)])))
    if terms:
        out.append(MetadataChangeProposalWrapper(entityUrn=urn, aspect=GlossaryTermsClass(
            terms=[GlossaryTermAssociationClass(urn=term_urn(t)) for t in terms], auditStamp=NOW)))
    if tags:
        out.append(MetadataChangeProposalWrapper(entityUrn=urn, aspect=GlobalTagsClass(
            tags=[TagAssociationClass(tag=make_tag_urn(t)) for t in tags])))
    return out

for table, (desc, domain, owner, terms, tags) in CATALOG.items():
    mcps += dataset_mcps(duck_urn(table), table, desc, domain, owner, terms, tags,
                         fields=schema_fields(table))

# raw source layer (the pre-existing sqlite corpus)
RAW_URN = make_dataset_urn("sqlite", "enron_loader.emails", "PROD")
mcps += dataset_mcps(RAW_URN, "enron_loader.emails",
    "Raw parsed Enron corpus (SQLite, 435,259 emails). Source of truth for staging layer.",
    "communications", "sally.beck", ["PII"], ["certified"])

# ---------- pipeline lineage: raw -> staging -> curated ----------
FLOW = make_data_flow_urn("paper_trail", "warehouse_build", "PROD")
mcps.append(MetadataChangeProposalWrapper(entityUrn=FLOW, aspect=DataFlowInfoClass(
    name="Warehouse Build", description="ingest/build_warehouse.py - converts raw corpus to analytical layers")))

def job(job_id, name, sql, inputs, outputs):
    urn = make_data_job_urn("paper_trail", "warehouse_build", job_id, "PROD")
    return [
        MetadataChangeProposalWrapper(entityUrn=urn, aspect=DataJobInfoClass(
            name=name, type="COMMAND", customProperties={"sql": sql})),
        MetadataChangeProposalWrapper(entityUrn=urn, aspect=DataJobInputOutputClass(
            inputDatasets=inputs, outputDatasets=outputs)),
    ]

mcps += job("build_staging", "Build staging layer",
    "CREATE TABLE staging.emails AS SELECT ... FROM src.emails; -- see build_warehouse.py",
    [RAW_URN],
    [duck_urn("staging.emails"), duck_urn("staging.recipients"), duck_urn("staging.employees")])
mcps += job("build_curated", "Build curated comm_edges",
    "CREATE TABLE curated.comm_edges AS SELECT sender, addr, date_trunc('week', sent_at), count(*) ...",
    [duck_urn("staging.emails"), duck_urn("staging.recipients")],
    [duck_urn("curated.comm_edges")])

# ---------- deliberate defects (the agent's prey) ----------
# 1: report with NO lineage, owned by a departed/implicated employee, not certified
mcps += dataset_mcps(duck_urn("finance.executive_summary_report"),
    "finance.executive_summary_report",
    "Quarterly executive summary figures. (Provenance undocumented.)",
    "finance", "andrew.fastow", ["FinanciallyMaterial"], [])
# 2: spe_entities deliberately has no lineage either (who compiled it?)

# ---------- emit ----------
for i, m in enumerate(mcps):
    emitter.emit_mcp(m)
print(f"Emitted {len(mcps)} aspects")

# ---------- verify ----------
from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig
graph = DataHubGraph(DatahubClientConfig(server=GMS))
time.sleep(5)
checks = {
    "dataset schema": graph.get_aspect(duck_urn("staging.emails"), SchemaMetadataClass) is not None,
    "domain assigned": graph.get_aspect(duck_urn("finance.spe_entities"), DomainsClass) is not None,
    "terms attached": graph.get_aspect(duck_urn("finance.spe_entities"), GlossaryTermsClass) is not None,
    "defect owner": graph.get_aspect(duck_urn("finance.executive_summary_report"), OwnershipClass) is not None,
    "curated lineage": graph.get_aspect(
        make_data_job_urn("paper_trail", "warehouse_build", "build_curated", "PROD"),
        DataJobInputOutputClass) is not None,
}
for k, v in checks.items():
    print(f"  {k}: {'OK' if v else 'MISSING'}")
assert all(checks.values()), "bootstrap verification failed"
print("BOOTSTRAP_DONE - estate modeled in DataHub")
print("  browse: http://localhost:9002/domain (datahub/datahub)")
