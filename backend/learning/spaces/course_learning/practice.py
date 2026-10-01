"""Course practice — ONE scoped set of questions, played one at a time.

WHAT THIS OWNS
--------------
Everything behind 专业学习 → 练习: the scope the learner chose, the question set a model
produced for that scope, the schema rules a question must satisfy before a learner is ever
shown it, the per-question verdict, and the write-back that turns a finished set into the
product's EXISTING learning facts.

WHAT IT IS NOT
--------------
Not a second wrong-answer system, not a second record chain, and not a second practice
core. A finished set writes through the paths that already exist:

    knowledge progress  →  learning.spaces.course_learning.knowledge.apply_knowledge_change
    study record        →  models.LearningRecord (record_type="practice")
    data plane          →  data_plane.emitter (course_practice events)
    canonical practice  →  learning.practice.adapters.course.mirror_ai_question_attempt

WHY THE SCOPE IS RESOLVED HERE, FROM THE LEARNER'S OWN STRUCTURE
----------------------------------------------------------------
"严格围绕这个知识点出题" is only checkable if the server knows what the allowed set IS.
So the scope is resolved SERVER-SIDE from the learner's ACTIVE knowledge structure before
any model call, the model is handed that set as a numbered allow-list, and every returned
question is mapped back onto it. A question the model cannot attribute to the allow-list is
refused — the model's own claim about what it covered is never trusted.

THE PUBLISHED-MAP FALLBACK
--------------------------
A course-scope request from a learner who has not built a structure yet would otherwise have
no allowed set at all. For that one case — and only for it — the course's published knowledge
map (``seed_data/knowledge_maps/<course>.json``) supplies the allowed set, which is what the
course space used before user structures existed. Point- and chapter-scoped requests are
NEVER answered from the map: the learner named a node of their own tree, and substituting a
differently-identified set for it is exactly the silent scope expansion this module exists to
prevent.

QUESTION IDENTITY
-----------------
``AIGeneratedQuestion.knowledge_point_id`` stores the canonical form:

    ``kp:<n>``    a point of the learner's OWN structure (``n`` is the ``knowledge_points`` id)
    anything else a knowledge-map code, resolved as a text code

The prefix is what makes the write-back unambiguous: a knowledge-map code is a number as often
as not, and a bare number could name either a structure point or a code.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session as DbSession

from .context import course_identity_forms, normalize_course_id
from .knowledge_structure import (
    STRUCTURE_ACTIVE,
    _knowledge_map_seed_path,
    _points,
    _structures,
    build_tree,
)
from . import question_quality as quality

logger = logging.getLogger("learning.spaces.course_learning")

# Unchanged: the workbook query and the wrong-answer content resolution read this value.
REQUIREMENT = "课程章节练习"

SCOPE_KNOWLEDGE_POINT = "knowledge_point"
SCOPE_CHAPTER = "chapter"
SCOPE_COURSE = "course"
SCOPES = (SCOPE_KNOWLEDGE_POINT, SCOPE_CHAPTER, SCOPE_COURSE)

GOAL_CONSOLIDATE = "consolidate"
GOAL_GAP_FILL = "gap_fill"
GOAL_EXAM_TRAIN = "exam_train"
GOALS = (GOAL_CONSOLIDATE, GOAL_GAP_FILL, GOAL_EXAM_TRAIN)
GOAL_LABELS = {GOAL_CONSOLIDATE: "巩固理解", GOAL_GAP_FILL: "查漏补缺", GOAL_EXAM_TRAIN: "考试训练"}

DIFFICULTY_ADAPTIVE = "adaptive"
DIFFICULTIES = (DIFFICULTY_ADAPTIVE, "basic", "medium", "hard")
# The stored vocabulary is the product's own — the same words the exam space stores.
DIFFICULTY_LABELS = {"basic": "基础", "medium": "中等", "hard": "较难"}

SINGLE_CHOICE = "single_choice"
MULTIPLE_CHOICE = "multiple_choice"
TRUE_FALSE = "true_false"
SHORT_ANSWER = "short_answer"
QUESTION_TYPES = (SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE, SHORT_ANSWER)

TRUE_FALSE_OPTIONS = {"A": "正确", "B": "错误"}
OPTION_LABELS = ("A", "B", "C", "D")

# What ability each type usually asks for, used only to read a verdict that was stored before
# questions carried their own level. Never used to choose what to generate.
_TYPE_LEVEL = {
    SINGLE_CHOICE: quality.UNDERSTAND,
    MULTIPLE_CHOICE: quality.ANALYZE,
    TRUE_FALSE: quality.ANALYZE,
    SHORT_ANSWER: quality.SYNTHESIZE,
}

COUNTS = (3, 5, 10)
DEFAULT_COUNT = 5

# How many questions of each type a set of a given size contains. A product decision, fixed
# rather than model-chosen: a learner must be able to see what they are getting, and the first
# question is always a single choice, so the entry question is the familiar one.
_TYPE_MIX = {
    3: (SINGLE_CHOICE, SINGLE_CHOICE, TRUE_FALSE),
    5: (SINGLE_CHOICE, SINGLE_CHOICE, TRUE_FALSE, MULTIPLE_CHOICE, SHORT_ANSWER),
    10: (SINGLE_CHOICE, SINGLE_CHOICE, SINGLE_CHOICE, SINGLE_CHOICE,
         TRUE_FALSE, TRUE_FALSE, MULTIPLE_CHOICE, MULTIPLE_CHOICE,
         SHORT_ANSWER, SHORT_ANSWER),
}

# Token budget per set.
#
# Sized from the provider's OWN reported usage, never from the size of the visible answer. The
# cheapest qualified model for this capability bills its hidden reasoning INSIDE ``max_tokens``
# (``ai.cost.REASONING_BOUNDED``), so a budget that looks generous for ten questions is not: the
# reasoning is spent first and the JSON is cut off mid-answer. That is the defect behind the
# production report — a 10-question request on 「循环队列」 returned ``finish_reason=length`` at
# 6,000 tokens with 5,552 of them reasoning, the parser discarded the truncated payload, and the
# set was filled from the local bank, which is where the "请简述「循环队列」的核心含义" questions
# came from. 3-question sets were broken the same way (4,333 > 3,000); only 5-question sets fit.
#
# Measured 2026-10-01, deepseek-flash, finish_reason=stop, thinking at provider default, with
# the coverage-matrix prompt this module now sends (reasoning is most of the total):
#     3 questions →  4,905 output tokens (4,011 reasoning)
#     5 questions →  8,046 output tokens (6,007 reasoning)
#    10 questions → 12,902 output tokens (9,974 reasoning)
# Reasoning varies run to run and is not bounded from above, so each budget carries headroom on
# top of the largest observed sample rather than sitting at it.
_TOKEN_BUDGET = {3: 10000, 5: 12000, 10: 16000}

# How many times the model is asked again for the slots that are still empty. A retry is
# per-slot (see ``generate``): the questions that DID pass are never regenerated.
_MAX_GENERATION_ATTEMPTS = 3

_KP_PREFIX = "kp:"


class PracticeError(Exception):
    """A request or a generation the caller must be told about, with its own status code."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class ScopeError(PracticeError):
    """The scope the learner asked for is not one this learner's course can be practised."""


