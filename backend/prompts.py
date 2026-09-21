import re

from subjects import normalize_subject as canonical_normalize_subject


QUESTION_TYPE_LABELS = {
    "concept_explanation": "概念解释",
    "code_debug": "代码报错分析",
    "exercise_solution": "题目讲解",
    "study_plan": "学习规划",
    "project_help": "项目开发帮助",
    "general": "普通问答",
}


QUESTION_TYPE_INSTRUCTIONS = {
    "concept_explanation": """请优先按这个结构回答：
一、一句话理解
二、核心概念
三、关键点
四、示例
五、常见误区
六、你接下来可以这样学""",
    "code_debug": """请优先按这个结构回答：
一、问题定位
二、原因分析
三、修改建议
四、示例代码
五、验证方式""",
    "exercise_solution": """请优先按这个结构回答：
一、题目考点
二、解题思路
三、逐步推导
四、最终答案
五、易错点
六、同类题方法总结""",
    "study_plan": """请优先按这个结构回答：
一、当前目标判断
二、推荐学习顺序
三、每阶段重点
四、练习建议
五、常见坑
六、下一步行动""",
    "project_help": """请优先按这个结构回答：
一、当前结论
二、你应该修改的文件
三、具体实现思路
四、关键代码或命令
五、验证方式
六、提交与部署建议""",
    "general": """请优先按这个结构回答：
一、核心回答
二、原因说明
三、建议操作""",
}


SUBJECT_GUIDANCE = {
    "计算系统基础": "当前课程偏向计算系统基础，请关注计算机系统整体结构、程序执行、二进制、存储、指令与软硬件协同。",
    "C语言": "当前课程偏向 C语言，请关注语法基础、指针、数组、结构体、内存、编译运行。",
    "C++": "当前课程偏向 C++，请关注面向对象、STL、模板、引用、内存管理、编译错误。",
    "Python": "当前课程偏向 Python，请关注语法、数据结构、函数、文件、库使用、脚本实践。",
    "Java": "当前课程偏向 Java，请关注面向对象、集合、异常、JVM、线程、项目开发。",
    "离散数学": "当前课程偏向离散数学，请关注集合、关系、函数、图论、逻辑、证明方法。",
    "数据结构与算法": "当前课程偏向数据结构与算法，请关注线性表、树、图、排序、查找、复杂度、算法思想。",
    "计算机组成结构": "当前课程偏向计算机组成结构，请关注数据表示、指令系统、CPU、存储系统、总线、流水线。",
    "互联网计算": "当前课程偏向互联网计算，请关注计算机网络、HTTP、TCP/IP、DNS、Web、分布式基础。",
    "计算机操作系统": "当前课程偏向计算机操作系统，请关注进程、线程、调度、内存管理、文件系统、死锁、同步互斥。",
    "编译原理": "当前课程偏向编译原理，请关注词法分析、语法分析、语义分析、中间代码、优化、目标代码。",
    "数据管理": "当前课程偏向数据管理，请关注数据库、SQL、关系模型、索引、事务、范式、查询优化。",
    "人机交互": "当前课程偏向人机交互，请关注交互设计、用户体验、可用性、界面设计、用户研究。",
}


CODE_DEBUG_KEYWORDS = (
    "报错",
    "错误",
    "异常",
    "bug",
    "debug",
    "traceback",
    "exception",
    "error",
    "failed",
    "失败",
    "运行不了",
    "运行失败",
    "编译失败",
    "崩溃",
    "syntaxerror",
    "nullpointer",
    "stack trace",
)

CONCEPT_KEYWORDS = (
    "是什么",
    "为什么",
    "解释",
    "概念",
    "原理",
    "区别",
    "作用",
    "含义",
    "什么意思",
)

EXERCISE_KEYWORDS = (
    "题目",
    "作业",
    "算法题",
    "选择题",
    "填空题",
    "证明",
    "求解",
    "计算",
    "写出",
    "解答",
)

STUDY_PLAN_KEYWORDS = (
    "怎么学",
    "如何学",
    "学习路线",
    "学习规划",
    "先学什么",
    "复习",
    "备考",
    "计划",
    "路线",
)

