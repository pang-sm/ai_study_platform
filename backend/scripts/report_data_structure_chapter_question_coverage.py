"""Coverage report for data_structure chapter questions.
Usage: python scripts/report_data_structure_chapter_question_coverage.py
"""
import json, os, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from database import SessionLocal
import models

SK = "data_structure"
REPORT_DIR = BASE / "exam_resources/11408/data_structure/chapter_questions/import_reports"

# Knowledge outline from the knowledge map data structure
# Each entry: (id, name, parent_id)
# Extracted from seed_data/knowledge_maps/data_structure_11408.json
OUTLINE_KPS = {
    "1": "第1章 总览",
    "1.1": "1.1 数据结构的基本概念",
    "1.1.1": "1.1.1 基本概念和术语",
    "1.2": "1.2 算法和算法评价",
    "1.2.1": "1.2.1 算法的基本概念",
    "1.2.2": "1.2.2 算法效率的度量",
    "2": "第2章 线性表",
    "2.1": "2.1 线性表的定义和基本操作",
    "2.2": "2.2 线性表的顺序表示",
    "2.3": "2.3 线性表的链式表示",
    "2.3.1": "2.3.1 单链表",
    "2.3.2": "2.3.2 循环链表",
    "2.3.3": "2.3.3 双向链表",
    "2.3.4": "2.3.4 静态链表",
    "3": "第3章 栈和队列",
    "3.1": "3.1 栈",
    "3.2": "3.2 队列",
    "3.2.1": "3.2.1 队列的基本概念",
    "3.2.2": "3.2.2 循环队列",
    "4": "第4章 树与二叉树",
    "4.1": "4.1 树的基本概念",
    "4.2": "4.2 二叉树",
    "5": "第5章 图",
    "5.1": "5.1 图的基本概念",
    "6": "第6章 查找",
    "6.1": "6.1 查找的基本概念",
    "7": "第7章 排序",
    "7.1": "7.1 排序的基本概念",
    "8": "第8章 排序",
    "8.1": "8.1 排序的基本概念",
    "8.2": "8.2 插入排序",
    "8.3": "8.3 交换排序",
    "8.4": "8.4 选择排序",
    "8.5": "8.5 归并排序、基数排序和计数排序",
    "8.6": "8.6 各种内部排序算法的比较及应用",
    "8.7": "8.7 外部排序",
}

def main():
    db = SessionLocal()
    items = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SK,
        models.ExamQuestionBank.source_type == "chapter",
        models.ExamQuestionBank.is_active == True).all()
    db.close()
    total_q = len(items)
    choice_q = sum(1 for i in items if (i.question_type or "").startswith("choice") or "选择" in (i.question_type or ""))
    big_q = total_q - choice_q

    # Per KP stats
    kp_counts = defaultdict(lambda: {"total": 0, "choice": 0, "big": 0, "basic": 0, "medium": 0, "hard": 0, "paths": set()})
    for i in items:
        kpid = (i.knowledge_point_id or "").strip()
        kp_counts[kpid]["total"] += 1
        if (i.question_type or "").startswith("choice") or "选择" in (i.question_type or ""):
            kp_counts[kpid]["choice"] += 1
        else: kp_counts[kpid]["big"] += 1
        d = (i.difficulty or "基础")
        if "基础" in d or "basic" in d: kp_counts[kpid]["basic"] += 1
        elif "中" in d or "medium" in d: kp_counts[kpid]["medium"] += 1
        else: kp_counts[kpid]["hard"] += 1
        kp_counts[kpid]["paths"].add(i.knowledge_point_path or "")

    outline_ids = set(OUTLINE_KPS.keys())
    db_ids = set(kp_counts.keys())
    covered = outline_ids & db_ids
    uncovered = outline_ids - db_ids
    orphans = db_ids - outline_ids

    pct = round(len(covered) / len(outline_ids) * 100, 1) if outline_ids else 0

    print(f"Outline KPs: {len(outline_ids)}  Covered: {len(covered)}  Uncovered: {len(uncovered)}  Coverage: {pct}%")
    print(f"Total questions: {total_q}  (choice={choice_q}, big={big_q})")
    print(f"Orphan KPs (in DB but not outline): {len(orphans)}")
    print(f"8.7: {kp_counts.get('8.7', {}).get('total', 0)} questions")

    # Top 20
    top20 = sorted(kp_counts.items(), key=lambda x: -x[1]["total"])[:20]
    bottom20 = sorted([(k, v) for k, v in kp_counts.items() if v["total"] > 0], key=lambda x: x[1]["total"])[:20]

    # MD report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md = [f"# 数据结构章节题库覆盖报告\n",
          f"## 总览", f"| 指标 | 值 |", f"|---|---|",
          f"| 知识点总数 | {len(outline_ids)} |", f"| 有题知识点 | {len(covered)} |",
          f"| 无题知识点 | {len(uncovered)} |", f"| 覆盖率 | {pct}% |",
          f"| 总题数 | {total_q} |", f"| 选择题 | {choice_q} |", f"| 大题 | {big_q} |",
          f"| 8.7 外部排序 | {kp_counts.get('8.7', {}).get('total', 0)} 题 |",
          f"| orphan | {len(orphans)} |",
          f"", f"## 无题知识点 ({len(uncovered)})"]
    for kp in sorted(uncovered, key=lambda x: (len(x), x)):
        md.append(f"- {kp}: {OUTLINE_KPS.get(kp, kp)}")
    md.append(f"\n## 题量 TOP20")
    md.append("| 知识点ID | 名称 | 总数 | 选择 | 大题 | 基础 | 中等 | 提高 |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for k, v in top20:
        md.append(f"| {k} | {OUTLINE_KPS.get(k, k)[:30]} | {v['total']} | {v['choice']} | {v['big']} | {v['basic']} | {v['medium']} | {v['hard']} |")
    md.append(f"\n## 题量最少非零 TOP20")
    md.append("| 知识点ID | 总数 |")
    md.append("|---|---|")
    for k, v in bottom20:
        md.append(f"| {k} ({OUTLINE_KPS.get(k, k)[:30]}) | {v['total']} |")
    (REPORT_DIR / "chapter_question_coverage_report.md").write_text("\n".join(md), encoding="utf-8")

    # JSON report
    report = {"outline_kp_count": len(outline_ids), "covered": len(covered), "uncovered": len(uncovered),
              "coverage_pct": pct, "total_questions": total_q, "choice": choice_q, "big": big_q,
              "orphans": list(orphans), "uncovered_list": sorted(uncovered),
              "kp_counts": {k: {"total": v["total"], "choice": v["choice"], "big": v["big"],
                                 "basic": v["basic"], "medium": v["medium"], "hard": v["hard"]} for k, v in kp_counts.items()}}
    (REPORT_DIR / "chapter_question_coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReports saved to {REPORT_DIR}")

if __name__ == "__main__":
    main()
