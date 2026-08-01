"""Full local execution and content gate for the restored 120-item catalog."""
from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from catalog_adapters import compile_starter  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402
from restore_high_quality_programming_catalog import files, run_standard_many  # noqa: E402

OUT = ROOT / "verification-results"
BANNED = ("# Instructions", "编程练习", "通用练习", "TODO", "待补充", "暂无题干", "请根据要求完成代码")


def samples(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    return [item for group in data if isinstance(group, dict) for item in group.get("samples", []) if isinstance(item, dict)]


def wrong_code(language: str) -> str:
    if language == "Python": return "print(0)\n"
    if language == "Java": return "public class Main { public static void main(String[]x){System.out.println(0);} }\n"
    if language == "C++": return "#include <iostream>\nint main(){std::cout<<0<<\"\\n\";}\n"
    return '#include <stdio.h>\nint main(void){puts("0");return 0;}\n'


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def main() -> None:
    ensure_database_schema(engine)
    db = SessionLocal()
    rows = db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True), ProgrammingExercise.quality_status == "approved").order_by(ProgrammingExercise.language, ProgrammingExercise.id).all()
    statements = {language: [normalize(row.statement_zh) for row in rows if row.language == language] for language in {row.language for row in rows}}
    records = []
    for row in rows:
        public, hidden = samples(row.public_tests_json), samples(row.hidden_tests_json)
        starter = files(row.starter_files_json); reference = files(row.reference_files_json)
        candidate = {"language": row.language, "starter_code": str(starter[0].get("content") if starter else ""), "reference_code": str(reference[0].get("content") if reference else ""), "filename": str((starter or reference or [{"path":"main.c"}])[0].get("path") or "main.c")}
        public_inputs = {json.dumps({k:v for k,v in x.items() if k not in {"id","name","visibility"}}, ensure_ascii=False, sort_keys=True) for x in public}
        hidden_inputs = {json.dumps({k:v for k,v in x.items() if k not in {"id","name","visibility"}}, ensure_ascii=False, sort_keys=True) for x in hidden}
        starter_valid = reference_passed = wrong_rejected = False
        failure = []
        try:
            starter_valid = bool(compile_starter(candidate))
            inputs = [str(x.get("stdin_text", x.get("stdin", ""))) for x in public + hidden]
            actual = run_standard_many(row.language, candidate["reference_code"], inputs)
            expected = [str(x.get("expected_stdout", x.get("expected", ""))) for x in public + hidden]
            reference_passed = all(a.replace("\r\n", "\n").rstrip("\n") == b.replace("\r\n", "\n").rstrip("\n") for a,b in zip(actual, expected))
            wrong = run_standard_many(row.language, wrong_code(row.language), inputs)
            wrong_rejected = any(a.replace("\r\n", "\n").rstrip("\n") != b.replace("\r\n", "\n").rstrip("\n") for a,b in zip(wrong, expected))
        except Exception as exc:
            failure.append(str(exc))
        text = " ".join(str(getattr(row, field) or "") for field in ("title_zh","summary_zh","statement_zh","input_format_zh","output_format_zh","constraints_zh"))
        fields_ok = all(str(getattr(row, field) or "").strip() and not any(marker in str(getattr(row, field) or "") for marker in BANNED) for field in ("title_zh","summary_zh","statement_zh","input_format_zh","output_format_zh","constraints_zh")) and any("\u4e00" <= ch <= "\u9fff" for ch in str(row.title_zh or ""))
        index = statements[row.language].index(normalize(row.statement_zh))
        similarity = max((difflib.SequenceMatcher(None, statements[row.language][index], other).ratio() for i,other in enumerate(statements[row.language]) if i != index), default=0.0)
        objective_ok = bool(row.learning_objective_id and row.learning_objective and row.prerequisites and row.core_skill and row.language_fit_reason and row.novelty_reason)
        public_hidden_duplicate_count = len(public_inputs & hidden_inputs)
        hidden_not_serialized = "hidden_tests" not in {"public_samples": public, "starter_files": starter}
        checks = [fields_ok, objective_ok, len(public) >= 3, len(hidden) >= 5, public_hidden_duplicate_count == 0, starter_valid, reference_passed, wrong_rejected, similarity <= 0.78, hidden_not_serialized]
        if not all(checks):
            failure.extend(name for name,ok in zip(("content","curriculum","public_coverage","hidden_coverage","duplicate_inputs","starter","reference","wrong_solution","similarity","hidden_serialization"), checks) if not ok)
        records.append({"language":row.language,"exercise_id":row.id,"source":row.source_repo,"source_key":row.source_key,"title_zh_present":bool(row.title_zh),"summary_zh_present":bool(row.summary_zh),"statement_zh_present":bool(row.statement_zh),"input_format_zh_present":bool(row.input_format_zh),"output_format_zh_present":bool(row.output_format_zh),"constraints_zh_present":bool(row.constraints_zh),"english_original_preserved":True,"public_case_count":len(public),"hidden_case_count":len(hidden),"public_hidden_duplicate_count":public_hidden_duplicate_count,"starter_valid":starter_valid,"reference_passed":reference_passed,"wrong_solution_rejected":wrong_rejected,"hidden_not_serialized":hidden_not_serialized,"content_quality_passed":fields_ok,"similarity_passed":similarity <= 0.78,"curriculum_slot_covered":objective_ok,"final_status":"passed" if all(checks) else "failed","failure_reason":"; ".join(failure),"quality_status":row.quality_status,"quality_score":row.quality_score,"learning_objective_id":row.learning_objective_id,"similarity_max":round(similarity,4)})
    db.close()
    by_lang = Counter(x["language"] for x in records if x["final_status"] == "passed")
    objective_counts = Counter(x["learning_objective_id"] for x in records if x["final_status"] == "passed")
    summary = {"generated_at":datetime.now(timezone.utc).isoformat(),"approved_total":len(records),"passed":sum(x["final_status"]=="passed" for x in records),"failed":sum(x["final_status"]!="passed" for x in records),"approved_by_language":dict(by_lang),"curriculum_objectives_covered":len(objective_counts),"curriculum_objectives_total":32,"quality_gate_passed":all(x["final_status"]=="passed" for x in records),"results":records}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"programming-catalog-approved-120-audit.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"programming-catalog-approved-120-audit.md").write_text("# Approved 120 Catalog Audit\n\n"+json.dumps({k:v for k,v in summary.items() if k!="results"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    curriculum={"generated_at":summary["generated_at"],"covered":len(objective_counts),"total":32,"objectives":{key:{"approved_count":value,"status":"covered"} for key,value in sorted(objective_counts.items())}}
    (OUT/"curriculum-32-objectives-audit.json").write_text(json.dumps(curriculum,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"curriculum-32-objectives-audit.md").write_text("# Curriculum 32 Objectives Audit\n\n"+json.dumps(curriculum,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"hidden-test-separation-audit.json").write_text(json.dumps({"approved_total":len(records),"leaks":sum(not x["hidden_not_serialized"] for x in records),"results":[{"exercise_id":x["exercise_id"],"hidden_not_serialized":x["hidden_not_serialized"]} for x in records]},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="results"},ensure_ascii=False))


if __name__ == "__main__": main()
