"""Whether a generated practice question is worth showing — the gates, one rule at a time.

WHY THIS FILE EXISTS SEPARATELY FROM THE PRACTICE CONTRACT TESTS
----------------------------------------------------------------
``test_course_practice_redesign.py`` asks "does the set behave like a set". This asks the
question a learner asked in production: the set behaved exactly as specified and taught nothing.
A learner requested ten questions on 「循环队列」 and got ten restatements of the point's title,
because the model's answer had been truncated and a local bank of title-derived questions filled
the set. Every question in it was structurally valid.

So these tests are mostly about REFUSALS. Each one names a shape that must never reach a
learner, and asserts the refusal rather than the acceptance — a gate that stops working is
otherwise invisible, since the set still looks like a set.

The pure gates are tested without a database or a provider: they are deterministic functions of
the text, and a rule whose reason cannot be stated without running a model is a rule that cannot
be explained to a maintainer.
"""
import itertools
import json
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from conftest import grant_unified_tier, register_and_login
import models
from learning.spaces.course_learning import knowledge_structure
from learning.spaces.course_learning import question_quality as quality
from learning.spaces.course_learning.practice import parse_questions

COURSE = "数据结构"
CHAPTERS = [{"title": "线性结构", "points": [{"title": "线性表的顺序存储"}]}]

# THE PERMANENT REGRESSION CASE. 「循环队列」 is the knowledge point the production report was
# written about, and the sentences below are quoted from it verbatim. They stay in this file as
# the fixture every quality rule is measured against — a rule that stops refusing them is a
# regression, not a preference.
POINT = "循环队列"
_MATRIX_RE = re.compile(r'第 (\d+) 题：question_type 必须是 "(\w+)"')

# The two stems the learner actually received, in their own words. Kept as constants so a
# regression names the report rather than a paraphrase of it.
REPORT_META_STEM = f"判断：「{POINT}」是本章需要掌握的内容之一。"
REPORT_GENERIC_STEM = f"请简述「{POINT}」的核心含义，并说明它在什么情况下适用。"


def _question(**overrides) -> dict:
    base = {
        "question_type": "single_choice",
        "stem": "长度为 n 的顺序表在表尾追加一个元素，需要移动的元素个数是（  ）",
        "options": {"A": "0", "B": "1", "C": "n-1", "D": "n"},
        "standard_answer": "A",
        "analysis": "表尾之后没有元素，追加不需要移动任何已有元素。",
        "assessment_target": "表尾追加的移动代价",
    }
    base.update(overrides)
    return base


def _batch(count=3, **kwargs) -> quality.Batch:
    return quality.Batch(count, point_titles=(POINT,), **kwargs)


# ---------------------------------------------------------------- 1-2. duplication


def test_an_exact_duplicate_stem_is_rejected():
    batch = _batch()
    batch.add(_question())
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(assessment_target="另一个能力"))
    assert rejected.value.kind == "duplicate"
    assert rejected.value.reason == "exact_stem"
    assert batch.report.duplicate_rejected == 1


def test_a_reworded_duplicate_is_rejected():
    """A question that only rewords another is the same question, and the second is refused."""
    batch = _batch()
    batch.add(_question(stem="顺序表在表尾追加一个元素需要移动多少个元素？"))
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem="顺序表在表尾追加一个元素，需要移动的元素个数是多少？",
                            assessment_target="另一个能力"))
    assert rejected.value.kind == "duplicate"
    assert rejected.value.reason in {"paraphrase_stem", "exact_stem"}


def test_the_definition_pair_from_the_report_does_not_both_ship():
    """§7's worked example. Character overlap cannot see this pair as the same question — the
    two sentences share almost no characters — so what refuses the second is that a set may ask
    for a point's definition ONCE."""
    batch = _batch(count=10)
    batch.add(_question(stem=f"{POINT}的核心含义是什么？", assessment_target="概念定义"))
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=f"请说明{POINT}的基本含义。", assessment_target="含义说明"))
    assert rejected.value.kind == "low_quality"


def test_a_repeat_of_a_previously_asked_question_is_counted_apart_from_an_in_batch_repeat():
    """"Asked this twice just now" and "asked this learner before" are different failures."""
    batch = _batch(count=10,
                   avoid_stems=("顺序表在表尾追加一个元素，需要移动的元素个数是多少？",))
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem="顺序表在表尾追加一个元素需要移动多少个元素？"))
    assert rejected.value.reason == "recently_asked_stem"
    assert batch.report.recent_duplicate_rejected == 1
    assert batch.report.duplicate_rejected == 1


