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
    # What the learner reads is derived from the plan, not narrated by the model: a headline, a
    # reason built from stored numbers, and a counted impact.
    assert body["summary"]
    assert body["rationale"]
    assert body["can_apply"] is True
    assert body["impact"]["inserted"] == 1
    assert body["impact"]["rescheduled"] == 1
    assert body["evidence"], "a plan with an overdue task has something real to cite"
    assert all(item["metric"] > 0 for item in body["evidence"])
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


# ================================================ 4. what a change MEANS, and its diff

def _propose_body(client, monkeypatch, changes, **overrides):
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(changes))
    response = _propose(client, **overrides)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_move_carries_its_before_from_the_plan_and_its_meaning_from_the_mutation(
        client, db_session, monkeypatch):
    """RESCHEDULE / INSERT are DERIVED. `before` is the plan's own value, never the model's."""
    register_and_login(client, "p3b_plan_types")
    grant_unified_tier(db_session, "p3b_plan_types", "standard")
    user = _user(db_session, "p3b_plan_types")
    task = _task(db_session, user.username, title="进程调度复习", due_date="2026-10-05")

    body = _propose_body(client, monkeypatch, [
        {"op": "update_task", "task_id": task.id, "due_date": "2026-09-30"},
        {"op": "create_task", "title": "进程调度专项练习", "task_type": "practice",
         "due_date": "2026-09-30"}])

    moved, added = body["proposed_changes"]
    assert moved["type"] == "RESCHEDULE"
    assert moved["field"] == "due_date"
    assert moved["direction"] == "earlier"
    assert moved["task_title"] == "进程调度复习"
    assert moved["before"] == "2026-10-05"          # read from the plan, not from the model
    assert moved["after"] == "2026-09-30"
    assert moved["op"] == "update_task"             # the mutation apply will run

    assert added["type"] == "INSERT"
    assert added["op"] == "create_task"
    assert added["after"] == "2026-09-30"

    assert set(body["adjustment_types"]) == {"RESCHEDULE", "INSERT", "INCREASE_LOAD"}
    # The headline names the first change in the learner's own words.
    assert "进程调度复习" in body["summary"]
    assert "提前" in body["summary"]


def test_a_title_change_is_a_replace_with_both_titles(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_replace")
    grant_unified_tier(db_session, "p3b_plan_replace", "standard")
    user = _user(db_session, "p3b_plan_replace")
    task = _task(db_session, user.username, title="完成章节阅读")

    body = _propose_body(client, monkeypatch, [
        {"op": "update_task", "task_id": task.id, "title": "完成对应练习"}])

    change = body["proposed_changes"][0]
    assert change["type"] == "REPLACE"
    assert change["field"] == "title"
    assert change["before"] == "完成章节阅读"
    assert change["after"] == "完成对应练习"
    assert "REPLACE" in body["adjustment_types"]


def test_a_change_that_changes_nothing_is_never_shown(client, db_session, monkeypatch):
    """A model that "reschedules" a task to the date it already holds has proposed nothing."""
    register_and_login(client, "p3b_plan_noop")
    grant_unified_tier(db_session, "p3b_plan_noop", "standard")
    user = _user(db_session, "p3b_plan_noop")
    task = _task(db_session, user.username, title="无变化任务", due_date="2026-09-01")

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "update_task", "task_id": task.id, "due_date": "2026-09-01"}]))
    refused = _propose(client)
    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"]["code"] == "empty_proposal"


def test_a_suggestion_cannot_write_learner_progress(client, db_session, monkeypatch):
    """`status` is a claim about what the learner HAS DONE. A planner may not make it."""
    register_and_login(client, "p3b_plan_status")
    grant_unified_tier(db_session, "p3b_plan_status", "standard")
    user = _user(db_session, "p3b_plan_status")
    task = _task(db_session, user.username, title="进度任务", status="not_started")

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "update_task", "task_id": task.id, "status": "completed"}]))
    refused = _propose(client)
    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"]["code"] == "empty_proposal"
    assert _task_state(db_session, task.id)[2] == "not_started"


# ================================================ 5. unsupported kinds are refused

def test_remove_and_reorder_are_refused_by_name(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_unsupported")
    grant_unified_tier(db_session, "p3b_plan_unsupported", "standard")
    user = _user(db_session, "p3b_plan_unsupported")
    keep = _task(db_session, user.username, title="保留任务")
    remove_me = _task(db_session, user.username, title="不该被删除")

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "remove_task", "task_id": remove_me.id},
         {"op": "reorder_tasks", "task_id": keep.id},
         {"op": "update_task", "task_id": keep.id, "due_date": "2026-09-29"}]))
    body = _propose(client).json()

    # only the supported change survives
    assert [change["task_id"] for change in body["proposed_changes"]] == [keep.id]
    refused = {item.get("adjustment_type") for item in body["dropped_changes"]
               if item["reason"] == "adjustment_type_not_supported"}
    assert refused == {"REMOVE", "REORDER"}
    assert "REMOVE" not in body["adjustment_types"]
    assert "REORDER" not in body["adjustment_types"]

    # …and applying writes exactly that one change, with the task still present
    applied = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"]})
    assert applied.status_code == 200, applied.text
    assert _task_state(db_session, remove_me.id)[0] == "不该被删除"
    assert _task_state(db_session, keep.id)[1] == "2026-09-29"