PROJECT_HELP_STRONG_KEYWORDS = (
    "项目",
    "部署",
    "git",
    "github",
    "服务器",
    "fastapi",
    "react",
    "vite",
    "nginx",
)

PROJECT_HELP_STACK_KEYWORDS = (
    "前端",
    "后端",
    "数据库",
    "接口",
    "api",
)

PROJECT_HELP_ACTION_KEYWORDS = (
    "实现",
    "修改",
    "开发",
    "联调",
    "部署",
    "提交",
    "推送",
    "构建",
    "配置",
    "路由",
)


def _normalize_subject(subject: str | None) -> str:
    return canonical_normalize_subject(subject)


def _normalize_question(question: str | None) -> str:
    return (question or "").strip()


def _contains_code_like_text(question: str) -> bool:
    if "```" in question:
        return True

    code_markers = ("def ", "class ", "import ", "public static", "console.log", "SELECT ", "FROM ", "{", "}", ";")
    return any(marker.lower() in question.lower() for marker in code_markers)


def detect_question_type(question: str | None) -> str:
    text = _normalize_question(question)
    lowered = text.lower()

    if not text:
        return "general"

    if _contains_code_like_text(text) or any(keyword in lowered for keyword in CODE_DEBUG_KEYWORDS):
        return "code_debug"

    if any(keyword in text for keyword in STUDY_PLAN_KEYWORDS):
        return "study_plan"

    if any(keyword in text for keyword in EXERCISE_KEYWORDS) or re.search(r"第\s*\d+\s*题|做题|刷题", text):
        return "exercise_solution"

    if any(keyword in lowered for keyword in PROJECT_HELP_STRONG_KEYWORDS):
        return "project_help"

    stack_hits = sum(1 for keyword in PROJECT_HELP_STACK_KEYWORDS if keyword in text or keyword in lowered)
    action_hits = sum(1 for keyword in PROJECT_HELP_ACTION_KEYWORDS if keyword in text or keyword in lowered)
    if stack_hits >= 2 or (stack_hits >= 1 and action_hits >= 1):
        return "project_help"

    if any(keyword in text for keyword in CONCEPT_KEYWORDS):
        return "concept_explanation"

    return "general"


def _build_rag_instruction(rag_chunks: list[dict] | None, is_attachment: bool = False) -> str:
    if not rag_chunks:
        return (
            "当前没有命中用户资料库片段。请正常回答；如果这个问题明显依赖课程资料，"
            "可以简短提醒用户补充该学科资料，但不要影响主回答。"
        )

    blocks = []
    filenames = set()
    for index, item in enumerate(rag_chunks[:6], start=1):
        filename = item.get("source_filename") or item.get("filename") or "未命名资料"
        filenames.add(filename)
        subject = item.get("subject") or "未分类"
        file_type = item.get("file_type") or "未知类型"
        score = item.get("score")
        source_text = (item.get("chunk_summary") or item.get("chunk_text") or "").strip()
        snippet = re.sub(r"\s+", " ", source_text)[:220]
        score_text = f"{score:.3f}" if isinstance(score, (int, float)) else "未知"
        blocks.append(
            f"{index}. 文件名：{filename}｜学科：{subject}｜类型：{file_type}｜相关度：{score_text}\n"
            f"片段：{snippet or '无可用片段'}"
        )

    if is_attachment:
        file_list = "、".join(sorted(filenames))
        header = (
            f"本轮用户明确上传了以下文件作为讨论对象：{file_list}。\n"
            "用户的所有问题（包括“解读一下”“总结一下”“分析一下”“讲讲”“重点是什么”等短指令）"
            "都必须默认理解为针对这些文件的操作。\n"
            "绝对不要追问“没有具体对象”“请说明你想了解什么”等。\n"
            "请优先根据这些文件的内容回答，并在回答中自然提及文件名。\n"
            "如果文件内容不足以完整回答，先基于文件已有内容给出分析，再说明哪些信息文件中未覆盖。\n"
            "不要编造资料中不存在的内容，不要把资料全文原样复制出来。\n"
            "本次可参考的资料片段如下：\n"
        )
    else:
        header = (
            "本次回答可以参考用户个人资料库。请优先根据资料库片段回答，"
            "并在回答中自然说明“根据你资料库中的内容”。\n"
            "如果资料片段不足以完整回答，请明确说明“资料中没有完整覆盖，我补充解释如下”。\n"
            "不要编造资料中不存在的内容，不要把资料全文原样复制出来。\n"
            "本次可参考的资料片段如下：\n"
        )

    return header + "\n\n".join(blocks)