def test_questions_that_only_share_a_knowledge_point_are_not_duplicates():
    """The point's own name must not make every question look like every other question."""
    batch = _batch()
    batch.add(_question(stem=f"{POINT}中 front 指向队头元素时，队满条件如何表示？"))
    batch.add(_question(stem=f"{POINT}的数组容量为 MaxSize 时，有效元素最多有多少个？",
                        assessment_target="有效容量计算",
                        options={"A": "MaxSize 个", "B": "MaxSize-1 个",
                                 "C": "MaxSize+1 个", "D": "0 个"},
                        standard_answer="B"))
    assert len(batch.questions) == 2


def test_options_that_differ_only_by_an_operator_are_still_distinct():
    """``MaxSize-1`` and ``MaxSize+1`` are different answers; only punctuation may be ignored."""
    batch = _batch()
    batch.add(_question(stem="采用牺牲一个存储单元的方法时，该队列最多能存放多少个元素？",
                        options={"A": "MaxSize 个", "B": "MaxSize-1 个",
                                 "C": "MaxSize+1 个", "D": "0 个"},
                        standard_answer="B"))
    assert len(batch.questions) == 1


# ---------------------------------------------------------------- 3. ability reuse


def test_one_ability_may_not_be_asked_a_third_time():
    batch = _batch(count=10)
    for index in range(quality.MAX_TARGET_REUSE):
        batch.add(_distinct(index, "队满条件的判断"))
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_distinct(quality.MAX_TARGET_REUSE, "队满条件的判断"))
    assert rejected.value.reason == "assessment_target_reused"


def test_an_ability_named_after_the_point_is_not_an_ability():
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(assessment_target=POINT))
    assert rejected.value.reason == "assessment_target_missing_or_generic"


def test_a_question_with_no_declared_ability_is_rejected():
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(assessment_target=""))
    assert rejected.value.reason == "assessment_target_missing_or_generic"


# ---------------------------------------------------------------- 4-6. low information


@pytest.mark.parametrize("stem", [
    REPORT_META_STEM,                                    # the report, verbatim
    f"「{POINT}」属于本课程的知识点。",
    f"学习「{POINT}」有助于理解后面的内容。",
    f"「{POINT}」是本章的重要内容。",
])
def test_a_claim_about_the_syllabus_is_not_a_question(stem):
    """The exact sentences the production report quoted, and the family they belong to."""
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=stem, question_type="true_false",
                            options={"A": "正确", "B": "错误"}, standard_answer="A",
                            analysis="因为它属于本章知识点。"))
    assert rejected.value.kind == "low_quality"
    where, _, rule = rejected.value.reason.partition(":")
    assert where in {"stem", "analysis"}
    assert rule in {"syllabus_membership", "study_advice"}


def test_a_definition_question_is_allowed_once_and_then_refused(monkeypatch):
    """A definition question is right ONCE for a point whose knowledge is a definition."""
    monkeypatch.setattr(quality, "_DEFINITION_RE", re.compile(r"含义是什么"))
    batch = _batch(count=10)
    batch.add(_question(stem=f"{POINT}的核心含义是什么？", assessment_target="概念定义"))
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=f"{POINT}的队满条件含义是什么？",
                            assessment_target="条件含义"))
    assert rejected.value.reason == "definition_quota"


def test_the_template_from_the_report_is_refused_outright():
    """§9 lists this exact sentence. It is refused even as the FIRST question, because the
    angle it asks for ("核心含义…适用情况") is the one that produces ten of the same thing."""
    batch = _batch(count=10)
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=REPORT_GENERIC_STEM,
                            question_type="short_answer", options={},
                            standard_answer="先说明定义，再说明适用条件。",
                            analysis="回答应包含定义与适用条件。",
                            assessment_target="概念定义"))
    assert rejected.value.reason == "stem:generic_explain"


def test_the_report_template_cannot_pose_as_a_whole_short_answer_block():
    """The production set carried this stem TWICE — as a short answer and, reworded, again.
    Neither the repeat nor a reworded repeat of it may enter a set."""
    batch = _batch(count=10)
    variants = [
        REPORT_GENERIC_STEM,
        REPORT_GENERIC_STEM,
        f"请说明「{POINT}」的核心含义和适用情况。",
    ]
    for index, stem in enumerate(variants):
        with pytest.raises(quality.Rejected) as rejected:
            batch.add(_question(stem=stem, question_type="short_answer", options={},
                                standard_answer="先说明定义，再说明适用条件。",
                                analysis="回答应包含定义与适用条件。",
                                assessment_target=f"概念定义 {index}"))
        assert rejected.value.kind == "low_quality"
    assert batch.questions == []


