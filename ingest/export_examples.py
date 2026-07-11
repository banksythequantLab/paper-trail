"""Export examples/ artifacts from live DataHub metadata (codegen judges)."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from datahub.emitter.mce_builder import make_data_job_urn, make_dataset_urn
from datahub.metadata.schema_classes import DataJobInfoClass, DatasetPropertiesClass
from agents.tools.metadata import get_graph
from ingest.verify_hunts import HUNTS

ROOT = pathlib.Path(__file__).resolve().parents[1] / "examples"
graph = get_graph()
for hunt, table in HUNTS.items():
    job = make_data_job_urn("paper_trail", "investigations", hunt, "PROD")
    ev = make_dataset_urn("duckdb", f"paper_trail.{table}", "PROD")
    info = graph.get_aspect(job, DataJobInfoClass)
    props = graph.get_aspect(ev, DatasetPropertiesClass)
    sql_path = ROOT / "generated_sql" / f"{hunt}.sql"
    sql_path.write_text(
        f"-- {info.name}\n-- producing task: {job}\n-- evidence: {ev}\n\n"
        + info.customProperties["sql"] + "\n", encoding="utf-8")
    ledger_path = ROOT / "ledger_entries" / f"{hunt}.json"
    ledger_path.write_text(json.dumps({
        "hunt_id": hunt, "title": info.name, "narrative": info.description,
        "evidence_dataset": ev, "producing_task": job,
        "evidence_properties": dict(props.customProperties or {}),
    }, indent=2), encoding="utf-8")
    print(f"  exported {hunt}")
print("EXPORT_DONE")
