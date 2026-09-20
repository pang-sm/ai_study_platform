"""CS408_INTERACTION_DATASET_V1 audit + readiness gate — ACCEL_SPRINT_S7 PART C/D/E.

Read-only. Trains nothing, predicts nothing, writes nothing to the database.

    DATABASE_URL=sqlite:///path/to/app.db python scripts/audit_kt_readiness.py --out report.json

The report is deterministic given the same snapshot: the audit reads through the same
contract the exporter uses, so it cannot describe a dataset the exporter would not produce.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def build_report(*, database_url: str, service_namespace: str | None = None,
                 limit: int = 20000, temporal_holdout_share: float = 0.20) -> dict:
    from science import kt_dataset, kt_native

    engine = create_engine(database_url)
    db = sessionmaker(bind=engine)()
    try:
        body = kt_native.build_v1(db, service_namespace=service_namespace, limit=limit)
        measured = kt_native.audit(db, service_namespace=service_namespace, limit=limit)
    finally:
        db.close()

    user_split = kt_native.primary_split(body)
    temporal = kt_native.temporal_holdout(body, holdout_share=temporal_holdout_share)
    readiness = kt_native.evaluate_readiness(measured, split=user_split)
    decision = kt_native.training_decision(readiness)
    ontology = kt_native.native_ontology(body)

    return {
        "dataset_spec": kt_native.dataset_spec(),
        "dataset_identity": kt_native.dataset_identity(body),
        "spec_compliance": kt_native.spec_compliance(body),
        "part_c_data_quality_audit": measured,
        "part_d_readiness_gate": readiness,
        "part_d_decision": decision,
        "part_e_user_grouped_split": user_split,
        "part_e_temporal_holdout": temporal,
        "part_f3_native_ontology": {
            k: v for k, v in ontology.items() if k != "mapping"},
        "part_f3_native_ontology_check": kt_native.ontology_is_native(ontology),
        "part_f_training_stage": kt_native.training_run_plan(readiness, ontology),
        "part_i_promotion_gate": kt_native.promotion_gate({}),
        "part_o_evidence_reliability_v2": kt_native.v2_decision(),
        "part_n_online_evaluator": _evaluator_state(),
    }


def _evaluator_state() -> dict:
    from science import kt_evaluation
    return kt_evaluation.evaluator_is_ready()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="-", help="output path, or - for stdout")
    parser.add_argument("--database-url", default=None, help="defaults to $DATABASE_URL")
    parser.add_argument("--service-namespace", default="exam_prep")
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--summary", action="store_true",
                        help="print the verdict-bearing lines only")
    args = parser.parse_args(argv)

    database_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not database_url:
        print("audit_kt_readiness: DATABASE_URL is required", file=sys.stderr)
        return 2

    namespace = None if args.service_namespace in ("", "all") else args.service_namespace
    report = build_report(database_url=database_url, service_namespace=namespace,
                          limit=args.limit)

    if args.summary:
        audit = report["part_c_data_quality_audit"]
        gate = report["part_d_readiness_gate"]
        print(json.dumps({
            "dataset_version": report["dataset_spec"]["dataset_version"],
            "dataset_hash": report["dataset_identity"]["dataset_hash"],
            "users_with_eligible_interactions": audit["users_with_eligible_interactions"],
            "total_eligible_interactions": audit["total_eligible_interactions"],
            "median_sequence_length": audit["sequence_length"]["p50"],
            "module_coverage_levels": audit["module_coverage"]["levels"],
            "chapter_coverage_levels": audit["chapter_coverage"]["levels"],
            "concept_coverage_levels": audit["concept_coverage"]["levels"],
            "data_readiness_gate": gate["verdict"],
            "failed_checks": gate["failed_checks"],
            "training_permitted": report["part_d_decision"]["training_permitted"],
            "native_concepts": report["part_f3_native_ontology"]["concept_count"],
            "user_grouped_overlap_empty":
                report["part_e_user_grouped_split"]["overlap_is_empty"],
            "metadata_spec_compliant": report["spec_compliance"]["compliant"],
            "pii_leaks": report["spec_compliance"]["forbidden_field_leak"],
        }, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    text = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
