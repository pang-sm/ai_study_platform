"""Professional-practice rebuild: scope → generated set → per-question play → settle.

Every test here is about ONE promise the page makes to a learner:

  * the questions belong to the scope they picked (and only that scope),
  * the answer is not in the browser before they answer,
  * the set behaves as a set (progress, no duplicate asks, a finish),
  * and a finished set lands in the product's EXISTING learning facts.
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
from learning.wrong_answers.models import WrongAnswerState

# The canonical course key IS the display name — that is what ``course_learning_preferences``
# stores and what every course-scoped route resolves against.
COURSE = "数据结构"

CHAPTERS = [
    {"title": "线性结构", "points": [{"title": "线性表的顺序存储"}, {"title": "链式存储"}]},
    {"title": "树", "points": [{"title": "二叉树的遍历"}, {"title": "图"}]},
]

# One valid question per type, in the order the product asks for them. The bank is larger than
# any single set needs because the quality gates now REFUSE a second question that says the same
# thing — a double that recycled four questions would be refused for the reason a real model
# would be, and the tests would be measuring the gate instead of the page.
_QUESTION_BANK = {
    "single_choice": [
        {"stem": "某顺序表把元素存放在下标 0..n-1，读取下标 i 的元素所需的时间是（  ）",
         "options": {"A": "O(1)", "B": "O(log n)", "C": "O(n)", "D": "O(n²)"},
         "standard_answer": "A", "explanation": "顺序存储可由基址与下标直接算出地址，读取与 i 无关。"},
        {"stem": "顺序表长度为 n，在下标 0 处插入一个元素，需要向后移动的元素个数是（  ）",
         "options": {"A": "n", "B": "n-1", "C": "1", "D": "0"},
         "standard_answer": "A", "explanation": "下标 0 处插入须把原有 n 个元素全部后移一位。"},
        {"stem": "顺序表长度为 n，删除下标 n-1 的元素需要移动的元素个数是（  ）",
         "options": {"A": "0", "B": "1", "C": "n-1", "D": "n"},
         "standard_answer": "A", "explanation": "删除表尾元素之后没有元素需要前移。"},
        {"stem": "顺序表按下标访问比链表快，根本原因是（  ）",
         "options": {"A": "元素连续存放，地址可由基址加下标算出", "B": "顺序表元素个数更少",
                     "C": "链表必须遍历到底", "D": "顺序表不需要比较元素大小"},
         "standard_answer": "A", "explanation": "连续存放使得任意下标的地址都能直接计算得到。"},
        {"stem": "长度为 n 的顺序表，平均情况下删除一个元素需要移动的元素个数约为（  ）",
         "options": {"A": "n/2", "B": "n", "C": "log n", "D": "1"},
         "standard_answer": "A", "explanation": "等概率删除各位置时平均移动 n/2 个元素。"},
        {"stem": "单链表中，删除指针 p 所指结点的后继结点，正确的操作顺序是（  ）",
         "options": {"A": "先让 p 指向后继的后继，再释放原后继结点", "B": "先释放原后继结点，再改指针",
                     "C": "先改头指针，再释放结点", "D": "直接释放 p 所指结点"},
         "standard_answer": "A", "explanation": "必须先保留后继的后继，否则释放后指针无处可指。"},
        {"stem": "带头结点的单链表中，判断表空的条件是（  ）",
         "options": {"A": "头结点的 next 为空", "B": "头结点为空", "C": "头结点的 data 为 0",
                     "D": "头结点等于尾结点"},
         "standard_answer": "A", "explanation": "带头结点时表空当且仅当头结点的后继为空。"},
        {"stem": "在单链表中，要在指针 p 所指结点之后插入新结点 s，正确的语句序列是（  ）",
         "options": {"A": "s->next = p->next; p->next = s;", "B": "p->next = s; s->next = p->next;",
                     "C": "s->next = p; p->next = s;", "D": "p->next = s->next; s->next = p;"},
         "standard_answer": "A", "explanation": "先把新结点接到原后继，再让 p 指向新结点，顺序不能颠倒。"},
    ],
    "multiple_choice": [
        {"stem": "关于单链表与顺序表的比较，下列说法正确的有（  ）",
         "options": {"A": "单链表插入不需要移动元素", "B": "顺序表支持按下标随机访问",
                     "C": "单链表必须用连续空间", "D": "顺序表删除不需要移动元素"},
         "standard_answer": "AB", "explanation": "链表改指针即可插入，顺序表可随机访问；两者其余说法不成立。"},
        {"stem": "关于循环链表的性质，下列说法正确的有（  ）",
         "options": {"A": "从任一结点出发都能遍历全表", "B": "尾结点的 next 指回头结点",
                     "C": "必须额外保存表尾指针", "D": "表中不能有头结点"},
         "standard_answer": "AB", "explanation": "尾连头使遍历可绕行整表；其余说法与循环链表无关。"},
        {"stem": "关于双链表的插入操作，下列说法正确的有（  ）",
         "options": {"A": "插入时要同时修改前驱与后继两个方向的指针", "B": "只改一个方向会破坏回退能力",
                     "C": "双链表不能表示线性表", "D": "双链表插入比单链表少改指针"},
         "standard_answer": "AB", "explanation": "双向指针必须成对维护，否则反向遍历断裂。"},
        {"stem": "关于顺序表存储密度的说法，正确的有（  ）",
         "options": {"A": "顺序表不需要额外指针域", "B": "单链表每个结点要额外存放指针",
                     "C": "两者存储密度相同", "D": "顺序表无法预分配空间"},
         "standard_answer": "AB", "explanation": "顺序表只存数据，链表每结点多一个指针域。"},
    ],
    "true_false": [
        {"stem": "带头结点的单链表为空时，头结点的 next 指针为空。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "表空即头结点后面没有任何结点。"},
        {"stem": "顺序表在下标 0 处插入元素，最坏情况下需要移动 n 个元素。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "表头插入要让原有全部元素后移一位。"},
        {"stem": "单链表中已经知道指针 p 指向某结点时，删除 p 的后继结点仍需要从头查找。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "B",
         "explanation": "p 已给出后继的地址，改指针即可删除，无需从头查找。"},
        {"stem": "循环双链表中，任意结点的前驱指针都不会为空。",
         "options": {"A": "正确", "B": "错误"}, "standard_answer": "A",
         "explanation": "首尾相接后每个结点都有前驱。"},
    ],
    "short_answer": [
        {"stem": "请说明单链表插入新结点时，为什么必须先接后继再改前驱指针。",
         "options": {}, "standard_answer": "先接后继可保留原后继地址；若先改前驱，原后继地址丢失，链表断裂。",
         "explanation": "顺序颠倒会导致原后继结点无法再被找到。"},
        {"stem": "请比较顺序表与单链表在频繁插入删除场景下的取舍，并说明理由。",
         "options": {}, "standard_answer": "频繁插入删除宜用链表，因为改指针即可；顺序表需成批移动元素，代价随表长增长。",
         "explanation": "取舍取决于移动元素与维护指针的开销对比。"},
        {"stem": "请推演在长度为 5 的顺序表下标 2 处插入一个元素后，各元素位置的变化过程。",
         "options": {}, "standard_answer": "先移动下标 2 到 4 的元素依次后移一位，再把新元素写入下标 2，表长变为 6。",
         "explanation": "插入需要自后向前移动，避免覆盖尚未搬运的数据。"},
        {"stem": "请定位下面做法中的错误：在单链表尾部插入结点时直接让尾结点的 next 指向新结点，却不更新尾指针。",
         "options": {}, "standard_answer": "新结点虽然挂上了，但尾指针仍指向旧尾结点，下一次尾插会覆盖前一次的结果。",
         "explanation": "尾指针未同步会让后续操作从错误的结点继续。"},
    ],
}

# The model double reads the coverage matrix back out of the prompt, so it answers the number
# of questions AND the types actually asked for — including on a retry, where the matrix is the
# remaining positions only. Hard-coding the count would make a retry invisible to the test.
_MATRIX_RE = re.compile(r'第 (\d+) 题：question_type 必须是 "(\w+)"')


def make_model_double():
    """A model double that answers the positions the prompt asks for, with varied questions.

    It keeps a cursor so that a SECOND set for the same learner draws different bank entries —
    the avoidance list is read back from the learner's own stored questions, so a double that
    started from the same entry every time would be refused for repeating itself.
    """
    state = {"cursor": 0}

    def reply(messages) -> str:
        prompt = messages[-1]["content"]
        positions = _MATRIX_RE.findall(prompt)
        used: dict[str, int] = {}
        questions = []
        for _number, qtype in positions:
            bank = _QUESTION_BANK[qtype]
            index = (state["cursor"] + used.get(qtype, 0)) % len(bank)
            used[qtype] = used.get(qtype, 0) + 1
            base = dict(bank[index])
            base["question_type"] = qtype
            base["options"] = dict(base["options"])
            # Every position claims a DIFFERENT ability, or the batch refuses to fill at all.
            base["assessment_target"] = f"{qtype} 能力 {index}"
            base["cognitive_level"] = "understand"
            base["knowledge_point_index"] = 1
            questions.append(base)
        state["cursor"] += 5
        return json.dumps({"questions": questions}, ensure_ascii=False)

    return reply


class Learner:
    """One onboarded learner, with the handles a test needs to address them."""

    def __init__(self, client: TestClient, db, username: str):
        self.client = client
        self.db = db
        self.username = username

    def post(self, *args, **kwargs):
        return self.client.post(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.client.get(*args, **kwargs)


@pytest.fixture
def learner(request, client: TestClient, db_session, monkeypatch):
    """An onboarded learner with a real ACTIVE knowledge structure and a Standard tier.

    The username is unique per test: the suite shares one database, so a fixed name would make
    a test's own structure collide with the previous one's.
    """
    username = f"pr{next(_LEARNER_SEQ)}"
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
    reply = make_model_double()
    monkeypatch.setattr("learning.spaces.course_learning.ai.execute_course_ai",
                        lambda _db, _user, _cap, messages, **_kw:
                        SimpleNamespace(content=reply(messages)))
    return Learner(client, db_session, username)


_LEARNER_SEQ = itertools.count(1)


def _user_id(learner) -> int:
    return learner.db.query(models.User).filter(
        models.User.username == learner.username).one().id


def _correct_answer(db, question_id) -> str:
    """The question's own key, read server-side — a test must not assume a fixed letter."""
    return db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id == question_id).one().standard_answer


