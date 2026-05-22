import re


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
一、先用一句话理解
二、核心概念
三、关键点拆解
四、举例说明
五、常见误区
六、你接下来可以这样学""",
    "code_debug": """请优先按这个结构回答：
一、问题定位
二、错误原因
三、应该修改的位置
四、修改建议或示例代码
五、为什么这样改
六、如何验证""",
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
    "python": "当前学科偏向 Python，请优先结合语法、函数、类、模块、调试思路和可运行示例来讲解。",
    "java": "当前学科偏向 Java，请优先结合语法、面向对象、集合、异常、JVM 和代码实践来讲解。",
    "data structures": "当前学科偏向数据结构，请优先强调抽象结构、操作过程、时间复杂度、空间复杂度和图示化理解。",
    "数据结构": "当前学科偏向数据结构，请优先强调抽象结构、操作过程、时间复杂度、空间复杂度和图示化理解。",
    "computer networks": "当前学科偏向计算机网络，请优先解释分层、协议作用、数据传输过程和典型场景。",
    "计算机网络": "当前学科偏向计算机网络，请优先解释分层、协议作用、数据传输过程和典型场景。",
    "operating systems": "当前学科偏向操作系统，请优先关注进程、线程、调度、内存管理、文件系统和考试常见易错点。",
    "操作系统": "当前学科偏向操作系统，请优先关注进程、线程、调度、内存管理、文件系统和考试常见易错点。",
    "databases": "当前学科偏向数据库，请优先结合表结构、SQL、索引、事务和查询过程来讲解。",
    "数据库": "当前学科偏向数据库，请优先结合表结构、SQL、索引、事务和查询过程来讲解。",
    "frontend development": "当前学科偏向前端开发，请优先结合 HTML、CSS、JavaScript、React 和页面交互场景来讲解。",
    "前端开发": "当前学科偏向前端开发，请优先结合 HTML、CSS、JavaScript、React 和页面交互场景来讲解。",
    "backend development": "当前学科偏向后端开发，请优先结合接口、业务逻辑、数据库、错误处理和部署来讲解。",
    "后端开发": "当前学科偏向后端开发，请优先结合接口、业务逻辑、数据库、错误处理和部署来讲解。",
    "algorithms": "当前学科偏向算法，请优先强调思路拆解、复杂度、边界条件和同类题方法。",
    "算法": "当前学科偏向算法，请优先强调思路拆解、复杂度、边界条件和同类题方法。",
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
    normalized = (subject or "").strip()
    return normalized or "通用学习"


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


def _build_rag_instruction(rag_chunks: list[dict] | None) -> str:
    if not rag_chunks:
        return (
            "当前没有命中用户资料库片段。请正常回答；如果这个问题明显依赖课程资料，"
            "可以简短提醒用户补充该学科资料，但不要影响主回答。"
        )

    blocks = []
    for index, item in enumerate(rag_chunks[:4], start=1):
        filename = item.get("source_filename") or item.get("filename") or "未命名资料"
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

    return (
        "本次回答可以参考用户个人资料库。请优先根据资料库片段回答，并在回答中自然说明“根据你资料库中的内容”。\n"
        "如果资料片段不足以完整回答，请明确说明“资料中没有完整覆盖，我补充解释如下”。\n"
        "不要编造资料中不存在的内容，不要把资料全文原样复制出来。\n"
        "本次可参考的资料片段如下：\n"
        + "\n\n".join(blocks)
    )


def build_system_prompt(
    subject: str | None,
    question: str | None,
    user_profile_data: dict | None = None,
    is_pdf: bool = False,
    rag_chunks: list[dict] | None = None,
) -> str:
    normalized_subject = _normalize_subject(subject)
    normalized_question = _normalize_question(question)
    question_type = detect_question_type(normalized_question)
    profile = user_profile_data or {}
    grade = (profile.get("grade") or "").strip() or "未填写"
    major = (profile.get("major") or "").strip() or "未填写"
    subject_guidance = SUBJECT_GUIDANCE.get(normalized_subject.lower()) or SUBJECT_GUIDANCE.get(normalized_subject)

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
        "- 对明显作业、考试或算法题，以讲解思路和推导过程为主，同时可以给出最终答案，但重点是帮助理解，不要鼓励抄作业。",
        QUESTION_TYPE_INSTRUCTIONS[question_type],
    ]

    if subject_guidance:
        sections.append(subject_guidance)

    sections.append(_build_rag_instruction(rag_chunks))

    if is_pdf:
        sections.append(
            "如果当前问题来自上传资料问答，请严格依据提取出的 PDF 或图片文本回答；"
            "若资料内容里没有答案，要直接说明资料未覆盖，不要编造。"
        )

    if normalized_question:
        sections.append(f"当前用户问题：{normalized_question}")

    return "\n\n".join(sections).strip()
