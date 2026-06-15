"""Remap chapter question knowledge points based on keyword analysis.
Usage: python scripts/remap_data_structure_chapter_question_kps.py --dry-run
       python scripts/remap_data_structure_chapter_question_kps.py --apply-high
"""
import argparse, json, os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from database import SessionLocal
import models

SK = "data_structure"
REPORT_DIR = BASE / "exam_resources/11408/data_structure/chapter_questions/import_reports"

OUTLINE = {
    "1.1.1": "1.1.1 基本概念和术语",
    "2.1": "2.1 线性表的定义和基本操作",
    "2.2": "2.2 线性表的顺序表示",
    "2.3": "2.3 线性表的链式表示",
    "3.1": "3.1 栈",
    "3.2": "3.2 队列",
    "3.3": "3.3 栈和队列的应用",
    "3.4": "3.4 数组和特殊矩阵",
    "4.1": "4.1 串的定义和实现",
    "4.2": "4.2 串的模式匹配",
    "5.1": "5.1 树的基本概念",
    "5.2": "5.2 二叉树的概念",
    "5.3": "5.3 二叉树的遍历和线索二叉树",
    "5.4": "5.4 树、森林",
    "5.5": "5.5 树与二叉树的应用",
    "6.1": "6.1 图的基本概念",
    "6.2": "6.2 图的遍历",
    "6.3": "6.3 图的存储及基本操作",
    "6.4": "6.4 图的应用",
    "7.1": "7.1 查找的基本概念",
    "7.2": "7.2 线性表的查找",
    "7.3": "7.3 树形查找",
    "7.4": "7.4 B树和B+树",
    "7.5": "7.5 散列表",
    "8.1": "8.1 排序的基本概念",
    "8.2": "8.2 插入排序",
    "8.3": "8.3 交换排序",
    "8.4": "8.4 选择排序",
    "8.5": "8.5 归并排序、基数排序和计数排序",
    "8.6": "8.6 各种内部排序算法的比较及应用",
    "8.7": "8.7 外部排序",
}

