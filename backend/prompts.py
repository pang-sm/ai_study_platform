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
    is_pdf: bool = False,
    rag_chunks: list[dict] | None = None,
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
        "- 请使用 Markdown 格式回答。正文像教材讲解一样自然分段。重点内容用加粗突出。\n"
        "- 遇到代码、命令行、配置、LaTeX 推导时，必须使用带语言标识的代码块。代码块语言名使用 python、java、c、latex、bash、sql、json、javascript 等。\n"
        "- 遇到公式时使用 LaTeX 格式：行内公式用 $...$ 包裹，块级公式用 $$...$$ 包裹。\n"
        "- 数学公式优先使用 $...$ 表示行内公式，使用 $$...$$ 表示块级公式；不要使用 HTML；不要把 LaTeX 公式放在普通代码块里，除非用户明确要求 LaTeX 源码。\n"
        "- 不要输出 HTML。不要把整段内容压缩成一个段落。学习类问题优先使用小标题、分点解释、例子、易错点和简短总结。",
        QUESTION_TYPE_INSTRUCTIONS[question_type],
    ]

    if subject_guidance:
        sections.append(subject_guidance)

    sections.append(_build_rag_instruction(rag_chunks, is_attachment=is_pdf))

    if is_pdf:
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
