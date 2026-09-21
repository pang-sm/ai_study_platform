"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3B — Dynamic Planning.

WHAT THESE TESTS HOLD
---------------------
1. a PROPOSAL changes nothing: the plan is byte-identical after the AI has spoken;
2. only an explicit APPLY mutates, and only after re-verifying ownership and that the plan is
   still EXACTLY the plan the proposal was built from — a stale proposal is refused (409)
   instead of overwriting newer work;
3. the model can only touch THIS plan's tasks: a change aimed at another learner's task, or at
   another space's / another language's plan, is dropped rather than applied;
4. the capability follows the unified policy for the proposal, while APPLY needs no AI at all
   (it is a plan edit the learner asked for, gated by ownership and identity).

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json
from datetime import datetime

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import ExamStudyPlanTask, User

PROPOSE = "/ai/plan-adjustment"
APPLY = "/ai/plan-adjustment/apply"
COURSE = "数据结构"
MOMENT = datetime(2026, 9, 20, 7, 30, 0)


class _ScriptedProvider(FakeProvider):
    def __init__(self, content, capture=None, **kwargs):
        super().__init__(**kwargs)
        self._content = content
        self._capture = capture

    def complete(self, spec):
        if self._capture is not None:
            self._capture.append("\n".join(m.content for m in spec.messages))
        return dataclasses.replace(super().complete(spec), content=self._content)


def _provider(changes, *, reason="计划已逾期，先补上再复习", capture=None):
    content = json.dumps({"reason": reason, "changes": changes}, ensure_ascii=False)

    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, capture=capture, provider=name,
                                 input_tokens=150, output_tokens=120)
    return _make


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _plan_key(course_id=COURSE) -> str:
    import main
    return main._course_learning_task_subject_key(course_id)


def _task(db, username, *, title, status="not_started", due_date="2026-09-01",
          subject_key=None) -> ExamStudyPlanTask:
    row = ExamStudyPlanTask(username=username, subject_key=subject_key or _plan_key(),
                            title=title, task_type="knowledge", status=status,
                            due_date=due_date)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _propose(client, **overrides):
    payload = {"service_key": "course_learning", "course_id": COURSE}
    payload.update(overrides)
    return client.post(PROPOSE, json=payload)


def _task_state(db, task_id):
    # the request writes through its OWN session, so the test session must re-read
    db.expire_all()
    row = db.query(ExamStudyPlanTask).filter(ExamStudyPlanTask.id == task_id).one()
    return (row.title, row.due_date, row.status, row.subject_key)


# ================================================================ 1. propose mutates nothing


def test_the_proposal_does_not_mutate_the_plan(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_propose")
    grant_unified_tier(db_session, "p3b_plan_propose", "standard")
    user = _user(db_session, "p3b_plan_propose")
    overdue = _task(db_session, user.username, title="逾期任务", due_date="2026-09-01")
    done = _task(db_session, user.username, title="已完成", status="completed")

    def own_tasks():
        # the test DB is shared: only THIS learner's plan is being asserted
        db_session.expire_all()
        return {row.id: _task_state(db_session, row.id) for row in
                db_session.query(ExamStudyPlanTask)
                .filter(ExamStudyPlanTask.username == user.username).all()}

    before = own_tasks()

    captured: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "create_task", "title": "补做线性表练习", "task_type": "practice",
          "due_date": "2026-09-22", "reason": "逾期"},
         {"op": "update_task", "task_id": overdue.id, "due_date": "2026-09-23",
          "reason": "顺延"}],
        capture=captured))

    response = _propose(client, goal="先把逾期的补上")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["plan_identity"]
    assert body["subject_key"] == _plan_key()
    assert body["reason"]
    assert len(body["proposed_changes"]) == 2
    assert overdue.id in body["affected_tasks"]
    assert body["plan_snapshot"]["total"] == 2
    assert body["plan_snapshot"]["overdue"] == 1

    # NOTHING changed
    after = own_tasks()
    assert after == before
    assert len(after) == 2
    assert done.id in after

    # the model saw the real plan and the real facts, and only those
    assert captured and "逾期任务" in captured[0]
    assert str(overdue.id) in captured[0]


# ================================================================ 2. apply


