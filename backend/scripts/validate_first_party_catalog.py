from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from database import engine
from database_schema import ensure_database_schema
from catalog_adapters import validate_candidate

REQUIRED = {"source_key", "language", "title_zh", "summary_zh", "statement_zh", "input_format_zh", "output_format_zh", "constraints_zh", "starter_code", "reference_code", "public_cases", "hidden_cases", "problem_family_id", "language_fit_reason", "learning_objective_id", "learning_objective", "prerequisites", "core_skill", "novelty_reason", "difficulty", "knowledge_tags"}

def validate(item: dict) -> bool:
    missing = [key for key in REQUIRED if not item.get(key)]
    if missing:
        raise ValueError(",".join(missing))
    if item.get("source_repo") != "first_party_original" or item.get("license") != "project_owned":
        raise ValueError("invalid first-party provenance")
    if len(item["public_cases"]) < 3 or len(item["hidden_cases"]) < 5:
        raise ValueError("test count")
    validate_candidate(item)
    return True

if __name__ == "__main__":
    ensure_database_schema(engine)
    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    [validate(item) for item in items]
    print("validated", len(items))
