"""Idempotent transactional seed for validated first-party candidates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from database import SessionLocal, engine
from database_schema import ensure_database_schema
from models import ProgrammingExercise


def normalize_case(item: dict, visibility: str, index: int) -> dict:
    """Persist the canonical API-safe stdin/stdout field names."""
    return {
        "id": str(item.get("id") or f"{visibility}-{index}"),
        "name": str(item.get("name") or f"{visibility}-{index}"),
        "visibility": visibility,
        "stdin_text": str(item.get("stdin_text", item.get("stdin", ""))),
        "expected_stdout": str(item.get("expected_stdout", item.get("expected", ""))),
    }


def seed(items: list[dict]) -> int:
    ensure_database_schema(engine)
    db = SessionLocal()
    added = 0
    try:
        for item in items:
            if not item.get("validated"):
                raise ValueError(f"candidate is not validated: {item.get('source_key')}")
            if item.get("quality_status") != "approved":
                raise ValueError(f"candidate is not quality-approved: {item.get('source_key')}")
            required_quality = (
                "learning_objective_id", "learning_objective", "prerequisites",
                "core_skill", "novelty_reason", "language_fit_reason",
            )
            missing_quality = [key for key in required_quality if not str(item.get(key) or "").strip()]
            if missing_quality:
                raise ValueError(f"candidate quality metadata missing: {','.join(missing_quality)}")
            existing = db.query(ProgrammingExercise).filter_by(source_key=item["source_key"]).first()
            if existing:
                if existing.quality_status == "rejected":
                    raise ValueError(f"source_key was rejected; use a reviewed replacement key: {item['source_key']}")
                continue
            public = [{**normalize_case(test, "public", i), "id": f"{item['source_key']}-public-{i}"} for i, test in enumerate(item["public_cases"], 1)]
            hidden = [{**normalize_case(test, "hidden", i), "id": f"{item['source_key']}-hidden-{i}"} for i, test in enumerate(item["hidden_cases"], 1)]
            db.add(ProgrammingExercise(
                slug=item["source_key"].replace(":", "-"), source_key=item["source_key"], language=item["language"],
                title=item["title_zh"], title_zh=item["title_zh"], summary_zh=item["summary_zh"], statement_zh=item["statement_zh"],
                input_format_zh=item["input_format_zh"], output_format_zh=item["output_format_zh"], constraints_zh=item["constraints_zh"],
                title_en=item["title_en"], statement_en=item["statement_en"], difficulty=item["difficulty"],
                tags_json=json.dumps(item["knowledge_tags"], ensure_ascii=False), description=item["summary_zh"],
                starter_files_json=json.dumps([{"path": item["filename"], "content": item["starter_code"]}], ensure_ascii=False),
                reference_files_json=json.dumps([{"path": item["filename"], "content": item["reference_code"]}], ensure_ascii=False),
                public_tests_json=json.dumps([{"samples": public}], ensure_ascii=False), hidden_tests_json=json.dumps([{"samples": hidden}], ensure_ascii=False),
                official_test_files_json="[]", source_repo="first_party_original", source_path=item["source_key"], source_commit="generated-2026-07-31",
                license="project_owned", license_text="第一方原创", attribution="AI Study Platform first-party original content",
                reference_verified=True, starter_verified=True, is_active=True, problem_family_id=item["problem_family_id"], language_fit_reason=item["language_fit_reason"],
                quality_status="approved", quality_score=float(item.get("quality_score", 100)),
                quality_failure_reasons="[]", learning_objective_id=item["learning_objective_id"],
                learning_objective=item["learning_objective"], prerequisites=item["prerequisites"],
                core_skill=item["core_skill"], novelty_reason=item["novelty_reason"],
            ))
            added += 1
        db.commit()
        return added
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