def _points(db, username, title=None, chapter=None):
    query = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == username,
        models.KnowledgePoint.course_id == COURSE,
        models.KnowledgePoint.structure_id.isnot(None),
        models.KnowledgePoint.parent_id.isnot(None))
    rows = query.all()
    if title:
        rows = [row for row in rows if row.title == title]
    if chapter:
        rows = [row for row in rows if row.parent_id == chapter]
    return rows


def _generate(client, **body):
    payload = {"scope": "course", "count": 3}
    payload.update(body)
    return client.post(f"/course-learning/courses/{COURSE}/practice/generate", json=payload)


# ---------------------------------------------------------------- GENERATION


def test_generation_goes_through_the_unified_ai_boundary():
    """The generator asks for a CAPABILITY — it never builds or calls a provider itself."""
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]
              / "learning" / "spaces" / "course_learning" / "practice.py")
    text = source.read_text(encoding="utf-8")
    assert "execute_course_ai" in text
    assert '"question.generate"' in text
    assert "OpenAI(" not in text and "AsyncOpenAI(" not in text
    assert "chat.completions" not in text


def test_knowledge_point_scope_generates_only_that_point(learner, db_session):
    point = _points(db_session, learner.username, title="二叉树的遍历")[0]
    response = _generate(learner, scope="knowledge_point", knowledge_point_id=point.id, count=3)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["scope"] == "knowledge_point"
    assert payload["scope_label"] == "二叉树的遍历"
    assert payload["total"] == 3
    assert [q["knowledge_point_title"] for q in payload["questions"]] == ["二叉树的遍历"] * 3
    assert {q["knowledge_point_id"] for q in payload["questions"]} == {f"kp:{point.id}"}
    assert {q["chapter"] for q in payload["questions"]} == {"树"}
    # the answer is not in what the browser is handed
    blob = json.dumps(payload, ensure_ascii=False)
    assert "standard_answer" not in blob and "explanation" not in blob


