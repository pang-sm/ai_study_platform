"""ACCEL_PRODUCT_S9 PART B/C — canonical concept identity on chapter practice.

The product decision this file pins: when a learner reaches chapter practice FROM a
canonical knowledge leaf, the concept the product already knows must travel with the
attempt — into the canonical ``PracticeAttempt``, into the ``LearningEvent``, and out
through the KT dataset export — without being inferred and without being rewritten.

Five properties are asserted, each because the alternative is a fabricated fact:

  * PROPAGATION. A validated concept id on the attempt reaches the event's concept
    reference byte-for-byte, and the dataset groups the interaction under it.
  * REFUSAL. A value that is not a canonical leaf of the requested module is a 422 with a
    machine-readable code. It is never silently dropped, normalised or re-mapped.
  * CONSISTENCY. The question list and the write boundary share ONE predicate, so a set
    the product served can always be submitted, and a set that does not belong to the
    concept cannot be labelled with it.
  * NULL IS VALID. Direct entry, past papers and legacy attempts carry no canonical
    concept, and the absence is preserved rather than filled in.
  * NO INFERENCE. Nothing is derived from a title, a path, an array index or the question
    text — the ``computer_network`` chapter-4 numeric collision is the worked example.
"""
from __future__ import annotations

import json

import pytest
from conftest import register_and_login

import main as app_main
from data_plane.models import LearningEvent
from learning.records import native_concept
from learning.spaces.exam_prep.context import canonical_module_concept
from models import ExamQuestionBank, ExamWrongQuestion, ExamQuestionDoneRecord
from science import concept_coverage, kt_dataset

DS = "data_structure"
CN = "computer_network"

# `1.3` is a canonical leaf of operating_system and NOT of data_structure: the smallest
# provable "belongs to the wrong module" case.
OS_ONLY_LEAF = "1.3"
CN_COLLISION_STORED_ID = "4.2 路由与转发"


# ---------------------------------------------------------------- fixtures

def _seed_bank(db, subject_key=DS):
    """A deterministic chapter bank whose ids ARE canonical leaves of the module."""
    rows = [
        dict(knowledge_point_id="1.1", stem="第一章选择一", question_type="choice",
             standard_answer="A"),
        dict(knowledge_point_id="1.1", stem="第一章选择二", question_type="choice",
             standard_answer="B"),
        dict(knowledge_point_id="1.2", stem="第一章选择三", question_type="choice",
             standard_answer="A"),
        dict(knowledge_point_id="2.1", stem="第二章选择", question_type="choice",
             standard_answer="A"),
        # A sibling module's row, so a cross-module question set is expressible.
        dict(knowledge_point_id="1.1", stem="操作系统选择", question_type="choice",
             standard_answer="A", subject_key=OS_ONLY_MODULE),
        # A computer_network chapter-4 collision row: the stored id is NOT a canonical leaf.
        dict(knowledge_point_id=CN_COLLISION_STORED_ID, stem="网络第四章", question_type="choice",
             standard_answer="A", subject_key=CN),
    ]
    created = []
    for row in rows:
        row = dict(row)
        module = row.pop("subject_key", subject_key)
        item = ExamQuestionBank(
            subject_key=module, subject_name=module, source_type="chapter",
            visibility="public", options_json=json.dumps({"A": "甲", "B": "乙"}),
            analysis="", **row)
        db.add(item)
        created.append(item)
    db.commit()
    for item in created:
        db.refresh(item)
    return created


OS_ONLY_MODULE = "operating_system"
# `1.3` exists in operating_system and not in data_structure.
OS_ONLY_LEAF = "1.3"


@pytest.fixture
def bank(db_session):
    created = _seed_bank(db_session)
    ids = [q.id for q in created]
    try:
        yield {q.stem: q for q in created}
    finally:
        db_session.query(ExamWrongQuestion).filter(
            ExamWrongQuestion.question_bank_id.in_(ids)).delete(synchronize_session=False)
        db_session.query(ExamQuestionDoneRecord).filter(
            ExamQuestionDoneRecord.question_bank_id.in_(ids)).delete(synchronize_session=False)
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_(ids)).delete(synchronize_session=False)
        db_session.commit()


