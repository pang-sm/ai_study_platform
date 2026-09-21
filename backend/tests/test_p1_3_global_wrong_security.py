"""THREE_DOMAIN_PRODUCTIZATION_P1_3 — global wrong-answer content resolution.

WHAT THESE TESTS HOLD
---------------------
The global ``GET /wrong-answers`` surface serves EVERY learning space, and before P1.3 it
rendered every state through the EXAM resolver: a course question was read with the exam
space's rules, and the exam resolver resolved content from a BARE primary key — an id that
another learner's row (or another table's row) could equally well own.

P1.3 makes content resolution fail-closed everywhere:

1. the global surface DISPATCHES by namespace: a course state is rendered by the course
   resolver (which verifies owner + course + declared table), an exam state by the exam
   resolver;
2. an AI-generated exam question must belong to the state's OWN learner and to the state's own
   MODULE — another learner's question and another subject's question both resolve to nothing;
3. public exam-bank content still resolves (it is public teaching material, not learner data),
   but only when it is proven public (or the caller's own) and of this state's module;
4. an id that two sources claim for DIFFERENT questions is AMBIGUOUS and resolves to nothing —
   no source is preferred, and no lookup falls through to a second table because the first one
   missed;
5. a state that cannot prove its owner fails closed;
6. P1.2's course semantics are unchanged and still green.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import json
from datetime import datetime

from conftest import register_and_login

from core.learning_context import LearningContext, ServiceNamespace
from learning.practice import service as practice_service
from learning.practice.refs import QuestionRef, QuestionSourceType
from learning.spaces.course_learning.context import build_course_context
from learning.wrong_answers import project as wrong_project
from learning.wrong_answers import service as wrong_service
from learning.wrong_answers.models import WrongAnswerState
from learning.wrong_answers.project import past_exam_scope
from models import (AIGeneratedQuestion, CourseLearningPreference, ExamQuestionBank, User)

GLOBAL_WRONG = "/wrong-answers"
COURSE = "数据结构"
MODULE = "operating_system"
OTHER_MODULE = "computer_network"
MOMENT = datetime(2026, 9, 20, 7, 0, 0)


# ---------------------------------------------------------------- helpers

def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _own_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))
    db.commit()


def _exam_context(user, module=MODULE) -> LearningContext:
    return LearningContext(user_id=user.id, service_namespace=ServiceNamespace.EXAM_PREP,
                           subject_key=module, exam_subject_id="cs_408",
                           exam_module_id=module)


def _exam_state(db, user, *, source_type, qid, module=MODULE, source_id=None):
    """One real exam attempt through the Practice Core (which projects the state)."""
    context = _exam_context(user, module)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "exam_prep", source_type="p13_test",
        source_session_key=f"p13:{module}", mode="p13", context=context, started_at=None)
    ref = QuestionRef(source_type=source_type, source_id=str(qid),
                      service_namespace=ServiceNamespace.EXAM_PREP,
                      context={"subject_key": module, "exam_subject_id": "cs_408",
                               "exam_module_id": module})
    return practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity(
            "p13_attempt", source_id or f"{module}:{qid}", f"{qid}:0")).attempt


def _ai_question(db, username, *, qid=None, module=MODULE, stem, answer="A"):
    row = AIGeneratedQuestion(
        id=qid, username=username, subject_key=module, subject_name=module,
        question_type="选择题", stem=stem,
        options_json=json.dumps({"A": "甲", "B": "乙"}, ensure_ascii=False),
        standard_answer=answer, analysis=f"{stem} 的解析", difficulty="基础",
        quality_status="unchecked", generation_mode="ai")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _bank_question(db, *, qid=None, module=MODULE, stem, answer="A", number=None,
                   source_type="chapter", year=None, visibility="public", owner=None):
    row = ExamQuestionBank(
        id=qid, subject_key=module, subject_name=module, source_type=source_type,
        year=year, question_number=number, question_type="choice", stem=stem,
        options_json=json.dumps({"A": "甲", "B": "乙"}, ensure_ascii=False),
        standard_answer=answer, analysis=f"{stem} 的解析", difficulty="基础",
        visibility=visibility, owner_username=owner, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _listed(client, namespace=None) -> list[dict]:
    params = {"service_namespace": namespace} if namespace else {}
    response = client.get(GLOBAL_WRONG, params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _only(client, namespace=None) -> dict:
    items = _listed(client, namespace)
    assert len(items) == 1, items
    return items[0]


def _detail(client, state_id) -> dict:
    response = client.get(f"{GLOBAL_WRONG}/{state_id}")
    assert response.status_code == 200, response.text
    return response.json()


# ================================================================ 1. AI questions (owner/context)


def test_the_global_route_cannot_show_another_learners_ai_question(client, db_session):
    register_and_login(client, "p13_stranger")
    stranger_question = _ai_question(db_session, "p13_stranger", stem="陌生人的 AI 题面")

    register_and_login(client, "p13_owner")
    owner = _user(db_session, "p13_owner")
    _exam_state(db_session, owner, source_type=QuestionSourceType.AI_GENERATED,
                qid=stranger_question.id)

    record = _only(client, "exam_11408")
    assert record["stem"] == ""
    assert record["reference_answer"] == ""
    assert "陌生人的 AI 题面" not in json.dumps(record, ensure_ascii=False)

    detail = _detail(client, record["wrong_record_id"])
    assert detail["stem"] == ""
    assert "陌生人的 AI 题面" not in json.dumps(detail, ensure_ascii=False)
    # the FACT is intact: the learner's own answer and the state survive
    assert detail["user_answer"] == "B"
    assert detail["status"] == "active"


def test_an_exam_ai_question_must_belong_to_the_states_module(client, db_session):
    register_and_login(client, "p13_module")
    owner = _user(db_session, "p13_module")

    # the SAME question id cannot be filed under two modules — the module is a filter
    # dimension, not part of the state identity — so the two cases are two questions.
    foreign = _ai_question(db_session, "p13_module", module=OTHER_MODULE,
                           stem="计算机网络题面")
    own = _ai_question(db_session, "p13_module", module=MODULE, stem="操作系统题面", answer="B")

    # a question of ANOTHER subject, filed under this state's module
    _exam_state(db_session, owner, source_type=QuestionSourceType.AI_GENERATED,
                qid=foreign.id, module=MODULE, source_id="wrong-module")
    # …and this module's own question
    _exam_state(db_session, owner, source_type=QuestionSourceType.AI_GENERATED,
                qid=own.id, module=MODULE, source_id="right-module")

    states = {state.question_source_id: state.id for state in
              db_session.query(WrongAnswerState).filter(
                  WrongAnswerState.user_id == owner.id).all()}
    items = {item["wrong_record_id"]: item for item in _listed(client, "exam_11408")}
    assert items[states[str(foreign.id)]]["stem"] == ""            # another subject → refused
    assert items[states[str(own.id)]]["stem"] == "操作系统题面"     # its own module → resolved


def test_a_state_without_an_owner_resolves_nothing(client, db_session):
    """A legacy state that cannot prove whose question it points at fails closed."""
    register_and_login(client, "p13_no_owner")
    owner = _user(db_session, "p13_no_owner")
    question = _ai_question(db_session, "p13_no_owner", stem="没有归属的题面")

    # a legacy-only state: no facts, and no username recorded on the row
    state = wrong_project.recompute(
        db_session, user_id=owner.id, service_namespace="exam_prep",
        question_source_type=QuestionSourceType.AI_GENERATED.value,
        question_source_id=str(question.id), question_scope_key="",
        legacy={"source_type": "exam_wrong_question", "source_id": 1})
    assert state is not None
    db_session.refresh(state)
    assert not (state.username or "").strip()

    record = _only(client, "exam_11408")
    assert record["stem"] == ""
    assert record["question_bank_id"] is None
    assert "没有归属的题面" not in json.dumps(record, ensure_ascii=False)


# ================================================================ 2. public bank content


def test_public_bank_content_still_resolves_but_foreign_private_does_not(client, db_session):
    register_and_login(client, "p13_bank")
    owner = _user(db_session, "p13_bank")

    public_row = _bank_question(db_session, stem="公开题库题面", answer="A")
    private_row = _bank_question(db_session, stem="别人的私有题库题面", answer="B",
                                 visibility="private", owner="someone_else")

    _exam_state(db_session, owner, source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                qid=public_row.id, source_id="public")
    _exam_state(db_session, owner, source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                qid=private_row.id, source_id="private")

    by_id = {item["question_bank_id"]: item for item in _listed(client, "exam_11408")}
    assert set(by_id) == {public_row.id, private_row.id}

    resolved = by_id[public_row.id]
    assert resolved["stem"] == "公开题库题面"
    assert resolved["reference_answer"] == "A"
    assert resolved["source_kind"] == "chapter_practice"

    refused = by_id[private_row.id]
    assert refused["stem"] == ""
    assert "别人的私有题库题面" not in json.dumps(refused, ensure_ascii=False)


def test_a_bank_row_of_another_module_is_not_shown(client, db_session):
    register_and_login(client, "p13_bank_module")
    owner = _user(db_session, "p13_bank_module")
    foreign = _bank_question(db_session, module=OTHER_MODULE, stem="别的模块的题库题面")
    _exam_state(db_session, owner, source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                qid=foreign.id, module=MODULE)

    record = _only(client, "exam_11408")
    assert record["stem"] == ""
    assert "别的模块的题库题面" not in json.dumps(record, ensure_ascii=False)


# ================================================================ 3. no source switching


def test_a_colliding_id_across_tables_cannot_switch_source(client, db_session):
    """The same number in ``ai_generated_questions`` and ``exam_question_bank``.

    Each declared source reads its OWN table: the AI state shows the AI question, the bank
    state shows the bank question, and neither can be made to show the other's content.
    """
    register_and_login(client, "p13_collide")
    owner = _user(db_session, "p13_collide")
    colliding_id = 970101
    _ai_question(db_session, "p13_collide", qid=colliding_id, stem="AI 表题面")
    _bank_question(db_session, qid=colliding_id, stem="题库表题面")

    _exam_state(db_session, owner, source_type=QuestionSourceType.AI_GENERATED,
                qid=colliding_id, source_id="ai-side")
    _exam_state(db_session, owner, source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                qid=colliding_id, source_id="bank-side")

    by_kind = {item["source_kind"]: item for item in _listed(client, "exam_11408")}
    assert set(by_kind) == {"ai_generated", "chapter_practice"}
    assert by_kind["ai_generated"]["stem"] == "AI 表题面"
    assert by_kind["chapter_practice"]["stem"] == "题库表题面"
    # the bank identity is only reported by the bank state
    assert by_kind["ai_generated"]["question_bank_id"] is None
    assert by_kind["chapter_practice"]["question_bank_id"] == colliding_id


def test_a_legacy_past_paper_id_two_sources_disagree_about_fails_closed(
        client, db_session, monkeypatch):
    """An id that names DIFFERENT questions in the bank and the document corpus.

    (The document corpus is stubbed so the two sources provably share one id — the case the
    resolver must refuse rather than prefer one of them.)
    """
    import exam_past_paper

    register_and_login(client, "p13_past_paper")
    owner = _user(db_session, "p13_past_paper")
    bank_row = _bank_question(db_session, stem="题库来源题面", answer="B",
                              number=9, source_type="past_paper", year=2022)
    shared_id = str(bank_row.id)
    # the SAME id in the document source, naming a DIFFERENT public question (number 7)
    monkeypatch.setattr(exam_past_paper, "document_questions",
                        lambda subject_key, year: [{
                            "id": shared_id, "number": 7, "type": "选择题",
                            "stem": "文档来源题面", "options": {"A": "甲", "B": "乙"},
                            "answer": "A", "analysis": "文档解析"}])

    scope = past_exam_scope(exam_subject_id="cs_408", exam_module_id=MODULE,
                            question_year=2022)
    state = wrong_project.recompute(
        db_session, user_id=owner.id, service_namespace="exam_prep",
        question_source_type=QuestionSourceType.PAST_EXAM.value,
        question_source_id=shared_id, question_scope_key=scope,
        legacy={"source_type": "past_paper_wrong_question", "source_id": 1},
        username=owner.username)
    assert state is not None

    record = _only(client, "exam_11408")
    assert record["stem"] == ""
    assert record["reference_answer"] == ""
    assert record["question_number"] is None
    assert "题库来源题面" not in json.dumps(record, ensure_ascii=False)
    assert "文档来源题面" not in json.dumps(record, ensure_ascii=False)


# ================================================================ 4. course states on the global route


def test_a_course_state_is_rendered_by_the_course_resolver(client, db_session):
    """The dispatch, observed through the fields only the course resolver fills."""
    register_and_login(client, "p13_course_dispatch")
    owner = _user(db_session, "p13_course_dispatch")
    _own_course(db_session, owner.username)
    question = _ai_question(db_session, "p13_course_dispatch", module=COURSE,
                            stem="课程 AI 题面", answer="A")

    context = build_course_context(owner, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db_session, owner, "course_learning", source_type="p13_course",
        source_session_key="p13:course", mode="p13", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db_session, owner, session, ref, answer="C", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p13_course_attempt", "course-1", "1:0"))

    record = _only(client, "course_learning")
    assert record["service_namespace"] == "course_learning"
    assert record["source_kind"] == "ai_generated"
    assert record["course_id"] == COURSE                 # course resolver semantics
    assert record["module_key"] == "" and record["module_name"] == ""
    assert record["stem"] == "课程 AI 题面"
    assert record["reference_answer"] == "A"
    assert record["question_id"] == question.id          # the course redo identity
    assert record["question_bank_id"] is None and record["year"] is None

    # the detail and the manual lifecycle routes dispatch the same way
    detail = _detail(client, record["wrong_record_id"])
    assert detail["course_id"] == COURSE
    assert detail["attempt_history"][-1]["correct"] is False
    patched = client.patch(f"{GLOBAL_WRONG}/{record['wrong_record_id']}",
                           json={"resolved": True})
    assert patched.status_code == 200, patched.text
    assert patched.json()["course_id"] == COURSE


def test_a_course_state_pointing_at_an_exam_question_resolves_nothing(client, db_session):
    """Cross-space content stays refused even on the union surface."""
    register_and_login(client, "p13_cross_space")
    owner = _user(db_session, "p13_cross_space")
    _own_course(db_session, owner.username)
    exam_question = _ai_question(db_session, "p13_cross_space", module=MODULE,
                                 stem="考试空间题面")

    context = build_course_context(owner, course_id=COURSE)
    session, _ = practice_service.ensure_legacy_session(
        db_session, owner, "course_learning", source_type="p13_cross",
        source_session_key="p13:cross", mode="p13", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(exam_question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": COURSE})
    practice_service.record_attempt(
        db_session, owner, session, ref, answer="C", correct=False, submitted_at=MOMENT,
        context=context,
        source=practice_service.SourceIdentity("p13_cross_attempt", "cross-1", "1:0"))

    record = _only(client, "course_learning")
    assert record["course_id"] == COURSE
    assert record["stem"] == ""
    assert "考试空间题面" not in json.dumps(record, ensure_ascii=False)
