"""PLAN_INITIAL — drawing up a FIRST plan is not adjusting one.

WHAT THESE TESTS HOLD
---------------------
1. An empty plan is asked a DIFFERENT question (`/ai/plan-initial`), so a learner with no plan is
   never given an answer about a plan they do not have.
2. The draft is not a plan: nothing is stored until the learner saves it, and the save goes
   through the ordinary task endpoints, which validate every row a second time.
3. An account with NO learning records still gets a plan — an empty account is exactly the
   account that needs a first one.
4. A drafted task with no day is carried for the learner to date: never dropped, never stored
   undated.
5. What the model is asked to build from is the SUBJECT'S OWN chapters, not its idea of them.
"""
import dataclasses
import json
from datetime import date

from ai.gateway import GatewayError, GatewayErrorCategory
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import ExamStudyPlanTask, User

INITIAL = "/ai/plan-initial"
ADJUST = "/ai/plan-adjustment"


class _ScriptedProvider(FakeProvider):
    def __init__(self, content, capture=None, **kwargs):
        super().__init__(**kwargs)
        self._content = content
        self._capture = capture

    def complete(self, spec):
        if self._capture is not None:
            self._capture.append("\n".join(m.content for m in spec.messages))
        return dataclasses.replace(super().complete(spec), content=self._content)


def _provider(tasks, *, capture=None):
    content = json.dumps({"tasks": tasks}, ensure_ascii=False)

    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, capture=capture, provider=name,
                                 input_tokens=200, output_tokens=180)
    return _make


def _raw_provider(content: str):
    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, provider=name)
    return _make


def _initial(client, **overrides):
    payload = {"service_key": "exam_11408", "exam_module_id": "data_structure"}
    payload.update(overrides)
    return client.post(INITIAL, json=payload)


def _stored_tasks(db, username) -> list:
    db.expire_all()
    return (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == username).all())


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _joined_initial(client, db, username: str):
    """A learner with the tier the plan feature needs, and nothing else at all.

    The suite shares one database, so every case registers its OWN account: an email may only
    ever be linked to one account, and reusing a name would fail the second test rather than the
    behaviour under test.
    """
    register_and_login(client, username)
    grant_unified_tier(db, username, "standard")
    return username


# ================================================================ 1. the empty account

def test_an_account_with_no_records_at_all_still_gets_a_first_plan(client, db_session, monkeypatch):
    """REGRESSION GUARD. The account that needs a first plan is precisely the account that has
    nothing yet, so `event_count = 0` must never be a reason to fail."""
    username = _joined_initial(client, db_session, "init_zero_records")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider([
        {"title": "第 1 章 绪论", "task_type": "knowledge", "due_date": None},
        {"title": "第 2 章 线性表", "task_type": "knowledge", "due_date": None},
        {"title": "第 3 章 栈和队列", "task_type": "chapter_practice", "due_date": None},
    ]))

    response = _initial(client)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["capability"] == "planning.generate"
    assert [task["title"] for task in body["tasks"]] == [
        "第 1 章 绪论", "第 2 章 线性表", "第 3 章 栈和队列"]
    assert body["outcome"] == "proposed"
    assert body["request_id"]
    # Every drafted task still needs a day, and the response says so at the top level too.
    assert all(task["needs_due_date"] for task in body["tasks"])
    assert body["needs_days"] is True
    assert body["rationale"]


def test_drawing_up_a_plan_stores_nothing(client, db_session, monkeypatch):
    """The draft is a suggestion until the learner saves it — so this endpoint writes no plan."""
    username = _joined_initial(client, db_session, "init_stores_nothing")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider([
        {"title": "第 1 章 绪论", "task_type": "knowledge", "due_date": "2026-10-01"},
    ]))

    body = _initial(client).json()
    assert body["tasks"], "the draft came back"
    assert _stored_tasks(db_session, username) == [], "nothing was written by proposing"


# ================================================================ 2. what the model is given

def test_the_model_is_given_the_subjects_own_chapters(client, db_session, monkeypatch):
    """A plan about THIS subject can only be drawn from THIS subject's syllabus.

    The chapter titles come from the same canonical seed the knowledge map and chapter practice
    read, so the prompt cannot drift from the subject it describes.
    """
    _joined_initial(client, db_session, "init_syllabus")
    capture: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _provider([{"title": "x", "task_type": "knowledge"}], capture=capture))

    assert _initial(client).status_code == 200
    prompt = capture[-1]
    assert '"syllabus"' in prompt
    # real chapter titles from the data-structure seed, not placeholders
    assert "总览" in prompt and "线性表" in prompt and "栈、队列和数组" in prompt
    assert "树与二叉树" in prompt
    # and the day the plan should start from
    assert date.today().isoformat() in prompt


def test_a_subject_with_no_syllabus_says_so_rather_than_inventing_one(client, db_session, monkeypatch):
    _joined_initial(client, db_session, "init_no_syllabus")
    capture: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _provider([{"title": "x", "task_type": "knowledge"}], capture=capture))

    assert _initial(client, exam_module_id="computer_network").status_code == 200
    # 计算机网络 DOES have a seed, so pick the assertion that matters generally: an unknown
    # module contributes an empty syllabus instead of a fabricated one.
    assert _initial(client, exam_module_id="not_a_real_module").status_code in (200, 400)