def _create(client, question_ids, module=DS, **extra):
    return client.post(f"/exam/11408/{module}/chapter-practice/attempts",
                       json={"question_ids": question_ids, **extra})


def _concept_ids(bank, module=DS, concept="1.1"):
    return [q.id for q in bank.values()
            if q.subject_key == module and q.knowledge_point_id == concept]


def _submit(client, attempt_id, answers, module=DS):
    return client.post(
        f"/exam/11408/{module}/chapter-practice/attempts/{attempt_id}/submit",
        json={"answers": answers})


def _events_for(db, user_id, question_ids):
    return (db.query(LearningEvent)
            .filter(LearningEvent.user_id == user_id,
                    LearningEvent.question_id.in_([str(q) for q in question_ids]))
            .all())


# ================================================================ the resolver gate

def test_canonical_module_concept_resolves_a_real_leaf_and_refuses_the_rest():
    """The mirror boundary's gate: canonical in, ``None`` for everything else."""
    assert canonical_module_concept(DS, "1.1") == "1.1"
    # the computer_network chapter-4 collision: a real stored id, a real title, NOT a leaf
    assert canonical_module_concept(CN, CN_COLLISION_STORED_ID) is None
    # a practice sub-group label from an older release
    assert canonical_module_concept(DS, "第一章 绪论") is None
    # absent / blank stay absent rather than becoming an empty concept
    assert canonical_module_concept(DS, None) is None
    assert canonical_module_concept(DS, "   ") is None
    # nothing is normalised into a leaf
    assert canonical_module_concept(DS, "1.1.1") is None


# ================================================================ PROPAGATION

def test_concept_id_propagates_leaf_to_attempt_to_event_to_dataset(client, db_session, bank):
    """The end-to-end product flow the sprint exists for."""
    register_and_login(client, "s9_propagate")
    ids = _concept_ids(bank)                       # exactly the questions of concept 1.1

    created = _create(client, ids, knowledge_point_id="1.1")
    assert created.status_code == 200, created.text
    attempt_id = created.json()["attempt_id"]

    # 1. the legacy attempt row holds the canonical concept verbatim
    from models import ExamPracticeAttempt
    legacy = db_session.query(ExamPracticeAttempt).filter(
        ExamPracticeAttempt.id == attempt_id).one()
    assert legacy.knowledge_point_id == "1.1"

    submitted = _submit(client, attempt_id, {str(ids[0]): "A", str(ids[1]): "B"})
    assert submitted.status_code == 200, submitted.text

    user_id = legacy_user_id(client)
    events = _events_for(db_session, user_id, ids)
    assert events, "the submission produced no learning events"

    # 2. every event carries the SAME concept id, and the module beside it
    for event in events:
        reference = native_concept.reference_from_event(event)
        assert reference.get("knowledge_point_id") == "1.1", reference
        assert reference.get("exam_module_id") == DS, reference
        assert native_concept.concept_key(reference) == "1.1"
        assert native_concept.concept_level(reference) == "knowledge_point_id"

    # 3. the canonical PracticeAttempt carries it too (its own context snapshot).
    #    Scoped to THIS learner: question-bank rowids are reused across test files, so an id
    #    alone does not identify a row.
    from learning.practice.models import PracticeAttempt
    canonical = (db_session.query(PracticeAttempt)
                 .filter(PracticeAttempt.user_id == user_id,
                         PracticeAttempt.question_source_id.in_([str(q) for q in ids]))
                 .all())
    assert canonical, "the submission was not mirrored into the Practice Core"
    for attempt in canonical:
        assert json.loads(attempt.context_json)["knowledge_point_id"] == "1.1"

    # 4. the KT dataset export groups the interactions under the same concept key.
    #    `concept_key` / `concept_level` belong to the SEQUENCE (the ordered interactions of
    #    one learner on one concept), which is the grouping the export exists to produce.
    body = kt_dataset.build(db_session, service_namespace="exam_prep")
    by_ref = {i["attempt_ref"]: (sequence, i)
              for sequence in body["sequences"] for i in sequence["interactions"]}
    for event in events:
        entry = by_ref.get(str(event.event_id))
        assert entry is not None, "the dataset dropped an eligible interaction"
        sequence, interaction = entry
        assert sequence["concept_key"] == "1.1"
        assert sequence["concept_level"] == "knowledge_point_id"
        assert interaction["exam_module_id"] == DS
        assert interaction["source_type"] == "exam_practice_attempt"
    assert body["concept_levels"].get("knowledge_point_id", 0) >= len(events)


