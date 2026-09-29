"""Which task kinds a plan may contain — one answer, enforced at every writer.

WHY THIS FILE EXISTS
--------------------
`ExamStudyPlanTask` is one table shared by three learning spaces, and its `task_type` used to be
validated by four independent lists that did not agree: the course creation endpoint allowed
`knowledge` / `review`, the programming endpoint its own four, the exam endpoint allowed anything
at all, and the plan-adjustment path allowed `knowledge` / `review` / `practice` / `custom` for
every space — so a plan adjustment could file a `practice` task into a course plan, which the
course endpoint itself would have refused and, worse, which nothing could ever complete.

These tests hold the closure: the vocabularies live in ONE place
(`learning.spaces.plan_task_types`), every creation route enforces its own space's vocabulary,
plan adjustment enforces the same vocabulary for the plan it is adjusting, and — for the two
spaces whose completion is derived — every accepted kind is one the completion engine can
actually finish.
"""
import inspect
import itertools
import re

from conftest import grant_unified_tier, register_and_login

import main
from learning.spaces.plan_task_types import (COURSE_LEARNING_TASK_TYPES, EXAM_PREP_TASK_TYPES,
                                             PROGRAMMING_TASK_TYPES, PLAN_TASK_TYPES_BY_NAMESPACE,
                                             plan_task_types)

# The suite shares one temp database for the whole session, so a fixed learner name would collide
# with a sibling test's registration. Every test registers its own.
_NAMES = itertools.count(1)


def _new_learner(client, db_session) -> str:
    name = f"e2e_ttc_{next(_NAMES)}"
    register_and_login(client, name)
    grant_unified_tier(db_session, name, "standard")
    return name

COURSE = "数据结构"
EXAM_MODULE = "data_structure"
COURSE_TASKS = "/course-learning/study-plan/tasks"
PROGRAMMING_TASKS = "/programming/plan/tasks"
PROPOSE = "/ai/plan-adjustment"
APPLY = "/ai/plan-adjustment/apply"

# A kind that legitimately exists in ANOTHER space — the leak each endpoint must still refuse.
FOREIGN_TYPE = "chapter_practice"
# Kinds no space has a completion rule for. These are the drift this closure removed.
DEAD_TYPES = ("practice", "custom")


def _exam_tasks(module: str = EXAM_MODULE) -> str:
    return f"/exam/11408/subjects/{module}/study-plan/tasks"


def _course_task(client, username: str, **overrides) -> tuple[int, dict]:
    payload = {"username": username, "subject_key": COURSE, "title": "契约任务",
               "scope_type": "all", "task_type": "knowledge"}
    payload.update(overrides)
    response = client.post(COURSE_TASKS, json=payload)
    return response.status_code, (response.json() if response.content else {})


# ================================================================ 1. one definition

def test_every_space_has_one_vocabulary_and_an_unknown_space_has_none():
    assert PLAN_TASK_TYPES_BY_NAMESPACE == {
        "course_learning": COURSE_LEARNING_TASK_TYPES,
        "exam_prep": EXAM_PREP_TASK_TYPES,
        "programming": PROGRAMMING_TASK_TYPES,
    }
    assert plan_task_types("course_learning") == COURSE_LEARNING_TASK_TYPES
    assert plan_task_types("exam_prep") == EXAM_PREP_TASK_TYPES
    assert plan_task_types("programming") == PROGRAMMING_TASK_TYPES
    # An unknown space owns nothing, so nothing can be written for it.
    assert plan_task_types("nope") == ()
    assert plan_task_types("") == ()


def test_no_space_offers_a_task_kind_that_cannot_be_completed():
    """The predicate that would have caught the drift, read off the completion engine itself.

    Course and exam plan status is DERIVED by ``main._compute_task_completion``; a kind with no
    branch there is a task no learner action can ever finish. (Programming is excluded: its plan
    carries a real status column its own endpoint writes, so it does not use that engine.)
    """
    source = inspect.getsource(main._compute_task_completion)
    completable = set(re.findall(r'task_type == "([a-z_]+)"', source))
    assert completable == {"knowledge", "chapter_practice", "review"}, completable
    for space in ("course_learning", "exam_prep"):
        unknown = set(plan_task_types(space)) - completable
        assert not unknown, f"{space} accepts incompletable kinds: {sorted(unknown)}"


def test_no_space_offers_the_dead_kinds():
    for space, types in PLAN_TASK_TYPES_BY_NAMESPACE.items():
        for dead in DEAD_TYPES:
            assert dead not in types, f"{space} still accepts {dead}"