def build_system_prompt(
    subject: str | None,
    question: str | None,
    user_profile_data: dict | None = None,
    has_attachment: bool = False,
    rag_chunks: list[dict] | None = None,
    knowledge_context: str = "",
) -> str:
    normalized_subject = _normalize_subject(subject)
    normalized_question = _normalize_question(question)
    question_type = detect_question_type(normalized_question)
    profile = user_profile_data or {}
    grade = (profile.get("grade") or "").strip() or "未填写"
    major = (profile.get("major") or "").strip() or "未填写"
    subject_guidance = SUBJECT_GUIDANCE.get(normalized_subject)

    sections = [
        "你是一个面向高校学生的计算机学习导师，重点帮助学生真正理解知识，而不是只给最终答案。",
        "请始终使用中文回答，语气专业、清晰、适合课程学习场景。",
        f"当前学科：{normalized_subject}",
        f"用户年级：{grade}",
        f"用户专业：{major}",
        f"问题类型：{QUESTION_TYPE_LABELS[question_type]}",
        "回答总原则：\n"
        "- 回答要结构清晰，优先分步骤讲解。\n"
        "- 先给结论，再展开原因；简单问题不要过度展开。\n"
        "- 默认控制在中等长度；复杂问题可以分层讲，但避免堆成长篇大段。\n"
        "- 如果内容很多，最后提示用户可以继续问“展开某一部分”。\n"
        "- 不确定时要明确说明不确定，不要编造。\n"
        "- 如果用户信息不足，先基于已有信息给出可执行建议，再说明还需要什么信息。\n"
        "- 不要过度迎合用户的错误观点，发现问题要及时纠正。\n"
        "- 涉及代码时，要明确指出问题位置、修改原因和验证方式。\n"
        "- 涉及学习问题时，要给出学习路径、易错点和下一步建议。\n"
        "- 对明显作业、考试或算法题，以讲解思路和推导过程为主，同时可以给出最终答案，但重点是帮助理解，不要鼓励抄作业。\n"
        "## Markdown 格式规范（必须严格遵守）\n"
        "- 正文像教材讲解一样自然分段。\n"
        "- 重点概念和关键词用**加粗**（如**变量类型**、**控制流**、**时间复杂度**）。\n"
        "- 代码类术语（类名、方法名、关键字、API名、变量名、文件名）一律使用行内代码 `反引号`，例如 `String`、`Stream`、`map`、`filter`、`for`、`int`、`main.py`。\n"
        "- 核心禁令：不要把单个词、单个 API、单个变量名放进独立的围栏代码块。不要把普通中文解释放进代码块。不要连续输出多个只有一行单词的代码块。\n"
        "- 如果只是单个术语、变量名、API 名、关键字或短语，请使用行内代码或加粗，不要使用围栏代码块。围栏代码块只用于多行代码、完整代码片段、命令序列或配置文件。\n"
        "- 不要为了突出重点而使用 text/plain 代码块。只有真正代码、命令序列、配置文件、LaTeX 源码才使用围栏代码块。普通术语、变量名、API 名称请使用行内代码或加粗。\n"
        "- 包含完整逻辑的代码片段（多行、跨行、控制流、函数体）才使用围栏代码块。\n"
        "- 围栏代码块必须带语言标识：```python、```java、```c、```cpp、```javascript、```bash、```sql、```json、```latex。\n"
        "- 单行 Shell 命令或配置项优先用行内代码 `command`，不要单独开围栏代码块。只有多行命令序列或完整脚本才用围栏代码块。\n"
        "- 输出示例、简短错误信息展示可用不带语言标识的代码块（仅此一种例外）。\n"
        "## 数学公式格式规范\n"
        "- 行内公式用 $...$ 包裹，块级公式用 $$...$$ 包裹。\n"
        "- 不要把 LaTeX 公式放在普通代码块里，除非用户明确要求 LaTeX 源码。\n"
        "- 不要使用 HTML 标签。\n"
        "## 推荐回答结构\n"
        "- 资料类问题：**核心结论** → **资料主要内容** → **重点知识点** → **代码/注意事项（如有）** → **学习建议** → **简短总结**。\n"
        "- 概念类问题：**一句话理解** → **核心概念** → **关键点** → **示例** → **常见误区** → **你接下来可以这样学**。\n"
        "- 代码类问题：**问题定位** → **原因分析** → **修改建议** → **示例代码** → **验证方式**。\n"
        "- 题目类问题：**题目考点** → **解题思路** → **逐步推导** → **最终答案** → **易错点** → **同类题方法总结**。\n"
        "- 如果回答内容较多，用二级标题 ## 划分段落，方便阅读。\n"
        "- 每个部分的标题直接写中文，不需要在标题文字外再加粗。\n"
        "- 学习类问题优先使用小标题、分点解释、例子、易错点和简短总结。",
        QUESTION_TYPE_INSTRUCTIONS[question_type],
    ]

    if subject_guidance:
        sections.append(subject_guidance)

    if knowledge_context:
        sections.append(knowledge_context)

    sections.append(_build_rag_instruction(rag_chunks, is_attachment=has_attachment))

    if has_attachment:
        sections.append(
            "用户本轮上传了资料文件。请严格依据资料提取出的文本回答。"
            "用户的问题（即使是“解读一下”“总结一下”“分析一下”等简短指令）默认就是针对这些文件的。"
            "绝对不要回复“没有具体对象”“请说明你想了解什么”“请问您想让我解读什么”等。"
            "直接开始解读上传的文件内容。"
            "若资料内容里没有覆盖用户的问题，要直接说明资料未覆盖，不要编造。"
        )

    if normalized_question:
        sections.append(f"当前用户问题：{normalized_question}")

    return "\n\n".join(sections).strip()


