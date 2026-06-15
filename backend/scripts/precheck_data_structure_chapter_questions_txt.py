"""Pre-check data_structure chapter questions TXT file.
Usage: python scripts/precheck_data_structure_chapter_questions_txt.py
       python scripts/precheck_data_structure_chapter_questions_txt.py --limit 20 --show-samples
"""
import argparse, json, os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
TXT_PATH = BASE / "exam_resources/11408/data_structure/chapter_questions/raw/data_structure_chapter_questions.txt"
REPORT_DIR = BASE / "exam_resources/11408/data_structure/chapter_questions/import_reports"

KNOWLEDGE_MAP = {
    "1.1.1 基本概念和术语": "1.1.1 基本概念和术语",
    "2.1 线性表的定义和基本操作": "2.1 线性表的定义和基本操作",
    "2.2 线性表的顺序表示": "2.2 线性表的顺序表示",
    "2.3 线性表的链式表示": "2.3 线性表的链式表示",
    "3.1 栈": "3.1 栈",
    "3.2 队列": "3.2 队列",
    "4.1 树的基本概念": "4.1 树的基本概念",
    "4.2 二叉树": "4.2 二叉树",
    "5.1 图的基本概念": "5.1 图的基本概念",
    "6.1 查找的基本概念": "6.1 查找的基本概念",
    "7.1 排序的基本概念": "7.1 排序的基本概念",
    "8.1 排序的基本概念": "8.1 排序的基本概念",
}

KP_TITLES = {
    "数据": "1.1.1 基本概念和术语",
    "数据元素": "1.1.1 基本概念和术语",
    "数据对象": "1.1.1 基本概念和术语",
    "数据类型": "1.1.1 基本概念和术语",
    "数据结构": "1.1.1 基本概念和术语",
    "线性表": "2.1 线性表的定义和基本操作",
    "顺序表": "2.2 线性表的顺序表示",
    "链表": "2.3 线性表的链式表示",
    "单链表": "2.3 线性表的链式表示",
    "循环链表": "2.3 线性表的链式表示",
    "双向链表": "2.3 线性表的链式表示",
    "静态链表": "2.3 线性表的链式表示",
    "栈": "3.1 栈",
    "队列": "3.2 队列",
    "循环队列": "3.2 队列",
    "树": "4.1 树的基本概念",
    "二叉树": "4.2 二叉树",
    "图": "5.1 图的基本概念",
    "有向图": "5.1 图的基本概念",
    "查找": "6.1 查找的基本概念",
    "排序": "7.1 排序的基本概念",
}

def normalize_stem(s):
    return re.sub(r'\s+', '', str(s or '')).lower()

def find_kp(text, context_kp=""):
    for kw, kp_id in KP_TITLES.items():
        if kw in text:
            return kp_id
    if context_kp:
        return context_kp
    return ""

def parse_questions(txt, limit=0):
    lines = txt.split('\n')
    questions = []
    i = 0
    n = len(lines)
    current_kp = ""
    current_type = "choice"

    total_est = len([l for l in lines if re.match(r'^\d{2,3}\.\s', l)])
    est_big = len([l for l in lines if re.match(r'^综合\d{1,2}\.', l)])

    while i < n:
        line = lines[i].strip()
        # Detect knowledge point
        for kp_name in KP_TITLES:
            if line.startswith(kp_name) or f" - {kp_name}" in line:
                # Extract the KP path from the line
                parts = line.split(" - ")
                if len(parts) >= 2:
                    current_kp = KP_TITLES.get(parts[0], line[:30])
                else:
                    current_kp = KP_TITLES.get(line[:20], line[:30])
                i += 1
                continue

        # Detect question type
        if "单项选择题" in line:
            current_type = "choice"
            i += 1; continue
        if "综合应用" in line or "综合" in line and "大题" in line:
            current_type = "big"
            i += 1; continue

        # Detect choice question
        m = re.match(r'^(\d{2,3})\.\s(.+)', line)
        if m:
            qnum = int(m.group(1))
            stem = m.group(2).strip()
            opts = {}
            ans = ""
            j = i + 1
            while j < n and j < i + 10:
                nl = lines[j].strip()
                om = re.match(r'^([A-D])[.．、]\s*(.+)', nl)
                if om:
                    opts[om.group(1)] = om.group(2).strip()
                elif nl.startswith("答案："):
                    ans = nl.replace("答案：", "").replace("答案:", "").strip()
                    j += 1
                    break
                elif re.match(r'^\d{2,3}\.\s', nl) or re.match(r'^综合', nl) or "单项选择题" in nl:
                    break
                j += 1
            questions.append({
                "knowledge_point_path": current_kp, "question_type": "choice",
                "stem": stem, "options": opts, "standard_answer": ans,
                "analysis": "", "difficulty": "基础", "raw_index": len(questions)+1,
            })
            i = j
            if limit > 0 and len(questions) >= limit:
                break
            continue

        # Detect big question
        m = re.match(r'^综合(\d{1,2})[.．]\s*(.+)', line)
        if m:
            stem = m.group(2).strip()
            ans = ""
            j = i + 1
            while j < n and j < i + 5:
                nl = lines[j].strip()
                if nl.startswith("答案："):
                    ans = nl.replace("答案：", "").replace("答案:", "").strip()
                    j += 1
                    break
                if re.match(r'^\d{2,3}\.\s', nl) or "单项选择题" in nl:
                    break
                j += 1
            questions.append({
                "knowledge_point_path": current_kp, "question_type": "big",
                "stem": stem, "options": {}, "standard_answer": ans,
                "analysis": "", "difficulty": "基础", "raw_index": len(questions)+1,
            })
            i = j
            if limit > 0 and len(questions) >= limit:
                break
            continue

        i += 1

    return questions, total_est, est_big