# Keyword matching rules: (keywords, target_kp_id, confidence, priority)
RULES = [
    # Sort - high
    (["外部排序", "败者树", "置换选择", "归并段", "多路平衡归并", "初始归并段", "最佳归并树", "多路归并"], "8.7", "high", 10),
    (["快速排序", "快排"], "8.3", "high", 9),
    (["冒泡排序"], "8.3", "high", 8),
    (["插入排序", "直接插入", "折半插入", "希尔排序", "shell"], "8.2", "high", 9),
    (["选择排序", "堆排序", "简单选择", "堆调整", "大根堆", "小根堆", "大顶堆", "小顶堆", "最大堆", "最小堆"], "8.4", "high", 9),
    (["归并排序", "归并", "二路归并"], "8.5", "high", 9),
    (["基数排序", "计数排序", "桶排序"], "8.5", "high", 8),
    (["排序", "稳定性", "不稳定", "关键字", "升序", "降序", "趟数"], "8.1", "medium", 5),
    # Search
    (["KMP", "next数组", "nextval", "模式匹配", "串匹配", "前缀函数"], "4.2", "high", 10),
    (["顺序查找", "折半查找", "二分查找", "分块查找", "索引查找", "查找长度", "ASL"], "7.2", "high", 8),
    (["二叉排序树", "BST", "二叉搜索树"], "7.3", "high", 9),
    (["平衡二叉树", "AVL", "红黑树", "旋转"], "7.3", "high", 9),
    (["B树", "B+树", "m阶B树"], "7.4", "high", 10),
    (["散列", "哈希", "hash", "装填因子", "冲突", "线性探测", "二次探测", "再散列", "链地址", "探查"], "7.5", "high", 9),
    # Graph
    (["Dijkstra", "Floyd", "最小生成树", "Prim", "Kruskal", "最短路径", "拓扑排序", "关键路径", "AOE", "AOV"], "6.4", "high", 10),
    (["BFS", "DFS", "广度优先", "深度优先", "遍历", "连通分量"], "6.2", "high", 8),
    (["邻接矩阵", "邻接表", "邻接多重表", "十字链表"], "6.3", "high", 8),
    (["图", "顶点", "有向图", "无向图", "度", "入度", "出度", "连通", "完全图"], "6.1", "medium", 6),
    # Tree
    (["哈夫曼", "Huffman", "WPL", "带权路径长度", "前缀编码"], "5.5", "high", 10),
    (["二叉树", "满二叉树", "完全二叉树", "二叉链表", "n0=n2+1"], "5.2", "high", 8),
    (["先序", "中序", "后序", "层序", "遍历", "线索二叉树", "前序"], "5.3", "high", 8),
    (["森林", "树转二叉树", "孩子兄弟"], "5.4", "high", 8),
    (["树", "结点", "叶子", "深度", "高度", "度", "双亲", "孩子"], "5.1", "medium", 5),
    # Stack/Queue
    (["栈", "入栈", "出栈", "栈顶", "后进先出", "LIFO", "括号匹配"], "3.1", "high", 9),
    (["队列", "循环队列", "入队", "出队", "先进先出", "FIFO", "队头", "队尾", "rear", "front"], "3.2", "high", 9),
    (["递归", "表达式求值", "后缀表达式", "前缀表达式", "中缀"], "3.3", "high", 8),
    (["数组", "三元组", "特殊矩阵", "稀疏矩阵", "对称矩阵", "三角矩阵", "对角矩阵"], "3.4", "high", 8),
    # Linear list
    (["顺序表", "顺序存储", "随机访问", "数组下标", "顺序结构"], "2.2", "high", 8),
    (["单链表", "链表", "指针域", "next指针", "头结点", "链式存储", "头插法", "尾插法"], "2.3", "high", 8),
    (["线性表", "数据元素", "插入", "删除", "查找", "合并", "逆置"], "2.1", "medium", 5),
    # String
    (["串", "字符串", "子串", "主串", "空串", "模式匹配"], "4.1", "medium", 6),
]

def classify_question(stem, analysis="", opts_json=""):
    text = f"{stem} {analysis} {opts_json}".lower()
    best = ("", "low", 0)
    for keywords, kpid, conf, pri in RULES:
        matches = sum(1 for kw in keywords if kw.lower() in text)
        if matches > 0:
            score = pri + matches * 2
            if score > best[2]:
                best = (kpid, conf, score)
    if best[1] == "low" and not best[0]:
        return "", "low", ""
    return best

OUTLINE_ORDER = list(OUTLINE.keys())

def parse_raw_index(item):
    src = item.source_ref or ""
    m = re.search(r'raw_index:(\d+)', str(src))
    if m: return int(m.group(1))
    return item.id + 10000  # fallback: use id

def score_sequence_match(item, kp_index, outline_order):
    """Score how well an item matches the KP at given position."""
    text = f"{item.stem or ''} {item.analysis or ''} {item.options_json or ''}".lower()
    kpid = outline_order[kp_index]
    score = 0
    for keywords, target, conf, pri in RULES:
        if target != kpid: continue
        matches = sum(1 for kw in keywords if kw.lower() in text)
        if matches > 0:
            score += pri + matches * 2
    # Sequence bonus: prefer current position
    score += max(0, 5 - abs(kp_index - kp_index))  # self bonus
    return score