# ---------------------------------------------------------------- Deep Study (P3A)
#
# The Deep Study prompt is built from the SAME system prompt the product already uses (so the
# evidence rules, the citation behaviour and the markdown contract do not fork), plus the ONE
# instruction block that makes the workflow a deep study rather than a single answer. Keeping
# it here — and not in the endpoint — is the long-term Prompt Registry rule: business code
# asks for a message list, it does not assemble one.

DEEP_STUDY_INSTRUCTION = (
    "## 深度研习模式（Strong Reasoning）\n"
    "用户请求的是一次深入研习，而不是一句话回答。请严格遵守：\n"
    "- 先给出**结论**，再展开**推理过程**，明确写出关键判断的依据。\n"
    "- 当参考片段支持某个结论时，在句末用【文件名】标注来源；只标注真实命中的资料。\n"
    "- 如果参考片段不足以支撑某个结论，直接说明“资料未覆盖”，再给出通用解释，"
    "并且不要为该部分标注来源。\n"
    "- 涉及易混淆概念时，给出**对比**与**常见误区**。\n"
    "- 最后给出**可执行的下一步**（下一步该学什么、该练什么），但不要编造用户的学习数据。\n"
    "- 不要臆造资料内容、页码、公式编号或引用。\n"
)


PLAN_ADJUSTMENT_INSTRUCTION = (
    "你是一名学习规划助手。下面给出学生**当前计划**的真实状态、复习投影、练习统计与最近的"
    "学习事件。请给出一次**有界**的计划调整建议，严格返回 JSON（不要 markdown 代码块）：\n"
    '{"reason":"为什么要这样调整（结合给定数据，80字内）",\n'
    ' "changes":[{"op":"create_task","title":"任务标题","task_type":"knowledge|review|practice",'
    '"due_date":"YYYY-MM-DD 或 null","reason":"理由"},\n'
    '            {"op":"update_task","task_id":123,"due_date":"YYYY-MM-DD 或 null",'
    '"title":"可选的新标题","status":"可选：not_started|in_progress|completed",'
    '"reason":"理由"}]}'
    "\n\n要求："
    "\n- 只能使用给定数据中出现的事实，禁止编造学生没有的课程、知识点或成绩；"
    "\n- changes 最多 5 条，优先处理逾期任务与到期复习项；"
    "\n- update_task 只能针对 tasks 中出现的 task_id；不要删除任务；"
    "\n- 不要做长期预测，也不要替学生决定学习目标。"
)