def legacy_user_id(client):
    """The id of the learner `register_and_login` just created, read from the session."""
    body = client.get("/auth/me").json() if client.get("/auth/me").status_code == 200 else None
    if body and body.get("id") is not None:
        return body["id"]
    # fall back to the newest user, which is the one just registered in this test
    from database import SessionLocal
    from models import User
    session = SessionLocal()
    try:
        return session.query(User).order_by(User.id.desc()).first().id
    finally:
        session.close()


# ================================================================ REFUSAL

def test_a_concept_that_is_not_a_leaf_of_the_module_is_rejected(client, bank):
    register_and_login(client, "s9_bad_concept")
    ids = _concept_ids(bank)
    response = _create(client, ids, knowledge_point_id="9.9")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == app_main.CONCEPT_NOT_CANONICAL
    assert detail["concept_code"] == "9.9"
    # the identity is reported, never rewritten to something "close"
    assert "9.9" in detail["message"]


def test_a_concept_from_another_module_is_rejected(client, bank):
    """`1.3` is canonical for operating_system and not for data_structure."""
    register_and_login(client, "s9_wrong_module")
    assert OS_ONLY_LEAF in concept_coverage.load_module_concepts(OS_ONLY_MODULE)["concepts"]
    assert OS_ONLY_LEAF not in concept_coverage.load_module_concepts(DS)["concepts"]

    ids = _concept_ids(bank)
    response = _create(client, ids, module=DS, knowledge_point_id=OS_ONLY_LEAF)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == app_main.CONCEPT_NOT_CANONICAL


def test_a_question_set_that_does_not_belong_to_the_concept_is_rejected(client, bank):
    """Declaring 1.1 over questions of 1.2 would label them with a concept they lack."""
    register_and_login(client, "s9_inconsistent_set")
    ids = _concept_ids(bank) + _concept_ids(bank, concept="1.2")
    response = _create(client, ids, knowledge_point_id="1.1")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == app_main.CONCEPT_QUESTION_NOT_IN_SET
    assert detail["mismatched_question_ids"] == sorted(_concept_ids(bank, concept="1.2"))


def test_a_cross_module_question_set_is_rejected(client, bank):
    register_and_login(client, "s9_cross_module_set")
    foreign = [bank["操作系统选择"].id]
    response = _create(client, foreign, module=DS, knowledge_point_id="1.1")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == app_main.CONCEPT_QUESTION_MODULE_MISMATCH
    assert detail["other_modules"] == [OS_ONLY_MODULE]


def test_the_canonical_concept_filter_refuses_a_non_canonical_id(client, bank):
    """A GET must not answer "no questions" for an id that is not a concept at all."""
    register_and_login(client, "s9_filter_refuses")
    response = client.get(
        f"/exam/11408/{DS}/chapter-practice/questions",
        params={"chapter_code": "4", "concept_code": CN_COLLISION_STORED_ID})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == app_main.CONCEPT_NOT_CANONICAL


def test_the_canonical_concept_filter_serves_exactly_the_concepts_questions(client, bank):
    register_and_login(client, "s9_filter_serves")
    response = client.get(f"/exam/11408/{DS}/chapter-practice/questions",
                          params={"concept_code": "1.1"})
    assert response.status_code == 200
    body = response.json()
    served = {item["id"] for item in body["items"]}
    assert served == set(_concept_ids(bank))
    assert body["total"] == len(served)
    # the legacy sub-group filter is untouched and still answers its own ids
    legacy = client.get(f"/exam/11408/{DS}/chapter-practice/questions",
                        params={"knowledge_point_id": "1.2"})
    assert legacy.status_code == 200
    assert {i["id"] for i in legacy.json()["items"]} == set(_concept_ids(bank, concept="1.2"))


# ================================================================ NULL IS VALID