def classify_sequence(items_list, outline_order):
    """Map items to KPs using sequential scanning."""
    n_kp = len(outline_order)
    kp_idx = 0
    results = []
    for item in items_list:
        best_kp = ""
        best_score = 0
        # Try from current kp_idx forward up to n_kp-1
        for j in range(kp_idx, min(kp_idx + 6, n_kp)):
            s = score_sequence_match(item, j, outline_order)
            if s > best_score:
                best_score = s
                best_kp = outline_order[j]
        # If no match, try keyword fallback
        if best_score < 5:
            kw_kp, kw_conf, _ = classify_question(item.stem or "", item.analysis or "", item.options_json or "")
            if kw_kp and kw_conf == "high":
                best_kp = kw_kp
                # Update kp_idx if high-confidence keyword match
                if kw_kp in outline_order:
                    new_idx = outline_order.index(kw_kp)
                    if new_idx > kp_idx: kp_idx = new_idx
        # Update position
        if best_kp in outline_order:
            new_pos = outline_order.index(best_kp)
            if new_pos >= kp_idx: kp_idx = new_pos
        conf = "high" if best_score >= 10 else ("medium" if best_score >= 5 else "low")
        results.append((best_kp, conf, best_score))
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply-high", action="store_true")
    parser.add_argument("--apply-medium", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--strategy", type=str, default="keyword", choices=["keyword","sequence"])
    args = parser.parse_args()

    db = SessionLocal()
    items = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SK,
        models.ExamQuestionBank.source_type == "chapter",
        models.ExamQuestionBank.is_active == True).all()
    # Sort by raw_index if available
    items_sorted = sorted(items, key=parse_raw_index)

    old_kp_counts = defaultdict(int)
    for i in items_sorted: old_kp_counts[(i.knowledge_point_id or "")] += 1

    remap = {"high": 0, "medium": 0, "low": 0, "skipped": 0}
    suggestions = []
    new_kp_counts = dict(old_kp_counts)

    if args.strategy == "sequence":
        seq_results = classify_sequence(items_sorted, OUTLINE_ORDER)
        for item, (kp_id, conf, score) in zip(items_sorted, seq_results):
            if kp_id and kp_id != (item.knowledge_point_id or ""):
                old = item.knowledge_point_id or ""
                suggestions.append({"id": item.id, "stem": item.stem[:80], "old_kp": old,
                                    "new_kp": kp_id, "confidence": conf,
                                    "raw_index": parse_raw_index(item)})
                remap[conf] += 1
                if old in new_kp_counts: new_kp_counts[old] -= 1
                new_kp_counts[kp_id] = new_kp_counts.get(kp_id, 0) + 1
            else:
                remap["skipped"] += 1
    else:
        for item in items_sorted:
            if args.limit > 0 and len(suggestions) >= args.limit: break
            kp_id, conf, score = classify_question(item.stem, item.analysis or "",
                                                   item.options_json or "")
            if kp_id and kp_id != (item.knowledge_point_id or ""):
                old = item.knowledge_point_id or ""
                suggestions.append({"id": item.id, "stem": item.stem[:80], "old_kp": old,
                                    "new_kp": kp_id, "confidence": conf})
                remap[conf] += 1
                if old in new_kp_counts: new_kp_counts[old] -= 1
                new_kp_counts[kp_id] = new_kp_counts.get(kp_id, 0) + 1
            else:
                remap["skipped"] += 1

    old_cov = sum(1 for k in OUTLINE if old_kp_counts.get(k, 0) > 0)
    new_cov = sum(1 for k in OUTLINE if new_kp_counts.get(k, 0) > 0)
    old_zero = sum(1 for k in OUTLINE if old_kp_counts.get(k, 0) == 0)
    new_zero = sum(1 for k in OUTLINE if new_kp_counts.get(k, 0) == 0)

    print(f"Current coverage: {old_cov}/{len(OUTLINE)} ({round(old_cov/len(OUTLINE)*100,1)}%)  uncovered: {old_zero}")
    print(f"Projected: {new_cov}/{len(OUTLINE)} ({round(new_cov/len(OUTLINE)*100,1)}%)  uncovered: {new_zero}")
    print(f"8.7 current: {old_kp_counts.get('8.7',0)}  projected: {new_kp_counts.get('8.7',0)}")
    print(f"Suggestions: total={len(suggestions)}  high={remap['high']}  medium={remap['medium']}  low={remap['low']}  skipped={remap['skipped']}")

    # Top overloaded
    top_overloaded = sorted(old_kp_counts.items(), key=lambda x: -x[1])[:5]
    print(f"Top overloaded: {[(k, v) for k, v in top_overloaded]}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"kp_remap_{args.strategy}_dry_run"
    report = {"strategy": args.strategy, "current_coverage": f"{old_cov}/{len(OUTLINE)}",
              "projected_coverage": f"{new_cov}/{len(OUTLINE)}",
              "current_uncovered": old_zero, "projected_uncovered": new_zero,
              "8.7_current": old_kp_counts.get("8.7", 0), "8.7_projected": new_kp_counts.get("8.7", 0),
              "5.1_current": old_kp_counts.get("5.1", 0), "5.1_projected": new_kp_counts.get("5.1", 0),
              "2.3_current": old_kp_counts.get("2.3", 0), "2.3_projected": new_kp_counts.get("2.3", 0),
              "suggestions": remap, "old_counts": dict(old_kp_counts), "new_counts": dict(new_kp_counts),
              "details": [{"id": s["id"], "stem": s["stem"], "old_kp": s["old_kp"],
                           "new_kp": s["new_kp"], "confidence": s["confidence"]} for s in suggestions[:300]]}
    (REPORT_DIR / f"{prefix}_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # KP range info
    kp_ranges = defaultdict(list)
    for s in suggestions:
        kp_ranges[s["new_kp"]].append(s.get("raw_index", 0))
    range_info = {k: {"min": min(v), "max": max(v), "count": len(v)} for k, v in kp_ranges.items()}
    report["kp_ranges"] = range_info

    md = [f"# KP重映射 {args.strategy} dry-run\n",
          f"## 覆盖率", f"- 当前: {old_cov}/{len(OUTLINE)} ({round(old_cov/len(OUTLINE)*100,1)}%) 无题: {old_zero}",
          f"- 预计: {new_cov}/{len(OUTLINE)} ({round(new_cov/len(OUTLINE)*100,1)}%) 无题: {new_zero}",
          f"- 8.7: {old_kp_counts.get('8.7',0)} -> {new_kp_counts.get('8.7',0)}",
          f"- 5.1 树: {old_kp_counts.get('5.1',0)} -> {new_kp_counts.get('5.1',0)}",
          f"- 2.3 链表: {old_kp_counts.get('2.3',0)} -> {new_kp_counts.get('2.3',0)}",
          f"", f"## 重映射", f"- high: {remap['high']} medium: {remap['medium']} low: {remap['low']} skipped: {remap['skipped']}"]
    (REPORT_DIR / f"{prefix}_report.md").write_text("\n".join(md), encoding="utf-8")
    # Per-KP counts table
    kp_table = "| KP | 当前 | 预计 |\n|---|---|---|\n"
    for k in OUTLINE_ORDER[:12]:
        kp_table += f"| {k} | {old_kp_counts.get(k,0)} | {new_kp_counts.get(k,0)} |\n"
    (REPORT_DIR / f"{prefix}_counts.md").write_text(f"# 题量对比\n\n{kp_table}", encoding="utf-8")
    # Reversal check
    reversals = [s for s in suggestions if s.get("raw_index", 0) > 0 and s["new_kp"] in OUTLINE_ORDER and s["old_kp"] in OUTLINE_ORDER and OUTLINE_ORDER.index(s["new_kp"]) < OUTLINE_ORDER.index(s["old_kp"]) - 5]
    print(f"Reversals (skip back >5): {len(reversals)}")
    print(f"\nReports saved to {REPORT_DIR}")

    if not args.dry_run and (args.apply_high or args.apply_medium):
        applied = 0
        for s in suggestions:
            if s["confidence"] == "high" or (s["confidence"] == "medium" and args.apply_medium):
                item = db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.id == s["id"]).first()
                if item:
                    item.knowledge_point_id = s["new_kp"]
                    item.knowledge_point_name = OUTLINE.get(s["new_kp"], "")
                    item.knowledge_point_path = OUTLINE.get(s["new_kp"], "")
                    item.updated_at = models.utc_now()
                    applied += 1
        db.commit()
        print(f"Applied {applied} remaps")
    db.close()

if __name__ == "__main__":
    main()
