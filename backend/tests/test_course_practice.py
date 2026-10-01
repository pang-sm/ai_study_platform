"""The course practice surface at ``/course-learning/courses/{course}/practice/...``.

Two promises: a learner's own set is theirs alone, and a finished set is readable as a set.
The generation rules themselves (scope, schema, write-back) live in
``test_course_practice_redesign.py``; this file keeps the course-scoped contract.
"""
import json
import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

from conftest import grant_unified_tier, register_and_login
import models
from learning.spaces.course_learning import knowledge_structure

COURSE = "数据结构"
CHAPTERS = [{"title": "线性结构", "points": [{"title": "线性表的顺序存储"}]}]


def _model_reply(messages) -> str:
    count = int(re.search(r"题目数量：(\d+)", messages[-1]["content"]).group(1))
    return json.dumps({"questions": [{
        "question_type": "single_choice",
        "stem": f"线性表的顺序存储结构最适合哪种访问方式？（第 {index} 题）",
        "options": {"A": "按下标随机访问", "B": "只允许尾部访问", "C": "不支持元素定位",
                    "D": "只能反向访问"},
        "standard_answer": "A",
        "explanation": "顺序存储通过基址和下标可以直接计算元素位置，因此支持随机访问。",
        "knowledge_point_index": 1,
    } for index in range(1, count + 1)]}, ensure_ascii=False)


def test_course_practice_set_is_the_learners_own(client: TestClient, db_session, monkeypatch):
    register_and_login(client, "practice-a")
    onboarded = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": [COURSE], "material_types": ["课件"],
        "onboarding_completed": True})
    assert onboarded.status_code == 200, onboarded.text
    user = db_session.query(models.User).filter(models.User.username == "practice-a").one()
    structure = knowledge_structure.create_draft(
        db_session, user, COURSE, source_mode="ai_generated", chapters=CHAPTERS)
    knowledge_structure.confirm(db_session, user, COURSE, structure.id)
    grant_unified_tier(db_session, "practice-a", "standard")
    monkeypatch.setattr("learning.spaces.course_learning.ai.execute_course_ai",
                        lambda _db, _user, _cap, messages, **_kw:
                        SimpleNamespace(content=_model_reply(messages)))

    generated = client.post(f"/course-learning/courses/{COURSE}/practice/generate",
                            json={"scope": "course", "count": 3})
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    assert payload["total"] == 3
    assert all("standard_answer" not in question for question in payload["questions"])
    attempt_id = payload["attempt_id"]

    other = TestClient(client.app)
    try:
        register_and_login(other, "practice-b")
        assert other.get(f"/course-learning/courses/{COURSE}/practice/session",
                         params={"attempt_id": attempt_id}).status_code == 404
        assert other.post(
            f"/course-learning/courses/{COURSE}/practice/{attempt_id}/answer",
            json={"question_id": payload["questions"][0]["id"],
                  "answer": "A"}).status_code == 404
    finally:
        other.close()

    answered = client.post(
        f"/course-learning/courses/{COURSE}/practice/{attempt_id}/answer",
        json={"question_id": payload["questions"][0]["id"], "answer": "A"})
    assert answered.status_code == 200, answered.text
    assert answered.json()["feedback"]["correct"] is True
    assert answered.json()["session"]["answered"] == 1

    session = client.get(f"/course-learning/courses/{COURSE}/practice/session").json()
    assert session["session"]["attempt_id"] == attempt_id

    history = client.get(f"/course-learning/courses/{COURSE}/practice/history").json()
    assert history["course_id"] == COURSE
    assert history["items"] == []          # the set is still open, so it is not history yet
