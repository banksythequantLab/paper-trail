"""The Scribe: writes investigation findings back to DataHub as first-class
metadata. Every finding = evidence Dataset + DataJob (with exact SQL) +
lineage + pending-review tag. This IS the paper trail.
"""
import os
import time
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.emitter.mce_builder import (
    make_dataset_urn, make_data_flow_urn, make_data_job_urn,
    make_tag_urn, make_term_urn, make_domain_urn,
)
from datahub.metadata.schema_classes import (
    AuditStampClass, DataFlowInfoClass, DataJobInfoClass, DataJobInputOutputClass,
    DatasetPropertiesClass, DomainsClass, GlobalTagsClass,
    GlossaryTermAssociationClass, GlossaryTermsClass, OtherSchemaClass,
    SchemaFieldClass, SchemaFieldDataTypeClass, SchemaMetadataClass,
    StringTypeClass, NumberTypeClass, DateTypeClass, BooleanTypeClass,
    TagAssociationClass,
)
from .warehouse import describe

GMS = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
FLOW_URN = make_data_flow_urn("paper_trail", "investigations", "PROD")
TYPEMAP = {"VARCHAR": StringTypeClass, "BIGINT": NumberTypeClass, "INTEGER": NumberTypeClass,
           "DOUBLE": NumberTypeClass, "DATE": DateTypeClass, "BOOLEAN": BooleanTypeClass,
           "TIMESTAMP": DateTypeClass}

def _now():
    return AuditStampClass(time=int(time.time() * 1000), actor="urn:li:corpuser:paper-trail-agent")

def duck_urn(table):
    return make_dataset_urn("duckdb", f"paper_trail.{table}", "PROD")

def record_finding(hunt_id: str, title: str, narrative: str, sql: str,
                   evidence_table: str, input_tables: list[str],
                   terms: list[str] = (), confidence: str = "medium"):
    """Write a finding to the ledger. evidence_table like 'analytics.hunt1_x'.
    input_tables like ['curated.comm_edges', ...]. Returns (dataset_urn, job_urn)."""
    emitter = DatahubRestEmitter(gms_server=GMS)
    ev_urn = duck_urn(evidence_table)
    job_urn = make_data_job_urn("paper_trail", "investigations", hunt_id, "PROD")
    fields = [SchemaFieldClass(fieldPath=c, nativeDataType=t,
                type=SchemaFieldDataTypeClass(type=TYPEMAP.get(t.split("(")[0].upper(), StringTypeClass)()))
              for c, t, *_ in describe(evidence_table)]
    desc = (f"**FINDING ({confidence} confidence):** {title}\n\n{narrative}\n\n"
            f"*Recorded by Paper Trail agent. Full derivation: see lineage + producing task SQL.*")
    mcps = [
        MetadataChangeProposalWrapper(entityUrn=FLOW_URN, aspect=DataFlowInfoClass(
            name="Paper Trail Investigations",
            description="Autonomous fraud-pattern hunts; every finding carries lineage to raw evidence.")),
        MetadataChangeProposalWrapper(entityUrn=ev_urn, aspect=DatasetPropertiesClass(
            name=evidence_table, description=desc)),
        MetadataChangeProposalWrapper(entityUrn=ev_urn, aspect=SchemaMetadataClass(
            schemaName=evidence_table, platform="urn:li:dataPlatform:duckdb", version=0,
            hash="", platformSchema=OtherSchemaClass(rawSchema=""), fields=fields)),
        MetadataChangeProposalWrapper(entityUrn=ev_urn, aspect=DomainsClass(
            domains=[make_domain_urn("investigations")])),
        MetadataChangeProposalWrapper(entityUrn=ev_urn, aspect=GlobalTagsClass(tags=[
            TagAssociationClass(tag=make_tag_urn("risk-flagged")),
            TagAssociationClass(tag=make_tag_urn("pending-review")),
            TagAssociationClass(tag=make_tag_urn(f"confidence-{confidence}"))])),
        MetadataChangeProposalWrapper(entityUrn=job_urn, aspect=DataJobInfoClass(
            name=title, type="COMMAND", description=narrative,
            customProperties={"sql": sql, "hunt_id": hunt_id})),
        MetadataChangeProposalWrapper(entityUrn=job_urn, aspect=DataJobInputOutputClass(
            inputDatasets=[duck_urn(t) for t in input_tables], outputDatasets=[ev_urn])),
    ]
    if terms:
        mcps.append(MetadataChangeProposalWrapper(entityUrn=ev_urn, aspect=GlossaryTermsClass(
            terms=[GlossaryTermAssociationClass(urn=make_term_urn(f"PaperTrail.{t}")) for t in terms],
            auditStamp=_now())))
    for m in mcps:
        emitter.emit_mcp(m)
    return ev_urn, job_urn


def record_exhibits(hunt_id: str, finding_table: str, exhibits_table: str,
                    title: str, description: str, sql: str, input_tables: list,
                    tags=("evidence", "exhibit")):
    """Register an exhibits Dataset (the individual raw messages behind a finding)
    plus its extraction DataJob, so the chain of custody reaches actual emails.
    Lineage: input_tables (incl. the finding) -> exhibit task -> exhibits_table
    -> and the exhibit task's inputs include staging.emails, i.e. the raw corpus.
    Returns (exhibits_urn, job_urn)."""
    emitter = DatahubRestEmitter(gms_server=GMS)
    ex_urn = duck_urn(exhibits_table)
    job_urn = make_data_job_urn("paper_trail", "investigations", f"{hunt_id}_exhibits", "PROD")
    fields = [SchemaFieldClass(fieldPath=c, nativeDataType=t,
                type=SchemaFieldDataTypeClass(type=TYPEMAP.get(t.split("(")[0].upper(), StringTypeClass)()))
              for c, t, *_ in describe(exhibits_table)]
    mcps = [
        MetadataChangeProposalWrapper(entityUrn=ex_urn, aspect=DatasetPropertiesClass(
            name=exhibits_table, description=description)),
        MetadataChangeProposalWrapper(entityUrn=ex_urn, aspect=SchemaMetadataClass(
            schemaName=exhibits_table, platform="urn:li:dataPlatform:duckdb", version=0,
            hash="", platformSchema=OtherSchemaClass(rawSchema=""), fields=fields)),
        MetadataChangeProposalWrapper(entityUrn=ex_urn, aspect=DomainsClass(
            domains=[make_domain_urn("investigations")])),
        MetadataChangeProposalWrapper(entityUrn=ex_urn, aspect=GlobalTagsClass(
            tags=[TagAssociationClass(tag=make_tag_urn(t)) for t in tags])),
        MetadataChangeProposalWrapper(entityUrn=job_urn, aspect=DataJobInfoClass(
            name=title, type="COMMAND",
            description="Selects the individual messages behind the finding (verbatim SQL below).",
            customProperties={"sql": sql, "hunt_id": hunt_id, "exhibit_of": finding_table})),
        MetadataChangeProposalWrapper(entityUrn=job_urn, aspect=DataJobInputOutputClass(
            inputDatasets=[duck_urn(t) for t in input_tables], outputDatasets=[ex_urn])),
    ]
    for m in mcps:
        emitter.emit_mcp(m)
    return ex_urn, job_urn
