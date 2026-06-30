COURSE_OPTIONS = [
    "计算系统基础",
    "C语言",
    "C++",
    "Python",
    "Java",
    "离散数学",
    "数据结构与算法",
    "计算机组成结构",
    "互联网计算",
    "计算机操作系统",
    "编译原理",
    "数据管理",
    "人机交互",
]

DEFAULT_SUBJECT = "计算系统基础"

SUBJECT_ALIASES = {
    "": DEFAULT_SUBJECT,
    "数据库": "数据管理",
    "数据管理": "数据管理",
    "操作系统": "计算机操作系统",
    "计算机操作系统": "计算机操作系统",
    "计算机组成": "计算机组成结构",
    "计算机组成原理": "计算机组成结构",
    "计算机组成结构": "计算机组成结构",
    "计算机网络": "计算机网络",
    "网络": "互联网计算",
    "互联网计算": "互联网计算",
    "数据结构": "数据结构与算法",
    "算法": "数据结构与算法",
    "数据结构与算法": "数据结构与算法",
    "c": "C语言",
    "C": "C语言",
    "C语言": "C语言",
    "c++": "C++",
    "C++": "C++",
    "c＋+": "C++",
    "C＋+": "C++",
    "python": "Python",
    "Python": "Python",
    "java": "Java",
    "Java": "Java",
    "离散数学": "离散数学",
    "编译原理": "编译原理",
    "人机交互": "人机交互",
    "计算系统基础": "计算系统基础",

    # course_learning self-aliases (override canonical remaps above for strict course name matching)
    "数据结构": "数据结构",
    "操作系统": "操作系统",
}


def normalize_subject(
    subject: str | None = None,
    course: str | None = None,
    default: str = DEFAULT_SUBJECT,
) -> str:
    raw_value = (subject or course or "").strip()
    if not raw_value:
        return default

    if raw_value in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[raw_value]

    lowered = raw_value.lower()
    if lowered in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[lowered]

    return raw_value


def get_subject_migration_pairs():
    pairs: list[tuple[str, str]] = []
    seen_aliases: set[str] = set()

    for alias, canonical in SUBJECT_ALIASES.items():
        cleaned_alias = (alias or "").strip()
        if not cleaned_alias or cleaned_alias == canonical:
            continue
        if cleaned_alias in seen_aliases:
            continue
        pairs.append((cleaned_alias, canonical))
        seen_aliases.add(cleaned_alias)

    return pairs