def test_chapter_practice_belongs_to_exam_prep_alone():
    assert FOREIGN_TYPE in EXAM_PREP_TASK_TYPES
    assert FOREIGN_TYPE not in COURSE_LEARNING_TASK_TYPES
    assert FOREIGN_TYPE not in PROGRAMMING_TASK_TYPES


# ================================================================ 2. the course route

def test_the_course_route_accepts_its_own_vocabulary(client, db_session):
    username = _new_learner(client, db_session)

    for task_type in COURSE_LEARNING_TASK_TYPES:
        status, body = _course_task(client, username, task_type=task_type,
                                    title=f"契约-{task_type}")
        assert status == 200, f"{task_type}: {body}"
        assert body["task"]["task_type"] == task_type


def test_the_course_route_refuses_kinds_it_does_not_own(client, db_session):
    username = _new_learner(client, db_session)

    # The two that used to be reachable only through plan adjustment
    for dead in DEAD_TYPES:
        status, body = _course_task(client, username, task_type=dead, title=f"非法-{dead}")
        assert status == 400, f"{dead} was accepted: {body}"
        assert "task_type" in str(body)

    # …and the kind that exists in another space keeps its own named refusal
    status, body = _course_task(client, username, task_type=FOREIGN_TYPE, title="非法-章节练习")
    assert status == 400
    assert "chapter_practice is not available for course learning" in body["detail"]

    # nothing was written by any of the refusals
    from models import ExamStudyPlanTask
    db_session.expire_all()
    titles = {row.title for row in db_session.query(ExamStudyPlanTask)
              .filter(ExamStudyPlanTask.username == username).all()}
    assert not {f"非法-{dead}" for dead in DEAD_TYPES} & titles
    assert "非法-章节练习" not in titles


# ================================================================ 3. the exam route

def test_the_exam_route_accepts_its_own_vocabulary_and_refuses_the_rest(client, db_session):
    username = _new_learner(client, db_session)

    for task_type in EXAM_PREP_TASK_TYPES:
        response = client.post(_exam_tasks(), json={
            "username": username, "subject_key": EXAM_MODULE,
            "title": f"考试-{task_type}", "scope_type": "all", "task_type": task_type,
            "due_date": "2026-10-01"})
        assert response.status_code == 200, f"{task_type}: {response.text}"

    for dead in DEAD_TYPES:
        response = client.post(_exam_tasks(), json={
            "username": username, "subject_key": EXAM_MODULE,
            "title": f"非法-{dead}", "scope_type": "all", "task_type": dead,
            "due_date": "2026-10-01"})
        assert response.status_code == 400, f"{dead} was accepted: {response.text}"


def test_the_update_paths_enforce_the_same_vocabulary_as_creation(client, db_session):
    """An EDIT must not reach a kind the creation endpoint would have refused."""
    username = _new_learner(client, db_session)

    status, body = _course_task(client, username, title="可编辑任务")
    assert status == 200
    task_id = body["task"]["id"]

    patch = client.patch(f"{COURSE_TASKS}/{task_id}", json={
        "username": username, "subject_key": COURSE, "task_type": "review"})
    assert patch.status_code == 200, patch.text
    assert patch.json()["task"]["task_type"] == "review"

    for dead in DEAD_TYPES:
        refused = client.patch(f"{COURSE_TASKS}/{task_id}", json={
            "username": username, "subject_key": COURSE, "task_type": dead})
        assert refused.status_code == 400, f"{dead} was accepted: {refused.text}"

    foreign = client.patch(f"{COURSE_TASKS}/{task_id}", json={
        "username": username, "subject_key": COURSE, "task_type": FOREIGN_TYPE})
    assert foreign.status_code == 400
    assert "chapter_practice is not available for course learning" in foreign.json()["detail"]

    # the exam update path, which previously accepted anything at all
    created = client.post(_exam_tasks(), json={
        "username": username, "subject_key": EXAM_MODULE, "title": "可编辑考试任务",
        "scope_type": "all", "task_type": "knowledge", "due_date": "2026-10-01"})
    assert created.status_code == 200, created.text
    exam_task_id = created.json()["task"]["id"]

    ok = client.patch(f"{_exam_tasks()}/{exam_task_id}", json={
        "username": username, "subject_key": EXAM_MODULE, "task_type": FOREIGN_TYPE})
    assert ok.status_code == 200, ok.text
    for dead in DEAD_TYPES:
        refused = client.patch(f"{_exam_tasks()}/{exam_task_id}", json={
            "username": username, "subject_key": EXAM_MODULE, "task_type": dead})
        assert refused.status_code == 400, f"{dead} was accepted: {refused.text}"


# ================================================================ 4. the programming route