# ------------------------------------------------------------------ scope resolution


@dataclass
class ScopePoint:
    """One knowledge point a generated question may be attributed to."""

    key: str                 # what the question row stores in knowledge_point_id
    title: str
    chapter: str
    description: str = ""


@dataclass
class Scope:
    kind: str
    course_id: str
    course_name: str
    chapters: list[dict]            # [{id, title, points: [ScopePoint]}] — the allowed set
    label: str                      # what the page says the learner is practising
    points: list[ScopePoint] = field(default_factory=list)
    source: str = "structure"       # structure | knowledge_map
    structure_id: int | None = None


def _course_name(db: DbSession, course_id: str) -> str:
    """The course's own display name from the learner's preference row, else the id."""
    from models import CourseLearningPreference
    row = (db.query(CourseLearningPreference)
           .filter(CourseLearningPreference.course_id == course_id)
           .first())
    name = getattr(row, "display_name", None)
    return name.strip() if isinstance(name, str) and name.strip() else course_id


def _structure_chapters(db: DbSession, username: str, course_id: str) -> tuple[int | None, list[dict]]:
    """The learner's ACTIVE structure as chapters of ScopePoints — or (None, []) when none."""
    forms = course_identity_forms(normalize_course_id(course_id))
    rows = _structures(db, username, forms, STRUCTURE_ACTIVE)
    if not rows:
        return None, []
    structure = rows[0]
    chapters = []
    for chapter in build_tree(_points(db, username, forms, structure.id)):
        title = chapter.get("title") or ""
        chapters.append({
            "id": chapter.get("id"),
            "title": title,
            "points": [ScopePoint(key=f"{_KP_PREFIX}{point['id']}", title=point["title"],
                                  chapter=title, description=point.get("description") or "")
                       for point in chapter["points"]],
        })
    return structure.id, [chapter for chapter in chapters if chapter["points"]]


def _knowledge_map_chapters(course_id: str) -> list[dict]:
    """The course's published knowledge map, used ONLY when the learner has no structure.

    A course's *identity* here is its display name (``数据结构``), while the published maps are
    filed under their English keys. Both are tried, through the same resolver the course space
    has always used, so the fallback does not depend on which form the caller holds.
    """
    from subjects import resolve_course_id_from_display

    path = _knowledge_map_seed_path(course_id)
    if not path.exists():
        mapped = resolve_course_id_from_display(course_id)
        if mapped:
            path = _knowledge_map_seed_path(mapped)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("practice.knowledge_map_unreadable course=%r", course_id)
        return []

    chapters: list[dict] = []

    def walk(nodes, chapter_title: str = "", depth: int = 0):
        for index, node in enumerate(nodes or [], start=1):
            children = node.get("children") or []
            title = str(node.get("title") or node.get("name") or "").strip()
            if children:
                walk(children, chapter_title or title, depth + 1)
                continue
            code = str(node.get("code") or f"_leaf:{index}").strip()
            target = chapters[-1] if chapters and chapters[-1]["title"] == chapter_title else None
            if target is None:
                target = {"id": None, "title": chapter_title, "points": []}
                chapters.append(target)
            target["points"].append(ScopePoint(
                key=code, title=title, chapter=chapter_title,
                description=str(node.get("description") or "").strip()))

    walk(payload.get("chapters") or [])
    return [chapter for chapter in chapters if chapter["points"]]


def _all_points(chapters: list[dict]) -> list[ScopePoint]:
    return [point for chapter in chapters for point in chapter["points"]]


def resolve_scope(db: DbSession, username: str, course_id: str, *,
                  scope: str, knowledge_point_id: int | None = None,
                  chapter_id: int | None = None) -> Scope:
    """The allowed question set for this request — or a refusal naming what is wrong."""
    key = normalize_course_id(course_id)
    course_name = _course_name(db, key)
    structure_id, chapters = _structure_chapters(db, username, key)

    if scope in (SCOPE_KNOWLEDGE_POINT, SCOPE_CHAPTER):
        if structure_id is None or not chapters:
            raise ScopeError("当前课程还没有知识结构，请先在知识结构里建立后再练习。", 409)
        if scope == SCOPE_KNOWLEDGE_POINT:
            if not knowledge_point_id:
                raise ScopeError("请选择一个知识点。", 400)
            wanted = f"{_KP_PREFIX}{int(knowledge_point_id)}"
            for chapter in chapters:
                hit = next((point for point in chapter["points"] if point.key == wanted), None)
                if hit is not None:
                    return Scope(kind=scope, course_id=key, course_name=course_name,
                                 chapters=[{"id": chapter["id"], "title": chapter["title"],
                                            "points": [hit]}],
                                 points=[hit], label=hit.title,
                                 source="structure", structure_id=structure_id)
            raise ScopeError("这个知识点不在当前知识结构里，请返回知识结构重新进入。", 404)
        if not chapter_id:
            raise ScopeError("请选择一个章节。", 400)
        for chapter in chapters:
            if chapter["id"] == int(chapter_id):
                return Scope(kind=scope, course_id=key, course_name=course_name,
                             chapters=[chapter], points=chapter["points"],
                             label=chapter["title"],
                             source="structure", structure_id=structure_id)
        raise ScopeError("这个章节不在当前知识结构里，请返回知识结构重新进入。", 404)

    if chapters:
        return Scope(kind=scope, course_id=key, course_name=course_name,
                     chapters=chapters, points=_all_points(chapters),
                     label=f"{course_name}整门课程",
                     source="structure", structure_id=structure_id)
    chapters = _knowledge_map_chapters(key)
    if not chapters:
        raise ScopeError("当前课程还没有可练习的知识范围。", 409)
    return Scope(kind=scope, course_id=key, course_name=course_name,
                 chapters=chapters, points=_all_points(chapters),
                 label=f"{course_name}整门课程", source="knowledge_map")


# ------------------------------------------------------------------ adaptive context


