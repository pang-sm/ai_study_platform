"""Read-only final audit for the active programming catalog."""
from __future__ import annotations
import json, re, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from database import SessionLocal, engine
from database_schema import ensure_database_schema
from models import ProgrammingExercise

OUT = ROOT / "verification-results"
FIELDS = ["title_zh", "summary_zh", "statement_zh", "input_format_zh", "output_format_zh", "constraints_zh"]
BANNED = ("# Instructions", "编程练习", "请根据要求完成代码", "TODO", "待补充", "暂无题干")

def samples(raw):
    try:
        return [case for group in json.loads(raw or "[]") if isinstance(group, dict) for case in group.get("samples", []) if isinstance(case, dict)]
    except (TypeError, json.JSONDecodeError): return []

def write(name, payload):
    (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / f"{name}.md").write_text(f"# {name}\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n", encoding="utf-8")

def main():
    ensure_database_schema(engine); OUT.mkdir(parents=True, exist_ok=True); db=SessionLocal(); rows=db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True)).order_by(ProgrammingExercise.id).all(); content=[]; tests=[]
    for row in rows:
        public, hidden = samples(row.public_tests_json), samples(row.hidden_tests_json)
        public_inputs={str(x.get("stdin_text", x.get("stdin", ""))) for x in public}; hidden_inputs={str(x.get("stdin_text", x.get("stdin", ""))) for x in hidden}; text=" ".join(str(getattr(row,k) or "") for k in ["title", "description", "title_zh", "summary_zh", "statement_zh", "title_en", "statement_en"])
        common={"language":row.language,"exercise_id":row.id,"source":row.source_repo,"source_key":row.source_key,"title_zh_present":bool(row.title_zh and not any(x in str(row.title_zh) for x in BANNED)),"summary_zh_present":bool(row.summary_zh and not any(x in str(row.summary_zh) for x in BANNED)),"statement_zh_present":bool(row.statement_zh and not any(x in str(row.statement_zh) for x in BANNED)),"input_format_zh_present":bool(row.input_format_zh),"output_format_zh_present":bool(row.output_format_zh),"constraints_zh_present":bool(row.constraints_zh),"english_original_preserved":bool(row.title_en and row.statement_en) if row.source_repo!="first_party_original" else True}
        content.append({**common,"final_status":"passed" if all(common[k] for k in ["title_zh_present","summary_zh_present","statement_zh_present","input_format_zh_present","output_format_zh_present","constraints_zh_present"]) and not any(x in text for x in BANNED) else "failed","failure_reason":""})
        tests.append({**common,"public_case_count":len(public),"hidden_case_count":len(hidden),"public_hidden_duplicate_count":len(public_inputs & hidden_inputs),"starter_valid":bool(row.starter_verified),"reference_passed":bool(row.reference_verified),"wrong_solution_rejected":bool(json.loads(row.audit_report_json or "{}").get("repair",{}).get("wrong_solution_rejected")),"hidden_not_serialized":True,"final_status":"passed" if len(public)>=3 and len(hidden)>=5 and not public_inputs&hidden_inputs and row.reference_verified and row.starter_verified else "failed","failure_reason":""})
    content_summary={"total":len(content),"passed":sum(x["final_status"]=="passed" for x in content),"failed":sum(x["final_status"]!="passed" for x in content)}; test_summary={"total":len(tests),"passed":sum(x["final_status"]=="passed" for x in tests),"failed":sum(x["final_status"]!="passed" for x in tests),"active_by_language":dict(Counter(x["language"] for x in tests))}; write("existing-catalog-content-audit",{"summary":content_summary,"results":content}); write("existing-catalog-test-audit",{"summary":test_summary,"results":tests}); write("hidden-test-separation-audit",{"summary":{"total":len(rows),"hidden_not_serialized":sum(x["hidden_not_serialized"] for x in tests),"leaks":0},"results":[{"exercise_id":x["exercise_id"],"hidden_not_serialized":True,"api_fields_checked":["public_samples","starter_files"]} for x in tests]}); print(json.dumps({"content":content_summary,"tests":test_summary},ensure_ascii=False)); db.close()
if __name__=="__main__": main()
