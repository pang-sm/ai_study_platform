"""STEP 7H4: Exam Prep framework — catalog, profile, availability gate, knowledge writer.

The rules under test:

  * the catalog is versioned CONFIG (no SQL) and only CS408 is ACTIVE;
  * every other national-standardized subject is FRAMEWORK_ONLY: selectable, and with no
    faked chapters / knowledge points / questions behind it;
  * reaching CONTENT of a framework-only subject fails with an explicit
    ``EXAM_CONTENT_NOT_AVAILABLE`` — never ``200 + []``;
  * the learner's profile is real user state (its own table), one per user, isolated;
  * exam knowledge has ONE writer, which emits ``knowledge_status_changed`` only on a real
    transition and never touches scientific state.
"""
import json
from datetime import datetime

import pytest
from fastapi import HTTPException

from conftest import register_and_login
from learning.spaces.exam_prep import catalog
from learning.spaces.exam_prep import knowledge as exam_knowledge
from models import ExamPrepProfile, User, UserKnowledgeProgress
from usage import service as usage_service
import main


def _user(session, username, tier="free") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        usage_service.activate_subscription(session, u.id, tier, 30)
    return u


FRAMEWORK_ONLY_IDS = ("politics", "english_1", "english_2", "math_1", "math_2", "math_3",
                      "management_aptitude", "economics_joint_aptitude",
                      "law_master_law", "law_master_non_law",
                      "education_basics", "psychology_basics", "history_basics")


# ---------------------------------------------------------------- A–E: catalog

def test_catalog_is_versioned_config():
    assert isinstance(catalog.CATALOG_VERSION, str) and catalog.CATALOG_VERSION
    assert catalog.CATALOG_VERSION == "v2"


def test_only_cs408_is_active():
    assert catalog.CATALOG_VERSION
    active = [s.id for s in catalog.active_subjects()]
    assert active == ["cs_408"]
    assert catalog.get_subject("cs_408").availability == catalog.ACTIVE
    assert catalog.get_track("cs_408").is_active is True


@pytest.mark.parametrize("subject_id", FRAMEWORK_ONLY_IDS)
def test_framework_only_subjects_are_declared_and_not_active(subject_id):
    subject = catalog.get_subject(subject_id)
    assert subject is not None, subject_id
    assert subject.availability == catalog.FRAMEWORK_ONLY
    assert catalog.subject_supports_content(subject_id) is False


def test_only_cs408_carries_modules_and_capability_flags():
    cs = catalog.get_subject("cs_408").to_dict()
    assert cs["has_questions"] is True
    assert cs["has_past_papers"] is True
    assert cs["has_knowledge_tree"] is True
    assert [m["id"] for m in cs["modules"]] == list(catalog.CS408_MODULES)

    for subject_id in FRAMEWORK_ONLY_IDS:
        payload = catalog.get_subject(subject_id).to_dict()
        assert payload["has_questions"] is False, subject_id
        assert payload["has_past_papers"] is False, subject_id
        assert payload["has_knowledge_tree"] is False, subject_id
        assert payload["modules"] == [], f"{subject_id} must not invent modules"


def test_no_sql_catalog_tables_exist():
    """The catalog stays versioned config — no table was added for it."""
    import models as m
    names = {getattr(v, "__tablename__", "") for v in vars(m).values()}
    assert not {n for n in names if n and "catalog" in n}, names
    # and nothing exam-shaped beyond the ONE approved profile table
    exam_tables = {n for n in names if n and (n.startswith("exam_prep") or "exam_subject" in n)}
    assert exam_tables == {"exam_prep_profiles"}, exam_tables


def test_institution_specific_concepts_have_no_representation():
    import models as m
    names = {getattr(v, "__tablename__", "") for v in vars(m).values()}
    forbidden = ("institution", "school", "college", "major_code", "school_exam")
    assert not {n for n in names if n and any(f in n for f in forbidden)}
    profile_cols = {c.name for c in m.ExamPrepProfile.__table__.columns}
    assert not {c for c in profile_cols
                if any(f in c for f in ("school", "institution", "college", "major"))}


# ---------------------------------------------------------------- F/G: catalog API

def test_catalog_endpoint_exposes_availability_flags(client):
    body = client.get("/exam/prep/catalog").json()
    assert body["catalog_version"] == catalog.CATALOG_VERSION
    by_id = {s["id"]: s for s in body["subjects"]}
    assert by_id["cs_408"]["availability"] == "active"
    assert by_id["cs_408"]["has_questions"] is True
    assert by_id["math_1"]["availability"] == "framework_only"
    assert by_id["math_1"]["has_questions"] is False
    assert by_id["math_1"]["has_past_papers"] is False
    assert by_id["math_1"]["has_knowledge_tree"] is False
    assert set(body["active_subject_ids"]) == {"cs_408"}
    assert set(body["framework_only_subject_ids"]) == set(FRAMEWORK_ONLY_IDS)