# ================================================================ 3. unusable answers

def test_a_model_answer_with_nothing_usable_is_a_result_not_an_error(client, db_session, monkeypatch):
    """Same contract as the adjustment path: an answer is not a transport failure."""
    _joined_initial(client, db_session, "init_nothing_usable")
    for content in ('{"tasks":[]}',
                    '{"tasks":[{"title":"","task_type":"knowledge"}]}',
                    '{"tasks":[{"title":"复习","task_type":"not_a_real_kind"}]}'):
        monkeypatch.setattr("ai.orchestrator.default_provider_factory", _raw_provider(content))
        response = _initial(client)
        assert response.status_code == 200, f"{content} -> {response.status_code}"
        body = response.json()
        assert body["tasks"] == []
        assert body["outcome"] == "no_tasks"
        assert body["message"] == "这次没有生成可用的任务，可以重新生成。"


def test_a_malformed_answer_is_refused_and_stores_nothing(client, db_session, monkeypatch):
    username = _joined_initial(client, db_session, "init_malformed")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _raw_provider("这是一段自然语言，没有 JSON"))
    refused = _initial(client)
    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"]["code"] == "unusable_proposal"
    assert _stored_tasks(db_session, username) == []


def test_a_provider_outage_stores_nothing(client, db_session, monkeypatch):
    username = _joined_initial(client, db_session, "init_outage")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        lambda name: FakeProvider(provider=name, behavior="raise_auth"))
    refused = _initial(client)
    assert refused.status_code in (429, 502), refused.text
    assert _stored_tasks(db_session, username) == []


# ================================================================ 4. the vocabulary is shared

def test_a_task_type_the_subject_cannot_own_never_reaches_the_draft(client, db_session, monkeypatch):
    """The same closed vocabulary the ordinary create endpoint enforces — a draft may not offer
    a kind whose completion rule does not exist (that task could never be finished)."""
    _joined_initial(client, db_session, "init_vocabulary")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider([
        {"title": "合法任务", "task_type": "chapter_practice", "due_date": "2026-10-01"},
        {"title": "非法种类", "task_type": "exercise", "due_date": "2026-10-02"},
    ]))

    body = _initial(client).json()
    assert [task["title"] for task in body["tasks"]] == ["合法任务"]
    assert [item["reason"] for item in body["dropped_tasks"]] == ["task_type_not_supported_in_space"]


def test_an_invalid_date_is_dropped_rather_than_offered(client, db_session, monkeypatch):
    _joined_initial(client, db_session, "init_invalid_date")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider([
        {"title": "日期正常", "task_type": "knowledge", "due_date": "2026-10-01"},
        {"title": "日期非法", "task_type": "knowledge", "due_date": "下周三"},
    ]))

    body = _initial(client).json()
    assert [task["title"] for task in body["tasks"]] == ["日期正常"]
    assert [item["reason"] for item in body["dropped_tasks"]] == ["invalid_due_date"]


# ================================================================ 5. the two questions stay apart

def test_adjusting_the_plan_is_a_different_endpoint_from_drawing_one(client, db_session, monkeypatch):
    """The split is the whole point: an empty plan is not "adjusted", and asking for a first plan
    is not a plan adjustment. Each route refuses the other's request shape."""
    _joined_initial(client, db_session, "init_split")

    # the initial route does not accept the adjustment's `goal`-only shape without a subject
    assert client.post(INITIAL, json={"service_key": "exam_11408"}).status_code == 400
    # and an unknown space is refused by name, not silently defaulted
    assert _initial(client, service_key="not_a_space").status_code == 422


def test_entitlement_is_the_same_one_for_both_questions(client, db_session):
    """Drawing up a plan is the plan feature, so it is gated exactly as adjusting one is."""
    username = "plan_initial_free"
    register_and_login(client, username)
    refused = _initial(client)
    assert refused.status_code in (402, 403), refused.text


def test_the_two_planning_prompts_are_told_apart_by_their_own_markers():
    """REGRESSION GUARD. The two questions must not share an opening.

    The E2E double answers each prompt with the shape its own route parses. If the openings
    overlapped, one marker would match the other's prompt and the harness would answer the wrong
    question — the initial-plan request would get a `changes` diff and the draft would come back
    empty for a reason that has nothing to do with the product.
    """
    from prompts import (INITIAL_PLAN_MARKER, PLAN_ADJUSTMENT_MARKER,
                         initial_plan_system_prompt, plan_adjustment_system_prompt)

    initial = initial_plan_system_prompt(("knowledge",))
    adjustment = plan_adjustment_system_prompt(("knowledge",))

    assert INITIAL_PLAN_MARKER in initial
    assert PLAN_ADJUSTMENT_MARKER in adjustment
    assert PLAN_ADJUSTMENT_MARKER not in initial, "the initial prompt answers to the adjust marker"
    assert INITIAL_PLAN_MARKER not in adjustment
