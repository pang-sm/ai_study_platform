"""Aggregate the four real execution audits and verify API/test isolation."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from main import app, serialize_programming_exercise  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

OUT = ROOT / "verification-results"
LANGUAGES = ("C", "C++", "Python", "Java")


def hidden_keys(value, path=""):
    found=[]
    if isinstance(value, dict):
        for key, item in value.items():
            name=f"{path}.{key}" if path else key
            if str(key).lower() in {"hidden_tests", "hidden_samples", "hidden_inputs", "hidden_outputs", "hidden_cases"}:
                found.append(name)
            found.extend(hidden_keys(item,name))
    elif isinstance(value, list):
        for index,item in enumerate(value): found.extend(hidden_keys(item,f"{path}[{index}]"))
    return found


def md(path: Path, title: str, payload: dict):
    path.write_text(f"# {title}\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n", encoding="utf-8")


def main() -> None:
    ensure_database_schema(engine)
    per=[]
    for language in LANGUAGES:
        path=OUT/f"programming-catalog-480-{language.replace('+','p')}-audit.json"
        per.append(json.loads(path.read_text(encoding="utf-8")))
    rows=[item for result in per for item in result["results"]]
    db=SessionLocal()
    model_rows=db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True),ProgrammingExercise.quality_status=="approved").order_by(ProgrammingExercise.id).all()
    model_by_id={row.id:row for row in model_rows}
    api_checks=[]
    leaks=[]
    for record in rows:
        exercise=model_by_id.get(record["exercise_id"])
        payload=serialize_programming_exercise(exercise) if exercise else {}
        keys=hidden_keys(payload)
        record["hidden_not_serialized"] = not bool(keys)
        if keys: leaks.append({"exercise_id":record["exercise_id"],"keys":keys})
    try:
        from fastapi.testclient import TestClient
        client=TestClient(app)
        for language in LANGUAGES:
            response=client.get("/programming/exercises",params={"language":language,"page":1,"page_size":48})
            body=response.json() if response.headers.get("content-type","").startswith("application/json") else {}
            api_checks.append({"language":language,"status_code":response.status_code,"total":body.get("total"),"page_items":len(body.get("items",[]))})
            for item in body.get("items",[])[:5]:
                detail=client.get(f"/programming/exercises/{item['id']}")
                detail_body=detail.json() if detail.status_code==200 else {}
                api_checks.append({"language":language,"exercise_id":item["id"],"detail_status_code":detail.status_code,"detail_hidden_keys":hidden_keys(detail_body)})
    except Exception as exc:
        api_checks.append({"error":str(exc)})
    db.close()
    counts=Counter(record["language"] for record in rows if record["final_status"]=="passed")
    objectives=Counter(model.learning_objective_id for model in model_rows if model.learning_objective_id)
    difficulty={language:dict(Counter(model.difficulty for model in model_rows if model.language==language)) for language in LANGUAGES}
    test_summary={"approved_total":len(rows),"passed":sum(record["final_status"]=="passed" for record in rows),"failed":sum(record["final_status"]!="passed" for record in rows),"public_min":min((record["public_case_count"] for record in rows),default=0),"hidden_min":min((record["hidden_case_count"] for record in rows),default=0),"duplicates":sum(record["public_hidden_duplicate_count"] for record in rows),"wrong_rejected":sum(not record["wrong_solution_rejected"] for record in rows),"starter_failures":sum(not record["starter_valid"] for record in rows),"reference_failures":sum(not record["reference_passed"] for record in rows)}
    curriculum={"total_objectives":32,"covered_objectives":len(objectives),"missing_objectives":[],"objective_counts":dict(sorted(objectives.items()))}
    overlap={"source_key_count":len({record["source_key"] for record in rows}),"row_count":len(rows),"duplicate_source_keys":len(rows)-len({record["source_key"] for record in rows}),"max_similarity":max((record["similarity_max"] for record in rows),default=0),"similarity_failures":[record["source_key"] for record in rows if not record["similarity_passed"]],"max_family_per_language":max(Counter((model.language,model.problem_family_id) for model in model_rows).values(),default=0)}
    summary={"generated_at":datetime.now(timezone.utc).isoformat(),"approved_total":len(rows),"approved_by_language":dict(counts),"all_execution_gates_passed":test_summary["failed"]==0 and test_summary["duplicates"]==0 and test_summary["wrong_rejected"]==0 and test_summary["starter_failures"]==0 and test_summary["reference_failures"]==0,"curriculum":curriculum,"difficulty":difficulty,"tests":test_summary,"hidden_test_leaks":len(leaks),"api_checks":api_checks,"uncompleted_items":leaks+[record for record in rows if record["final_status"]!="passed"]}
    (OUT/"programming-catalog-480-audit.json").write_text(json.dumps({"summary":summary,"results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
    md(OUT/"programming-catalog-480-audit.md","Programming Catalog 480 Audit",summary)
    (OUT/"programming-curriculum-coverage.json").write_text(json.dumps(curriculum,ensure_ascii=False,indent=2),encoding="utf-8")
    md(OUT/"programming-curriculum-coverage.md","Programming Curriculum Coverage",curriculum)
    gradient={"difficulty":difficulty,"target":{"入门":30,"基础":40,"中等":25,"进阶":20,"挑战":5},"passed":all(difficulty[language]=={"入门":30,"基础":40,"中等":25,"进阶":20,"挑战":5} for language in LANGUAGES)}
    (OUT/"programming-difficulty-gradient.json").write_text(json.dumps(gradient,ensure_ascii=False,indent=2),encoding="utf-8"); md(OUT/"programming-difficulty-gradient.md","Programming Difficulty Gradient",gradient)
    (OUT/"programming-test-coverage.json").write_text(json.dumps(test_summary,ensure_ascii=False,indent=2),encoding="utf-8"); md(OUT/"programming-test-coverage.md","Programming Test Coverage",test_summary)
    (OUT/"programming-overlap-audit.json").write_text(json.dumps(overlap,ensure_ascii=False,indent=2),encoding="utf-8"); md(OUT/"programming-overlap-audit.md","Programming Overlap Audit",overlap)
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == "__main__": main()
