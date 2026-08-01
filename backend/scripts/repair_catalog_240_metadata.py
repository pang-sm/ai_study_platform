"""Align the new 240 rows with the repository's 32-objective curriculum.

Only rows created by build_catalog_240_quality.py are touched.  Rejected rows,
submissions, progress and all other user data remain unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import KnowledgePoint, ProgrammingExercise  # noqa: E402

BLUEPRINT = ROOT / "backend/data/programming_catalog/curriculum_blueprint.json"
LANGUAGES = ("C", "C++", "Python", "Java")
VARIANT_STATEMENTS = (
    "运营人员要把{title}接入批处理程序。请逐项读取输入记录，按照业务规则计算最终结果；不能丢弃零值，也不能改变记录的原始顺序。{clue}",
    "请为{title}编写一个可重复运行的校验器。输入可能包含最小规模、相等边界和负数记录，程序应先建立必要的数据结构，再完成一次完整处理并输出唯一结果。{clue}",
    "维护{title}时，人工汇总容易在边界处出错。本题要求你直接从标准输入重建汇总过程：每条记录都要参与规则计算，最后只打印题目规定的结果，不输出解释文字。{clue}",
)
TASK_CLUES = {
    "recipe": "计算时每条配方记录都是一项乘积，最后把所有乘积累加，而不是只统计记录数量。",
    "transfer": "首段时长完整计入，后续相邻工序各扣除一次固定衔接时间，并将负结果截为零。",
    "month": "二月要按公历闰年规则判断，整百年份只有能被四百整除时才算闰年。",
    "checksum": "编号下标从零开始，偶数位置加上数字、奇数位置减去数字，结果可以为负。",
    "scoreboard": "积分先比较胜场三分与平局一分的总和，积分相同再比较名称的字典序。",
    "times": "时间采用固定宽度的二十四小时格式，因此按字符串升序即可得到时刻顺序。",
    "intervals": "排序后只要新区间起点不超过当前右端点就合并，并保留覆盖范围更大的右端点。",
    "inventory": "同名物品必须在映射中合并，净值为零的条目不应出现在最终清单。",
    "unique": "字符的出现次数要基于完整字符串统计，答案取满足次数为一的最左字符。",
    "words": "词频并列时不能依赖输入顺序，而要选择字典序更小的单词。",
    "brackets": "遇到闭括号必须匹配最近的同类开括号，扫描结束时栈也必须为空。",
    "caesar": "只移动英文字母并循环回到字母表开头，数字、空格和标点保持原样。",
    "prefix": "前缀匹配必须从字符串第一个字符开始，不能把中间出现的相同片段算进去。",
    "rotate": "右移量先对序列长度取模，再通过首尾两段拼接得到环形顺序。",
    "dedup": "第一次见到的元素立即保留，后续重复元素跳过，不能对结果再次排序。",
    "ranges": "先建立包含零号前缀的累计和数组，每个闭区间用两个前缀值相减得到。",
    "maxsub": "子数组必须非空；遇到新的起点更优时重置当前和，同时维护历史最大值。",
    "overlap": "同一时刻若有区间结束和开始，先处理结束事件，因此相接区间不算重叠。",
    "coins": "每种硬币可以重复使用，动态规划状态表示凑出每个金额所需的最少数量。",
    "bfs": "从 S 开始按层扩展可达格子，第一次到达 E 的层数就是最短步数。",
}


def main() -> None:
    ensure_database_schema(engine)
    blueprint = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    db = SessionLocal()
    changed = 0
    try:
        for language in LANGUAGES:
            course_id = f"programming_{language.lower().replace('+', 'p')}"
            objectives = blueprint["languages"][language]
            points = {
                point.title: point
                for point in db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
            }
            rows = db.query(ProgrammingExercise).filter(
                ProgrammingExercise.language == language,
                ProgrammingExercise.source_key.like(f"first_party_original_v2|{language}|%"),
            ).all()
            for row in rows:
                slug = str(row.source_key).rsplit("|", 1)[-1]
                kind, raw_variant = slug.rsplit("-", 1)
                family = {item["objective_id"]: item for item in objectives}
                # The builder assigns task families cyclically across the eight
                # real objectives. Recover that stable assignment from row id
                # order within this language rather than from prose.
                ordinal = sorted(rows, key=lambda item: item.id).index(row)
                meta = objectives[(ordinal // 3) % len(objectives)]
                point = points.get(meta["objective"])
                row.learning_objective_id = meta["objective_id"]
                row.learning_objective = meta["objective"]
                row.prerequisites = meta["prerequisites"]
                row.core_skill = meta["core_skill"]
                row.knowledge_point_ids = json.dumps([meta["objective_id"]], ensure_ascii=False)
                row.primary_knowledge_point_id = point.id if point else None
                row.prerequisite_knowledge_point_ids = "[]"
                row.curriculum_module = f"{language} · {meta['objective']}"
                variant = int(raw_variant) % 3 if raw_variant.isdigit() else 0
                row.statement_zh = VARIANT_STATEMENTS[variant].format(title=row.title_zh, clue=TASK_CLUES.get(kind, "请严格遵守题目给出的数据协议。"))
                changed += 1
        db.commit()
    finally:
        db.close()
    print(json.dumps({"updated": changed, "curriculum_objectives": 32}, ensure_ascii=False))


if __name__ == "__main__":
    main()
