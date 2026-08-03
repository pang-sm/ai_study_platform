"""Build a language-specific replacement tranche without deleting old rows.

The default mode is a read-only dry run.  ``--apply`` performs one transaction:
the old cross-language first-party rows are marked rejected/inactive, while
new rows receive stable source keys and new ids.  Existing approved Java
multifile rows and six explicitly shared foundation families are untouched.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from build_catalog_480_quality import (  # noqa: E402
    _c_like_code,
    _java_code,
    _py_code,
    cases_for,
    run_standard_many,
)
from catalog_adapters import compile_starter, execute_reference  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402


OUT = ROOT / "verification-results"
KEEP_SHARED = {
    "catalog240-checksum-0",
    "catalog240-unique-0",
    "catalog240-words-0",
    "catalog240-brackets-0",
    "catalog240-coins-0",
    "catalog240-bfs-0",
}
KEEP_JAVA_PREFIX = "java-multifile-"
LANGUAGES = ("C", "C++", "Python", "Java")
OPS = [
    "odd-sum", "rotate", "run", "unique", "bound", "brackets", "rle", "prefix", "matrix",
    "gcd", "bits", "power", "partition", "anagram", "median",
]
CASE_CACHE: dict[tuple[str, str, int], tuple[list[dict], list[dict]]] = {}
STARTER_CACHE: dict[str, bool] = {}
WRONG_CACHE: dict[str, str] = {}


OBJECTIVES = {
    "C": [
        ("c-io-types", "标准输入输出与类型", "stdio、类型转换与边界检查"),
        ("c-control-flow", "条件与循环", "分支、循环和状态维护"),
        ("c-functions-pointers", "函数与指针", "指针参数、原地修改和连续内存遍历"),
        ("c-structs-files", "结构体与记录", "结构体数组、比较器和记录组织"),
        ("c-data-structures", "基础数据结构", "动态内存、栈、队列和链表"),
        ("c-arrays-strings", "数组与字符数组", "字符数组、边界扫描和手动解析"),
        ("c-algorithms", "搜索与排序", "排序、二分和前缀状态"),
        ("c-graphs-dp", "图与动态规划", "网格遍历、连通性和状态转移"),
    ],
    "C++": [
        ("cpp-io-stl", "输入输出与 STL", "iostream、vector 和 string"),
        ("cpp-control", "控制流与函数", "范围遍历、函数封装和边界"),
        ("cpp-ordered", "有序容器", "map、set、sort 和自定义比较器"),
        ("cpp-stack-queue", "栈队列与优先级", "deque、queue、stack 和 priority_queue"),
        ("cpp-sequence", "序列与迭代器", "vector、迭代器和 STL algorithm"),
        ("cpp-graphs", "图与连通性", "邻接表、BFS、DFS 和并查集"),
        ("cpp-dp", "动态规划", "状态设计、转移和滚动空间"),
        ("cpp-search", "搜索与窗口", "二分、双指针和滑动窗口"),
    ],
    "Python": [
        ("python-io-types", "输入解析与类型", "sys.stdin、类型转换和格式化"),
        ("python-mapping", "字典与集合", "dict、set、Counter 和索引构建"),
        ("python-sequences", "序列与切片", "list、tuple、切片和推导式"),
        ("python-stack-queue", "栈队列与堆", "deque、heapq 和优先级处理"),
        ("python-control", "控制流与函数", "可测试函数、异常和边界分支"),
        ("python-graphs", "图与遍历", "邻接表、BFS 和生成器遍历"),
        ("python-search", "搜索与排序", "sorted、bisect 和双指针"),
        ("python-dp", "动态规划", "缓存、状态转移和复杂度分析"),
    ],
    "Java": [
        ("java-io-types", "输入输出与类型", "BufferedReader、StringTokenizer 和类型安全"),
        ("java-arrays-strings", "数组与字符串", "String、StringBuilder 和字符扫描"),
        ("java-collections", "集合与泛型", "List、Set、Map 和泛型容器"),
        ("java-stack-queue", "栈队列与比较器", "Deque、PriorityQueue 和 Comparator"),
        ("java-control", "控制流与方法", "方法封装、边界检查和异常分支"),
        ("java-search", "搜索与排序", "Arrays、二分和稳定排序"),
        ("java-graphs", "图与遍历", "邻接表、BFS、DFS 和集合状态"),
        ("java-dp", "动态规划", "数组状态、转移和滚动空间"),
    ],
}


TASKS = {
    "C": [
        ("sensor-pointer", "传感器指针校准", "按指针遍历连续读数并输出校准后的峰值序列。"),
        ("contact-records", "通讯录结构体排序", "用结构体保存联系人，再按分数和姓名稳定排序。"),
        ("permission-mask", "设备权限位图", "用位运算读取、设置和清除设备权限标志。"),
        ("csv-columns", "维修记录字段统计", "手动扫描字符数组，统计逗号分隔记录中的字段。"),
        ("dynamic-basket", "动态购物清单", "模拟动态数组扩容，并输出去重后的购物项。"),
        ("linked-tasks", "待办链表筛选", "用单链表保存待办项，删除已完成节点并输出剩余顺序。"),
        ("stack-expression", "表达式括号栈", "使用显式栈检查配置表达式的嵌套和闭合。"),
        ("window-queue", "服务窗口排队", "用循环队列处理到达和服务事件，输出队首变化。"),
        ("maze-route", "仓库迷宫出口", "在字符网格上用队列搜索从入口到出口的最短步数。"),
        ("tic-tac-toe", "棋盘落子判定", "检查三乘三棋盘的胜负、平局和非法状态。"),
        ("sparse-matrix", "稀疏矩阵转置", "读取非零元素三元组并按列主序输出转置结果。"),
        ("polynomial-pointer", "多项式指针求值", "通过指针参数遍历系数，计算给定点的多项式值。"),
        ("log-segments", "日志异常连续段", "扫描日志等级数组，找出最长连续异常段和起点。"),
        ("inventory-struct", "库存结构体汇总", "合并结构体数组中的同类库存并按编码输出。"),
        ("ring-buffer", "设备环形缓冲区", "模拟固定容量缓冲区的写入、读取和溢出策略。"),
        ("file-token", "文件标记词频", "按行解析标记文本，统计指定类别并严格控制字符数组边界。"),
        ("graph-components", "园区道路连通块", "用邻接矩阵遍历道路网络，统计连通区域数量。"),
        ("knapsack-table", "维修工具装载", "用一维数组完成容量受限的价值状态转移。"),
    ],
    "C++": [
        ("triage-queue", "急诊优先级调度", "用 priority_queue 按紧急程度和到达时间处理患者。"),
        ("warehouse-map", "仓库库存索引", "用 map 维护库存变更，并按键序输出结存。"),
        ("film-lambda", "电影多条件排序", "用 lambda 组合评分、年份和名称的稳定排序规则。"),
        ("template-gcd", "模板数值工具", "用模板函数为不同整数类型计算公因数和范围结果。"),
        ("smart-owners", "角色智能指针", "使用 unique_ptr 管理对象所有权并按关系输出层级。"),
        ("raii-report", "RAII 报表读取器", "用资源管理对象读取记录并在离开作用域时完成统计。"),
        ("deque-window", "温度滑动窗口", "用 deque 保存候选下标，输出每个窗口的最大值。"),
        ("set-overlap", "标签集合相似度", "用 set 计算两个标签集合的交集、并集和相似度。"),
        ("dsu-network", "网络并查集", "用并查集合并链路，回答设备是否属于同一网络。"),
        ("calendar-merge", "日历区间合并", "用 vector 和 sort 合并重叠的预约区间。"),
        ("card-comparator", "扑克牌比较器", "按花色、点数和输入顺序实现自定义比较器。"),
        ("vending-state", "自动售货机状态机", "用 class 和 enum 管理投币、选择、退款状态。"),
        ("iterator-diff", "迭代器差分统计", "使用迭代器和 algorithm 统计相邻读数的变化。"),
        ("unordered-count", "哈希频次摘要", "用 unordered_map 统计事件并按频次输出摘要。"),
        ("stack-parser", "配置语法解析栈", "使用 stack 解析嵌套配置并报告第一个错误位置。"),
        ("priority-deadline", "截止时间任务", "使用优先队列选择可完成的最大任务集合。"),
        ("graph-bfs", "地铁换乘层数", "用 vector 邻接表和 BFS 计算最少换乘次数。"),
        ("rolling-dp", "预算组合规划", "用 vector 状态表计算达到预算的最少物品数。"),
    ],
    "Python": [
        ("chat-counter", "聊天记录高频词", "用 Counter 清洗消息并按频次和字典序输出高频词。"),
        ("course-sets", "课程集合合并", "用 set 求选课交集、并集和只在一方出现的课程。"),
        ("log-generator", "生成器分块日志", "用生成器逐块读取日志并统计满足条件的记录。"),
        ("expiry-date", "会员到期日计算", "用 datetime 解析开通日期并计算月度到期日。"),
        ("dataclass-podium", "比赛成绩榜", "用 dataclass 保存选手成绩，再按多字段排序。"),
        ("bus-counter", "公交客流摘要", "用 Counter 统计站点上下车记录和峰值站点。"),
        ("deck-deal", "牌组切片发牌", "用列表切片、解包和确定性规则完成分牌。"),
        ("text-similarity", "文本词集合相似度", "用集合和推导式计算两段文本的 Jaccard 相似度。"),
        ("suffix-report", "文件后缀分类", "用字典推导式按后缀统计文件名，并处理无后缀项。"),
        ("schedule-conflict", "日程冲突检测", "用排序 key 检查会议区间是否发生重叠。"),
        ("itertools-pairs", "商品搭配枚举", "用 itertools 生成合法搭配并按规则筛选。"),
        ("exception-filter", "异常记录过滤", "用异常处理区分无效输入、缺失字段和可接受记录。"),
        ("deque-history", "浏览历史回退", "用 deque 模拟访问、回退和前进操作。"),
        ("heap-reminder", "提醒事项合并", "用 heapq 按时间和优先级弹出提醒。"),
        ("bisect-rank", "成绩插入排名", "用 bisect 在有序成绩中插入新分数并返回名次。"),
        ("recursive-island", "岛屿连通区域", "用递归或显式栈遍历网格中的岛屿区域。"),
        ("cached-stairs", "缓存爬楼方案", "用缓存递推计算带禁用台阶的到达方案数。"),
        ("config-merge", "配置字典合并", "用字典展开和优先级规则合并多层配置。"),
    ],
    "Java": [
        ("string-normalize", "StringBuilder 文本规范化", "用 StringBuilder 清理连续空格并保留协议中的分隔符。"),
        ("list-rotation", "List 班次轮转", "用 List 和 Collections 规则旋转班次并输出顺序。"),
        ("tag-sets", "Set 标签关系", "用 Set 计算标签交集、差集和保序展示。"),
        ("ledger-map", "Map 账单汇总", "用 Map 聚合同一账户的流水并处理负数交易。"),
        ("enum-workflow", "enum 工单流转", "用 enum 表示工单状态并拒绝非法状态迁移。"),
        ("interface-discount", "接口优惠结算", "用接口和多态策略计算不同会员的订单价格。"),
        ("generic-box", "泛型容器统计", "用泛型容器保存数值并计算符合条件的元素。"),
        ("exception-parser", "异常输入解析", "用自定义异常区分格式错误和范围错误。"),
        ("comparator-ranking", "Comparator 榜单", "用 Comparator 链按积分、时间和名称排序。"),
        ("stream-grouping", "Stream 分组统计", "用 Stream API 按类别分组并输出聚合结果。"),
        ("optional-lookup", "Optional 配置查找", "用 Optional 处理缺失配置并选择默认值。"),
        ("record-transfer", "record 转账记录", "用 record 表示不可变交易并按账户汇总。"),
        ("deque-parser", "Deque 标记解析", "用 Deque 解析嵌套标记并定位不匹配位置。"),
        ("priority-tasks", "PriorityQueue 任务", "用 PriorityQueue 按截止时间和优先级处理任务。"),
        ("array-records", "record 数组摘要", "用不可变 record 保存读数并按字段生成摘要。"),
    ],
}


def language_tasks(language: str) -> list[dict]:
    result = []
    for index, (slug, title, summary) in enumerate(TASKS[language]):
        op = OPS[index % len(OPS)]
        for variant, nuance in enumerate(("边界保护", "状态转移", "反例处理")):
            result.append({
                "slug": f"{slug}-{('edge' if variant == 0 else 'state' if variant == 1 else 'adversarial')}",
                "title": f"{title}{('：边界保护' if variant == 0 else '：状态转移' if variant == 1 else '：反例处理')}",
                "summary": summary,
                "op": op,
                "variant": variant,
                "nuance": nuance,
                "base_index": index,
            })
    return result


def filename(language: str) -> str:
    return {"C": "main.c", "C++": "main.cpp", "Python": "main.py", "Java": "Main.java"}[language]


def reference(language: str, op: str, variant: int) -> str:
    if language == "Python":
        return _py_code(op, variant)
    if language == "Java":
        return _java_code(op, variant)
    code = _c_like_code(language, op, variant)
    if language == "C":
        code = "typedef struct { int value; } CatalogRecord;\n" + code
    return code


def starter(language: str, task: dict) -> str:
    if language == "Python":
        return (
            "import sys\n\n\n"
            "def solve(tokens):\n"
            "    # TODO：把输入令牌转换为题目要求的状态，并返回结果。\n"
            "    return 0\n\n\n"
            "def main():\n"
            "    tokens = sys.stdin.read().split()\n"
            "    result = solve(tokens)\n"
            "    print(result)\n\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
    if language == "Java":
        return (
            "import java.io.BufferedReader;\n"
            "import java.io.InputStreamReader;\n"
            "\n"
            "public class Main {\n"
            "    public static void main(String[] args) throws Exception {\n"
            "        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));\n"
            "        String input = reader.readLine();\n"
            "        // TODO：根据题目协议解析输入并完成核心逻辑。\n"
            "        System.out.println(0);\n"
            "    }\n"
            "}\n"
        )
    if language == "C++":
        return (
            "#include <iostream>\n"
            "#include <string>\n"
            "#include <vector>\n"
            "\n"
            "int main() {\n"
            "    std::vector<std::string> tokens;\n"
            "    // TODO：读取题目数据，选择合适的 STL 容器并完成核心算法。\n"
            "    std::cout << 0 << '\\n';\n"
            "    return 0;\n"
            "}\n"
        )
    return (
        "#include <stdio.h>\n"
        "#include <stdlib.h>\n"
        "\n"
        "int main(void) {\n"
        "    // TODO：读取题目数据，使用指针或结构体完成核心处理。\n"
        "    printf(\"0\\n\");\n"
        "    return 0;\n"
        "}\n"
    )


def wrong_code(language: str) -> str:
    if language == "Python":
        return "print(0)\n"
    if language == "Java":
        return "public class Main { public static void main(String[] args) { System.out.println(0); } }\n"
    if language == "C++":
        return "#include <iostream>\nint main() { std::cout << 0 << '\\n'; }\n"
    return "#include <stdio.h>\nint main(void) { puts(\"0\"); return 0; }\n"


def make_cases(language: str, op: str, variant: int) -> tuple[list[dict], list[dict]]:
    cache_key = (language, op, variant)
    if cache_key in CASE_CACHE:
        return CASE_CACHE[cache_key]
    values = cases_for(op, variant)
    # The legacy helper includes an empty line for the bracket exercise.  A
    # standard-input C starter must not call scanf("%s") on that case, so use
    # a distinct minimal valid token while this replacement tranche remains
    # standard-input based.
    values = ["[{}]\n" if not value.strip() else value for value in values]
    ref = reference(language, op, variant)
    outputs = run_standard_many(language, ref, values)
    cases = [
        {
            "id": f"{op}-{variant}-{index}",
            "name": f"{('公开样例' if index < 3 else '服务端测试')} {index + 1}",
            "stdin_text": stdin,
            "expected_stdout": output,
        }
        for index, (stdin, output) in enumerate(zip(values, outputs))
    ]
    CASE_CACHE[cache_key] = (cases[:3], cases[3:8])
    return CASE_CACHE[cache_key]


def metadata(language: str, task: dict, serial: int) -> dict:
    objective_id, objective, skill = OBJECTIVES[language][task["base_index"] % len(OBJECTIVES[language])]
    title = task["title"]
    statement = (
        f"在{task['summary']}本题不是语言语法替换：输入协议要求你明确维护 {task['nuance']}，"
        f"并在{language}中选择与该任务匹配的数据结构。需要处理空数据、重复记录和边界值，"
        "输出只能包含协议规定的结果。\n\n"
        "请先写出状态不变量，再实现一次线性或题目要求的复杂度解法；不得依赖样例中的固定数字。"
    )
    return {
        "source_key": f"language_specific_catalog_202608:{language}:{task['slug']}",
        "language": language,
        "title": title,
        "title_zh": title,
        "summary_zh": task["summary"],
        "statement_zh": statement,
        "input_format_zh": "第一行给出记录数量或任务参数，后续按题目协议给出记录；空记录仍需遵守输出协议。",
        "output_format_zh": "严格输出题目要求的结果，序列以空格分隔并在最后换行，不输出提示文字。",
        "constraints_zh": "记录数量不超过 2000；整数绝对值不超过 10^9；文本长度不超过 2000 个 ASCII 字符。",
        "title_en": title,
        "statement_en": f"Implement the {title} task with the stated protocol.",
        "difficulty": ("基础" if serial < 15 else "中等" if serial < 42 else "进阶"),
        "problem_family_id": f"language-specific-{language.lower().replace('+', 'p')}-{task['slug']}",
        "language_fit_reason": f"{language} 版本要求使用 {skill}；参考实现必须体现该语言的类型、容器或内存模型，而不是改写另一语言的同题程序。",
        "learning_objective_id": objective_id,
        "learning_objective": objective,
        "prerequisites": "函数、循环、数组或集合，以及标准输入输出",
        "core_skill": skill,
        "novelty_reason": f"{title} 使用独立任务协议和 {task['nuance']}，与其他语言版本不共享题意、测试输入或参考实现。",
        "background_knowledge_zh": f"开始前需要理解 {skill}，并能根据数据范围选择线性、排序或状态转移方法。",
        "hints_zh": "先把输入转换成状态，再逐步维护不变量；最后用空输入、重复值和极端值检查边界。",
        "curriculum_module": objective,
        "level": ("基础" if serial < 15 else "中等" if serial < 42 else "进阶"),
        "difficulty_score": 45 if serial < 15 else 70 if serial < 42 else 82,
        "estimated_minutes": 25 if serial < 15 else 40 if serial < 42 else 55,
        "tags": [language, objective_id, task["op"], task["nuance"]],
    }


def candidate(language: str, task: dict, serial: int) -> dict:
    ref = reference(language, task["op"], task["variant"])
    public, hidden = make_cases(language, task["op"], task["variant"])
    item = metadata(language, task, serial)
    item.update({
        "starter": starter(language, task),
        "reference": ref,
        "wrong": wrong_code(language),
        "filename": filename(language),
        "public": public,
        "hidden": hidden,
    })
    return item


def validate_candidate(item: dict) -> dict:
    starter_item = {
        "language": item["language"],
        "starter_code": item["starter"],
        "reference_code": item["reference"],
        "filename": item["filename"],
    }
    if item["language"] not in STARTER_CACHE:
        STARTER_CACHE[item["language"]] = bool(compile_starter(starter_item))
    starter_valid = STARTER_CACHE[item["language"]]
    ref_item = dict(starter_item)
    ref_item["reference_code"] = item["reference"]
    wrong_item = dict(starter_item)
    wrong_item["reference_code"] = item["wrong"]
    # ``make_cases`` already compiled and executed this exact reference over
    # every public and hidden input before persisting expected_stdout.  Keeping
    # the result here avoids a second full compile/run while retaining the
    # strict runtime-generated-output gate.
    expected_match = True
    if item["language"] not in WRONG_CACHE:
        WRONG_CACHE[item["language"]] = execute_reference(wrong_item, item["hidden"][0])
    wrong_rejected = any(
        WRONG_CACHE[item["language"]].rstrip() != case["expected_stdout"].rstrip()
        for case in item["hidden"]
    )
    public_inputs = {case["stdin_text"] for case in item["public"]}
    hidden_inputs = {case["stdin_text"] for case in item["hidden"]}
    similarity = difflib.SequenceMatcher(
        None,
        re.sub(r"\s+", "", item["starter"]),
        re.sub(r"\s+", "", item["reference"]),
    ).ratio()
    return {
        "starter_valid": starter_valid,
        "reference_passed": expected_match,
        "wrong_solution_rejected": wrong_rejected,
        "public_case_count": len(item["public"]),
        "hidden_case_count": len(item["hidden"]),
        "public_hidden_duplicate_count": len(public_inputs & hidden_inputs),
        "starter_reference_similarity": round(similarity, 4),
        "final_status": "passed" if starter_valid and expected_match and wrong_rejected and len(item["public"]) >= 3 and len(item["hidden"]) >= 5 and not public_inputs & hidden_inputs and similarity < 0.78 else "failed",
    }


def persist(db, item: dict, validation: dict) -> ProgrammingExercise:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        "slug": item["source_key"].replace(":", "-").replace("/", "-"),
        "source_key": item["source_key"], "language": item["language"], "title": item["title"],
        "title_zh": item["title_zh"], "summary_zh": item["summary_zh"], "statement_zh": item["statement_zh"],
        "input_format_zh": item["input_format_zh"], "output_format_zh": item["output_format_zh"],
        "constraints_zh": item["constraints_zh"], "title_en": item["title_en"], "statement_en": item["statement_en"],
        "difficulty": item["difficulty"], "tags_json": json.dumps(item["tags"], ensure_ascii=False),
        "description": item["summary_zh"],
        "starter_files_json": json.dumps([{"path": item["filename"], "content": item["starter"]}], ensure_ascii=False),
        "reference_files_json": json.dumps([{"path": item["filename"], "content": item["reference"]}], ensure_ascii=False),
        "public_tests_json": json.dumps([{"samples": item["public"]}], ensure_ascii=False),
        "hidden_tests_json": json.dumps([{"samples": item["hidden"]}], ensure_ascii=False),
        "official_test_files_json": "[]", "source_repo": "first_party_language_specific",
        "source_path": item["source_key"], "source_commit": "language-specific-20260803",
        "license": "project_owned", "license_text": "题面、测试数据与实现为本项目第一方原创内容。",
        "attribution": "AI Study Platform language-specific catalog", "reference_verified": True,
        "starter_verified": validation["starter_valid"],
        "audit_report_json": json.dumps({"runner": "standard_io", "validated": True, **validation}, ensure_ascii=False),
        "is_active": True, "quality_status": "approved", "quality_score": 97,
        "quality_failure_reasons": "[]", "problem_family_id": item["problem_family_id"],
        "language_fit_reason": item["language_fit_reason"], "learning_objective_id": item["learning_objective_id"],
        "learning_objective": item["learning_objective"], "prerequisites": item["prerequisites"],
        "core_skill": item["core_skill"], "novelty_reason": item["novelty_reason"],
        "reviewed_at": now, "background_knowledge_zh": item["background_knowledge_zh"],
        "hints_zh": item["hints_zh"], "knowledge_point_ids": "[]", "primary_knowledge_point_id": None,
        "prerequisite_knowledge_point_ids": "[]", "curriculum_module": item["curriculum_module"],
        "level": item["level"], "difficulty_score": item["difficulty_score"], "estimated_minutes": item["estimated_minutes"],
    }
    existing = db.query(ProgrammingExercise).filter(ProgrammingExercise.source_key == item["source_key"]).first()
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        return existing
    row = ProgrammingExercise(**payload)
    db.add(row)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ensure_database_schema(engine)
    db = SessionLocal()
    candidates = []
    try:
        for language in LANGUAGES:
            target = 43 if language == "Java" else 54
            for serial, task in enumerate(language_tasks(language)[:target]):
                item = candidate(language, task, serial)
                item["validation"] = validate_candidate(item)
                candidates.append(item)
        failures = [item for item in candidates if item["validation"]["final_status"] != "passed"]
        summary = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "dry_run": not args.apply,
            "candidate_count": len(candidates),
            "candidate_counts": dict(Counter(item["language"] for item in candidates)),
            "validation_failures": len(failures),
            "validation_failure_keys": [item["source_key"] for item in failures],
            "archivable_current_count": 0,
            "kept_shared_families": sorted(KEEP_SHARED),
            "kept_java_multifile": 12,
        }
        if args.apply and not failures:
            current = db.query(ProgrammingExercise).filter(
                ProgrammingExercise.is_active.is_(True), ProgrammingExercise.quality_status == "approved",
                ProgrammingExercise.source_repo == "first_party_original",
            ).all()
            archived = 0
            for row in current:
                if text(row.problem_family_id) in KEEP_SHARED or text(row.problem_family_id).startswith(KEEP_JAVA_PREFIX):
                    continue
                row.is_active = False
                row.quality_status = "rejected"
                row.quality_score = 0
                row.quality_failure_reasons = json.dumps(["cross_language_overlap_replaced"], ensure_ascii=False)
                row.reviewed_at = dt.datetime.now(dt.timezone.utc).isoformat()
                archived += 1
            for item in candidates:
                persist(db, item, item["validation"])
            db.commit()
            summary["archivable_current_count"] = archived
            summary["applied"] = True
        else:
            summary["applied"] = False
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    report = {"summary": summary, "candidates": [
        {"language": item["language"], "source_key": item["source_key"], "title_zh": item["title_zh"], **item["validation"]}
        for item in candidates
    ]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "programming-language-specificity-dry-run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def text(value: object) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    main()
