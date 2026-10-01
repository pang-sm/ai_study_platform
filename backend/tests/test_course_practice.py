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


# The generator now hands the model a coverage matrix and refuses a set whose questions repeat
# each other, so the double answers the matrix and gives every position a different question.
_MATRIX_RE = re.compile(r'第 (\d+) 题：question_type 必须是 "(\w+)"')

_BY_TYPE = {
    "single_choice": [
        {"stem": "线性表的顺序存储结构最适合哪种访问方式？（  ）",
         "options": {"A": "按下标随机访问", "B": "只允许尾部访问", "C": "不支持元素定位",
                     "D": "只能反向访问"},
         "standard_answer": "A",
         "explanation": "顺序存储通过基址和下标可以直接计算元素位置，因此支持随机访问。"},
        {"stem": "长度为 n 的顺序表在表尾追加一个元素，需要移动的元素个数是（  ）",
         "options": {"A": "0", "B": "1", "C": "n-1", "D": "n"},
         "standard_answer": "A", "explanation": "表尾之后没有元素，追加不需要移动任何已有元素。"},
    ],
    "true_false": [
        {"stem": "顺序表把元素存放在连续的空间里。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "顺序存储要求物理位置相邻。"},
    ],
}


def _model_reply(messages) -> str:
    positions = _MATRIX_RE.findall(messages[-1]["content"])
    used: dict[str, int] = {}
    questions = []
    for _number, qtype in positions:
        bank = _BY_TYPE[qtype]
        index = used.get(qtype, 0)
        used[qtype] = index + 1
        base = dict(bank[index % len(bank)])
        base["question_type"] = qtype
        base["options"] = dict(base["options"])
        base["assessment_target"] = f"{qtype} 能力 {index}"
        base["knowledge_point_index"] = 1
        questions.append(base)
    return json.dumps({"questions": questions}, ensure_ascii=False)


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
