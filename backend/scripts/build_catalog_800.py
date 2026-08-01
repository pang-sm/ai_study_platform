"""Resumable, real-compiler first-party catalog builder."""
from __future__ import annotations
import argparse, datetime, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from catalog_adapters import validate_candidate
from database import SessionLocal, engine
from database_schema import ensure_database_schema
from models import ProgrammingExercise
from seed_first_party_catalog import seed

TARGETS = {"C": 100, "C++": 75, "Python": 75, "Java": 50}
BLUEPRINT = ROOT / "backend/data/programming_catalog/curriculum_blueprint.json"
STATE = ROOT / "backend/data/programming_catalog/build_state.json"
LIVE = ROOT / "verification-results/catalog-build-live-progress.json"
LIVE_MD = ROOT / "verification-results/catalog-build-live-progress.md"

def _cases(index: int, op: str) -> list[dict]:
    pairs = [(1, 2), (5, 3), (-7, 4), (0, 9), (12, -5), (100, 10), (-9, -2), (6, 6)]
    def calc(a, b): return {"add": a + b, "sub": a - b, "mul": a * b, "max": max(a, b), "min": min(a, b)}[op]
    return [{"name": f"case-{index}-{n}", "stdin_text": f"{a} {b}\n", "expected_stdout": f"{calc(a,b)}\n"} for n, (a,b) in enumerate(pairs, 1)]

def candidate(language: str, index: int) -> dict:
    ops = ["add", "sub", "mul", "max", "min"]
    op = ops[index % len(ops)]
    symbol = {"add": "a+b", "sub": "a-b", "mul": "a*b", "max": "a>b?a:b", "min": "a<b?a:b"}[op]
    title = f"{language} 双整数 {op} 练习 {index + 1}"
    if language == "C":
        reference = f'#include <stdio.h>\nint main(void){{long long a,b;if(scanf("%lld%lld",&a,&b)!=2)return 1;printf("%lld\\n",{symbol});return 0;}}\n'
        wrong_symbol = "a-b" if op == "add" else "a+b"
        wrong = reference.replace(symbol, wrong_symbol, 1)
        starter = '#include <stdio.h>\nint main(void){ return 0; }\n'; filename = "main.c"
    elif language == "C++":
        reference = f'#include <iostream>\n#include <algorithm>\nusing namespace std;\nint main(){{long long a,b;if(!(cin>>a>>b))return 1;cout<<({symbol})<<"\\n";}}\n'
        wrong_symbol = "a-b" if op == "add" else "a+b"
        wrong = reference.replace(symbol, wrong_symbol, 1)
        starter = '#include <iostream>\nint main(){return 0;}\n'; filename = "main.cpp"
    elif language == "Python":
        expr = {"add":"a+b","sub":"a-b","mul":"a*b","max":"max(a,b)","min":"min(a,b)"}[op]
        reference = f'import sys\na,b=map(int,sys.stdin.read().split())\nprint({expr})\n'
        wrong_expr = "a-b" if op == "add" else "a+b"
        wrong = reference.replace(expr, wrong_expr, 1)
        starter = 'import sys\n'; filename = "main.py"
    else:
        expr = {"add":"a+b","sub":"a-b","mul":"a*b","max":"Math.max(a,b)","min":"Math.min(a,b)"}[op]
        reference = f'import java.util.*;\npublic class Main {{ public static void main(String[] args) {{ Scanner s=new Scanner(System.in); long a=s.nextLong(),b=s.nextLong(); System.out.println({expr}); }} }}\n'
        wrong_expr = "a-b" if op == "add" else "a+b"
        wrong = reference.replace(expr, wrong_expr, 1)
        starter = 'public class Main { public static void main(String[] args) {} }\n'; filename = "Main.java"
    return {"source_key": f"first_party_{language.lower().replace('+','p')}_v3:binary-{index}", "language": language, "title_zh": title, "summary_zh": f"使用 {language} 读取两个整数并完成 {op} 运算。", "statement_zh": f"给定两个整数，输出 {op} 运算结果。", "input_format_zh": "一行输入两个整数。", "output_format_zh": "输出一个整数并换行。", "constraints_zh": "整数绝对值不超过 10^9。", "title_en": f"{language} Binary Operation {index + 1}", "statement_en": f"Read two integers and compute {op}.", "starter_code": starter, "reference_code": reference, "wrong_code": wrong, "filename": filename, "public_cases": _cases(index, op)[:3], "hidden_cases": _cases(index, op)[3:], "problem_family_id": f"{language.lower()}-binary-{op}-{index}", "language_fit_reason": f"练习 {language} 的标准输入输出与 {op} 语法。", "difficulty": "入门", "knowledge_tags": [language, "标准输入输出", op], "source_repo": "first_party_original", "license": "project_owned"}

def counts(db):
    return {lang: db.query(ProgrammingExercise).filter(ProgrammingExercise.language == lang, ProgrammingExercise.is_active.is_(True)).count() for lang in TARGETS}

def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True); LIVE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2); STATE.write_text(payload, encoding="utf-8"); LIVE.write_text(payload, encoding="utf-8")
    LIVE_MD.write_text("# Catalog build progress\n\n```json\n" + payload + "\n```\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--resume", action="store_true"); parser.add_argument("--target-per-language", type=int, default=0); parser.add_argument("--batch-size", type=int, default=10); args = parser.parse_args()
    raise RuntimeError(
        f"quantity-first catalog expansion is disabled after quality reform; review {BLUEPRINT} and use a blueprint-driven generator"
    )
    targets = {lang: max(target, args.target_per_language) for lang, target in TARGETS.items()}
    state = {"targets": targets, "generated": 0, "validated": 0, "written": 0, "quarantined": 0, "zero_write_batches": 0, "updated_at": ""}
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        for language, target in targets.items():
            index = db.query(ProgrammingExercise).filter(ProgrammingExercise.language == language).count()
            while (current := counts(db)[language]) < target:
                items = []
                for _ in range(min(args.batch_size, target - current)):
                    item = candidate(language, index); index += 1; state["generated"] += 1
                    try:
                        validate_candidate(item); items.append(item); state["validated"] += 1
                    except Exception as exc:
                        state["quarantined"] += 1; state["last_failure"] = f"{language}: {exc}"
                written = seed(items); state["written"] += written; state["zero_write_batches"] = state["zero_write_batches"] + 1 if written == 0 else 0
                state["active_counts"] = counts(db); state["current_language"] = language; state["updated_at"] = datetime.datetime.now().isoformat(); save(state)
                if state["zero_write_batches"] >= 3: raise RuntimeError("three consecutive zero-write batches")
        state["complete"] = True; state["active_counts"] = counts(db); state["updated_at"] = datetime.datetime.now().isoformat(); save(state); print(json.dumps(state, ensure_ascii=False))
    finally: db.close()
if __name__ == "__main__": main()