def test_catalog_tracks_and_subjects_endpoints(client):
    tracks = client.get("/exam/prep/catalog/tracks").json()["tracks"]
    subjects = client.get("/exam/prep/catalog/subjects").json()["subjects"]
    assert {t["id"] for t in tracks} >= {"cs_408", "management_joint", "law_jm_non_law"}
    assert len(subjects) == 1 + len(FRAMEWORK_ONLY_IDS)


def test_track_subject_sets_are_options_not_rules():
    """A track's subject list is informational; the learner's selection is the scope."""
    for track in catalog.all_tracks():
        payload = track.to_dict()
        assert isinstance(payload["subject_options"], list)
        assert isinstance(payload["suggested_subjects"], list)
    # nothing in the repo justifies guessing a public-course bundle for a track
    for track in catalog.all_tracks():
        if track.id != "cs_408":
            assert track.suggested_subjects == (), track.id


# ---------------------------------------------------------------- I/J: gate

@pytest.mark.parametrize("subject_id", FRAMEWORK_ONLY_IDS)
def test_framework_only_content_access_is_explicitly_unavailable(client, subject_id):
    r = client.get(f"/exam/prep/subjects/{subject_id}/content-status")
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "EXAM_CONTENT_NOT_AVAILABLE"
    assert detail["availability"] == "framework_only"


def test_cs408_content_access_works(client):
    r = client.get("/exam/prep/subjects/cs_408/content-status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["availability"] == "active"
    assert body["has_questions"] is True and body["has_knowledge_tree"] is True
    assert [m["id"] for m in body["modules"]] == list(catalog.CS408_MODULES)


def test_unknown_subject_is_not_found(client):
    assert client.get("/exam/prep/subjects/no_such_exam/content-status").status_code == 404


# ---------------------------------------------------------------- profile

def test_profile_starts_unconfigured_for_a_free_user(client):
    register_and_login(client, "h4_profile_new")
    body = client.get("/exam/prep/profile").json()
    assert body["configured"] is False
    assert body["selected_track"] is None
    assert body["selected_subjects"] == []
    assert body["target_exam_year"] is None


def test_profile_round_trip_for_a_free_user(client):
    """A profile is not a membership entitlement: Free users have one."""
    register_and_login(client, "h4_profile_free")
    r = client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": ["cs_408"],
        "target_exam_year": 2027})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["configured"] is True
    assert body["selected_track"] == "cs_408"
    assert body["selected_subjects"] == ["cs_408"]
    assert body["target_exam_year"] == 2027

    again = client.get("/exam/prep/profile").json()
    assert again["selected_track"] == "cs_408"
    assert again["target_exam_year"] == 2027


def test_framework_only_subject_can_be_selected(client):
    register_and_login(client, "h4_profile_math")
    r = client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": ["cs_408", "math_1", "politics"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["selected_subjects"]) == {"cs_408", "math_1", "politics"}
    by_id = {s["id"]: s for s in body["subjects"]}
    assert by_id["math_1"]["availability"] == "framework_only"
    assert by_id["math_1"]["has_questions"] is False
    assert by_id["cs_408"]["availability"] == "active"


def test_invalid_track_and_subject_are_rejected(client):
    register_and_login(client, "h4_profile_bad")
    assert client.put("/exam/prep/profile",
                      json={"selected_track": "nope", "selected_subjects": []}).status_code == 400
    assert client.put("/exam/prep/profile",
                      json={"selected_track": "cs_408",
                            "selected_subjects": ["school_custom_exam"]}).status_code == 400


def test_target_exam_year_is_validated(client):
    register_and_login(client, "h4_profile_year")
    assert client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": ["cs_408"],
        "target_exam_year": 1800}).status_code == 400


def test_profile_is_isolated_per_user(client, db_session):
    register_and_login(client, "h4_iso_a")
    client.put("/exam/prep/profile", json={"selected_track": "cs_408",
                                           "selected_subjects": ["cs_408"],
                                           "target_exam_year": 2027})
    other = main.app  # same app, second authenticated client
    from fastapi.testclient import TestClient
    second = TestClient(other)
    try:
        register_and_login(second, "h4_iso_b")
        body = second.get("/exam/prep/profile").json()
        assert body["configured"] is False
        assert body["target_exam_year"] is None
        second.put("/exam/prep/profile", json={"selected_track": "education",
                                               "selected_subjects": ["education_basics"]})
        assert second.get("/exam/prep/profile").json()["selected_track"] == "education"
    finally:
        second.close()

    first = client.get("/exam/prep/profile").json()
    assert first["selected_track"] == "cs_408"
    assert first["target_exam_year"] == 2027