def test_direct_entry_keeps_the_concept_null_all_the_way_to_the_event(client, db_session, bank):
    register_and_login(client, "s9_direct_entry")
    ids = [q.id for q in bank.values() if q.subject_key == DS]
    created = _create(client, ids)                     # no concept declared
    assert created.status_code == 200
    attempt_id = created.json()["attempt_id"]

    from models import ExamPracticeAttempt
    legacy = db_session.query(ExamPracticeAttempt).filter(
        ExamPracticeAttempt.id == attempt_id).one()
    assert legacy.knowledge_point_id is None

    assert _submit(client, attempt_id, {str(ids[0]): "A"}).status_code == 200
    events = _events_for(db_session, legacy_user_id(client), ids)
    assert events
    for event in events:
        reference = native_concept.reference_from_event(event)
        # the module is known; the CONCEPT is honestly absent rather than filled in
        assert reference.get("exam_module_id") == DS
        assert "knowledge_point_id" not in reference
        assert native_concept.concept_key(reference) == DS
        assert native_concept.concept_level(reference) == "exam_module_id"


def test_a_legacy_attempt_with_a_non_canonical_id_gains_no_concept_reference(
        client, db_session, bank):
    """The pre-S9 written value is provenance; it must not become a concept key."""
    from learning.practice.adapters import exam as exam_adapter
    from models import ExamPracticeAttempt, User

    register_and_login(client, "s9_legacy_id")
    user = db_session.query(User).filter(
        User.id == legacy_user_id(client)).one()

    ids = [q.id for q in bank.values() if q.subject_key == DS and q.stem.startswith("第一章")]
    legacy = ExamPracticeAttempt(
        username=user.username, subject_key=DS, practice_type="chapter",
        source_type="chapter", status="submitted",
        # exactly what an older release could have stored
        knowledge_point_id="第一章 绪论", knowledge_point_name="第一章 绪论",
        knowledge_point_path="第一章",
        question_ids_json=json.dumps(ids), total_questions=len(ids),
        result_json=json.dumps({"results": [
            {"question_id": qid, "user_answer": "A", "correct": True,
             "question_type": "choice", "standard_answer": "A", "judge": None}
            for qid in ids]}),
    )
    db_session.add(legacy)
    db_session.commit()

    exam_adapter.mirror_exam_practice_attempt(db_session, user, legacy)

    events = _events_for(db_session, user.id, ids)
    assert events, "the legacy mirror produced no events"
    for event in events:
        reference = native_concept.reference_from_event(event)
        assert "knowledge_point_id" not in reference
        assert native_concept.concept_key(reference) == DS


def test_no_concept_is_ever_inferred_from_a_title_path_or_index(client, db_session, bank):
    """The stored TITLE of a canonical leaf is not an identity the write path accepts.

    The knowledge tree publishes both a `code` and a `title`, and the resolver CAN recover a
    question-bank row whose identity column happens to hold the title verbatim (that is the
    S8 recovery rule). The WRITE boundary is stricter on purpose: a client declares a
    concept by CODE only, so a display string — a title, a path, a sequence position — can
    never silently become an identity.
    """
    register_and_login(client, "s9_no_title_inference")
    titles = concept_coverage.load_module_concepts(DS)["titles"]
    # the TITLE of leaf 1.1 — the string the resolver itself recovers a BANK ROW from
    leaf_title = next(t for t, code in sorted(titles.items()) if code == "1.1")
    assert titles[leaf_title] == "1.1"

    ids = _concept_ids(bank)
    for display_only in (leaf_title, "第一章 / 数据结构的基本概念", "0", "1"):
        response = _create(client, ids, knowledge_point_id=display_only,
                           knowledge_point_name=leaf_title,
                           knowledge_point_path="第一章 / 数据结构的基本概念")
        assert response.status_code == 422, display_only
        assert response.json()["detail"]["code"] == app_main.CONCEPT_NOT_CANONICAL

    # the NAME and PATH themselves are stored as given, and resolve to nothing
    accepted = _create(client, ids, knowledge_point_name=leaf_title,
                       knowledge_point_path="第一章 / 数据结构的基本概念")
    assert accepted.status_code == 200
    from models import ExamPracticeAttempt
    row = db_session.query(ExamPracticeAttempt).filter(
        ExamPracticeAttempt.id == accepted.json()["attempt_id"]).one()
    assert row.knowledge_point_id is None              # a display string is not an identity
    assert row.knowledge_point_name == leaf_title      # ... and is preserved as display