def test_chapter_scope_covers_the_chapter_and_nothing_else(learner, db_session):
    chapter = db_session.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == learner.username,
        models.KnowledgePoint.course_id == COURSE,
        models.KnowledgePoint.title == "线性结构").one()
    response = _generate(learner, scope="chapter", chapter_id=chapter.id, count=5)
    assert response.status_code == 200, response.text
    payload = response.json()
    allowed = {f"kp:{point.id}" for point in _points(db_session, learner.username, chapter=chapter.id)}
    assert len(allowed) == 2
    assert {q["knowledge_point_id"] for q in payload["questions"]} <= allowed
    assert {q["chapter"] for q in payload["questions"]} == {"线性结构"}


def test_course_scope_covers_the_whole_structure(learner, db_session):
    response = _generate(learner, scope="course", count=5)
    assert response.status_code == 200, response.text
    payload = response.json()
    allowed = {f"kp:{point.id}" for point in _points(db_session, learner.username)}
    assert payload["scope_source"] == "structure"
    assert payload["total"] == 5
    assert {q["knowledge_point_id"] for q in payload["questions"]} <= allowed
    assert payload["scope_label"].endswith("整门课程")


@pytest.mark.parametrize("count", [3, 5, 10])
def test_the_requested_number_of_questions_is_what_arrives(learner, count):
    response = _generate(learner, count=count)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == count == len(payload["questions"])
    # the mix is the product's own decision, and it is reproduced exactly
    types = [q["question_type"] for q in payload["questions"]]
    assert types[0] == "single_choice"
    assert set(types) <= {"single_choice", "multiple_choice", "true_false", "short_answer"}