def adaptive_context(db: DbSession, user, scope: Scope) -> dict:
    """What the product already knows about this learner, for difficulty and type mix.

    Facts only, and only about the points in scope: stored knowledge status, review dates, the
    learner's own recent practice results, and the course's ACTIVE wrong-answer states. No
    model is consulted, and nothing here is a claim about ability.
    """
    from sqlalchemy import or_

    from models import AIQuestionAttempt, UserKnowledgeProgress

    point_ids = [int(point.key[len(_KP_PREFIX):]) for point in scope.points
                 if point.key.startswith(_KP_PREFIX)]
    codes = [point.key for point in scope.points if not point.key.startswith(_KP_PREFIX)]

    conditions = []
    if point_ids:
        conditions.append(UserKnowledgeProgress.knowledge_point_id.in_(point_ids))
    if codes:
        conditions.append(UserKnowledgeProgress.knowledge_point_code.in_(codes))
    rows = []
    if conditions:
        rows = (db.query(UserKnowledgeProgress)
                .filter(UserKnowledgeProgress.username == user.username,
                        UserKnowledgeProgress.course_id == scope.course_id,
                        or_(*conditions))
                .all())

    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row.status or "not_started"] = statuses.get(row.status or "not_started", 0) + 1

    recent = (db.query(AIQuestionAttempt)
              .filter(AIQuestionAttempt.username == user.username,
                      AIQuestionAttempt.mode == "course_learning",
                      AIQuestionAttempt.subject_key == scope.course_id,
                      AIQuestionAttempt.status == "submitted")
              .order_by(AIQuestionAttempt.submitted_at.desc())
              .limit(10).all())
    graded = 0
    correct = 0
    by_level: dict[str, list[int]] = {}
    for attempt in recent:
        try:
            data = json.loads(attempt.result_json or "{}")
        except (TypeError, ValueError):
            continue
        for item in (data.get("results") or []):
            if isinstance(item, dict) and item.get("correct") is not None:
                graded += 1
                correct += 1 if item["correct"] else 0
                # Which ABILITY the learner got right matters more than the raw score: a set
                # can be chosen to ask more of what they are getting wrong. Questions answered
                # before levels were recorded fall back to the level their type usually asks.
                level = (item.get("cognitive_level")
                         or _TYPE_LEVEL.get(str(item.get("question_type") or "")))
                if level:
                    by_level.setdefault(level, []).append(1 if item["correct"] else 0)

    # A level is only reported once there is enough of it to mean something. Three answers is
    # the floor: below that a single wrong answer would look like a weakness in the ability.
    level_accuracy = {level: sum(scores) / len(scores)
                      for level, scores in by_level.items() if len(scores) >= 3}

    wrong_count = 0
    try:
        from learning.wrong_answers.models import STATUS_ACTIVE, WrongAnswerState
        from learning.wrong_answers.service import course_scope_key
        wrong_count = (db.query(WrongAnswerState)
                       .filter(WrongAnswerState.user_id == user.id,
                               WrongAnswerState.service_namespace == "course_learning",
                               WrongAnswerState.question_scope_key == course_scope_key(scope.course_id),
                               WrongAnswerState.status == STATUS_ACTIVE)
                       .count())
    except Exception as exc:  # noqa: BLE001 — this read only informs the difficulty choice
        logger.warning("practice.wrong_count_unavailable %s", type(exc).__name__)

    return {
        "has_history": bool(rows or graded),
        "attempts": graded,
        "accuracy": (correct / graded) if graded else None,
        "level_accuracy": level_accuracy,
        "statuses": statuses,
        "review_due": statuses.get("review_due", 0),
        "wrong_count": wrong_count,
    }


def choose_difficulty(requested: str, context: dict) -> str:
    """'自适应' resolved to ONE stored difficulty, from the learner's own record.

    With no history the ask is ANSWERED rather than refused: a first practice is generated at
    中等, which is the difficulty the learner's choice names — never an error and never an
    empty set.
    """
    if requested in DIFFICULTY_LABELS:
        return requested
    accuracy = context.get("accuracy")
    if accuracy is None:
        return "medium"
    if accuracy >= 0.8 and context.get("wrong_count", 0) == 0:
        return "hard"
    if accuracy <= 0.4 or context.get("wrong_count", 0) >= 3:
        return "basic"
    return "medium"


# ------------------------------------------------------------------ prompt


# Each rule leads with the LITERAL value of ``question_type``. Describing the type without
# naming it is not enough: asked for "判断", a model answered with ``"judge"``, and a question
# that is perfectly well formed was thrown away for a label the prompt never fixed.
_TYPE_RULES = {
    SINGLE_CHOICE: ('question_type 必须是 "single_choice"（单项选择）：options 固定为 A/B/C/D 四个，'
                    "正确选项恰好 1 个，standard_answer 写成一个字母"),
    MULTIPLE_CHOICE: ('question_type 必须是 "multiple_choice"（多项选择）：options 固定为 A/B/C/D 四个，'
                      "正确选项 2-3 个，standard_answer 按字母升序连写（如 AC）"),
    TRUE_FALSE: ('question_type 必须是 "true_false"（判断题，不要写成 judge 等其他字样）：'
                 'options 固定为 {"A": "正确", "B": "错误"}，standard_answer 为 "A" 或 "B"'),
    SHORT_ANSWER: ('question_type 必须是 "short_answer"（简答）：options 为空对象 {}，'
                   "standard_answer 是参考答案要点"),
}