def test_computer_network_chapter4_collision_rows_still_carry_no_concept(db_session, bank):
    """The collision S8 refused is still refused — at the identity level, not just the matcher."""
    collision = bank["网络第四章"]
    assert app_main._question_carries_concept(collision, "4.2") is False
    assert app_main._question_canonical_leaf_codes(collision) == ()
    assert canonical_module_concept(CN, collision.knowledge_point_id) is None


# ================================================================ PART D — content re-key

@pytest.fixture
def cn_rows(db_session):
    """A computer_network bank carrying the real chapter-4 collision shape, plus one leaf."""
    rows = [
        # canonical: the stored id IS the leaf code
        dict(knowledge_point_id="3.6", source_ref="chapter:3:3.6", stem="网络3.6"),
        # the collision: the source's own 4.x numbering against canonical 4.x
        dict(knowledge_point_id=CN_COLLISION_STORED_ID, source_ref="chapter:4:4.2", stem="网络4.2"),
        # the source's numbering runs past the canonical chapter's 7 leaves
        dict(knowledge_point_id="4.10 IPv4 地址", source_ref="chapter:4:4.10",
             stem="网络4.10"),
        # a past-paper row with no concept at all
        dict(knowledge_point_id=None, source_ref=None, stem="网络真题",
             source_type="past_paper"),
    ]
    created = []
    for row in rows:
        row = dict(row)
        item = ExamQuestionBank(
            subject_key=CN, subject_name=CN,
            source_type=row.pop("source_type", "chapter"), visibility="public",
            options_json=json.dumps({"A": "甲", "B": "乙"}), analysis="", **row)
        db_session.add(item)
        created.append(item)
    db_session.commit()
    for item in created:
        db_session.refresh(item)
    ids = [q.id for q in created]
    try:
        yield {q.stem: q for q in created}
    finally:
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_(ids)).delete(synchronize_session=False)
        db_session.commit()


def test_the_rekey_report_finds_no_provable_mapping_for_computer_network(db_session, cn_rows):
    """PART D: the collision stays refused, and the report PROVES nothing is provable.

    The report is a whole-MODULE measurement, so the per-row assertions below are scoped to
    the rows this test created (by question id) — another test file's bank rows are also
    active in the shared database and are not this test's subject. The headline claim
    (``provable_rekeys == 0``) is deliberately NOT scoped: it is the whole module's answer,
    and a leak that could produce a provable re-key would be exactly what we want to catch.
    """
    report = concept_coverage.unresolved_identity_report(db_session, CN)
    # the headline: no row of this module can be re-keyed from the content it stores
    assert report["provable_rekeys"] == 0
    assert all(record["candidate"] is None for record in report["records"])
    assert all(record["provable"] is False for record in report["records"])

    mine = {q.id for q in cn_rows.values()}
    records = {record["question_id"]: record for record in report["records"]
               if record["question_id"] in mine}
    assert len(records) == len(cn_rows) - 1        # the canonical 3.6 row is not in the report
    by_stem = {record["stored_source_identity"]: record for record in records.values()}

    # the collision is reported at its true chapter and refused a concept
    collision = by_stem[CN_COLLISION_STORED_ID]
    assert collision["current_chapter"] == "4"
    assert collision["current_level"] == "chapter"
    assert collision["near_match_leaf_code"] == "4.2"          # the shape a lax rule accepts
    assert collision["reason"] == concept_coverage.UNRESOLVED_NOT_A_LEAF
    # a source point numbering past the canonical chapter is NOT a near-match at all
    assert by_stem["4.10 IPv4 地址"]["near_match_leaf_code"] is None
    # a row with no concept is reported as empty, not as unresolved identity
    assert by_stem[None]["reason"] == concept_coverage.UNRESOLVED_NO_CODE
    assert by_stem[None]["current_level"] == "module_only"


def test_the_rekey_report_writes_nothing(db_session, cn_rows):
    """PART D: a content re-key is a content decision, and this report never takes it."""
    before = {(q.id, q.knowledge_point_id, q.source_ref)
              for q in db_session.query(ExamQuestionBank).all()}
    concept_coverage.unresolved_identity_report(db_session, CN)
    db_session.expire_all()
    after = {(q.id, q.knowledge_point_id, q.source_ref)
             for q in db_session.query(ExamQuestionBank).all()}
    assert before == after