def test_the_programming_route_keeps_its_own_vocabulary(client, db_session):
    _new_learner(client, db_session)

    for task_type in PROGRAMMING_TASK_TYPES:
        response = client.post(PROGRAMMING_TASKS, json={
            "title": f"编程-{task_type}", "task_type": task_type, "language": "Python"})
        assert response.status_code == 200, f"{task_type}: {response.text}"

    for refused in DEAD_TYPES + (FOREIGN_TYPE,):
        response = client.post(PROGRAMMING_TASKS, json={
            "title": f"非法-{refused}", "task_type": refused, "language": "Python"})
        assert response.status_code == 400, f"{refused} was accepted: {response.text}"


# ================================================================ 5. plan adjustment

def _propose(client, monkeypatch, changes, *, service_key="course_learning", **scope):
    import dataclasses
    import json

    from ai.providers import FakeProvider

    content = json.dumps({"changes": changes}, ensure_ascii=False)

    class _Provider(FakeProvider):
        def complete(self, spec):
            return dataclasses.replace(super().complete(spec), content=content)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        lambda name: _Provider(provider=name))
    payload = {"service_key": service_key, "goal": "按当前进度调整", **scope}
    return client.post(PROPOSE, json=payload)


def test_a_course_proposal_cannot_file_a_kind_the_course_plan_cannot_hold(
        client, db_session, monkeypatch):
    username = _new_learner(client, db_session)
    from models import ExamStudyPlanTask
    import main as main_module

    key = main_module._course_learning_task_subject_key(COURSE)
    task = ExamStudyPlanTask(username=username, subject_key=key, title="契约任务",
                             task_type="knowledge", status="not_started", due_date="2026-12-31")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    body = _propose(client, monkeypatch, [
        {"op": "create_task", "title": "不该出现的练习", "task_type": "practice",
         "due_date": "2026-09-30"},
        {"op": "create_task", "title": "不该出现的自定义", "task_type": "custom",
         "due_date": "2026-09-30"},
        {"op": "update_task", "task_id": task.id, "due_date": "2026-09-30"},
    ], course_id=COURSE).json()

    # only the legal change survives, and the refusals say which kind was refused
    assert [change["type"] for change in body["proposed_changes"]] == ["RESCHEDULE"]
    refused = {item.get("task_type") for item in body["dropped_changes"]
               if item["reason"] == "task_type_not_supported_in_space"}
    assert refused == set(DEAD_TYPES)

    applied = client.post(APPLY, json={
        "service_key": "course_learning", "course_id": COURSE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"]})
    assert applied.status_code == 200, applied.text

    db_session.expire_all()
    titles = {row.title for row in db_session.query(ExamStudyPlanTask)
              .filter(ExamStudyPlanTask.username == username).all()}
    assert "不该出现的练习" not in titles
    assert "不该出现的自定义" not in titles


def test_an_exam_proposal_may_file_a_chapter_practice_task(client, db_session, monkeypatch):
    """The kind the course space refuses is exactly the kind the exam space owns."""
    username = _new_learner(client, db_session)

    body = _propose(client, monkeypatch, [
        {"op": "create_task", "title": "章节练习任务", "task_type": FOREIGN_TYPE,
         "due_date": "2026-09-30"},
    ], service_key="exam_11408", exam_module_id=EXAM_MODULE).json()

    assert [change["type"] for change in body["proposed_changes"]] == ["INSERT"]
    assert body["proposed_changes"][0]["task_type"] == FOREIGN_TYPE
    assert not [item for item in body["dropped_changes"]
                if item["reason"] == "task_type_not_supported_in_space"]

    applied = client.post(APPLY, json={
        "service_key": "exam_11408", "exam_module_id": EXAM_MODULE,
        "plan_identity": body["plan_identity"],
        "proposed_changes": body["proposed_changes"]})
    assert applied.status_code == 200, applied.text

    from models import ExamStudyPlanTask
    db_session.expire_all()
    created = (db_session.query(ExamStudyPlanTask)
               .filter(ExamStudyPlanTask.username == username,
                       ExamStudyPlanTask.title == "章节练习任务").one())
    assert created.task_type == FOREIGN_TYPE


def test_the_proposal_prompt_names_the_space_vocabulary(client, db_session, monkeypatch):
    """The model is TOLD the space's kinds, so it cannot propose one that will be refused."""
    from prompts import plan_adjustment_system_prompt

    assert "knowledge|review" in plan_adjustment_system_prompt(COURSE_LEARNING_TASK_TYPES)
    assert ("knowledge|chapter_practice|review"
            in plan_adjustment_system_prompt(EXAM_PREP_TASK_TYPES))
    for dead in DEAD_TYPES:
        prompt = plan_adjustment_system_prompt(COURSE_LEARNING_TASK_TYPES)
        assert f'"{dead}"' not in prompt
