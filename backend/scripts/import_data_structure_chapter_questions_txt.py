"""Import safe chapter questions into ExamQuestionBank.
Usage: python scripts/import_data_structure_chapter_questions_txt.py --dry-run --limit 50
       python scripts/import_data_structure_chapter_questions_txt.py --limit 50
"""
import argparse, json, os, re, sys
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent.parent
PREVIEW_PATH = BASE / "exam_resources/11408/data_structure/chapter_questions/import_reports/precheck_report.json"
CHECKED_DIR = BASE / "exam_resources/11408/data_structure/chapter_questions/checked"
REPORT_DIR = BASE / "exam_resources/11408/data_structure/chapter_questions/import_reports"

STUDY_KP_MAP = {
    "数据": ("1.1.1", "基本概念和术语", "1.1.1 基本概念和术语"),
    "数据元素": ("1.1.1", "基本概念和术语", "1.1.1 基本概念和术语"),
    "数据对象": ("1.1.1", "基本概念和术语", "1.1.1 基本概念和术语"),
    "数据类型": ("1.1.1", "基本概念和术语", "1.1.1 基本概念和术语"),
    "数据结构": ("1.1.1", "基本概念和术语", "1.1.1 基本概念和术语"),
    "基本概念和术语": ("1.1.1", "基本概念和术语", "1.1.1 基本概念和术语"),
    "线性表": ("2.1", "线性表的定义和基本操作", "2.1 线性表的定义和基本操作"),
    "顺序表": ("2.2", "线性表的顺序表示", "2.2 线性表的顺序表示"),
    "链表": ("2.3", "线性表的链式表示", "2.3 线性表的链式表示"),
    "单链表": ("2.3", "线性表的链式表示", "2.3 线性表的链式表示"),
    "循环链表": ("2.3", "线性表的链式表示", "2.3 线性表的链式表示"),
    "双向链表": ("2.3", "线性表的链式表示", "2.3 线性表的链式表示"),
    "静态链表": ("2.3", "线性表的链式表示", "2.3 线性表的链式表示"),
    "栈": ("3.1", "栈", "3.1 栈"),
    "队列": ("3.2", "队列", "3.2 队列"),
    "循环队列": ("3.2", "队列", "3.2 队列"),
    "树": ("4.1", "树的基本概念", "4.1 树的基本概念"),
    "二叉树": ("4.2", "二叉树", "4.2 二叉树"),
    "图": ("5.1", "图的基本概念", "5.1 图的基本概念"),
    "有向图": ("5.1", "图的基本概念", "5.1 图的基本概念"),
    "查找": ("6.1", "查找的基本概念", "6.1 查找的基本概念"),
    "排序": ("7.1", "排序的基本概念", "7.1 排序的基本概念"),
}

def norm_stem(s):
    return re.sub(r'\s+', '', str(s or '')).lower()

def enrich_kp(q):
    kp_raw = (q.get("knowledge_point_path") or "").strip()
    for kw, (kp_id, kp_name, kp_path) in STUDY_KP_MAP.items():
        if kw in kp_raw:
            return kp_id, kp_name, kp_path
    return "", "", kp_raw

