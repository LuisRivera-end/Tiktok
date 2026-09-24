"""Generate a reproducible, explicitly simulated MMoE development dataset.

Run from apps/api: python -m app.ml.generate ../../data/synthetic/mmoe_v2_exposures.csv
"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.ml.demo import demo_exposures
from app.ml.features import FEATURE_VERSION, TASKS
from app.ml.readiness import partition, task_counts
from app.telemetry.exposures import csv_export, dataset_rows


def generate(output, *, users=100, days=24, campaigns=5, seed=20260924,
             base_date="2026-05-01"):
    if users < 50 or days < 4 or campaigns < 2:
        raise ValueError("Se requieren >=50 usuarios, >=4 días y >=2 campañas para comprobar cortes y grupos")
    base = datetime.fromisoformat(base_date).replace(tzinfo=timezone.utc)
    exposures = demo_exposures(users=users, days=days, campaigns=campaigns, seed=seed, base=base)
    rows = dataset_rows(exposures, now=base + timedelta(days=days + 2))
    if len(rows) != users * days * 8 or len({r["exposure_id"] for r in rows}) != len(rows):
        raise ValueError("El generador produjo una cantidad o identidad inesperada")
    if any(r["origin"] != "simulated" or r["feature_version"] != FEATURE_VERSION for r in rows):
        raise ValueError("El origen o el esquema de características no es válido")
    groups = partition(rows, seed=42)
    split_counts = {name: {"exposures": len(group), "users": len({r["user_id"] for r in group}),
                           "campaigns": len({r["campaign_id"] for r in group if r["campaign_id"]}),
                           "tasks": task_counts(group)} for name, group in groups.items()}
    for name in ("test", "unseen_users"):
        if split_counts[name]["users"] < 10 or split_counts[name]["campaigns"] < 2:
            raise ValueError(f"{name} no cubre usuarios y campañas suficientes")
        for task in TASKS:
            counts = split_counts[name]["tasks"][task]
            if counts["observed"] < 100 or min(counts["positive"], counts["negative"]) < 10:
                raise ValueError(f"{task} no tiene suficiente variedad en {name}")
    content = csv_export(rows).encode("utf-8")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    manifest = {
        "origin": "simulated", "purpose": "development and pipeline verification only",
        "activation_allowed": False, "feature_version": FEATURE_VERSION,
        "generator": "app.ml.generate / app.ml.demo", "parameters": {
            "users": users, "days": days, "campaigns": campaigns, "seed": seed,
            "base_date_utc": base_date, "slots_per_user_day": 8,
            "ad_slots": [2, 7], "label_maturity_hours": 24},
        "csv_sha256": hashlib.sha256(content).hexdigest(), "rows": len(rows),
        "first_exposure_utc": rows[0]["started_at"], "last_exposure_utc": rows[-1]["started_at"],
        "users": len({r["user_id"] for r in rows}),
        "sessions": len({(r["user_id"], r["session_id"]) for r in rows}),
        "campaigns": dict(sorted(Counter(r["campaign_id"] for r in rows if r["campaign_id"]).items())),
        "genders": dict(sorted(Counter(r["gender"] for r in rows).items())),
        "tasks": task_counts(rows), "splits": split_counts,
        "limitations": [
            "No contiene usuarios, impresiones ni clics reales.",
            "Las preferencias y resultados se muestrean de reglas del generador; no prueban incremento causal.",
            "El género es una etiqueta sintética para probar agrupaciones, no una inferencia de personas.",
        ],
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--days", type=int, default=24)
    parser.add_argument("--campaigns", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--base-date", default="2026-05-01")
    args = parser.parse_args()
    result = generate(args.output, users=args.users, days=args.days,
                      campaigns=args.campaigns, seed=args.seed, base_date=args.base_date)
    print(json.dumps({k: result[k] for k in ("rows", "users", "sessions", "campaigns", "tasks", "csv_sha256")},
                     ensure_ascii=False, indent=2))
