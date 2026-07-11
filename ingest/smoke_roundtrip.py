"""Paper Trail week-1 milestone: SDK write + read round-trip.
Emits: 2 datasets, 1 dataflow, 1 datajob with input/output lineage.
Reads back the lineage aspect to verify. GMS: http://localhost:8080
"""
import time
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.emitter.mce_builder import make_dataset_urn, make_data_flow_urn, make_data_job_urn
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass,
    DataFlowInfoClass,
    DataJobInfoClass,
    DataJobInputOutputClass,
)

GMS = "http://localhost:8080"
emitter = DatahubRestEmitter(gms_server=GMS)
emitter.test_connection()
print("[1/4] GMS connection OK")

in_urn = make_dataset_urn("duckdb", "paper_trail.staging.emails", "PROD")
out_urn = make_dataset_urn("duckdb", "paper_trail.analytics.smoke_evidence_set", "PROD")
flow_urn = make_data_flow_urn("paper_trail", "investigation_smoke", "PROD")
job_urn = make_data_job_urn("paper_trail", "investigation_smoke", "hunt_smoke_test", "PROD")

mcps = [
    MetadataChangeProposalWrapper(entityUrn=in_urn, aspect=DatasetPropertiesClass(
        name="emails (staging)", description="SMOKE TEST input: parsed Enron emails.")),
    MetadataChangeProposalWrapper(entityUrn=out_urn, aspect=DatasetPropertiesClass(
        name="smoke_evidence_set", description="SMOKE TEST evidence set produced by Paper Trail agent.")),
    MetadataChangeProposalWrapper(entityUrn=flow_urn, aspect=DataFlowInfoClass(
        name="Paper Trail Investigation (smoke)")),
    MetadataChangeProposalWrapper(entityUrn=job_urn, aspect=DataJobInfoClass(
        name="hunt_smoke_test", type="COMMAND",
        customProperties={"sql": "SELECT sender, COUNT(*) FROM emails GROUP BY 1 -- smoke"})),
    MetadataChangeProposalWrapper(entityUrn=job_urn, aspect=DataJobInputOutputClass(
        inputDatasets=[in_urn], outputDatasets=[out_urn])),
]
for m in mcps:
    emitter.emit_mcp(m)
print(f"[2/4] Emitted {len(mcps)} aspects (2 datasets, flow, job, lineage)")

# --- read back ---
from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig

graph = DataHubGraph(DatahubClientConfig(server=GMS))
time.sleep(3)  # let GMS index
io_aspect = graph.get_aspect(job_urn, DataJobInputOutputClass)
assert io_aspect is not None, "DataJobInputOutput aspect not found on read-back!"
assert io_aspect.inputDatasets == [in_urn], f"input mismatch: {io_aspect.inputDatasets}"
assert io_aspect.outputDatasets == [out_urn], f"output mismatch: {io_aspect.outputDatasets}"
print("[3/4] Read-back OK: job lineage inputs/outputs match")

props = graph.get_aspect(out_urn, DatasetPropertiesClass)
assert props and "evidence set" in (props.description or "")
print("[4/4] Evidence dataset read-back OK")
print("ROUNDTRIP_PASS: write+read verified against local DataHub")
print(f"  view job: http://localhost:9002/tasks/{job_urn}")