def check_questions(questions):
    stats = {"total": len(questions), "choice": 0, "big": 0, "unknown_type": 0,
             "missing_stem": 0, "missing_answer": 0, "missing_options_choice": 0,
             "invalid_answer": 0, "missing_kp": 0,
             "dup_groups": 0, "matched_kp": 0, "fuzzy_kp": 0, "unmatched_kp": 0}
    seen_stems = defaultdict(list)
    matched_kps = set()
    unmatched_kps = set()
    for q in questions:
        t = q.get("question_type", "")
        if t == "choice": stats["choice"] += 1
        elif t == "big": stats["big"] += 1
        else: stats["unknown_type"] += 1
        if not (q.get("stem") or "").strip(): stats["missing_stem"] += 1
        if not (q.get("standard_answer") or "").strip(): stats["missing_answer"] += 1
        if t == "choice":
            opts = q.get("options", {})
            if len(opts) < 2: stats["missing_options_choice"] += 1
            ans = (q.get("standard_answer") or "").strip().upper()
            if ans and ans not in "ABCD": stats["invalid_answer"] += 1
        kp = (q.get("knowledge_point_path") or "").strip()
        if not kp: stats["missing_kp"] += 1
        elif kp in KNOWLEDGE_MAP: matched_kps.add(kp)
        else: unmatched_kps.add(kp)
        ns = normalize_stem(q.get("stem", ""))
        if ns: seen_stems[ns].append(q["raw_index"])

    stats["matched_kp"] = len(matched_kps)
    stats["unmatched_kp"] = len(unmatched_kps)
    stats["dup_groups"] = sum(1 for v in seen_stems.values() if len(v) > 1)

    return stats, matched_kps, unmatched_kps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--show-samples", action="store_true")
    args = parser.parse_args()

    txt = TXT_PATH.read_text(encoding="utf-8")
    chars = len(txt)
    questions, est_total, est_big = parse_questions(txt, limit=args.limit)
    stats, matched_kps, unmatched_kps = check_questions(questions)

    print(f"File: {TXT_PATH}")
    print(f"Chars: {chars}")
    print(f"Estimated total: {est_total} (choice={est_total-est_big}, big={est_big})")
    print(f"Parsed: {len(questions)}")
    print(f"  Choice: {stats['choice']}")
    print(f"  Big: {stats['big']}")
    print(f"  Unknown: {stats['unknown_type']}")
    print(f"Missing stem: {stats['missing_stem']}")
    print(f"Missing answer: {stats['missing_answer']}")
    print(f"Missing options (choice): {stats['missing_options_choice']}")
    print(f"Invalid answer: {stats['invalid_answer']}")
    print(f"Missing KP: {stats['missing_kp']}")
    print(f"KP matched: {stats['matched_kp']}")
    print(f"KP unmatched: {stats['unmatched_kp']}")
    print(f"Duplicate groups: {stats['dup_groups']}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Save JSON report
    report = {"source_file": str(TXT_PATH), "chars": chars, "estimated_total": est_total,
              "parsed_total": len(questions), "stats": stats,
              "matched_kps": sorted(matched_kps), "unmatched_kps": sorted(unmatched_kps),
              "questions": questions}
    (REPORT_DIR / "precheck_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReports saved to {REPORT_DIR}")

    # Save preview (limit to 100)
    preview = {"source_file": str(TXT_PATH), "total_parsed": len(questions),
               "questions": questions[:100]}
    (REPORT_DIR / "parsed_preview.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save MD
    md = [f"# 数据结构章节题库 TXT 预检报告\n",
          f"- 源文件: {TXT_PATH.name}", f"- 字符数: {chars}",
          f"- 估计总数: {est_total} (选择题 {est_total-est_big}, 大题 {est_big})",
          f"- 成功解析: {len(questions)}",
          f"", f"## 统计",
          f"| 指标 | 数量 |", f"|---|---|",
          f"| 选择题 | {stats['choice']} |", f"| 大题 | {stats['big']} |",
          f"| 缺题干 | {stats['missing_stem']} |", f"| 缺答案 | {stats['missing_answer']} |",
          f"| 选择题缺选项 | {stats['missing_options_choice']} |", f"| 答案非法 | {stats['invalid_answer']} |",
          f"| 缺知识点 | {stats['missing_kp']} |", f"| 知识点匹配 | {stats['matched_kp']} |",
          f"| 知识点未匹配 | {stats['unmatched_kp']} |", f"| 疑似重复 | {stats['dup_groups']} |",
    ]
    (REPORT_DIR / "precheck_report.md").write_text("\n".join(md), encoding="utf-8")

    if args.show_samples and questions:
        print("\n=== Samples ===")
        for q in questions[:5]:
            print(f"\n[#{q['raw_index']}] {q['knowledge_point_path']} | {q['question_type']}")
            print(f"  {q['stem'][:80]}")
            opts = q.get('options', {})
            for k, v in opts.items():
                print(f"  {k}. {v[:60]}")
            print(f"  答案: {q['standard_answer']}")


if __name__ == "__main__":
    main()