def test_apply_refuses_a_foreign_or_wrong_identity(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_identity")
    grant_unified_tier(db_session, "p3b_plan_identity", "standard")
    user = _user(db_session, "p3b_plan_identity")
    task = _task(db_session, user.username, title="任务A")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "update_task", "task_id": task.id, "due_date": "2026-09-25", "reason": "顺延"}]))

    body = _propose(client).json()
    before = _task_state(db_session, task.id)

    wrong = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": "0" * 32,
        "proposed_changes": body["proposed_changes"]})
    assert wrong.status_code == 409, wrong.text
    assert wrong.json()["detail"]["code"] == "stale_proposal"
    assert _task_state(db_session, task.id) == before

    applied = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"],
        "proposal_id": body["proposal_id"]})
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["applied_count"] == 1
    assert result["plan_identity"] != body["plan_identity"]     # the plan moved
    assert _task_state(db_session, task.id)[1] == "2026-09-25"

    # the applied fact is canonical, with the proposal it realised
    from data_plane.models import LearningEvent
    db_session.expire_all()
    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == user.id,
                      LearningEvent.event_type == "plan_adjustment_applied").all())
    assert events
    payload = json.loads(events[0].item_snapshot_json)
    assert payload["proposal_id"] == body["proposal_id"]
    assert payload["applied_count"] == 1


def test_a_stale_proposal_is_rejected_after_the_plan_changes(client, db_session,
                                                            monkeypatch):
    register_and_login(client, "p3b_plan_stale")
    grant_unified_tier(db_session, "p3b_plan_stale", "standard")
    user = _user(db_session, "p3b_plan_stale")
    task = _task(db_session, user.username, title="任务B")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "create_task", "title": "新任务", "task_type": "review",
          "due_date": "2026-09-24", "reason": "复习"}]))

    body = _propose(client).json()

    # the learner changes the plan between propose and apply
    _task(db_session, user.username, title="临时加的任务")

    refused = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"]})
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "stale_proposal"
    # …and the newer work was NOT overwritten
    db_session.expire_all()
    titles = {row.title for row in db_session.query(ExamStudyPlanTask)
              .filter(ExamStudyPlanTask.username == user.username).all()}
    assert "新任务" not in titles
    assert "临时加的任务" in titles
    assert task is not None


def test_another_learners_task_cannot_be_touched(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_owner")
    grant_unified_tier(db_session, "p3b_plan_owner", "standard")
    other = _user(db_session, "p3b_plan_owner")
    foreign_task = _task(db_session, other.username, title="别人的任务")

    register_and_login(client, "p3b_plan_me")
    grant_unified_tier(db_session, "p3b_plan_me", "standard")
    me = _user(db_session, "p3b_plan_me")
    mine = _task(db_session, me.username, title="我的任务")

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "update_task", "task_id": foreign_task.id, "title": "被篡改",
          "reason": "越权"},
         {"op": "update_task", "task_id": mine.id, "due_date": "2026-09-26", "reason": "顺延"}]))

    body = _propose(client).json()
    assert [change["task_id"] for change in body["proposed_changes"]] == [mine.id]
    assert body["dropped_changes"][0]["reason"] == "task_not_in_this_plan"

    applied = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"]})
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied_count"] == 1

    # the other learner's task is untouched
    assert _task_state(db_session, foreign_task.id)[0] == "别人的任务"
    assert _task_state(db_session, mine.id)[1] == "2026-09-26"


def test_another_spaces_plan_is_not_in_this_plan(client, db_session, monkeypatch):
    """A programming-plan task is invisible to a course-plan proposal."""
    register_and_login(client, "p3b_plan_spaces")
    grant_unified_tier(db_session, "p3b_plan_spaces", "standard")
    user = _user(db_session, "p3b_plan_spaces")
    python_task = _task(db_session, user.username, title="Python 练习",
                        subject_key="programming:Python")
    course_task = _task(db_session, user.username, title="课程任务")

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "update_task", "task_id": python_task.id, "title": "越界修改", "reason": "x"},
         {"op": "update_task", "task_id": course_task.id, "due_date": "2026-09-27",
          "reason": "顺延"}]))

    body = _propose(client).json()
    snapshot_ids = [task["task_id"] for task in body["plan_snapshot"]["tasks"]]
    assert python_task.id not in snapshot_ids
    assert snapshot_ids == [course_task.id]
    assert [change["task_id"] for change in body["proposed_changes"]] == [course_task.id]

    applied = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"]})
    assert applied.status_code == 200, applied.text
    assert _task_state(db_session, python_task.id)[0] == "Python 练习"


# ================================================================ 3. capability policy


def test_proposing_follows_the_capability_policy_while_apply_does_not_need_ai(
        client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_free")
    user = _user(db_session, "p3b_plan_free")
    task = _task(db_session, user.username, title="免费档任务")
    calls: list[str] = []
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _provider([{"op": "update_task", "task_id": task.id,
                                    "due_date": "2026-09-28", "reason": "顺延"}],
                                  capture=calls))

    denied = _propose(client)
    assert denied.status_code == 403, denied.text
    assert calls == []

    grant_unified_tier(db_session, "p3b_plan_free", "standard")
    body = _propose(client).json()
    assert calls, "an allowed proposal really reaches the provider seam"

    # APPLY is a plan edit the learner asked for — no capability gate, ownership + identity
    applied = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"]})
    assert applied.status_code == 200, applied.text
    assert _task_state(db_session, task.id)[1] == "2026-09-28"