def is_safe(q):
    """Return (True, None) or (False, reason)"""
    stem = (q.get("stem") or "").strip()
    ans = (q.get("standard_answer") or "").strip()
    qt = (q.get("question_type") or "").strip()
    opts = q.get("options") or {}
    if not stem: return False, "missing_stem"
    if not ans: return False, "missing_answer"
    kp_id, kp_name, kp_path = enrich_kp(q)
    if not kp_id: return False, "missing_knowledge_point"
    if qt not in ("choice", "big", "选择题", "大题"): return False, "unknown_type"
    if qt in ("choice", "选择题"):
        for l in "ABCD":
            if not (opts.get(l) or "").strip():
                return False, "missing_options"
        if ans.upper() not in "ABCD":
            return False, "invalid_answer"
    return True, None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    data = json.loads(PREVIEW_PATH.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    print(f"Total parsed: {len(questions)}")

    ready = []
    rejected = []
    reasons = {}
    for q in questions:
        ok, reason = is_safe(q)
        if ok:
            kp_id, kp_name, kp_path = enrich_kp(q)
            q["knowledge_point_id"] = kp_id
            q["knowledge_point_name"] = kp_name
            q["knowledge_point_path"] = kp_path
            q["difficulty"] = q.get("difficulty") or "基础"
            q["analysis"] = q.get("analysis") or "暂无解析"
            ready.append(q)
        else:
            rejected.append(q)
            reasons[reason] = reasons.get(reason, 0) + 1

    # Dedup ready
    seen = set()
    deduped = []
    for q in ready:
        ns = norm_stem(q["stem"])
        kp = q.get("knowledge_point_id", "")
        key = f"{kp}:{ns}"
        if key in seen:
            rejected.append(q)
            reasons["duplicated"] = reasons.get("duplicated", 0) + 1
            continue
        seen.add(key)
        deduped.append(q)
    ready = deduped

    rdy_choice = sum(1 for q in ready if q["question_type"] in ("choice", "选择题"))
    rdy_big = sum(1 for q in ready if q["question_type"] in ("big", "大题"))

    print(f"Ready: {len(ready)} (choice={rdy_choice}, big={rdy_big})")
    print(f"Rejected: {len(rejected)} reasons: {reasons}")

    CHECKED_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(ready, (CHECKED_DIR / "parsed_ready.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(rejected, (CHECKED_DIR / "parsed_rejected.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Reports
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rr = {"total_parsed": len(questions), "ready": len(ready), "rejected": len(rejected),
          "ready_choice": rdy_choice, "ready_big": rdy_big, "reasons": reasons}
    json.dump(rr, (REPORT_DIR / "ready_report.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
    md = [f"# 章节题库 ready 报告\n", f"- 解析: {len(questions)}", f"- ready: {len(ready)} (选择{rdy_choice} 大题{rdy_big})",
          f"- rejected: {len(rejected)}", ""] + [f"- {k}: {v}" for k,v in reasons.items()]
    (REPORT_DIR / "ready_report.md").write_text("\n".join(md), encoding="utf-8")

    if args.dry_run:
        print("DRY RUN - no database writes")
        return

    # Import
    sys.path.insert(0, str(BASE))
    from database import SessionLocal
    import models
    db = SessionLocal()
    limit = args.limit if args.limit > 0 else (len(ready) if args.all else 50)
    to_import = ready[:limit]
    inserted = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    for q in to_import:
        ns = norm_stem(q["stem"])
        kp_id = q.get("knowledge_point_id", "")
        dup = db.query(models.ExamQuestionBank).filter(
            models.ExamQuestionBank.subject_key == "data_structure",
            models.ExamQuestionBank.source_type == "chapter",
            models.ExamQuestionBank.knowledge_point_id == kp_id,
        ).all()
        dup_match = any(norm_stem(d.stem) == ns for d in dup)
        if dup_match:
            skipped += 1
            continue
        opts = q.get("options") or {}
        item = models.ExamQuestionBank(
            subject_key="data_structure", subject_name="数据结构",
            source_type="chapter", visibility="public",
            knowledge_point_id=kp_id,
            knowledge_point_name=q.get("knowledge_point_name", ""),
            knowledge_point_path=q.get("knowledge_point_path", ""),
            question_type="choice" if q["question_type"] in ("choice","选择题") else "big",
            stem=q["stem"], options_json=json.dumps(opts, ensure_ascii=False),
            standard_answer=q.get("standard_answer",""), analysis=q.get("analysis",""),
            difficulty=q.get("difficulty","基础"),
            source_ref=f"chapter_import:data_structure:txt:raw_index:{q.get('raw_index','')}",
        )
        db.add(item)
        inserted += 1
    db.commit()
    db.close()
    print(f"Imported: {inserted} inserted, {skipped} skipped")

    # Verify
    db2 = SessionLocal()
    total = db2.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == "data_structure",
        models.ExamQuestionBank.source_type == "chapter").count()
    db2.close()
    print(f"Total chapter questions in DB: {total}")

if __name__ == "__main__":
    main()