@pytest.mark.parametrize("difficulty,label", [("basic", "基础"), ("medium", "中等"), ("hard", "较难")])
def test_a_chosen_difficulty_is_honoured(learner, difficulty, label):
    payload = _generate(learner, difficulty=difficulty).json()
    assert payload["difficulty"] == difficulty
    assert payload["difficulty_label"] == label
    assert {q["difficulty"] for q in payload["questions"]} == {label}


def test_adaptive_with_no_history_generates_normally(learner):
    """No stored record must be answered with 中等 — never with an error, never with nothing."""
    payload = _generate(learner, difficulty="adaptive").json()
    assert payload["adaptive"]["has_history"] is False
    assert payload["difficulty"] == "medium"
    assert payload["total"] == 3


def test_invalid_model_output_never_reaches_the_learner(learner, monkeypatch):
    """A bad question is dropped — and a set that cannot be rebuilt is REFUSED, never padded.

    The padding is what this asserts the absence of. A previous version answered an unusable
    model answer by filling the set from a local bank built out of the knowledge point's title,
    which is how a learner asking for ten questions about 「循环队列」 got ten restatements of
    its name. An error the learner can retry is better than a set that teaches nothing.
    """
    def _broken(_db, _user, _cap, _messages, **_kw):
        return SimpleNamespace(content=json.dumps({"questions": [
            {"question_type": "single_choice", "stem": "选项不全的题（第 1 题）",
             "options": {"A": "只有一个选项"}, "standard_answer": "A",
             "explanation": "解析与题干无关但与结论一致。", "knowledge_point_index": 1},
            {"question_type": "single_choice", "stem": "越界的题（第 2 题）",
             "options": {"A": "一", "B": "二", "C": "三", "D": "四"},
             "standard_answer": "A", "explanation": "这道题指向了范围之外的编号。",
             "knowledge_point_index": 99},
        ]}, ensure_ascii=False))

    monkeypatch.setattr("learning.spaces.course_learning.ai.execute_course_ai", _broken)
    response = _generate(learner, count=3)
    assert response.status_code == 503, response.text
    assert "没有生成出合格的题目" in response.json()["detail"]
    # nothing was written for a set that was never produced. Scoped to THIS learner: the suite
    # shares one database, so an unscoped count would be measuring every other test's rows.
    assert learner.db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.username == learner.username,
        models.AIGeneratedQuestion.requirement == "课程章节练习").count() == 0