def test_an_opinion_request_is_refused():
    batch = _batch(count=10)
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=f"请谈谈你对「{POINT}」的理解。",
                            question_type="short_answer", options={},
                            standard_answer="应当说出自己的理解。",
                            analysis="回答要有自己的话。",
                            assessment_target="理解表述"))
    assert rejected.value.reason == "stem:generic_explain"


def test_the_generic_definition_template_itself_is_refused_at_any_quota():
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=f"请简述「{POINT}」的核心含义，并说明它在什么情况下适用。",
                            question_type="short_answer", options={},
                            standard_answer="先说明定义，再说明适用条件。",
                            analysis="回答应包含定义与适用条件。",
                            assessment_target="概念定义"))
    assert rejected.value.reason == "stem:generic_explain"


def test_a_bare_recitation_is_refused_but_the_same_verb_with_an_angle_is_not():
    """Banning "简述" outright would throw away real questions; the ANGLE is what matters."""
    batch = _batch(count=10)
    with pytest.raises(quality.Rejected):
        batch.add(_question(stem=f"请简述「{POINT}」。", question_type="short_answer",
                            options={}, standard_answer="说明它的要点。",
                            analysis="应说明要点。", assessment_target="要点罗列"))
    batch.add(_question(stem=f"请说明「{POINT}」中取模运算为什么能实现指针回绕。",
                        question_type="short_answer", options={},
                        standard_answer="因为取模把越界的下标折回数组开头。",
                        analysis="取模保证下标始终落在数组范围内。",
                        assessment_target="取模运算的作用"))


def test_a_flat_true_false_is_refused_and_a_real_proposition_is_kept():
    batch = _batch(count=10)
    with pytest.raises(quality.Rejected):
        batch.add(_question(stem=f"「{POINT}」需要学习。", question_type="true_false",
                            options={"A": "正确", "B": "错误"}, standard_answer="A",
                            analysis="它属于本章内容。", assessment_target="学习必要性"))
    batch.add(_question(
        stem="采用牺牲一个存储单元区分队空与队满时，队满条件是 (rear+1)%MaxSize == front。",
        question_type="true_false", options={"A": "正确", "B": "错误"}, standard_answer="A",
        analysis="牺牲一个单元后队满与队空的条件不再相同。",
        assessment_target="队满条件判断"))


def test_a_short_answer_without_an_angle_is_refused():
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=f"请介绍「{POINT}」。", question_type="short_answer",
                            options={}, standard_answer="介绍它的内容。",
                            analysis="应当介绍它的内容。", assessment_target="内容介绍"))
    assert rejected.value.kind == "low_quality"


# ---------------------------------------------------------------- 7-8. choice integrity


def test_two_options_that_say_the_same_thing_are_refused():
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(options={"A": "MaxSize-1", "B": " MaxSize - 1 ",
                                     "C": "MaxSize", "D": "MaxSize+1"},
                            standard_answer="A"))
    assert rejected.value.reason == "options_not_distinct"


def test_a_catch_all_option_is_refused():
    """An option that answers for the learner measures nothing."""
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(options={"A": "MaxSize 个", "B": "MaxSize-1 个",
                                     "C": "以上都对", "D": "MaxSize+1 个"},
                            standard_answer="A"))
    assert rejected.value.reason == "options_lazy_catch_all"


def test_an_option_that_repeats_the_stem_is_refused():
    stem = "循环队列中元素个数应如何计算？"
    batch = _batch()
    with pytest.raises(quality.Rejected) as rejected:
        batch.add(_question(stem=stem, options={"A": stem, "B": "(rear-front+MaxSize)%MaxSize",
                                                "C": "rear-front", "D": "MaxSize-front"},
                            standard_answer="B"))
    assert rejected.value.reason in {"option_repeats_stem", "options_not_distinct"}


def test_an_answer_that_is_not_one_of_the_options_is_refused_by_the_schema():
    """The schema gate runs before the quality gate, and this is what it is for."""
    from learning.spaces.course_learning.practice import validate_question
    point = SimpleNamespace(key="kp:1", title=POINT, chapter="栈和队列", description="")
    with pytest.raises(ValueError):
        validate_question({"question_type": "single_choice", "stem": "一个足够长的题干在这里（  ）",
                           "options": {"A": "甲", "B": "乙", "C": "丙", "D": "丁"},
                           "standard_answer": "Z", "explanation": "一句足够长的解析。",
                           "assessment_target": "某个能力", "knowledge_point_index": 1},
                          {1: point}, "medium")


