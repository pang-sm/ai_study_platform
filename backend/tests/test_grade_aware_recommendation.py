"""P3: a recommendation answers a MAJOR and a STAGE, not a major alone.

The product told a 大一 student and a 大三 student in the same major the same list of courses,
because the courses hung off the plan code alone. These tests assert the stage reaches the real
decision chain — they do NOT assert that any particular course comes back, so a change to a
direction's course pool does not make them fail.
"""
from __future__ import annotations

from types import SimpleNamespace

from conftest import register_and_login
from membership import (
    COURSE_SUGGESTIONS,
    MAJOR_CLASSIFICATION_PROMPT,
    _apply_stage,
    recommend_plan_by_major,
    stage_of_course,
)

MAJOR = "计算机科学与技术"


# ── the stage model itself ────────────────────────────────────

def test_course_stage_is_read_from_the_course_not_the_major():
    # A course is placed by what it teaches, so the rules serve any direction's pool.
    assert stage_of_course("高等数学") == 1
    assert stage_of_course("数据结构") == 2
    assert stage_of_course("操作系统") == 3
    assert stage_of_course("毕业设计") == 4
    # A name no rule recognises is not forced into a stage it does not belong to.
    assert stage_of_course("建模与仿真") is None


def test_a_stage_selects_its_own_courses_and_the_previous_stage_is_still_carried():
    pool = COURSE_SUGGESTIONS["cs_pro"]

    first_year = _apply_stage(pool, "大一")
    third_year = _apply_stage(pool, "大三")

    assert first_year != third_year
    assert "高等数学" in first_year and "操作系统" not in first_year
    assert "操作系统" in third_year and "高等数学" not in third_year
    # The grace band: a 大三 list still carries the previous stage's courses.
    assert "数据结构" in third_year


def test_an_unknown_grade_narrows_nothing():
    pool = COURSE_SUGGESTIONS["cs_pro"]
    assert _apply_stage(pool, "") == pool
    assert _apply_stage(pool, "二年级") == pool


# ── the stage reaches the real recommendation ─────────────────

def test_the_same_major_at_two_stages_gets_two_recommendations(db_session):
    first_year = recommend_plan_by_major(MAJOR, "大一", db_session)
    third_year = recommend_plan_by_major(MAJOR, "大三", db_session)

    # Both are the same direction — only the stage differs.
    assert first_year["recommended_plan"] == third_year["recommended_plan"] == "cs_pro"
    assert first_year["suggested_courses"] != third_year["suggested_courses"]
    assert "高等数学" in first_year["suggested_courses"]
    assert "操作系统" not in first_year["suggested_courses"]
    assert "操作系统" in third_year["suggested_courses"]


def test_the_grade_reaches_the_classification_prompt(db_session):
    """An unknown major is classified by the model, and the prompt it is asked with carries the
    stage — otherwise the AI path answers about a major in the abstract."""
    prompts: list[str] = []

    def create(**kwargs):
        prompts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"recommended_plan": "cs_pro", "category": "computer", "confidence": 0.8,'
                    ' "reason": "测试", "suggested_courses": ["高等数学", "操作系统"]}'))])

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    recommend_plan_by_major("跨学科交叉实验班", "大三", db_session, fake_client,
                            semester="下学期")

    assert prompts, "the classification was never asked"
    assert "大三" in prompts[0]
    assert "下学期" in prompts[0]
    # The prompt template itself is stage-shaped: the grade is an input, not decoration.
    assert "{grade}" in MAJOR_CLASSIFICATION_PROMPT


def test_a_cached_classification_is_still_staged_per_learner(db_session):
    """The classification cache is keyed by major, and the plan/category it stores ARE
    major-level facts. The course list is not: it is derived per stage, so two learners behind the
    same cache entry still get their own stage's courses."""
    payload = ('{"recommended_plan": "cs_pro", "category": "computer", "confidence": 0.8,'
               ' "reason": "测试", "suggested_courses":'
               ' ["高等数学", "线性代数", "大学物理", "数据结构", "操作系统"]}')
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **_: SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=payload))]))))

    # First call fills the cache for this unknown major.
    recommend_plan_by_major("交叉学科实验基地", "大一", db_session, fake_client)
    # Second call is served from that cache — the same stored courses, a different stage.
    first_year = recommend_plan_by_major("交叉学科实验基地", "大一", db_session, fake_client)
    third_year = recommend_plan_by_major("交叉学科实验基地", "大三", db_session, fake_client)

    assert first_year["source"] == third_year["source"] == "cache"
    assert first_year["suggested_courses"] == ["高等数学", "线性代数", "大学物理"]
    assert "操作系统" in third_year["suggested_courses"]
    assert "操作系统" not in first_year["suggested_courses"]


def test_the_endpoint_recommends_by_the_learners_own_grade(client, db_session):
    """End to end: the grade the learner saved is what the endpoint answers about."""
    register_and_login(client, "p3-grade-aware")

    for grade in ("大一", "大三"):
        reply = client.put("/me/profile", json={"major": MAJOR, "grade": grade})
        assert reply.status_code == 200, reply.text
    client.put("/me/profile", json={"major": MAJOR, "grade": "大一"})
    first_year = client.get("/membership/recommendation").json()

    client.put("/me/profile", json={"major": MAJOR, "grade": "大三"})
    third_year = client.get("/membership/recommendation").json()

    assert first_year["recommended_plan"] == third_year["recommended_plan"] == "cs_pro"
    assert first_year["suggested_courses"] != third_year["suggested_courses"]
    assert "操作系统" in third_year["suggested_courses"]
    assert "操作系统" not in first_year["suggested_courses"]