def build_prompt(scope: Scope, *, goal: str, difficulty: str, slots: tuple[quality.Slot, ...],
                 avoid_stems: list[str], avoid_targets: list[str] = (),
                 grounding: str = "") -> tuple[list[dict], dict[int, ScopePoint]]:
    """The generation request: the allowed set, the coverage matrix, and the output contract.

    The model is NOT handed a free "write N questions" ask. It is handed a matrix — for each
    position, the question type and the ability that position must exercise — and told that no
    two positions may test the same ability. That is what makes "十道题都是同一个模板换皮"
    detectable server-side rather than merely discouraged: every question declares the ability
    it covers, and the collector counts the distinct ones.
    """
    lines: list[str] = []
    available: dict[int, ScopePoint] = {}
    for chapter in scope.chapters:
        lines.append(f"【章节】{chapter['title'] or '未命名章节'}")
        for point in chapter["points"]:
            available[len(available) + 1] = point
            description = f"（{point.description}）" if point.description else ""
            lines.append(f"  {len(available)}. {point.title}{description}")
    catalogue = "\n".join(lines)

    matrix = "\n".join(
        f'  第 {index + 1} 题：{_TYPE_RULES[slot.question_type]}；'
        f'本题必须考查「{slot.role}」这一项能力，认知层级为 "{slot.cognitive_level}"'
        f"（{quality.LEVEL_LABELS[slot.cognitive_level]}）"
        for index, slot in enumerate(slots))
    avoided_stem_lines = "\n".join(f"- {stem}" for stem in avoid_stems[:24])
    avoided_target_lines = "\n".join(f"- {target}" for target in avoid_targets[:16])
    avoided = (avoided_stem_lines or "（还没有已生成的题目）")
    if avoided_target_lines:
        avoided += "\n\n这些能力点最近已经考过，本次换别的角度考：\n" + avoided_target_lines

    grounding_block = ""
    if grounding:
        grounding_block = f"""
课程资料中与本次范围相关的内容（请优先使用其中的术语、定义和例子出题；不要直接抄录原文当作题干）：
{grounding}
"""

    prompt = f"""你是大学课程「{scope.course_name}」的命题老师。下面是一份已经确定好的命题矩阵，请严格按矩阵出题。

课程：{scope.course_name}
练习范围：{scope.label}
练习目标：{GOAL_LABELS.get(goal, GOAL_LABELS[GOAL_CONSOLIDATE])}
难度：{DIFFICULTY_LABELS[difficulty]}
题目数量：{len(slots)}

允许出题的知识范围（只能从这份清单里选，清单编号就是 knowledge_point_index）：
{catalogue}
{grounding_block}
命题矩阵（位置、题型、必须考查的能力，顺序不可打乱）：
{matrix}

question_type 只能取这四个字符串之一：single_choice / multiple_choice / true_false / short_answer。
question_type 字段只能填这四个值之一（只能用英文，不要写成"判断""选择""judge"等其他字样）。

在写题之前，先在脑中为每一题确定一个具体的「考查能力」（assessment_target），
例如"队列长度的计算""队满条件的判断""入队后 rear 的推演""某种实现错误的定位"。
它必须是这个知识点下面的一个具体能力，不能是知识点名称本身。
整份题目的考查能力必须互不相同——十道题就必须是十个不同的能力角度。
这个能力写进每题的 assessment_target 字段，学生看不到它，只用于质检。

必须避开的题干（不要重复，也不要只改几个字）：
{avoided}

禁止出现的题型（出现即作废）：
- 问"X 是不是本章需要掌握的内容""X 是否重要""学习 X 有什么意义"这类元问题；
- "请简述 X 的核心含义并说明适用情况""请介绍 X""谈谈你对 X 的理解"这类泛化模板；
- 把知识点标题直接改写成问题；
- 判断题用"X 是重要内容""X 是本章知识点"这种不学也会答的话；
- 选择题里放"以上都对""以上都不对"这类不用掌握知识也能选的选项；
- 同一个考点换几个词问第二遍。

命题要求：
1. 每道题只能考核上面清单里的某一个知识点，并必须在 knowledge_point_index 里写上它的编号。
2. 任何一道题如果无法明确归到清单中的某一个知识点，就不要输出这道题。
3. 不得考查清单之外的内容，不得扩展到其他章节或其他课程。
4. 题干要完整、自洽，能独立读懂，不要出现"如下图""参见课本"这类没有给出信息的表述。
5. 题干和选项都不得泄露答案，不得出现"正确答案是……"这类字样。
6. 同一道题内选项之间不得重复、不得含义相同，错误选项应当来自常见误解
   （边界条件弄错、公式记错、概念混淆、操作顺序弄错），不要随便编。
7. 计算题、推演题必须给出足够的初始条件，使答案唯一。
8. 简答题必须要求解释原因、推导过程、比较差异、推演状态或定位错误，不能只是要求背定义。
9. standard_answer 必须与 explanation 的结论一致。
10. explanation 要说明判断依据，不要只写"因为这是本章的重要内容"。
11. 只输出一个 JSON 对象，不要 Markdown，不要代码块，不要任何解释性文字。

输出格式（严格）：
{{
  "questions": [
    {{
      "question_type": "single_choice",
      "stem": "...",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "standard_answer": "A",
      "explanation": "...",
      "assessment_target": "本题考查的具体能力，如：队列长度计算",
      "cognitive_level": "understand | apply | analyze | evaluate | synthesize",
      "knowledge_point_index": 1
    }}
  ]
}}"""
    messages = [{"role": "system", "content": "你只输出符合要求的 JSON 对象，不要任何多余文字。"},
                {"role": "user", "content": prompt}]
    return messages, available


# ------------------------------------------------------------------ parsing + validation


def _normalize_options(raw) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    found = {}
    for key, value in raw.items():
        label = str(key).strip().upper()
        text = str(value or "").strip()
        if label in OPTION_LABELS and text:
            found[label] = text
    return {label: found[label] for label in OPTION_LABELS if label in found}


def _complete_objects(text: str, start: int) -> list[str]:
    """Every complete top-level ``{...}`` in the array beginning at ``start``.

    A truncated answer is the normal case, not the exception: the model's reasoning is billed
    inside the token budget, so the answer can end mid-object. The objects BEFORE the cut are
    complete and perfectly good, and reading them is the difference between "the model produced
    nine questions" and "the model produced nothing".
    """
    found: list[str] = []
    depth = 0
    in_string = False
    escaped = False
    begin: int | None = None
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                begin = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and begin is not None:
                found.append(text[begin:index + 1])
                begin = None
    return found