def test_a_proposal_of_only_unsupported_changes_is_refused(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_only_unsupported")
    grant_unified_tier(db_session, "p3b_plan_only_unsupported", "standard")
    user = _user(db_session, "p3b_plan_only_unsupported")
    task = _task(db_session, user.username, title="任务")

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider(
        [{"op": "remove_task", "task_id": task.id},
         {"op": "reorder_tasks", "task_id": task.id}]))
    refused = _propose(client)
    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"]["code"] == "empty_proposal"
    assert _task_state(db_session, task.id)[0] == "任务"


# ================================================ 6. the write matches the preview

def test_apply_writes_exactly_the_change_that_was_displayed(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_exact")
    grant_unified_tier(db_session, "p3b_plan_exact", "standard")
    user = _user(db_session, "p3b_plan_exact")
    task = _task(db_session, user.username, title="精确任务", due_date="2026-10-05")

    body = _propose_body(client, monkeypatch, [
        {"op": "update_task", "task_id": task.id, "due_date": "2026-09-30"}])
    displayed = body["proposed_changes"][0]
    assert displayed["before"] == "2026-10-05"

    # A client that lies about `before` cannot change what is written: apply re-reads the plan.
    tampered = dict(displayed)
    tampered["before"] = "1999-01-01"
    applied = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": [tampered]})
    assert applied.status_code == 200, applied.text
    # the write is the DISPLAYED `after`, and nothing else moved
    assert _task_state(db_session, task.id) == ("精确任务", "2026-09-30", "not_started",
                                                _plan_key())


def test_applying_the_same_proposal_twice_cannot_double_write(client, db_session, monkeypatch):
    """The plan identity is the guard: after the first apply the proposal is stale by definition."""
    register_and_login(client, "p3b_plan_twice")
    grant_unified_tier(db_session, "p3b_plan_twice", "standard")
    user = _user(db_session, "p3b_plan_twice")
    task = _task(db_session, user.username, title="幂等任务", due_date="2026-10-05")

    body = _propose_body(client, monkeypatch, [
        {"op": "create_task", "title": "一次性新增", "task_type": "review",
         "due_date": "2026-09-30"},
        {"op": "update_task", "task_id": task.id, "due_date": "2026-09-30"}])
    payload = {"service_key": "course_learning", "course_id": COURSE,
               "plan_identity": body["plan_identity"],
               "proposed_changes": body["proposed_changes"],
               "proposal_id": body["proposal_id"]}

    first = client.post(APPLY, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["applied_count"] == 2

    second = client.post(APPLY, json=payload)
    assert second.status_code == 409, second.text
    assert second.json()["detail"]["code"] == "stale_proposal"

    db_session.expire_all()
    titles = [row.title for row in db_session.query(ExamStudyPlanTask)
              .filter(ExamStudyPlanTask.username == user.username).all()]
    assert titles.count("一次性新增") == 1, "a replayed apply must not insert a second copy"


def _raw_provider(content: str):
    """A provider seam that answers with exactly this text, whatever it is."""
    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, provider=name)
    return _make


def test_an_unusable_proposal_never_reaches_the_plan(client, db_session, monkeypatch):
    register_and_login(client, "p3b_plan_unusable")
    grant_unified_tier(db_session, "p3b_plan_unusable", "standard")
    user = _user(db_session, "p3b_plan_unusable")
    task = _task(db_session, user.username, title="安全任务", due_date="2026-10-05")
    before = _task_state(db_session, task.id)

    # a model that answered with prose instead of JSON is unusable, and says so
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        _raw_provider("这是一段自然语言，没有 JSON"))
    unusable = _propose(client)
    assert unusable.status_code == 400, unusable.text
    assert unusable.json()["detail"]["code"] == "unusable_proposal"

    # JSON, but with nothing this endpoint can act on: a non-list, an empty list, and a task that
    # is not in this plan.
    for content in ('{"changes": "不是数组"}', '{"changes": []}',
                    '{"changes": [{"op": "update_task", "task_id": 999999,'
                    ' "due_date": "2026-09-30"}]}',
                    '{"changes": [{"op": "update_task", "task_id": null}]}'):
        monkeypatch.setattr("ai.orchestrator.default_provider_factory", _raw_provider(content))
        refused = _propose(client)
        assert refused.status_code == 400, f"{content} -> {refused.status_code}"
        assert refused.json()["detail"]["code"] == "empty_proposal"

    assert _task_state(db_session, task.id) == before


def test_keep_current_plan_leaves_no_trace_in_the_plan(client, db_session, monkeypatch):
    """Declining is not applying: a generated-then-dismissed suggestion writes nothing at all."""
    register_and_login(client, "p3b_plan_keep")
    grant_unified_tier(db_session, "p3b_plan_keep", "standard")
    user = _user(db_session, "p3b_plan_keep")
    task = _task(db_session, user.username, title="保留中", due_date="2026-10-05")

    own = lambda: {row.id: _task_state(db_session, row.id) for row in
                   db_session.query(ExamStudyPlanTask)
                   .filter(ExamStudyPlanTask.username == user.username).all()}
    before = own()

    _propose_body(client, monkeypatch, [
        {"op": "create_task", "title": "未采纳的新增", "task_type": "review",
         "due_date": "2026-09-30"},
        {"op": "update_task", "task_id": task.id, "due_date": "2026-09-30"}])

    assert own() == before

    from data_plane.models import LearningEvent
    db_session.expire_all()
    applied = (db_session.query(LearningEvent)
               .filter(LearningEvent.user_id == user.id,
                       LearningEvent.event_type == "plan_adjustment_applied").all())
    assert applied == []
