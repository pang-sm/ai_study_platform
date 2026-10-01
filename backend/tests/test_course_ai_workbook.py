"""The course workbook: a generated question's own attempt history, and redoing it.

The workbook is the READ view over generated questions, and it is what the wrong-answer page
resolves content through — so it has to keep working after the practice page changed how a
question is generated. Generation here goes through the product route; the redo path
(``workbook/{question}/attempts`` + the one-question submit) is untouched by this round.
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


# The generator hands the model a coverage matrix and refuses a set whose questions repeat one
# another, so the double answers the matrix with a different question per position.
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


def _learner(client: TestClient, db_session, monkeypatch, username: str):
    register_and_login(client, username)
    onboarded = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": [COURSE], "material_types": ["课件"],
        "onboarding_completed": True})
    assert onboarded.status_code == 200, onboarded.text
    user = db_session.query(models.User).filter(models.User.username == username).one()
    structure = knowledge_structure.create_draft(
        db_session, user, COURSE, source_mode="ai_generated", chapters=CHAPTERS)
    knowledge_structure.confirm(db_session, user, COURSE, structure.id)
    grant_unified_tier(db_session, username, "standard")
    monkeypatch.setattr("learning.spaces.course_learning.ai.execute_course_ai",
                        lambda _db, _user, _cap, messages, **_kw:
                        SimpleNamespace(content=_model_reply(messages)))


def test_course_ai_workbook_keeps_question_and_attempt_history(client: TestClient, db_session,
                                                               monkeypatch):
    _learner(client, db_session, monkeypatch, "workbook-owner")
    generated = client.post(f"/course-learning/courses/{COURSE}/practice/generate",
                            json={"scope": "knowledge_point", "count": 3,
                                  "knowledge_point_id": db_session.query(
                                      models.KnowledgePoint).filter(
                                      models.KnowledgePoint.username == "workbook-owner",
                                      models.KnowledgePoint.course_id == COURSE,
                                      models.KnowledgePoint.parent_id.isnot(None)).one().id})
    assert generated.status_code == 200, generated.text
    question_id = generated.json()["questions"][0]["id"]

    initial = client.get("/course-learning/practice/workbook", params={
        "username": "workbook-owner", "course_id": COURSE,
    })
    assert initial.status_code == 200
    item = next(row for row in initial.json()["items"] if row["id"] == question_id)
    assert item["workbook_status"] == "unanswered"
    assert item["attempt_count"] == 1
    # a question the learner has not answered must not arrive with its answer attached
    assert "standard_answer" not in item
    assert "analysis" not in item

    # the redo path opens a NEW one-question attempt without touching the set
    restarted = client.post(
        f"/course-learning/practice/workbook/{question_id}/attempts",
        json={"username": "workbook-owner"})
    assert restarted.status_code == 200, restarted.text
    redo_attempt = restarted.json()["attempt_id"]
    assert restarted.json()["question"]["id"] == question_id

    wrong = client.post(f"/course-learning/practice/{redo_attempt}/submit",
                        json={"username": "workbook-owner", "answer": "B"})
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["result"]["correct"] is False

    workbook = client.get("/course-learning/practice/workbook", params={
        "username": "workbook-owner", "course_id": COURSE, "status": "wrong",
    })
    assert workbook.status_code == 200
    item = next(row for row in workbook.json()["items"] if row["id"] == question_id)
    assert item["workbook_status"] == "wrong"
    assert item["attempt_count"] == 2
    assert [attempt["correct"] for attempt in item["attempts"]] == [False, None]

    # the redo's own verdict is readable back through the course-scoped contract
    session = client.get(f"/course-learning/courses/{COURSE}/practice/session",
                         params={"attempt_id": generated.json()["attempt_id"]}).json()
    assert session["session"]["answered"] == 0        # the SET is still untouched