def parse_questions(raw: str) -> list[dict]:
    """The questions the model returned, salvaging the complete ones from a truncated answer.

    ``raw_decode`` from the FIRST brace: a model that prefixes a sentence and then corrects
    itself leaves a second object behind, and slicing to the LAST brace swallows both. When the
    payload is cut off, the leading questions are recovered by brace matching rather than
    discarded whole.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) >= 3 else text
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    if start < 0:
        return []
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        questions = payload.get("questions")
        return [item for item in questions if isinstance(item, dict)] \
            if isinstance(questions, list) else []
    marker = text.find('"questions"', start)
    array_at = text.find("[", marker if marker >= 0 else start)
    if array_at < 0:
        return []
    salvaged = []
    for chunk in _complete_objects(text, array_at):
        try:
            item = json.loads(chunk)
        except ValueError:
            continue
        if isinstance(item, dict):
            salvaged.append(item)
    if salvaged:
        logger.info("practice.truncated_answer_salvaged questions=%d", len(salvaged))
    return salvaged


def validate_question(raw: dict, available: dict[int, ScopePoint], difficulty: str) -> dict:
    """ONE question, or a ValueError naming why it may never be shown to a learner."""
    qtype = str(raw.get("question_type") or "").strip().lower()
    if qtype not in QUESTION_TYPES:
        raise ValueError("unknown question_type")

    stem = str(raw.get("stem") or "").strip()
    if len(stem) < 8:
        raise ValueError("stem too short")

    explanation = str(raw.get("explanation") or raw.get("analysis") or "").strip()
    if len(explanation) < 4:
        raise ValueError("explanation missing")
    if explanation == stem:
        raise ValueError("explanation repeats the stem")

    try:
        index = int(raw.get("knowledge_point_index"))
    except (TypeError, ValueError):
        raise ValueError("knowledge_point_index missing")
    point = available.get(index)
    if point is None:
        raise ValueError("knowledge_point_index outside the allowed scope")

    options = _normalize_options(raw.get("options"))
    answer = str(raw.get("standard_answer") or "").strip().upper()

    if qtype in (SINGLE_CHOICE, MULTIPLE_CHOICE):
        if len(options) != 4 or len(set(options.values())) != 4:
            raise ValueError("a choice question needs four distinct options")
        if qtype == SINGLE_CHOICE:
            if answer not in options:
                raise ValueError("the answer is not one of the question's own options")
        else:
            letters = sorted(set(answer))
            if not 2 <= len(letters) <= 3 or any(letter not in options for letter in letters):
                raise ValueError("a multiple choice needs two or three of its own options")
            answer = "".join(letters)
    elif qtype == TRUE_FALSE:
        options = dict(TRUE_FALSE_OPTIONS)
        if answer not in options:
            raise ValueError("a true/false answer must be A or B")
    else:
        options = {}
        if len(answer) < 4:
            raise ValueError("a short answer needs a reference answer")

    if any(text == stem for text in options.values()):
        raise ValueError("an option repeats the stem")

    # The ability the question claims to exercise, and at what cognitive level. Both are
    # server-side only; neither is ever rendered. A missing target is refused by the batch's
    # own gate rather than here, so the refusal is reported as a QUALITY verdict.
    target = str(raw.get("assessment_target") or "").strip()[:120]
    level = str(raw.get("cognitive_level") or "").strip().lower()
    if level not in quality.COGNITIVE_LEVELS:
        level = ""

    return {"question_type": qtype, "stem": stem, "options": options,
            "standard_answer": answer, "analysis": explanation,
            "assessment_target": target, "cognitive_level": level,
            "knowledge_point": point, "difficulty": difficulty, "from_model": True}


# ------------------------------------------------------------------ giving up, honestly

# There is deliberately NO deterministic question bank here any more.
#
# There used to be one, and it is what the learner saw. Its items were built from the point's
# TITLE alone — "判断：「循环队列」是本章需要掌握的内容之一。", "请简述「循环队列」的核心含义，
# 并说明它在什么情况下适用。" — because a title is all a deterministic generator has. Those are
# not questions about the knowledge; they are questions about the syllabus, and they are
# answerable without knowing anything. When the model's answer is truncated they are a
# plausible-looking set of ten, which is worse than an error: the learner has no way to tell
# they were not taught anything.
#
# So a set that cannot be completed from the model is a FAILURE the learner is told about, not
# a set padded to size. Padding preserved "a set is always produced" at the cost of producing a
# set worth nothing, and the trade is not worth making.

_BATCH_FAILED_MESSAGE = "这次没有生成出合格的题目，请稍后重试。"


# ------------------------------------------------------------------ persistence helpers


def question_payload(item) -> dict:
    """ONE question as the learner may see it BEFORE answering: never answer, never analysis."""
    try:
        options = json.loads(item.options_json or "{}")
    except (TypeError, ValueError):
        options = {}
    return {
        "id": item.id,
        "question_type": item.question_type,
        "stem": item.stem or "",
        "options": options if isinstance(options, dict) else {},
        "difficulty": item.difficulty or "",
        "chapter": item.knowledge_point_path or "",
        "knowledge_point_id": item.knowledge_point_id or "",
        "knowledge_point_title": item.knowledge_point_name or "",
    }


def _progress_identity(db: DbSession, username: str, course_id: str, raw_id: str) -> dict:
    """How a question's stored knowledge-point id is written into knowledge progress.

    ``kp:<n>`` is a point of the learner's OWN structure, so the write goes through the
    canonical writer's id path (which also derives the point's code). Anything else is a
    published-map code and is written as a code. The row's own id decides; nothing is guessed.
    """
    from models import KnowledgePoint
    value = (raw_id or "").strip()
    if value.startswith(_KP_PREFIX):
        point_id = int(value[len(_KP_PREFIX):] or 0)
        point = (db.query(KnowledgePoint)
                 .filter(KnowledgePoint.id == point_id,
                         KnowledgePoint.username == username,
                         KnowledgePoint.course_id == course_id)
                 .first())
        if point is None:
            logger.warning("practice.structure_point_missing id=%s", point_id)
            return {}
        return {"knowledge_point_id": point.id,
                "knowledge_point_code": getattr(point, "node_key", None)}
    return {"knowledge_point_code": value} if value else {}


def _row_mode(row) -> str:
    raw = str(getattr(row, "generation_mode", None) or "").strip().lower()
    return "ai" if raw in {"ai", "deepseek", "openai", "model"} else "fallback"


def _generation_mode(rows: list) -> str:
    modes = {_row_mode(row) for row in rows}
    if modes == {"ai"}:
        return "ai"
    if modes == {"fallback"}:
        return "fallback"
    return "mixed"


# ------------------------------------------------------------------ generation


def _recently_asked(db: DbSession, user, scope: Scope,
                    limit: int = 60) -> tuple[list[str], list[str], list[str]]:
    """What this learner was ALREADY asked in this course — the material to avoid repeating.

    Read from the learner's own course questions, so the avoidance survives across sessions
    and is not merely a within-batch check. Stems, abilities and fingerprints are all carried:
    the same ability asked again with different words is the failure this is here to stop.
    """
    from models import AIGeneratedQuestion
    rows = (db.query(AIGeneratedQuestion)
            .filter(AIGeneratedQuestion.username == user.username,
                    AIGeneratedQuestion.subject_key == scope.course_id,
                    AIGeneratedQuestion.requirement == REQUIREMENT)
            .order_by(AIGeneratedQuestion.created_at.desc()).limit(limit).all())
    stems = [row.stem for row in rows if row.stem]
    targets = [row.assessment_target for row in rows if getattr(row, "assessment_target", None)]
    marks = [row.question_fingerprint for row in rows
             if getattr(row, "question_fingerprint", None)]
    return stems, targets, marks


def _point_grounding(db: DbSession, user, scope: Scope, limit: int = 1600) -> str:
    """What the learner already HAS about these points, for the questions to lean on.

    Two sources, in the order §5 of the brief names them:

      1. the EXPLANATION the learner read for this point, if they have read one — their own
         words for the topic, and already paid for. Nothing here generates an explanation:
         the generator would make one request buy two.
      2. the passages of their own MATERIALS for this point, through the SAME grounding rule
         the explanation uses, so 学习 and 练习 cannot disagree about which files are this
         point's.

    Both are best-effort. An empty result means "no material to lean on", never a failure — the
    questions are still generated, just from the knowledge point alone.
    """
    from models import KnowledgePointStudyContent

    ids = [int(point.key[len(_KP_PREFIX):]) for point in scope.points
           if point.key.startswith(_KP_PREFIX)]
    if not ids:
        return ""
    chunks = []
    rows = (db.query(KnowledgePointStudyContent)
            .filter(KnowledgePointStudyContent.username == user.username,
                    KnowledgePointStudyContent.knowledge_point_id.in_(ids[:3]))
            .limit(3).all())
    for row in rows:
        title = next((point.title for point in scope.points
                      if point.key == f"{_KP_PREFIX}{row.knowledge_point_id}"), "")
        body = " ".join(str(row.content or "").split())
        if body:
            chunks.append(f"【{title} 的讲解】{body}")
    try:
        from . import study_content as study
        for point_id in ids[:2]:
            title = next((point.title for point in scope.points
                          if point.key == f"{_KP_PREFIX}{point_id}"), "")
            text = study.grounding_text(db, user.username, scope.course_id, point_id,
                                        query=title, limit=800)
            if text:
                chunks.append(text)
    except Exception as exc:  # noqa: BLE001 — grounding is an addition, never a gate
        logger.warning("practice.material_grounding_unavailable %s", type(exc).__name__)
    return "\n".join(chunks)[:limit]


def _assign_slot(pending: tuple[quality.Slot, ...], offset: int,
                 question_type: str) -> quality.Slot | None:
    """The position a returned question fills: the next empty one, else the next of its type.

    Positional first, because the prompt fixes the order. The type scan is the fallback for a
    model that shuffled them, and a question that matches no remaining position is refused
    rather than dropped into an arbitrary one.
    """
    if offset < len(pending) and pending[offset].question_type == question_type:
        return pending[offset]
    return next((slot for slot in pending[offset:] if slot.question_type == question_type), None)


def generate(db: DbSession, user, course_id: str, *, scope: str, goal: str = GOAL_CONSOLIDATE,
             count: int = DEFAULT_COUNT, difficulty: str = DIFFICULTY_ADAPTIVE,
             knowledge_point_id: int | None = None, chapter_id: int | None = None) -> dict:
    """Generate ONE scoped set from a coverage matrix, and open the session that plays it.

    The model is asked, then asked AGAIN for exactly the positions that are still empty — the
    questions that passed are never regenerated, so a retry spends the learner's credits only
    on what is missing. A set that cannot be completed is refused with a message rather than
    padded to size (see the note above ``_BATCH_FAILED_MESSAGE``).
    """
    from fastapi import HTTPException

    from models import AIGeneratedQuestion, AIQuestionAttempt

    from .ai import execute_course_ai
    from .context import build_course_context

    if scope not in SCOPES:
        raise PracticeError("未知的练习范围。", 400)
    goal = goal if goal in GOALS else GOAL_CONSOLIDATE
    count = count if count in COUNTS else DEFAULT_COUNT
    difficulty = difficulty if difficulty in DIFFICULTIES else DIFFICULTY_ADAPTIVE

    resolved = resolve_scope(db, user.username, course_id, scope=scope,
                             knowledge_point_id=knowledge_point_id, chapter_id=chapter_id)
    context = adaptive_context(db, user, resolved)
    difficulty = choose_difficulty(difficulty, context)

    plan, adaptive_note = quality.reweight(quality.set_plan(count),
                                           context.get("level_accuracy") or {})
    point_titles = tuple(point.title for point in resolved.points if point.title)
    known_stems, known_targets, known_marks = _recently_asked(db, user, resolved)
    batch = quality.Batch(count, point_titles=point_titles,
                          avoid_stems=tuple(known_stems), avoid_targets=tuple(known_targets),
                          avoid_fingerprints=tuple(known_marks))
    grounding = _point_grounding(db, user, resolved)
    learning_context = build_course_context(
        user, course_id=resolved.course_id,
        chapter_id=(chapter_id or resolved.chapters[0]["id"]),
        knowledge_point_id=knowledge_point_id)

    retries = 0
    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        if batch.full():
            break
        offset = len(batch.questions)
        pending = plan[offset:]
        if not pending:
            break
        if attempt:
            retries += 1
        messages, available = build_prompt(
            resolved, goal=goal, difficulty=difficulty, slots=pending,
            avoid_stems=list(known_stems) + list(batch.stems) + batch.rejected_stems(),
            avoid_targets=list(known_targets) + list(batch.targets),
            grounding=grounding)
        try:
            result = execute_course_ai(
                db, user, "question.generate", messages,
                learning_context=learning_context,
                max_tokens=_TOKEN_BUDGET.get(count, 12000))
        except HTTPException as exc:
            if exc.status_code in (403, 429):
                raise                      # an entitlement or budget decision is an ANSWER
            logger.warning("practice.generation_model_unavailable status=%s attempt=%d",
                           exc.status_code, attempt)
            break
        except Exception as exc:  # noqa: BLE001 — any other failure ends generation, never raises
            logger.warning("practice.generation_failed %s attempt=%d",
                           type(exc).__name__, attempt)
            break

        for raw in parse_questions(result.content):
            if batch.full():
                break
            try:
                question = validate_question(raw, available, difficulty)
            except ValueError as exc:
                # Counted, not merely logged: a schema rejection is still a question the model
                # produced that the learner will never see, and a batch that fails should say
                # whether it failed on shape or on content.
                batch.reject("low_quality", f"schema:{exc}", str(raw.get("stem") or ""))
                logger.info("practice.question_rejected reason=%s", exc)
                continue
            slot = _assign_slot(pending, len(batch.questions) - offset, question["question_type"])
            if slot is None:
                batch.reject("low_quality", "no_matching_slot", question["stem"])
                continue
            if not question["cognitive_level"]:
                question["cognitive_level"] = slot.cognitive_level
            try:
                batch.add(question)
            except quality.Rejected:
                continue

    if not batch.full() or not batch.coverage_ok():
        report = batch.finish("failed", retry_count=retries, adaptive=adaptive_note)
        logger.warning("practice.generation_quality_failure %s",
                       json.dumps(report.metric(), ensure_ascii=False))
        raise PracticeError(_BATCH_FAILED_MESSAGE, 503)
    report = batch.finish("accepted", retry_count=retries, adaptive=adaptive_note)
    logger.info("practice.generation_quality %s",
                json.dumps(report.metric(), ensure_ascii=False))

    accepted = batch.questions
    rows = []
    for question in accepted:
        point: ScopePoint = question["knowledge_point"]
        rows.append(AIGeneratedQuestion(
            username=user.username,
            subject_key=resolved.course_id,
            subject_name=resolved.course_name,
            knowledge_point_id=point.key,
            knowledge_point_name=point.title or None,
            knowledge_point_path=point.chapter or (resolved.chapters[0]["title"] if resolved.chapters else None),
            question_type=question["question_type"],
            stem=question["stem"],
            options_json=json.dumps(question["options"], ensure_ascii=False),
            standard_answer=question["standard_answer"],
            analysis=question["analysis"],
            difficulty=DIFFICULTY_LABELS[difficulty],
            requirement=REQUIREMENT,
            generation_mode="ai",
            quality_status="accepted",
            assessment_target=question.get("assessment_target") or None,
            cognitive_level=question.get("cognitive_level") or None,
            question_fingerprint=quality.fingerprint(
                question["stem"], drop=(point.title or "")),
        ))
    db.add_all(rows)
    db.flush()

    attempt = AIQuestionAttempt(
        username=user.username, mode="course_learning",
        subject_key=resolved.course_id, subject_name=resolved.course_name,
        knowledge_point_id=(rows[0].knowledge_point_id if len(resolved.points) == 1 else None),
        knowledge_point_name=(rows[0].knowledge_point_name if len(resolved.points) == 1 else None),
        knowledge_point_path=(rows[0].knowledge_point_path if len(resolved.points) == 1 else None),
        question_ids_json=json.dumps([row.id for row in rows]),
        total_questions=len(rows),
        status="in_progress",
        result_json=json.dumps({"results": []}, ensure_ascii=False),
    )
    db.add(attempt)
    db.commit()
    for row in rows:
        db.refresh(row)
    db.refresh(attempt)

    return {
        "course_id": resolved.course_id,
        "scope": resolved.kind,
        "scope_label": resolved.label,
        "scope_source": resolved.source,
        "goal": goal,
        "difficulty": difficulty,
        "difficulty_label": DIFFICULTY_LABELS[difficulty],
        "generation_mode": _generation_mode(rows),
        "adaptive": {"has_history": context["has_history"],
                     "review_due": context["review_due"],
                     "wrong_count": context["wrong_count"]},
        "quality": report.metric(),
        "attempt_id": attempt.id,
        "total": len(rows),
        "questions": [question_payload(row) for row in rows],
    }


# ------------------------------------------------------------------ playing


def _load_attempt(db: DbSession, user, attempt_id: int):
    from models import AIQuestionAttempt
    attempt = (db.query(AIQuestionAttempt)
               .filter(AIQuestionAttempt.id == attempt_id,
                       AIQuestionAttempt.username == user.username,
                       AIQuestionAttempt.mode == "course_learning")
               .first())
    if attempt is None:
        raise PracticeError("这次练习不存在。", 404)
    return attempt


def load_attempt(db: DbSession, user, attempt_id: int):
    """The caller's own course-practice session, or a refusal."""
    return _load_attempt(db, user, attempt_id)