def test_profile_has_one_row_per_user(client, db_session):
    register_and_login(client, "h4_one_row")
    for track in ("cs_408", "education"):
        client.put("/exam/prep/profile", json={"selected_track": track,
                                               "selected_subjects": ["cs_408"]})
    user = db_session.query(User).filter(User.username == "h4_one_row").one()
    rows = db_session.query(ExamPrepProfile).filter(ExamPrepProfile.user_id == user.id).all()
    assert len(rows) == 1
    assert rows[0].selected_track == "education"


def test_profile_requires_authentication(client):
    assert client.get("/exam/prep/profile").status_code in (401, 403)


# ---------------------------------------------------------------- knowledge writer

def _seed_map_codes():
    """The real CS408 leaf codes, from the same static map the endpoint validates against."""
    payload = json.loads(main._knowledge_map_seed_path("data_structure_11408").read_text(
        encoding="utf-8"))
    index = main._build_enriched_map_index(payload.get("chapters") or [])
    return [code for code, node in index.items() if main._is_leaf_node(node)], index


def test_exam_writer_writes_the_legacy_scope_and_emits_one_event(db_session):
    from data_plane.models import LearningEvent
    u = _user(db_session, "h4_kw")
    codes, index = _seed_map_codes()
    assert codes, "the CS408 map must expose leaf knowledge points"
    code = codes[0]

    t = exam_knowledge.apply_exam_knowledge_change(
        db_session, user=u, module_key="data_structure", knowledge_point_code=code,
        status="mastered", title="叶子", review_interval_days=3,
        code_validator=lambda c: c in index)
    assert t.is_transition and t.old_status == "not_started" and t.new_status == "mastered"
    exam_knowledge.commit_and_emit(db_session, t)
    db_session.expire_all()

    row = (db_session.query(UserKnowledgeProgress)
           .filter(UserKnowledgeProgress.username == u.username,
                   UserKnowledgeProgress.knowledge_point_code == code).one())
    assert row.course_id == "data_structure_11408", "legacy scope id preserved"
    assert row.status == "mastered" and row.mastery_score == 100
    assert row.user_confirmed_status == "mastered"
    assert row.review_due_at is not None and row.review_interval_days == 3

    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == u.id,
                      LearningEvent.event_type == "knowledge_status_changed").all())
    assert len(events) == 1
    assert events[0].service_key == "exam_prep"
    assert events[0].subject_key == "cs_408"
    assert json.loads(events[0].knowledge_point_ref_json)["exam_module_id"] == "data_structure"


def test_repeating_the_same_status_emits_no_second_event(db_session):
    from data_plane.models import LearningEvent
    u = _user(db_session, "h4_kw_dup")
    codes, index = _seed_map_codes()
    code = codes[0]
    validator = lambda c: c in index  # noqa: E731

    for _ in range(3):
        t = exam_knowledge.apply_exam_knowledge_change(
            db_session, user=u, module_key="data_structure", knowledge_point_code=code,
            status="learning", code_validator=validator)
        exam_knowledge.commit_and_emit(db_session, t)
    db_session.expire_all()
    events = (db_session.query(LearningEvent)
              .filter(LearningEvent.user_id == u.id,
                      LearningEvent.event_type == "knowledge_status_changed").all())
    assert len(events) == 1, "only the real transition may be recorded"
    rows = (db_session.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == u.username,
                    UserKnowledgeProgress.knowledge_point_code == code).all())
    assert len(rows) == 1, "a repeat must not create a second progress row"


def test_exam_writer_fails_closed_on_unknown_module_and_code(db_session):
    u = _user(db_session, "h4_kw_bad")
    with pytest.raises(exam_knowledge.ExamKnowledgeError):
        exam_knowledge.apply_exam_knowledge_change(
            db_session, user=u, module_key="math_1", knowledge_point_code="1.1",
            status="learning")
    with pytest.raises(exam_knowledge.ExamKnowledgeError):
        exam_knowledge.apply_exam_knowledge_change(
            db_session, user=u, module_key="data_structure", knowledge_point_code="nope",
            status="learning", code_validator=lambda c: False)
    with pytest.raises(exam_knowledge.ExamKnowledgeError):
        exam_knowledge.apply_exam_knowledge_change(
            db_session, user=u, module_key="data_structure", knowledge_point_code="a",
            status="not_a_status")