# ---------------------------------------------------------------- 9-11. coverage


# Enough genuinely different questions to fill the largest set from a single ability.
_DISTINCT_STEMS = [
    "顺序表在表尾追加一个元素需要移动多少个元素？（  ）",
    "顺序表删除表头元素需要移动多少个元素？（  ）",
    "下标定位读取顺序表元素的时间复杂度是多少？（  ）",
    "顺序表插入元素时元素为什么要自后向前移动？（  ）",
    "单链表删除结点后为什么要释放内存？（  ）",
    "双链表插入结点要修改几处指针？（  ）",
    "循环链表从任意结点能否遍历全表？（  ）",
    "顺序表扩容时为什么要重新申请空间？（  ）",
    "单链表求表长为什么需要遍历？（  ）",
    "顺序表与链表在存储密度上有什么区别？（  ）",
]


def _distinct(index: int, target: str) -> dict:
    return _question(stem=_DISTINCT_STEMS[index],
                     options={"A": f"选项甲{index}", "B": f"选项乙{index}",
                              "C": f"选项丙{index}", "D": f"选项丁{index}"},
                     standard_answer="A", assessment_target=target)


@pytest.mark.parametrize("count,minimum", [(3, 2), (5, 3), (10, 5)])
def test_one_ability_can_never_fill_a_set(count, minimum):
    """Ten questions that all claim ONE ability is the failure the coverage rule exists for.

    It is refused while the set is being BUILT rather than after the fact: the third question
    claiming an ability already asked twice is rejected, which is what makes the coverage
    threshold below a consequence of the build rather than a hope about the model.
    """
    assert quality.MIN_UNIQUE_TARGETS[count] == minimum
    batch = _batch(count=count)
    accepted = 0
    for index in range(count):
        try:
            batch.add(_distinct(index, "队满条件的判断"))
            accepted += 1
        except quality.Rejected as rejected:
            assert rejected.reason == "assessment_target_reused"
    assert accepted == quality.MAX_TARGET_REUSE
    assert batch.unique_targets() == 1


@pytest.mark.parametrize("count,minimum", [(3, 2), (5, 3), (10, 5)])
def test_the_reuse_cap_guarantees_the_coverage_threshold(count, minimum):
    """Whatever fills a set, the distinct abilities cannot fall below the threshold."""
    assert quality.MAX_TARGET_REUSE * minimum >= count
    batch = _batch(count=count)
    batch.targets = [f"能力 {index}" for index in range(minimum)]
    assert batch.unique_targets() == minimum
    assert batch.coverage_ok()


def test_coverage_is_reported_as_a_failure_when_it_is_short():
    batch = _batch(count=10)
    batch.targets = ["能力 0", "能力 1"]
    assert batch.unique_targets() == 2
    assert not batch.coverage_ok()


@pytest.mark.parametrize("count", [3, 5, 10])
def test_a_batch_that_names_enough_abilities_fills(count):
    batch = _batch(count=count)
    minimum = quality.MIN_UNIQUE_TARGETS[count]
    for index in range(count):
        batch.add(_distinct(index, f"能力 {index % minimum}"))
    assert batch.full()
    assert batch.coverage_ok()


@pytest.mark.parametrize("count", [3, 5, 10])
def test_the_plan_keeps_the_question_type_mix_the_product_promises(count):
    from learning.spaces.course_learning.practice import _TYPE_MIX
    assert tuple(slot.question_type for slot in quality.set_plan(count)) == _TYPE_MIX[count]


def test_every_plan_position_asks_for_an_ability_not_a_title():
    for count in (3, 5, 10):
        plan = quality.set_plan(count)
        assert len({slot.role for slot in plan}) >= quality.MIN_UNIQUE_TARGETS[count] - 1
        assert all(slot.cognitive_level in quality.COGNITIVE_LEVELS for slot in plan)


def test_the_adaptive_nudge_moves_one_slot_from_a_strong_ability_to_a_weak_one():
    plan = quality.set_plan(10)
    adjusted, note = quality.reweight(plan, {quality.UNDERSTAND: 1.0, quality.APPLY: 0.1})
    assert note["reweighted"] is True
    assert len(adjusted) == len(plan)
    # The visible contract is unchanged: only WHAT a position asks for moves.
    assert tuple(slot.question_type for slot in adjusted) == \
        tuple(slot.question_type for slot in plan)
    assert sum(slot.cognitive_level == quality.APPLY for slot in adjusted) > \
        sum(slot.cognitive_level == quality.APPLY for slot in plan)