def _attempt_questions(db: DbSession, user, attempt) -> list:
    from models import AIGeneratedQuestion
    try:
        ids = [int(value) for value in json.loads(attempt.question_ids_json or "[]")]
    except (TypeError, ValueError):
        ids = []
    if not ids:
        return []
    rows = (db.query(AIGeneratedQuestion)
            .filter(AIGeneratedQuestion.id.in_(ids),
                    AIGeneratedQuestion.username == user.username)
            .all())
    by_id = {row.id: row for row in rows}
    return [by_id[qid] for qid in ids if qid in by_id]


def _results(attempt) -> list[dict]:
    """The verdicts stored on the attempt, in either shape the product has written.

    A set writes ``{"results": [...]}``; the older one-question submit wrote the single verdict
    flat. Both are real rows a learner's history can point at, so both are read — a verdict that
    exists but cannot be shown would make a finished set look unanswered.
    """
    try:
        data = json.loads(attempt.result_json or "{}")
    except (TypeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("results")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    if data.get("question_id") is not None:
        return [data]
    return []


def session_view(db: DbSession, user, attempt, *, include_verdicts: bool = True) -> dict:
    """The session as the page renders it — the answer to an UNANSWERED question is never sent."""
    questions = _attempt_questions(db, user, attempt)
    results = {int(item["question_id"]): item for item in _results(attempt)
               if item.get("question_id") is not None}
    viewed = []
    for question in questions:
        payload = question_payload(question)
        verdict = results.get(question.id) if include_verdicts else None
        payload["answered"] = verdict is not None
        if verdict is not None:
            # The learner has already submitted this one, so its verdict is theirs to see.
            payload["result"] = _feedback(verdict, question)
        viewed.append(payload)
    return {
        "attempt_id": attempt.id,
        "course_id": attempt.subject_key,
        "status": attempt.status,
        "total": attempt.total_questions or len(viewed),
        "answered": len(results),
        "correct_count": sum(1 for item in results.values() if item.get("correct") is True),
        "questions": viewed,
    }


def latest_open_session(db: DbSession, user, course_id: str):
    """The course's newest unfinished set — what a page reload resumes."""
    from models import AIQuestionAttempt
    return (db.query(AIQuestionAttempt)
            .filter(AIQuestionAttempt.username == user.username,
                    AIQuestionAttempt.mode == "course_learning",
                    AIQuestionAttempt.subject_key == normalize_course_id(course_id),
                    AIQuestionAttempt.status == "in_progress")
            .order_by(AIQuestionAttempt.created_at.desc())
            .first())


def _normalize_answer(question_type: str, raw) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if question_type == SHORT_ANSWER:
        return text[:4000]
    return text.upper().replace(" ", "").replace(",", "").replace("，", "")[:8]


def _graded(question_type: str, answer: str, standard: str) -> bool | None:
    """The server's verdict. A short answer is never auto-scored — the learner reviews it."""
    if question_type == SHORT_ANSWER:
        return None
    given = str(answer or "").strip().upper()
    if not given:
        return None
    if question_type == MULTIPLE_CHOICE:
        return sorted(set(given)) == sorted(set(str(standard or "").strip().upper()))
    return given == str(standard or "").strip().upper()


def _feedback(item: dict, question) -> dict:
    return {
        "question_id": question.id,
        "user_answer": item.get("user_answer") or "",
        "correct": item.get("correct"),
        "judge": item.get("judge") or "",
        "standard_answer": item.get("standard_answer") or "",
        "analysis": item.get("analysis") or "",
        "knowledge_point_title": question.knowledge_point_name or "",
    }


def answer(db: DbSession, user, attempt, question_id: int, raw_answer: str) -> dict:
    """Grade ONE question inside the set and, on the last one, close the set.

    Answering a question that is already answered returns that question's stored verdict: it
    never re-grades, and it never writes a second fact for the same submission.
    """
    if (attempt.status or "") != "in_progress":
        raise PracticeError("这次练习已经结束。", 409)
    questions = _attempt_questions(db, user, attempt)
    question = next((row for row in questions if row.id == question_id), None)
    if question is None:
        raise PracticeError("这道题不属于本次练习。", 404)

    results = _results(attempt)
    existing = next((item for item in results
                     if int(item.get("question_id", 0)) == question_id), None)
    if existing is not None:
        return {"created": False, "question_id": question_id, "attempt_id": attempt.id,
                "feedback": _feedback(existing, question),
                "session": session_view(db, user, attempt)}

    answer_text = _normalize_answer(question.question_type, raw_answer)
    if not answer_text:
        raise PracticeError("请先作答再提交。", 400)

    correct = _graded(question.question_type, answer_text, question.standard_answer or "")
    judge = "self_review" if correct is None else ("correct" if correct else "incorrect")
    item = {
        "question_id": question.id,
        "user_answer": answer_text,
        "standard_answer": question.standard_answer or "",
        "analysis": question.analysis or "",
        "correct": correct,
        "judge": judge,
        "question_type": question.question_type,
        "generation_mode": _row_mode(question),
        # The ability this answer was about. Server-side: it decides which ability the NEXT
        # set should ask more of, and is never shown to the learner.
        "cognitive_level": getattr(question, "cognitive_level", None)
        or _TYPE_LEVEL.get(question.question_type, ""),
        "assessment_target": getattr(question, "assessment_target", None) or "",
    }
    results.append(item)

    try:
        answers = json.loads(attempt.answers_json or "{}")
    except (TypeError, ValueError):
        answers = {}
    if not isinstance(answers, dict):
        answers = {}
    answers[str(question.id)] = answer_text
    attempt.answers_json = json.dumps(answers, ensure_ascii=False)
    attempt.result_json = json.dumps({"results": results}, ensure_ascii=False)
    db.flush()

    if len(results) >= (attempt.total_questions or len(questions)):
        _settle(db, user, attempt, questions, results)
    else:
        db.commit()

    return {"created": True, "question_id": question.id, "attempt_id": attempt.id,
            "feedback": _feedback(item, question),
            "session": session_view(db, user, attempt)}


# ------------------------------------------------------------------ write-back


def _settle(db: DbSession, user, attempt, questions: list, results: list[dict]) -> None:
    """Close the set and write its facts through the paths that already exist."""
    from models import LearningRecord, utc_now

    from .knowledge import apply_knowledge_change, commit_and_emit

    by_id = {row.id: row for row in questions}
    transitions = []
    for item in results:
        question = by_id.get(int(item.get("question_id", 0)))
        if question is None:
            continue
        identity = _progress_identity(db, user.username, attempt.subject_key,
                                      question.knowledge_point_id or "")
        correct = item.get("correct")
        if identity:
            transition = apply_knowledge_change(
                db, username=user.username, course_id=attempt.subject_key,
                event_type=("question_correct" if correct else "question_incorrect")
                if correct is not None else "question_attempt",
                knowledge_point_title=question.knowledge_point_name or None,
                delta=15 if correct else (-8 if correct is False else 0),
                source_type="course_learning_practice",
                set_system_suggested=True, protect_user_confirmed=True,
                target_user_id=user.id, **identity)
            if transition is not None:
                transitions.append(transition)
        db.add(LearningRecord(
            user_id=user.id, subject=attempt.subject_key, record_type="practice",
            question=question.stem or "",
            answer=json.dumps(item, ensure_ascii=False),
            tags=json.dumps(["course_learning", question.knowledge_point_name or ""],
                            ensure_ascii=False),
            review_status="pending", is_deleted=False))

    graded = [item for item in results if item.get("correct") is not None]
    correct_count = sum(1 for item in graded if item["correct"])
    attempt.correct_count = correct_count
    attempt.accuracy = round(correct_count / len(graded) * 100.0, 1) if graded else None
    attempt.status = "submitted"
    attempt.submitted_at = utc_now()
    db.commit()

    for transition in transitions:
        try:
            commit_and_emit(db, transition)
        except Exception as exc:  # noqa: BLE001 — the event is an addition, never a gate
            logger.warning("practice.transition_emit_failed %s", type(exc).__name__)

    try:
        from database import SessionLocal
        from data_plane import emitter as _dp_emitter
        _dp_emitter.best_effort_emit(
            _dp_emitter.build_course_practice_events_batch(attempt, questions, results, user),
            SessionLocal)
    except Exception as exc:  # noqa: BLE001
        logger.warning("practice.data_plane_emit_failed %s", type(exc).__name__)

    try:
        from learning.practice.adapters import course as _practice_course
        _practice_course.mirror_ai_question_attempt(db, user, attempt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("practice.mirror_failed %s", type(exc).__name__)


def history(db: DbSession, user, course_id: str, limit: int = 20) -> list[dict]:
    """Finished sets for this course, newest first — a SET, not one row per question."""
    from models import AIQuestionAttempt
    rows = (db.query(AIQuestionAttempt)
            .filter(AIQuestionAttempt.username == user.username,
                    AIQuestionAttempt.mode == "course_learning",
                    AIQuestionAttempt.subject_key == normalize_course_id(course_id),
                    AIQuestionAttempt.status == "submitted")
            .order_by(AIQuestionAttempt.submitted_at.desc())
            .limit(limit).all())
    items = []
    for attempt in rows:
        questions = _attempt_questions(db, user, attempt)
        first = questions[0] if questions else None
        items.append({
            "session_id": attempt.id,
            "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
            "chapter": (first.knowledge_point_path if first else "") or "",
            "knowledge_point_title": (first.knowledge_point_name if first else "") or "",
            "total": attempt.total_questions or len(questions),
            "correct_count": attempt.correct_count or 0,
        })
    return items