def build_plan_adjustment_messages(facts: dict, goal: str = "") -> list[dict]:
    """The ONLY thing the planning model sees: the learner's real plan and real facts."""
    import json as _json

    payload = _json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str)
    parts = [f"学生当前状态：\n{payload}"]
    if goal:
        parts.append(f"学生本次的目标/偏好：{goal}")
    return [{"role": "system", "content": PLAN_ADJUSTMENT_INSTRUCTION},
            {"role": "user", "content": "\n\n".join(parts)}]


WRONG_ANALYSIS_INSTRUCTION = (
    "你是一名计算机课程老师，正在分析学生一道错题的原因。\n"
    "下面给出的是学生这道题的**真实记录**（题干、学生的答案、参考答案、解析、作答历史）。\n"
    "请做错因分析，严格返回 JSON（不要 markdown 代码块），字段如下：\n"
    '{"error_category":"错误类型（如：概念混淆/计算错误/审题偏差/步骤缺失/知识空缺）",\n'
    ' "reasoning_gap":"学生的推理在哪里断了（结合其真实答案说明）",\n'
    ' "correct_reasoning":"正确的推理过程（简明的步骤化讲解）",\n'
    ' "next_action":"下一步具体可执行的复习动作（一条）",\n'
    ' "review_recommendation":"建议的复习重点与时机"}'
    "\n\n要求："
    "\n- 只依据给出的记录分析，不要编造学生没有出现过的答案或历史；"
    "\n- 不要对学生能力、天赋或掌握程度下结论，也不要预测分数；"
    "\n- 每个字段控制在 120 字以内，使用中文。"
)


def build_wrong_analysis_messages(facts: dict) -> list[dict]:
    """The ONLY thing the wrong-cause model sees: the state's own recorded facts."""
    import json as _json

    payload = _json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str)
    return [{"role": "system", "content": WRONG_ANALYSIS_INSTRUCTION},
            {"role": "user", "content": f"这道错题的记录：\n{payload}"}]


REPORT_NARRATIVE_INSTRUCTION = (
    "## 学习报告叙述（仅基于给定数据）\n"
    "下面是一份由系统确定性计算出的学习报告数据（JSON）。请写一段中文学习总结，严格遵守：\n"
    "- 只能使用 JSON 中出现的数字与事实，禁止编造任何未出现的数据、日期或事件。\n"
    "- 某个指标为 null 表示该学习空间没有这类数据，请直接不要提及，不要说成 0。\n"
    "- 不要评价学习者的能力、天赋或掌握程度，不要做预测；只描述这段时间发生了什么。\n"
    "- 若存在 attention 项，请在结尾给出一到两条具体、可执行的下一步建议。\n"
    "- 直接输出 150-300 字的总结，不要使用标题或代码块，不要复述 JSON。\n"
)


def build_report_narrative_messages(report_data: dict) -> list[dict]:
    """The ONLY thing a report narrative model is allowed to see: the computed ReportData."""
    import json as _json

    payload = _json.dumps(report_data, ensure_ascii=False, sort_keys=True, default=str)
    return [{"role": "system", "content": REPORT_NARRATIVE_INSTRUCTION},
            {"role": "user", "content": f"报告数据：\n{payload}"}]


def build_deep_study_messages(question: str,
                              subject: str | None = None,
                              rag_chunks: list[dict] | None = None,
                              knowledge_point_id: str | None = None) -> list[dict]:
    """System + user messages for ONE Deep Study answer.

    ``rag_chunks`` is the already-retrieved, already-isolated evidence: whatever is in it is
    what the answer may cite, and an empty list is a legitimate state that the prompt states
    honestly rather than papering over.
    """
    system_prompt = build_system_prompt(
        subject, question, user_profile_data=None,
        has_attachment=bool(rag_chunks), rag_chunks=rag_chunks,
        knowledge_context="")
    parts = [system_prompt, DEEP_STUDY_INSTRUCTION]
    if knowledge_point_id:
        parts.append(f"当前知识点：{knowledge_point_id}")
    parts.append(f"请就以下问题进行深度研习：{_normalize_question(question)}")
    return [{"role": "system", "content": "\n\n".join(parts)}]