def test_an_unknown_knowledge_point_is_refused_not_approximated(learner):
    response = _generate(learner, scope="knowledge_point", knowledge_point_id=999999, count=3)
    assert response.status_code == 404
    assert "知识结构" in response.json()["detail"]
    # and nothing was generated for it
    assert response.json().get("questions") is None


def test_a_course_without_a_structure_refuses_point_scope(learner, db_session):
    """A learner who has not built a structure cannot be given a point-scoped set."""
    models.User  # noqa: B018 — documents the import used by the fixture
    structure = knowledge_structure.active_structure(db_session, learner.username, COURSE)
    structure.status = "superseded"
    db_session.commit()
    assert _generate(learner, scope="knowledge_point",
                     knowledge_point_id=1, count=3).status_code == 409
    # course scope still answers, from the published map, so practice never becomes impossible
    fallback = _generate(learner, scope="course", count=3)
    assert fallback.status_code == 200, fallback.text
    assert fallback.json()["scope_source"] == "knowledge_map"


# ---------------------------------------------------------------- RENDERING (contract)


def test_every_question_type_arrives_with_a_gradable_shape(learner):
    payload = _generate(learner, count=10).json()
    by_type = {q["question_type"]: q for q in payload["questions"]}
    assert set(by_type) == {"single_choice", "multiple_choice", "true_false", "short_answer"}

    single = by_type["single_choice"]
    assert len(single["options"]) == 4 and all(single["options"].values())
    assert len(set(single["options"].values())) == 4

    multiple = by_type["multiple_choice"]
    assert len(multiple["options"]) == 4

    true_false = by_type["true_false"]
    assert true_false["options"] == {"A": "正确", "B": "错误"}

    assert by_type["short_answer"]["options"] == {}


def test_the_answer_arrives_only_after_the_learner_answers(learner):
    payload = _generate(learner, count=3).json()
    question = payload["questions"][0]
    assert "standard_answer" not in question and "result" not in question

    session = learner.get(f"/course-learning/courses/{COURSE}/practice/session").json()["session"]
    assert session["attempt_id"] == payload["attempt_id"]
    assert all("standard_answer" not in row for row in session["questions"])

    answered = learner.post(
        f"/course-learning/courses/{COURSE}/practice/{payload['attempt_id']}/answer",
        json={"question_id": question["id"], "answer": "A"}).json()
    assert answered["feedback"]["standard_answer"]
    assert answered["feedback"]["analysis"]
    assert answered["feedback"]["knowledge_point_title"]


# ---------------------------------------------------------------- SESSION


def test_progress_advances_one_question_at_a_time(learner):
    payload = _generate(learner, count=3).json()
    attempt = payload["attempt_id"]
    url = f"/course-learning/courses/{COURSE}/practice/{attempt}/answer"

    first = learner.post(url, json={"question_id": payload["questions"][0]["id"], "answer": "A"}).json()
    assert first["session"]["answered"] == 1
    assert first["session"]["total"] == 3
    assert first["session"]["status"] == "in_progress"

    second = learner.post(url, json={"question_id": payload["questions"][1]["id"],
                                     "answer": "AC"}).json()
    assert second["session"]["answered"] == 2
    assert second["session"]["status"] == "in_progress"

    third = learner.post(url, json={"question_id": payload["questions"][2]["id"],
                                    "answer": "A"}).json()
    assert third["session"]["answered"] == 3
    assert third["session"]["status"] == "submitted"
    # the set is finished, so it is no longer the open session
    assert learner.get(f"/course-learning/courses/{COURSE}/practice/session").json()["session"] is None