def test_the_rekey_report_carries_no_model_and_no_learner_data(db_session, cn_rows):
    report = concept_coverage.unresolved_identity_report(db_session, CN)
    blob = json.dumps(report, ensure_ascii=False)
    semantics = report["candidate_semantics"]
    assert "no model" in semantics and "no fuzzy match" in semantics
    assert "no title similarity" in semantics and "no positional inference" in semantics
    # the report describes IDENTITIES, never content or learners
    assert "stem" not in blob and "answer" not in blob and "username" not in blob


def test_the_shared_chapter_rule_agrees_with_the_served_question_list(db_session, cn_rows):
    """The chapter read off a stored id is ONE rule, used by the audit and by the list.

    They are deliberately not one FUNCTION, and the difference is pinned here rather than
    left to be discovered:

      * `main._question_chapter_code` additionally consults the row's JSON
        ``source_ref.chapter_id`` metadata, which a served question may carry, and answers
        ``""`` for "no chapter";
      * ``chapter_of_stored_id`` reads the stored code's own leading segment and falls back
        to a ``chapter:<n>:<code>`` provenance triple, and answers ``None``.

    On every row that carries a stored code they must name the SAME chapter — that is the
    rule both implement — and on a row with no identity both must report "no chapter".
    """
    for item in db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.subject_key == CN).all():
        from_audit = concept_coverage.chapter_of_stored_id(
            CN, item.knowledge_point_id, item.source_ref)
        from_api = app_main._question_chapter_code(item)
        if (item.knowledge_point_id or "").strip():
            assert from_audit == from_api, (item.stem, from_audit, from_api)
        else:
            assert not from_audit and not from_api        # both say "no chapter"


def test_the_canonical_filter_shares_one_predicate_with_the_write_boundary(db_session, cn_rows):
    """The list a learner is served can always be submitted — the predicate is one function."""
    from science import concept_coverage as cc
    concept = "3.6"
    for item in cn_rows.values():
        listed = app_main._question_carries_concept(item, concept)
        resolved = cc.canonical_leaf_code(CN, knowledge_point_id=item.knowledge_point_id,
                                          source_ref=item.source_ref)
        assert listed == (resolved == concept)


# ================================================================ the recorded stream

def _event(db, user, event_id, *, module=DS, concept=None, correct=True, qid=None):
    """One canonical event written through the real model, with the reference under test."""
    ref = {"exam_module_id": module} if module else {}
    if concept is not None:
        ref["knowledge_point_id"] = concept
    ev = LearningEvent(
        event_id=event_id, event_schema_version=2, event_type="question_answered",
        event_granularity="ITEM_LEVEL", source_type="exam_practice_attempt",
        source_attempt_id=f"att-{event_id}", source_item_key=f"{qid or event_id}:0",
        source_item_index=0, user_id=user.id, source_user_ref=user.username,
        service_key="exam_prep", course_id=None, subject_key="cs_408",
        question_id=qid or event_id,
        knowledge_point_ref_json=json.dumps(ref),
        item_snapshot_json=json.dumps({"question_id": qid or event_id}),
        item_content_hash="h", answer="A", correct=correct, score=None,
        response_time_ms=None, attempt_no=None, response_time_source=None,
        attempt_index=None, occurred_at=1000.0, ingested_at=1000.0,
        source_payload_version=1, idempotency_key=f"s9:{event_id}",
        snapshot_capture_mode="LIVE_EMITTER", snapshot_completeness="FULL",
        snapshot_missing_fields_json="[]")
    db.add(ev)
    return ev


