"""Run with Orange's Python. Build an inspection workflow from held-out predictions.

These probabilities are outputs, never input features for a new classifier.
"""
import argparse
import base64
import csv
import json
import pickle
from pathlib import Path
import xml.etree.ElementTree as ET
from Orange.data import Table
from Orange.widgets.utils.filedialogs import RecentPath

TASKS = {"complete": "Finalización", "engage": "Interacción", "continue": "Continuidad", "click": "Clic publicitario"}


def main():
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=root / "apps/api/artifacts/demo/mmoe")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = json.loads((args.model_dir / "report.json").read_text(encoding="utf-8"))
    rows = []
    for split in ("test", "unseen_users"):
        with (args.model_dir / f"{split}_predictions.csv").open(encoding="utf-8", newline="") as stream:
            rows.extend({**r, "split": split} for r in csv.DictReader(stream))
    label = "SIMULADO" if report["origin"] == "simulated" else "REAL"
    scheme = ET.Element("scheme", version="2.0", title=f"MMoE · {label} · resultados reservados",
                        description="Inspección de predicciones fuera de entrenamiento. No reentrena ni mide incremento causal de CTR.")
    nodes, links = ET.SubElement(scheme,"nodes"), ET.SubElement(scheme,"links")
    ET.SubElement(scheme,"annotations"); ET.SubElement(scheme,"thumbnail")
    properties = ET.SubElement(scheme,"node_properties")
    counts = {}
    for i, (task, title) in enumerate(TASKS.items()):
        path = args.output / f"{task}.tab"
        fields = ["exposure_id", "user_id", "gender", "origin", "split", task, *[f"p_{t}" for t in TASKS]]
        selected = [r for r in rows if int(r[f"mask_{task}"])]
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t")
            writer.writerow(fields)
            writer.writerow(["string","string","discrete","discrete","discrete","0 1", *["continuous"]*4])
            writer.writerow(["meta","meta","meta","meta","meta","class", *[""]*4])
            writer.writerows([[r[k] for k in fields] for r in selected])
        table = Table(str(path))
        assert len(table) == len(selected) and table.domain.class_var.name == task
        counts[task] = len(table)
        file_id, table_id = str(2*i), str(2*i+1)
        for nid, widget, qualified, x in ((file_id,"File","Orange.widgets.data.owfile.OWFile",100),
                                          (table_id,"Data Table","Orange.widgets.data.owtable.OWTable",420)):
            ET.SubElement(nodes,"node",id=nid,name=widget,qualified_name=qualified,project_name="Orange3",version="",
                          title=f"{title} · {label}" if widget == "File" else f"Resultados: {title}",position=f"({x}.0, {100+i*160}.0)")
        ET.SubElement(links,"link",id=str(i),source_node_id=file_id,sink_node_id=table_id,source_channel="Data",sink_channel="Data",
                      source_channel_id="data",sink_channel_id="data",enabled="true")
        settings = {"source":0,"recent_paths":[RecentPath(str(path.resolve()), "basedir", path.name)]}
        ET.SubElement(properties,"properties",node_id=file_id,format="pickle").text=base64.b64encode(pickle.dumps(settings)).decode("ascii")
    ET.SubElement(ET.SubElement(scheme,"session_state"),"window_groups")
    ET.indent(scheme,space="  ")
    ET.ElementTree(scheme).write(args.output/"flujo.ows",encoding="utf-8",xml_declaration=True)
    (args.output/"resumen.json").write_text(json.dumps({"origin":report["origin"],"dataset_sha256":report["dataset_sha256"],
        "selected":report["selected"],"approved":report["approved"],"heldout_rows_by_task":counts},indent=2),encoding="utf-8")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