def test_the_adaptive_nudge_does_nothing_without_evidence():
    plan = quality.set_plan(10)
    assert quality.reweight(plan, {})[1]["reweighted"] is False
    assert quality.reweight(plan, {quality.UNDERSTAND: 0.5})[1]["reweighted"] is False


# ---------------------------------------------------------------- truncation


def test_a_truncated_answer_still_yields_its_complete_questions():
    """Reasoning is billed inside ``max_tokens``, so a cut-off answer is the normal case."""
    truncated = (
        '{"questions": ['
        '{"question_type": "single_choice", "stem": "第一题？", "options": {"A": "甲", "B": "乙", '
        '"C": "丙", "D": "丁"}, "standard_answer": "A", "explanation": "解析一", '
        '"assessment_target": "能力一", "knowledge_point_index": 1},'
        '{"question_type": "single_choice", "stem": "第二题？", "options": {"A": "甲", "B": "乙", '
        '"C": "丙", "D": "丁"}, "standard_answer": "B", "explanation": "解析二", '
        '"assessment_target": "能力二", "knowledge_point_index": 1},'
        '{"question_type": "true_false", "stem": "第三题'
    )
    salvaged = parse_questions(truncated)
    assert [item["stem"] for item in salvaged] == ["第一题？", "第二题？"]


def test_a_fenced_answer_is_still_read():
    fenced = '```json\n{"questions": [{"stem": "有围栏的题"}]}\n```'
    assert [item["stem"] for item in parse_questions(fenced)] == ["有围栏的题"]


# ---------------------------------------------------------------- HTTP-level gates


class Learner:
    def __init__(self, client: TestClient, db, username: str):
        self.client = client
        self.db = db
        self.username = username


_LEARNER_SEQ = itertools.count(1)


@pytest.fixture
def learner(client: TestClient, db_session, monkeypatch):
    username = f"pq{next(_LEARNER_SEQ)}"
    register_and_login(client, username)
    response = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": [COURSE], "material_types": ["课件"],
        "onboarding_completed": True,
    })
    assert response.status_code == 200, response.text
    user = db_session.query(models.User).filter(models.User.username == username).one()
    structure = knowledge_structure.create_draft(
        db_session, user, COURSE, source_mode="ai_generated", chapters=CHAPTERS)
    knowledge_structure.confirm(db_session, user, COURSE, structure.id)
    grant_unified_tier(db_session, username, "standard")
    return Learner(client, db_session, username)