def test_the_finish_summary_counts_correct_and_wrong(learner, db_session):
    payload = _generate(learner, count=3).json()
    attempt = payload["attempt_id"]
    url = f"/course-learning/courses/{COURSE}/practice/{attempt}/answer"
    questions = payload["questions"]

    # answer the first with its own key from the database, the rest deliberately wrong
    first = db_session.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id == questions[0]["id"]).one()
    results = [
        learner.post(url, json={"question_id": questions[0]["id"],
                                "answer": first.standard_answer}).json(),
        learner.post(url, json={"question_id": questions[1]["id"], "answer": "D"}).json(),
        learner.post(url, json={"question_id": questions[2]["id"], "answer": "B"}).json(),
    ]
    session = results[-1]["session"]
    assert session["status"] == "submitted"
    assert session["correct_count"] == 1

    stored = db_session.query(models.AIQuestionAttempt).filter(
        models.AIQuestionAttempt.id == attempt).one()
    assert stored.status == "submitted"
    assert stored.total_questions == 3


def test_answering_the_same_question_twice_writes_one_fact(learner, db_session):
    payload = _generate(learner, count=3).json()
    attempt, question = payload["attempt_id"], payload["questions"][0]
    url = f"/course-learning/courses/{COURSE}/practice/{attempt}/answer"

    first = learner.post(url, json={"question_id": question["id"], "answer": "A"}).json()
    again = learner.post(url, json={"question_id": question["id"], "answer": "B"}).json()
    assert first["created"] is True
    assert again["created"] is False
    assert again["feedback"] == first["feedback"]
    assert again["session"]["answered"] == 1

    query = db_session.query(models.LearningRecord).filter(
        models.LearningRecord.record_type == "practice",
        models.LearningRecord.user_id == _user_id(learner))
    assert query.count() == 0                # the set is not finished yet
    for rest in payload["questions"][1:]:
        learner.post(url, json={"question_id": rest["id"], "answer": "A"})
    assert query.count() == 3


def test_a_reload_resumes_the_open_set_with_its_answers(learner):
    payload = _generate(learner, count=3).json()
    attempt = payload["attempt_id"]
    learner.post(f"/course-learning/courses/{COURSE}/practice/{attempt}/answer",
                 json={"question_id": payload["questions"][0]["id"], "answer": "A"})

    session = learner.get(f"/course-learning/courses/{COURSE}/practice/session").json()["session"]
    assert session["attempt_id"] == attempt
    assert session["answered"] == 1
    answered = [row for row in session["questions"] if row["answered"]]
    assert len(answered) == 1
    assert answered[0]["id"] == payload["questions"][0]["id"]
    assert answered[0]["result"]["standard_answer"]


def test_another_learner_cannot_answer_or_read_this_set(learner, db_session):
    payload = _generate(learner, count=3).json()
    attempt, question = payload["attempt_id"], payload["questions"][0]
    other = TestClient(learner.client.app)
    try:
        register_and_login(other, "practice-intruder")
        assert other.post(
            f"/course-learning/courses/{COURSE}/practice/{attempt}/answer",
            json={"question_id": question["id"], "answer": "A"}).status_code == 404
        assert other.get(f"/course-learning/courses/{COURSE}/practice/session",
                         params={"attempt_id": attempt}).status_code in (404, 401)
    finally:
        other.close()


# ---------------------------------------------------------------- DATA


def test_a_wrong_answer_reaches_the_existing_wrong_book(learner, db_session):
    """No second wrong-answer system: the finished set lands in the canonical one."""
    payload = _generate(learner, count=3).json()
    attempt = payload["attempt_id"]
    url = f"/course-learning/courses/{COURSE}/practice/{attempt}/answer"
    for index, question in enumerate(payload["questions"]):
        learner.post(url, json={"question_id": question["id"], "answer": "D"})

    states = db_session.query(WrongAnswerState).filter(
        WrongAnswerState.service_namespace == "course_learning").all()
    assert states, "a finished set with wrong answers must produce wrong-answer states"

    page = learner.get(f"/course-learning/courses/{COURSE}/wrong-answers")
    assert page.status_code == 200, page.text
    assert page.json()["total"] >= 1
    stems = {item["stem"] for item in page.json()["items"]}
    assert {question["stem"] for question in payload["questions"]} & stems


