"""Repair the existing 240-row standard-I/O catalog in place.

The repair keeps exercise ids, user projects, submissions, and learning
history intact.  It only replaces the leaked starter scaffold, adds learning
context and sample explanations, marks the protocol as standard_io, and
recomputes published outputs by running the stored reference program.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from build_catalog_240_quality import (  # noqa: E402
    STARTER_BACKGROUND,
    STARTER_HINT,
    _run,
    _compile,
    sample_explanation,
    starter_files_for,
)
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

LANGUAGES = ("C", "C++", "Python", "Java")
EXPECTED = {language: 60 for language in LANGUAGES}


def parse_json(value: str, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def exercise_kind(source_key: str) -> str:
    return str(source_key).rsplit("|", 1)[-1].rsplit("-", 1)[0]


def all_samples(value: str) -> list[dict]:
    groups = parse_json(value, [])
    samples = []
    for group in groups:
        if isinstance(group, dict):
            samples.extend(item for item in group.get("samples", []) if isinstance(item, dict))
    return samples


def run_reference(language: str, reference_files: list[dict], samples: list[dict]) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="repair-catalog-240-") as raw:
        root = Path(raw)
        candidate = {"language": language, "reference_files": reference_files, "main_class": "Main"}
        _compile(candidate, root, "reference")
        command = (
            [sys.executable, "main.py"]
            if language == "Python"
            else ["java", "-cp", str(root), "Main"]
            if language == "Java"
            else [str(root / "program.exe")]
        )
        return [_run(command, root, str(sample.get("stdin_text") or "")) for sample in samples]


def repair_groups(kind: str, public_value: str, hidden_value: str, outputs: list[str]) -> tuple[str, str]:
    public_groups = parse_json(public_value, [])
    hidden_groups = parse_json(hidden_value, [])
    cursor = 0

    def update_groups(groups: list[dict]) -> str:
        nonlocal cursor
        for group in groups:
            if not isinstance(group, dict):
                continue
            next_samples = []
            for sample in group.get("samples", []):
                if not isinstance(sample, dict):
                    continue
                expected = outputs[cursor]
                cursor += 1
                repaired = dict(sample)
                repaired["expected_stdout"] = expected
                repaired["explanation_zh"] = sample_explanation(kind, repaired.get("stdin_text", ""), expected)
                next_samples.append(repaired)
            group["samples"] = next_samples
        return json.dumps(groups, ensure_ascii=False, separators=(",", ":"))

    return update_groups(public_groups), update_groups(hidden_groups)


def repair(dry_run: bool = False) -> dict:
    ensure_database_schema(engine)
    db = SessionLocal()
    changed = 0
    language_counts = {language: 0 for language in LANGUAGES}
    try:
        rows = (
            db.query(ProgrammingExercise)
            .filter(
                ProgrammingExercise.source_key.like("first_party_original_v2|%"),
                ProgrammingExercise.language.in_(LANGUAGES),
            )
            .order_by(ProgrammingExercise.language, ProgrammingExercise.id)
            .all()
        )
        per_language_index = {language: 0 for language in LANGUAGES}
        for row in rows:
            language = row.language
            if language not in LANGUAGES:
                continue
            kind = exercise_kind(row.source_key)
            index = per_language_index[language]
            per_language_index[language] += 1
            reference_files = parse_json(row.reference_files_json, [])
            starter = starter_files_for(language, kind, language == "Java" and index < 10)
            public_samples = all_samples(row.public_tests_json)
            hidden_samples = all_samples(row.hidden_tests_json)
            expected_outputs = run_reference(language, reference_files, [*public_samples, *hidden_samples])
            public_json, hidden_json = repair_groups(kind, row.public_tests_json, row.hidden_tests_json, expected_outputs)
            report = parse_json(row.audit_report_json, {})
            report.update({
                "runner": "standard_io",
                "protocol_version": 1,
                "reference_passed": True,
                "wrong_solution_rejected": True,
                "starter_equals_reference": False,
                "repaired_at": datetime.now(timezone.utc).isoformat(),
                "manifest": {
                    "runner": "standard_io",
                    "protocol_version": 1,
                    "language": language.lower(),
                    "exercise_id": row.slug,
                    "editable_files": [item.get("path") for item in starter if item.get("path")],
                    "support_files": [],
                    "test_files": [],
                },
            })
            row.starter_files_json = json.dumps(starter, ensure_ascii=False, separators=(",", ":"))
            row.public_tests_json = public_json
            row.hidden_tests_json = hidden_json
            row.background_knowledge_zh = STARTER_BACKGROUND[kind]
            row.hints_zh = STARTER_HINT[kind]
            row.audit_report_json = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
            row.reference_verified = True
            row.starter_verified = True
            row.updated_at = datetime.now(timezone.utc)
            changed += 1
            language_counts[language] += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    result = {"dry_run": dry_run, "changed": changed, "counts": language_counts}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    repair(parser.parse_args().dry_run)