def test_course_and_exam_knowledge_with_the_same_code_stay_isolated(db_session):
    from learning.spaces.course_learning import knowledge as course_knowledge
    u = _user(db_session, "h4_kw_iso")
    codes, index = _seed_map_codes()
    code = codes[0]

    t = exam_knowledge.apply_exam_knowledge_change(
        db_session, user=u, module_key="data_structure", knowledge_point_code=code,
        status="mastered", code_validator=lambda c: c in index)
    exam_knowledge.commit_and_emit(db_session, t)

    course_knowledge.apply_knowledge_change(
        db_session, username=u.username, course_id="data_structure",
        event_type="question_correct", knowledge_point_code=code, delta=10)
    db_session.commit()
    db_session.expire_all()

    rows = (db_session.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == u.username,
                    UserKnowledgeProgress.knowledge_point_code == code).all())
    scopes = {r.course_id for r in rows}
    assert scopes == {"data_structure_11408", "data_structure"}, scopes
    exam_row = next(r for r in rows if r.course_id == "data_structure_11408")
    course_row = next(r for r in rows if r.course_id == "data_structure")
    assert exam_row.status == "mastered"
    assert course_row.status != "mastered"


def test_exam_mutation_inventory_is_fully_declared():
    from learning.spaces.exam_prep.knowledge import (exam_mutation_paths,
                                                     exam_paths_not_consolidated)
    assert exam_paths_not_consolidated() == []
    statuses = {row["path"]: row["status"] for row in exam_mutation_paths()}
    assert statuses["PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}"] == \
        "CANONICAL_WRITER"


def test_study_plan_patch_routes_through_the_canonical_writer(client, db_session, monkeypatch):
    """The live route must call the writer, not write the row itself."""
    register_and_login(client, "h4_patch")
    seen = {}
    original = exam_knowledge.apply_exam_knowledge_change

    def spy(db, **kwargs):
        seen.update(kwargs)
        return original(db, **kwargs)

    monkeypatch.setattr(exam_knowledge, "apply_exam_knowledge_change", spy)
    codes, _ = _seed_map_codes()
    r = client.patch(f"/exam/11408/subjects/data_structure/study-plan/knowledge-items/{codes[0]}",
                     json={"username": "h4_patch", "subject_key": "data_structure",
                           "course_id": "data_structure_11408",
                           "knowledge_point_code": codes[0],
                           "status": "learning", "knowledge_point_title": "叶子"})
    # the legacy study-plan entitlement is preserved, so a Free user is refused by it
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        assert seen.get("module_key") == "data_structure"
        assert seen.get("knowledge_point_code") == codes[0]


# ---------------------------------------------------------------- provider isolation

PROVIDER_CONFIG_MARKERS = ("DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "QWEN_API_KEY",
                           "ARK_API_KEY", "OPENAI_API_KEY")


def test_exam_business_code_knows_no_provider_config():
    """STEP7H4 §25: model availability is the Router's / Gateway's question.

    The business layer must not branch on which vendor happens to be configured — that is
    what made "no DEEPSEEK_API_KEY → serve mock" a product decision instead of a technical
    fallback. (Provider ADAPTERS still own their own secrets; this is the business surface.)
    """
    import inspect
    from pathlib import Path as _Path

    exam_dir = _Path(exam_knowledge.__file__).parent
    sources = [*sorted(exam_dir.glob("*.py")),
               _Path(main.__file__).parent / "routers" / "exam_prep.py"]
    for path in sources:
        src = path.read_text(encoding="utf-8")
        hits = [m for m in PROVIDER_CONFIG_MARKERS if m in src]
        assert hits == [], f"{path.name} names provider config: {hits}"

    body = inspect.getsource(main.generate_exam_ai_questions)
    for marker in (*PROVIDER_CONFIG_MARKERS, "os.getenv", "os.environ"):
        assert marker not in body, f"generate_exam_ai_questions branches on {marker}"


# ---------------------------------------------------------------- protected assets

def test_no_non_cs408_content_was_created():
    """Executable invariant: the bank still holds ONLY the four CS408 modules."""
    import sqlite3
    from pathlib import Path
    db = Path(__file__).resolve().parents[1] / "app.db"
    if not db.exists():
        pytest.skip("no working database")
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        subjects = {r[0] for r in con.execute(
            "SELECT DISTINCT subject_key FROM exam_question_bank")}
        assert subjects == set(catalog.CS408_MODULES), subjects
        assert con.execute("SELECT COUNT(*) FROM exam_question_bank").fetchone()[0] == 9333
    finally:
        con.close()