_BY_TYPE = {
    "single_choice": [
        {"stem": "线性表的顺序存储结构最适合哪种访问方式？（  ）",
         "options": {"A": "按下标随机访问", "B": "只允许尾部访问", "C": "不支持元素定位",
                     "D": "只能反向访问"},
         "standard_answer": "A", "explanation": "顺序存储通过基址和下标直接计算元素位置。"},
        {"stem": "长度为 n 的顺序表在表尾追加一个元素，需要移动的元素个数是（  ）",
         "options": {"A": "0", "B": "1", "C": "n-1", "D": "n"},
         "standard_answer": "A", "explanation": "表尾之后没有元素，追加不需要移动已有元素。"},
        {"stem": "顺序表删除表头元素之后，表中剩余元素的处理方式是（  ）",
         "options": {"A": "整体前移一位", "B": "保持原位留出空洞", "C": "整体后移一位",
                     "D": "重新申请空间"},
         "standard_answer": "A", "explanation": "顺序存储要求元素相邻，删除表头后需要前移。"},
        {"stem": "单链表中已知指向某结点的指针 p，删除 p 的后继需要的操作次数是（  ）",
         "options": {"A": "常数次", "B": "与表长成正比", "C": "与表长成对数", "D": "与表长成平方"},
         "standard_answer": "A", "explanation": "p 已给出后继地址，改一处指针即可。"},
        {"stem": "循环链表中判断遍历是否回到起点，依靠的是（  ）",
         "options": {"A": "比较当前指针与起点指针", "B": "统计结点个数", "C": "检查空指针",
                     "D": "比较结点数据"},
         "standard_answer": "A", "explanation": "循环链表没有空指针，只能与起点比较。"},
        {"stem": "双链表相对于单链表在删除结点时的主要优势是（  ）",
         "options": {"A": "可以直接找到前驱", "B": "占用空间更小", "C": "插入更快",
                     "D": "不需要头结点"},
         "standard_answer": "A", "explanation": "双链表每个结点保存前驱指针，删除无需从头查找。"},
    ],
    "multiple_choice": [
        {"stem": "关于顺序存储与链式存储的比较，下列说法正确的有（  ）",
         "options": {"A": "顺序存储支持按下标访问", "B": "链式存储插入不必移动元素",
                     "C": "链式存储必须占用连续空间", "D": "顺序存储无法预先分配空间"},
         "standard_answer": "AB", "explanation": "顺序表可随机访问，链表改指针即可插入。"},
        {"stem": "关于循环链表的性质，下列说法正确的有（  ）",
         "options": {"A": "从任一结点出发都能遍历全表", "B": "尾结点的后继指回头结点",
                     "C": "必须保存表尾指针才能遍历", "D": "表中不能设置头结点"},
         "standard_answer": "AB", "explanation": "尾连头使遍历可绕行整表。"},
        {"stem": "关于双链表插入操作，下列说法正确的有（  ）",
         "options": {"A": "要同时维护前驱与后继两个方向", "B": "只改一个方向会破坏反向遍历",
                     "C": "双链表不能表示线性表", "D": "双链表插入比单链表少改指针"},
         "standard_answer": "AB", "explanation": "双向指针必须成对维护。"},
        {"stem": "关于顺序表插入与删除的代价，下列说法正确的有（  ）",
         "options": {"A": "表头插入代价与表长成正比", "B": "表尾追加不需要移动元素",
                     "C": "删除表尾需要移动全部元素", "D": "插入位置越靠前代价越小"},
         "standard_answer": "AB", "explanation": "移动量取决于插入位置与表长。"},
    ],
    "true_false": [
        {"stem": "顺序表把元素存放在连续的空间里。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "顺序存储要求物理位置相邻。"},
        {"stem": "带头结点的单链表为空时，头结点的后继指针为空。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "表空即头结点后面没有任何结点。"},
        {"stem": "循环双链表中任意结点的前驱指针都不会为空。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "首尾相接后每个结点都有前驱。"},
        {"stem": "单链表中知道某结点指针时，删除该结点的前驱仍然需要从头查找。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "单链表只能向后走，前驱无法直接得到。"},
    ],
    "short_answer": [
        {"stem": "请说明顺序表插入元素时为什么必须自后向前移动数据。",
         "options": {}, "standard_answer": "若自前向后移动会覆盖尚未搬运的元素，自后向前可保证数据不被破坏。",
         "explanation": "移动方向决定了是否覆盖未处理的数据。"},
        {"stem": "请比较顺序表与单链表在频繁插入场景下的取舍，并说明理由。",
         "options": {}, "standard_answer": "频繁插入宜用链表，改指针即可；顺序表需成批移动元素，代价随表长增长。",
         "explanation": "取舍取决于移动元素与维护指针的开销对比。"},
        {"stem": "请推演在长度为 5 的顺序表下标 2 处插入一个元素后各元素位置的变化过程。",
         "options": {}, "standard_answer": "下标 2 到 4 的元素依次后移一位，再写入新元素，表长变为 6。",
         "explanation": "插入需要自后向前移动以避免覆盖。"},
        {"stem": "请定位下面做法中的错误：在单链表尾部插入结点后没有更新尾指针。",
         "options": {}, "standard_answer": "新结点虽已挂上，但尾指针仍指向旧尾结点，下一次尾插会覆盖前一次结果。",
         "explanation": "尾指针未同步会让后续操作从错误结点继续。"},
    ],
}


class RecordingModel:
    """A model double that records every prompt, so a test can see what was ASKED for.

    Each call draws from a different slice of the bank: the generator refuses a question the
    learner has already been asked, so a double that started from the same entry every time
    would be refused for the reason a real model would be.
    """

    def __init__(self, planner=None):
        self.prompts: list[str] = []
        self.calls = 0
        self._planner = planner

    def __call__(self, _db, _user, _cap, messages, **_kw):
        self.prompts.append(messages[-1]["content"])
        self.calls += 1
        positions = _MATRIX_RE.findall(messages[-1]["content"])
        if self._planner is not None:
            positions = self._planner(self.calls, positions)
        used: dict[str, int] = {}
        questions = []
        for _number, qtype in positions:
            bank = _BY_TYPE[qtype]
            index = (self.calls - 1) * 2 + used.get(qtype, 0)
            used[qtype] = used.get(qtype, 0) + 1
            base = dict(bank[index % len(bank)])
            base["question_type"] = qtype
            base["options"] = dict(base["options"])
            base["assessment_target"] = f"{qtype} 能力 {index}"
            base["knowledge_point_index"] = 1
            questions.append(base)
        return SimpleNamespace(content=json.dumps({"questions": questions}, ensure_ascii=False))


def _install(learner, monkeypatch, model) -> None:
    monkeypatch.setattr("learning.spaces.course_learning.ai.execute_course_ai", model)


def _generate(learner, **body):
    payload = {"scope": "course", "count": 3}
    payload.update(body)
    return learner.client.post(f"/course-learning/courses/{COURSE}/practice/generate", json=payload)


def test_only_the_rejected_positions_are_asked_again(learner, monkeypatch):
    """A retry re-asks the MISSING positions — the good questions are never regenerated."""
    def plan(call, positions):
        return positions[:1] if call == 1 else positions

    model = RecordingModel(planner=plan)
    _install(learner, monkeypatch, model)
    payload = _generate(learner, count=3).json()
    assert payload["total"] == 3
    assert len(model.prompts) == 2
    assert len(_MATRIX_RE.findall(model.prompts[0])) == 3
    assert len(_MATRIX_RE.findall(model.prompts[1])) == 2
    assert payload["quality"]["RETRY_COUNT"] == 1
    assert payload["quality"]["FINAL_ACCEPTED"] == 3
    # every question is distinct — the retry did not re-ask what the first call delivered
    stems = [question["stem"] for question in payload["questions"]]
    assert len(set(stems)) == 3


def test_a_recently_asked_question_is_not_asked_again(learner, monkeypatch):
    """§14: the learner's own recent questions are handed to the model as an avoid list."""
    model = RecordingModel()
    _install(learner, monkeypatch, model)
    first = _generate(learner, count=3)
    assert first.status_code == 200
    first_stems = [question["stem"] for question in first.json()["questions"]]
    stored_targets = [
        row.assessment_target for row in learner.db.query(models.AIGeneratedQuestion).filter(
            models.AIGeneratedQuestion.username == learner.username).all()]

    second = _generate(learner, count=3)
    assert second.status_code == 200
    avoid_block = model.prompts[-1].split("必须避开的题干")[-1]
    for stem in first_stems:
        assert stem in avoid_block
    # …and the ABILITY, not just the wording, is carried across — a reworded repeat of the
    # same ability is exactly what the first set's questions must not be.
    for target in stored_targets:
        assert target in avoid_block


def test_a_question_that_repeats_a_stored_one_is_refused(learner, monkeypatch):
    """The avoid list has teeth: a model that insists on the same question fails the batch."""
    model = RecordingModel()
    _install(learner, monkeypatch, model)
    first = _generate(learner, count=3)
    assert first.status_code == 200

    class Repeater(RecordingModel):
        def __call__(self, _db, _user, _cap, messages, **kw):
            response = super().__call__(_db, _user, _cap, messages, **kw)
            payload = json.loads(response.content)
            stored = first.json()["questions"]
            for index, question in enumerate(payload["questions"]):
                question["stem"] = stored[index % len(stored)]["stem"]
            return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))

    _install(learner, monkeypatch, Repeater())
    again = _generate(learner, count=3)
    assert again.status_code == 503
    assert "没有生成出合格的题目" in again.json()["detail"]


def test_the_knowledge_point_scope_is_still_enforced(learner, monkeypatch):
    """The quality gates must not weaken the scope guarantee they sit behind."""
    _install(learner, monkeypatch, RecordingModel())
    response = _generate(learner, scope="knowledge_point", knowledge_point_id=999999, count=3)
    assert response.status_code == 404


def test_every_question_is_still_attributed_to_the_active_structure(learner, monkeypatch):
    _install(learner, monkeypatch, RecordingModel())
    point = learner.db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == learner.username,
        models.KnowledgePoint.course_id == COURSE,
        models.KnowledgePoint.parent_id.isnot(None)).one()
    payload = _generate(learner, scope="knowledge_point",
                        knowledge_point_id=point.id, count=3).json()
    assert {question["knowledge_point_id"] for question in payload["questions"]} == {f"kp:{point.id}"}
    assert {question["knowledge_point_title"] for question in payload["questions"]} == {point.title}


def test_the_answers_and_the_quality_fields_stay_server_side(learner, monkeypatch):
    """Neither the answer NOR the new ability fields may reach the browser before answering."""
    _install(learner, monkeypatch, RecordingModel())
    payload = _generate(learner, count=3).json()
    for question in payload["questions"]:
        assert "standard_answer" not in question
        assert "analysis" not in question
        assert "assessment_target" not in question
        assert "cognitive_level" not in question
        assert "question_fingerprint" not in question
    # …and they are not sent for a question the learner HAS answered either
    question_id = payload["questions"][0]["id"]
    answered = learner.client.post(
        f"/course-learning/courses/{COURSE}/practice/{payload['attempt_id']}/answer",
        json={"question_id": question_id, "answer": "A"}).json()
    assert "assessment_target" not in answered["feedback"]
    assert "cognitive_level" not in answered["feedback"]


def test_the_batch_reports_its_own_quality_metrics(learner, monkeypatch):
    _install(learner, monkeypatch, RecordingModel())
    metrics = _generate(learner, count=3).json()["quality"]
    assert metrics["BATCH_SIZE"] == 3
    assert metrics["FINAL_ACCEPTED"] == 3
    assert metrics["UNIQUE_STEMS"] == 3
    assert metrics["UNIQUE_ASSESSMENT_TARGETS"] >= quality.MIN_UNIQUE_TARGETS[3]
    assert metrics["DUPLICATE_REJECTED"] == 0
    assert metrics["LOW_QUALITY_REJECTED"] == 0
    assert metrics["OUTCOME"] == "accepted"


def test_the_stored_question_records_the_ability_it_tested(learner, monkeypatch):
    """The next set can only avoid an ability the previous one wrote down."""
    _install(learner, monkeypatch, RecordingModel())
    payload = _generate(learner, count=3).json()
    ids = [question["id"] for question in payload["questions"]]
    rows = learner.db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id.in_(ids)).all()
    assert len(rows) == 3
    assert all(row.assessment_target for row in rows)
    assert all(row.cognitive_level for row in rows)
    assert all(row.question_fingerprint for row in rows)
    assert len({row.question_fingerprint for row in rows}) == 3


