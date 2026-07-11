"""Smoke: verify all five hunts left correct evidence + lineage in DataHub."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from datahub.emitter.mce_builder import make_data_job_urn, make_dataset_urn
from datahub.metadata.schema_classes import (
    DataJobInfoClass, DataJobInputOutputClass, GlobalTagsClass,
    SchemaMetadataClass)
from agents.tools.metadata import get_graph
from agents.tools.warehouse import query

HUNTS = {
    "hunt1_restatement_spikes": "analytics.hunt1_comm_spikes",
    "hunt2_material_leakage": "analytics.hunt2_external_leakage",
    "hunt3_spe_web": "analytics.hunt3_spe_web",
    "hunt4_orphaned_ownership": "analytics.hunt4_orphaned_ownership",
    "hunt5_provenance_gaps": "analytics.hunt5_provenance_gaps",
}

graph = get_graph()
ok = True
for hunt, table in HUNTS.items():
    ev = make_dataset_urn("duckdb", f"paper_trail.{table}", "PROD")
    job = make_data_job_urn("paper_trail", "investigations", hunt, "PROD")
    rows = query(f"SELECT count(*) FROM {table}")[1][0][0]
    info = graph.get_aspect(job, DataJobInfoClass)
    io = graph.get_aspect(job, DataJobInputOutputClass)
    tags = graph.get_aspect(ev, GlobalTagsClass)
    schema = graph.get_aspect(ev, SchemaMetadataClass)
    checks = {
        "warehouse rows": rows > 0,
        "job info + SQL": bool(info and info.customProperties.get("sql")),
        "lineage in>out": bool(io and io.inputDatasets and ev in io.outputDatasets),
        "evidence schema": bool(schema and schema.fields),
        "review state": bool(tags) and any(
            t.tag.split(":")[-1] in ("pending-review", "confirmed", "rejected")
            for t in tags.tags),
    }
    ok &= all(checks.values())
    bad = [k for k, v in checks.items() if not v]
    print(f"  {hunt}: rows={rows} {'OK' if not bad else 'FAIL ' + str(bad)}")
print("VERIFY_" + ("PASS" if ok else "FAIL"))