def test_interaction_coverage_splits_concept_level_by_canonical_identity(db_session):
    """The measurement Part C needs: what a CONCEPT-level model could actually train on."""
    from models import User

    user = User(username="s9_coverage", hashed_password="x", grade="freshman", major="cs")
    db_session.add(user)
    db_session.commit()

    _event(db_session, user, "s9c-canonical", concept="1.1")           # real leaf
    _event(db_session, user, "s9c-module-only", concept=None)          # module scope
    _event(db_session, user, "s9c-noncanonical", concept="第一章 绪论")  # legacy sub-group
    _event(db_session, user, "s9c-collision", module=CN,
           concept=CN_COLLISION_STORED_ID)                            # CN chapter-4 collision
    _event(db_session, user, "s9c-unanswered", concept="1.1", correct=None)
    db_session.commit()

    # Scoped to THIS learner: the report is a whole-stream measurement, and this test's
    # subject is the rule, not the rest of the suite's fixtures.
    report = kt_dataset.interaction_coverage(db_session, service_namespace="exam_prep",
                                            user_id=user.id)
    totals = report["totals"]

    # `concept_level_before` is the PRE-S9 reading: any stored id counted as a concept key.
    # Three events reach the level counting — the ungraded one is excluded BEFORE it, because
    # an item with no verdict is not a label at any granularity.
    assert totals["concept_level_before"] == 3
    # `concept_level_after` is what a concept-level model may actually consume.
    assert totals["concept_level_after"] == 1
    assert totals["non_canonical_concept_ids"] == 2
    assert totals["module_level"] == 1
    # an ungraded item is not a label, at either level
    assert report["excluded"][kt_dataset.EXCLUDED_NOT_BINARY] == 1
    assert report["eligible_interactions"] == 2          # 1 module + 1 canonical concept

    # the identities are LISTED rather than silently reinterpreted
    listed = {(row["exam_module_id"], row["stored_knowledge_point_id"])
              for row in report["non_canonical_concept_ids"]}
    assert (DS, "第一章 绪论") in listed
    assert (CN, CN_COLLISION_STORED_ID) in listed
    assert report["users_with_eligible_interactions"] == 1
    assert report["users_with_events"] == 1
    assert report["collection_start_version"]
    # no content and no learner identity leaks into the report
    blob = json.dumps(report, ensure_ascii=False)
    assert "s9_coverage" not in blob and "@example.test" not in blob


def test_interaction_coverage_on_an_empty_stream_reports_zero_not_a_guess(db_session):
    """The honest report when the product has recorded nothing yet."""
    report = kt_dataset.interaction_coverage(db_session, service_namespace="exam_prep",
                                             user_id=-1)
    assert report["events_scanned"] == 0
    assert report["totals"]["concept_level_before"] == 0
    assert report["totals"]["concept_level_after"] == 0
    assert report["eligible_interactions"] == 0
    assert report["users_with_events"] == 0
    assert report["per_module"] == {}
    assert report["non_canonical_concept_ids"] == []


# ================================================================ PART E / F

def test_no_hint_count_field_exists_on_any_fact():
    """F: the product has no hint mechanism, so no zero-valued field is created for one."""
    from learning.practice.models import PracticeAttempt
    from learning.practice import telemetry

    columns = {c.name for c in PracticeAttempt.__table__.columns}
    assert "hint_count" not in columns
    assert telemetry.HINT_NO_MECHANISM in telemetry.HINT_SOURCE_VALUES
    assert telemetry.AttemptTelemetry().hint_count is None
    # the rule that a zero must never be substituted for "not observed"
    with pytest.raises(ValueError):
        telemetry.AttemptTelemetry(hint_count=0, hint_source=telemetry.HINT_NO_MECHANISM)


def test_response_time_stays_unobserved_because_no_serve_boundary_is_recorded(
        client, db_session, bank):
    """E: a duration needs two real boundaries; if the product records none, it records NULL."""
    from learning.practice.models import PracticeAttempt
    from learning.practice import telemetry

    register_and_login(client, "s9_timing")
    ids = _concept_ids(bank)
    attempt_id = _create(client, ids, knowledge_point_id="1.1").json()["attempt_id"]
    assert _submit(client, attempt_id, {str(ids[0]): "A"}).status_code == 200

    mirrored = (db_session.query(PracticeAttempt)
                .filter(PracticeAttempt.question_source_id == str(ids[0])).all())
    assert mirrored
    for attempt in mirrored:
        assert attempt.response_time_ms is None
        assert attempt.response_time_source is None
    events = _events_for(db_session, legacy_user_id(client), ids)
    assert events
    for event in events:
        assert event.response_time_ms is None
        assert event.response_time_source is None
    # and the contract still PROHIBITS the derivations a convenience would reach for
    assert "created_at - submitted_at" in telemetry.DURATION_FORBIDDEN_DERIVATIONS
    assert telemetry.DURATION_UNAVAILABLE in telemetry.DURATION_SOURCE_VALUES