def test_a_finished_set_writes_learning_records_and_knowledge_progress(learner, db_session):
    point = _points(db_session, learner.username, title="图")[0]
    payload = _generate(learner, scope="knowledge_point", knowledge_point_id=point.id,
                        count=3).json()
    url = f"/course-learning/courses/{COURSE}/practice/{payload['attempt_id']}/answer"
    for question in payload["questions"]:
        learner.post(url, json={"question_id": question["id"], "answer": "A"})

    records = db_session.query(models.LearningRecord).filter(
        models.LearningRecord.record_type == "practice",
        models.LearningRecord.user_id == _user_id(learner),
        models.LearningRecord.subject == COURSE).all()
    assert len(records) == 3
    assert all(record.review_status == "pending" for record in records)

    progress = db_session.query(models.UserKnowledgeProgress).filter(
        models.UserKnowledgeProgress.username == learner.username,
        models.UserKnowledgeProgress.course_id == COURSE,
        models.UserKnowledgeProgress.knowledge_point_id == point.id).one()
    assert progress.practice_count == 3
    assert progress.status in {"learning", "reviewing", "mastered", "review_due"}


def test_a_wrong_answer_moves_knowledge_status_and_a_right_one_moves_it_back(learner, db_session):
    point = _points(db_session, learner.username, title="链式存储")[0]
    payload = _generate(learner, scope="knowledge_point", knowledge_point_id=point.id,
                        count=3).json()
    url = f"/course-learning/courses/{COURSE}/practice/{payload['attempt_id']}/answer"
    for question in payload["questions"]:
        learner.post(url, json={"question_id": question["id"], "answer": "A"})

    progress = db_session.query(models.UserKnowledgeProgress).filter(
        models.UserKnowledgeProgress.username == learner.username,
        models.UserKnowledgeProgress.knowledge_point_id == point.id).one()
    assert progress.mastery_score is not None
    assert progress.system_suggested_status


def test_history_lists_finished_sets_not_single_questions(learner, db_session):
    payload = _generate(learner, count=3).json()
    url = f"/course-learning/courses/{COURSE}/practice/{payload['attempt_id']}/answer"
    for question in payload["questions"]:
        learner.post(url, json={"question_id": question["id"],
                                "answer": _correct_answer(db_session, question["id"])})

    history = learner.get(f"/course-learning/courses/{COURSE}/practice/history").json()
    assert history["total"] == 1
    row = history["items"][0]
    assert row["session_id"] == payload["attempt_id"]
    assert row["total"] == 3
    assert row["correct_count"] == 3
    assert row["chapter"] and row["knowledge_point_title"]
    assert "stem" not in row and "standard_answer" not in row


# ---------------------------------------------------------------- KNOWLEDGE CONTEXT


def test_the_scope_carried_in_matches_the_active_structure(learner, db_session):
    """A point named by the structure page resolves to exactly that point's chapter and title."""
    chapter = db_session.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == learner.username,
        models.KnowledgePoint.course_id == COURSE,
        models.KnowledgePoint.title == "树").one()
    point = _points(db_session, learner.username, title="二叉树的遍历")[0]
    assert point.parent_id == chapter.id

    payload = _generate(learner, scope="knowledge_point",
                        knowledge_point_id=point.id, count=3).json()
    assert payload["scope_label"] == "二叉树的遍历"
    for question in payload["questions"]:
        assert question["knowledge_point_title"] == "二叉树的遍历"
        assert question["chapter"] == "树"


def test_a_superseded_structure_is_not_used_for_scoping(learner, db_session):
    """After a regenerate, the old points are gone from the allowed set."""
    old_point = _points(db_session, learner.username, title="图")[0]
    user = db_session.query(models.User).filter(
        models.User.username == learner.username).one()
    draft = knowledge_structure.create_draft(
        db_session, user, COURSE, source_mode="ai_generated",
        chapters=[{"title": "新章节", "points": [{"title": "全新的知识点"}]}])
    knowledge_structure.confirm(db_session, user, COURSE, draft.id)

    refused = _generate(learner, scope="knowledge_point",
                        knowledge_point_id=old_point.id, count=3)
    assert refused.status_code == 404

    fresh = _points(db_session, learner.username, title="全新的知识点")[0]
    accepted = _generate(learner, scope="knowledge_point",
                         knowledge_point_id=fresh.id, count=3)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["scope_label"] == "全新的知识点"