# ---------------------------------------------------------------- coverage, end to end


class OneAbilityModel(RecordingModel):
    """A model that writes ten different questions and claims ONE ability for all of them."""

    def __call__(self, db, user, capability, messages, **kwargs):
        response = super().__call__(db, user, capability, messages, **kwargs)
        payload = json.loads(response.content)
        for question in payload["questions"]:
            question["assessment_target"] = "队满条件的判断"
        return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))


def test_a_ten_question_set_that_names_one_ability_is_refused(learner, monkeypatch):
    """The brief's §8, end to end: ten questions is not ten questions if they name one ability.

    The refusal is the SAME one a learner sees when the model delivers nothing usable, because
    a set that cannot name five abilities is a set that was not worth generating.
    """
    _install(learner, monkeypatch, OneAbilityModel())
    response = _generate(learner, count=10)
    assert response.status_code == 503, response.text
    assert "没有生成出合格的题目" in response.json()["detail"]
    assert learner.db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.username == learner.username).count() == 0
    assert learner.db.query(models.AIQuestionAttempt).filter(
        models.AIQuestionAttempt.username == learner.username).count() == 0


# ---------------------------------------------------------------- no fallback bank


def test_there_is_no_local_question_bank_left_to_pad_a_set_with(learner, monkeypatch):
    """`_fallback_question` is what produced the reported set. Its absence is the guarantee.

    The set it built was made from the knowledge point's TITLE, so it could only ever ask
    "is X important" and "summarise X" — the two sentences the learner reported. Topping a set
    up to size is now impossible rather than merely discouraged, and this test fails the day a
    bank is added back.
    """
    from learning.spaces.course_learning import practice as practice_module
    assert not hasattr(practice_module, "_fallback_question")
    assert not hasattr(practice_module, "_fallback_variants")

    # …and nothing the CURRENT generator writes can be labelled a fallback.
    _install(learner, monkeypatch, RecordingModel())
    payload = _generate(learner, count=3).json()
    ids = [question["id"] for question in payload["questions"]]
    rows = learner.db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id.in_(ids)).all()
    assert {row.generation_mode for row in rows} == {"ai"}


def test_the_two_reported_stems_are_refused_by_the_generator_itself():
    """The report's own sentences, run through the gate the generator runs — not a paraphrase."""
    batch = _batch(count=10)
    for stem in (REPORT_META_STEM, REPORT_GENERIC_STEM):
        with pytest.raises(quality.Rejected):
            batch.add(_question(stem=stem, question_type="short_answer", options={},
                                standard_answer="先说明定义，再说明适用条件。",
                                analysis="回答应包含定义与适用条件。",
                                assessment_target="概念定义"))
    assert batch.questions == []