def test_the_timing_boundary_audit_matches_what_the_surface_actually_does(client, db_session, bank):
    """PART E: the refusal is a measured property of the request path, not an omission.

    Asserted against the REAL handlers so the audit cannot quietly become false: the surface
    serves a whole set in one response and receives a whole set in one submission, so the two
    boundaries a per-item duration would need do not exist.
    """
    from learning.practice import telemetry

    audit = telemetry.PER_QUESTION_TIMING_BOUNDARY_AUDIT
    assert audit["answer"] == "NO"
    assert audit["boundaries"]["per_item_serve"]["present"] is False
    assert audit["boundaries"]["per_item_submit"]["present"] is False
    assert audit["boundaries"]["attempt_serve"]["present"] is True

    register_and_login(client, "s9_timing_audit")
    ids = _concept_ids(bank)
    created = _create(client, ids, knowledge_point_id="1.1")
    assert created.status_code == 200
    attempt_id = created.json()["attempt_id"]

    # one response carried EVERY item — there is no per-item serve request to timestamp
    served = client.get(f"/exam/11408/{DS}/chapter-practice/questions",
                        params={"concept_code": "1.1"}).json()
    assert len(served["items"]) == len(ids) > 1

    # the attempt's own boundaries ARE recorded, which is why the span is refused rather
    # than merely unavailable
    from models import ExamPracticeAttempt
    row = db_session.query(ExamPracticeAttempt).filter(
        ExamPracticeAttempt.id == attempt_id).one()
    assert row.started_at is not None          # serve boundary, at INSERT
    assert row.submitted_at is None            # not submitted yet
    # and the span is NOT written anywhere as a duration
    assert attempt_id and "attempt_duration" not in {
        c.name for c in ExamPracticeAttempt.__table__.columns}


def test_an_abandoned_attempt_yields_no_duration_and_no_second_submission(
        client, db_session, bank):
    """PART E edge cases: an unfinished attempt has no span, and a repeat submit cannot
    double-count it."""
    register_and_login(client, "s9_abandoned")
    ids = _concept_ids(bank)
    attempt_id = _create(client, ids, knowledge_point_id="1.1").json()["attempt_id"]

    # abandoned: served, never submitted → no submitted_at, so no span exists at all
    from models import ExamPracticeAttempt
    row = db_session.query(ExamPracticeAttempt).filter(
        ExamPracticeAttempt.id == attempt_id).one()
    assert row.status == "in_progress" and row.submitted_at is None

    assert _submit(client, attempt_id, {str(ids[0]): "A"}).status_code == 200
    db_session.expire_all()
    after_first = db_session.query(ExamPracticeAttempt).filter(
        ExamPracticeAttempt.id == attempt_id).one()
    assert after_first.submitted_at is not None

    # a second submission is refused by the in_progress guard, so nothing is recounted
    assert _submit(client, attempt_id, {str(ids[1]): "B"}).status_code == 404


def test_no_hint_field_exists_in_the_schema_or_the_migration():
    """PART F: a surface with no hint mechanism records NO count — not a zero."""
    from pathlib import Path

    from data_plane.models import LearningEvent
    from learning.practice.models import PracticeAttempt

    for model in (PracticeAttempt, LearningEvent):
        assert "hint_count" not in {c.name for c in model.__table__.columns}
        assert "hint_source" not in {c.name for c in model.__table__.columns}

    # the migration that added the telemetry columns deliberately added NO hint column. It
    # does MENTION hints — to record why there is none — so the assertion is on the columns
    # it actually adds, not on its prose.
    import importlib.util

    path = (Path(__file__).resolve().parents[2] / "migrations" / "versions"
            / "20260919_0010_attempt_telemetry_provenance.py")
    spec = importlib.util.spec_from_file_location("s9_migration_0010", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    added = {name for columns in migration.NEW_COLUMNS.values()
             for name, _type in columns}
    assert added == {"response_time_source", "attempt_index"}
    assert not any("hint" in name for name in added)

    # and the dataset contract exposes no hint field, so nothing downstream can expect one
    from learning.practice import telemetry
    assert telemetry.AttemptTelemetry().as_dict()["hint_count"] is None
    assert telemetry.AttemptTelemetry().as_dict()["hint_source"] == telemetry.HINT_NO_MECHANISM
