"""THREE_DOMAIN_COMPETITIVE_PRODUCTIZATION_P3A — Strong Reasoning / Deep Study.

WHAT THESE TESTS HOLD
---------------------
1. the capability is gated by the UNIFIED tier (Free denied, Standard allowed) and a denial
   consumes nothing and records nothing;
2. an allowed run goes through the ONE lifecycle — permission → estimate → reserve → router →
   gateway → settle — with exactly one ``ai_requests`` row and a reserve+settle ledger pair;
3. it is GROUNDED: citations point only at chunks of materials the caller may use, and the
   materials that were refused are stated (``excluded``) instead of silently dropped;
4. isolation holds across users AND across courses, for both the explicit ``material_ids`` path
   and the space-scoped retrieval path;
5. the module reaches no provider directly — the answer comes from the orchestrator's provider
   seam and the model label is user-safe.

Every test runs against the TEMP DATABASE_URL that ``conftest`` installs before ``main`` is
imported.
"""
import dataclasses
import json
from pathlib import Path

from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from data_plane.models import LearningEvent
from models import MaterialChunk, StudyMaterial, User
from usage.models import AIRequest, UsageLedger

DEEP_STUDY = "/ai/deep-study"
COURSE = "数据结构"
OTHER_COURSE = "操作系统"
ANSWER = "虚拟内存通过分页把虚拟地址映射到物理页框。"

BACKEND = Path(__file__).resolve().parents[1]


class _ScriptedProvider(FakeProvider):
    """FakeProvider whose completion is the answer under test (the rest stays the real double)."""

    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self._content = content

    def complete(self, spec):
        return dataclasses.replace(super().complete(spec), content=self._content)


def _provider_factory(content: str = ANSWER):
    def _make(name: str) -> FakeProvider:
        return _ScriptedProvider(content, provider=name, input_tokens=80, output_tokens=60)
    return _make


def _user(db, username) -> User:
    return db.query(User).filter(User.username == username).one()


def _material(db, username, course_id, filename, text) -> StudyMaterial:
    material = StudyMaterial(
        username=username, course_id=course_id, subject_key=course_id, subject=course_id,
        file_type="text", original_filename=filename, file_hash=f"hash-{filename}",
        file_path=f"test/{filename}", file_size=len(text), extracted_text=text,
        summary="", parse_status="success", is_deleted=False,
        visibility="private", allow_private_rag=True)
    db.add(material)
    db.commit()
    db.refresh(material)
    db.add(MaterialChunk(
        material_id=material.id, username=username, course_id=course_id,
        subject_key=course_id, subject=course_id, chunk_index=0, chunk_text=text,
        chunk_summary=text[:80], keywords="虚拟内存 分页", source_filename=filename))
    db.commit()
    return material


# ================================================================ 1. gating


def test_free_tier_is_denied_and_records_nothing(client, db_session):
    register_and_login(client, "p3a_ds_free")

    denied = client.post(DEEP_STUDY, json={"question": "什么是虚拟内存？", "course_id": COURSE})
    assert denied.status_code == 403, denied.text

    user = _user(db_session, "p3a_ds_free")
    assert db_session.query(AIRequest).filter(AIRequest.user_id == user.id).count() == 0
    assert db_session.query(LearningEvent).filter(
        LearningEvent.user_id == user.id,
        LearningEvent.event_type.like("strong_reasoning%")).count() == 0


def test_standard_tier_runs_the_full_billed_lifecycle(client, db_session, monkeypatch):
    register_and_login(client, "p3a_ds_ok")
    grant_unified_tier(db_session, "p3a_ds_ok", "standard")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider_factory())
    material = _material(db_session, "p3a_ds_ok", COURSE, "os-notes.txt",
                         "虚拟内存通过分页机制管理物理内存，页面置换算法决定换出哪一页。")

    response = client.post(DEEP_STUDY, json={
        "question": "什么是虚拟内存？", "course_id": COURSE,
        "material_ids": [material.id]})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["capability"] == "tutor.strong_reasoning"
    assert body["answer"] == ANSWER
    assert body["status"] == "settled"
    assert body["context"]["course_id"] == COURSE
    assert body["context"]["service_namespace"] == "course_learning"
    assert body["evidence"]["retrieval"] == "fts_bm25"

    # ── grounded: every citation is a real chunk of the ONE material that was allowed
    assert body["materials"]["used"] == [material.id]
    assert body["materials"]["excluded"] == []
    assert body["citations"], "a grounded answer must cite what it was grounded in"
    assert {c["material_id"] for c in body["citations"]} == {material.id}
    assert {c["filename"] for c in body["citations"]} == {"os-notes.txt"}
    assert {r["material_id"] for r in body["material_refs"]} == {material.id}

    # ── billed exactly once, through the unified ledger
    user = _user(db_session, "p3a_ds_ok")
    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user.id,
                       AIRequest.capability == "tutor.strong_reasoning").one())
    assert request.status == "settled"
    assert request.service_namespace == "course_learning"
    assert body["request_id"] == request.request_id
    rows = (db_session.query(UsageLedger)
            .filter(UsageLedger.request_id == request.request_id).all())
    entry_types = {row.entry_type for row in rows}
    # reserve → settle, with the unused part of the reservation released back (the frozen
    # STEP7B model: one reserve entry per budget period, one settle, one release of the
    # difference). The amounts must agree with the request row — nothing is left reserved
    # and nothing is billed beyond the reservation.
    assert entry_types <= {"reserve", "settle", "release"}
    assert {"reserve", "settle"} <= entry_types
    settled = sum(row.amount for row in rows if row.entry_type == "settle")
    released = sum(row.amount for row in rows if row.entry_type == "release")
    assert settled == request.actual_credits == body["usage"]["actual_credits"]
    assert released == -(request.reserved_credits - request.actual_credits)
    assert request.reserved_credits >= request.actual_credits

    # ── the canonical events share the request's namespace
    db_session.expire_all()
    events = db_session.query(LearningEvent).filter(LearningEvent.user_id == user.id).all()
    types = {event.event_type for event in events}
    assert {"strong_reasoning_requested", "strong_reasoning_completed"} <= types
    assert all(event.service_key == "course_learning" for event in events)

    # ── the model label is user-safe: no provider name and no raw model id
    from ai.pool import QUALIFIED_POOL
    tokens = {e.model for e in QUALIFIED_POOL} | {e.provider for e in QUALIFIED_POOL}
    display = body["model"]["display_name"]
    assert not any(token in display for token in tokens), display
    assert body["model"]["selection"] == "auto"
    # the options ARE the frozen user-safe surface: production-eligible only
    assert all(o.get("deployment_eligibility") == "PRODUCTION"
               for o in body["model"]["options"])


# ================================================================ 2. material isolation


def test_another_learners_material_is_refused(client, db_session, monkeypatch):
    register_and_login(client, "p3a_ds_owner")
    grant_unified_tier(db_session, "p3a_ds_owner", "standard")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider_factory())

    stray = _material(db_session, "someone_else", COURSE, "stranger.txt",
                      "别人的私有资料内容，包含 虚拟内存 等关键词。")

    response = client.post(DEEP_STUDY, json={
        "question": "什么是虚拟内存？", "course_id": COURSE,
        "material_ids": [stray.id]})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["materials"]["used"] == []
    assert body["materials"]["excluded"] == [stray.id]
    assert body["citations"] == []
    assert body["material_refs"] == []
    assert "别人的私有资料内容" not in json.dumps(body, ensure_ascii=False)


def test_material_from_another_course_is_refused(client, db_session, monkeypatch):
    register_and_login(client, "p3a_ds_courses")
    grant_unified_tier(db_session, "p3a_ds_courses", "standard")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider_factory())

    mine = _material(db_session, "p3a_ds_courses", COURSE, "mine.txt", "数据结构的线性表内容。")
    foreign = _material(db_session, "p3a_ds_courses", OTHER_COURSE, "other.txt",
                        "操作系统的进程调度内容。")

    body = client.post(DEEP_STUDY, json={
        "question": "什么是虚拟内存？", "course_id": COURSE,
        "material_ids": [mine.id, foreign.id]}).json()
    assert body["materials"]["used"] == [mine.id]
    assert body["materials"]["excluded"] == [foreign.id]
    assert {c["material_id"] for c in body["citations"]} == {mine.id}


def test_space_scoped_retrieval_never_crosses_courses(client, db_session, monkeypatch):
    """Without explicit material_ids the search itself must stay inside the course."""
    register_and_login(client, "p3a_ds_search")
    grant_unified_tier(db_session, "p3a_ds_search", "standard")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider_factory())

    mine = _material(db_session, "p3a_ds_search", COURSE, "mine.txt",
                     "虚拟内存的课程笔记：分页与页面置换。")
    foreign = _material(db_session, "p3a_ds_search", OTHER_COURSE, "other.txt",
                        "虚拟内存的另一门课笔记。")

    body = client.post(DEEP_STUDY, json={
        "question": "虚拟内存 分页", "course_id": COURSE}).json()
    cited = {c["material_id"] for c in body["citations"]}
    assert foreign.id not in cited
    assert cited <= {mine.id}


def test_exam_space_runs_in_its_own_context(client, db_session, monkeypatch):
    register_and_login(client, "p3a_ds_exam")
    grant_unified_tier(db_session, "p3a_ds_exam", "advanced")
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", _provider_factory())

    body = client.post(DEEP_STUDY, json={
        "question": "请深入讲解进程调度", "service_key": "exam_11408",
        "subject_key": "operating_system"}).json()
    assert body["context"]["service_namespace"] == "exam_prep"
    assert body["context"]["exam_subject_id"] == "cs_408"
    assert body["context"]["exam_module_id"] == "operating_system"

    user = _user(db_session, "p3a_ds_exam")
    request = (db_session.query(AIRequest)
               .filter(AIRequest.user_id == user.id,
                       AIRequest.capability == "tutor.strong_reasoning").one())
    assert request.service_namespace == "exam_prep"
    db_session.expire_all()
    events = db_session.query(LearningEvent).filter(LearningEvent.user_id == user.id).all()
    assert all(event.service_key == "exam_prep" for event in events)
    assert any(event.event_type == "strong_reasoning_completed" for event in events)


# ================================================================ 3. capability surface


def test_the_new_capabilities_are_served_by_the_ai_models_surface(client, db_session):
    """``/ai/models`` answers for them, through the SAME tier + qualified-set rules."""
    register_and_login(client, "p3a_caps_models")
    for capability in ("tutor.strong_reasoning", "programming.agent"):
        denied = client.get("/ai/models", params={"capability": capability})
        assert denied.status_code == 403, (capability, denied.text)

    grant_unified_tier(db_session, "p3a_caps_models", "standard")
    for capability in ("tutor.strong_reasoning", "programming.agent"):
        allowed = client.get("/ai/models", params={"capability": capability})
        assert allowed.status_code == 200, (capability, allowed.text)
        body = allowed.json()
        assert body["capability"] == capability
        assert body["default"] == "auto"
        assert body["options"], capability
        # a small qualified set, not the registry — and never an internal-only endpoint
        assert all(option["deployment_eligibility"] == "PRODUCTION"
                   for option in body["options"])


# ================================================================ 4. no bypass


def test_the_deep_study_modules_reach_no_provider_directly(client):
    """The workflow requests a capability; only ``ai/providers`` may name a vendor."""
    from ai.pool import QUALIFIED_POOL

    sources = [(BACKEND / "learning" / "deep_study.py"),
               (BACKEND / "routers" / "deep_study.py")]
    providers = {entry.provider for entry in QUALIFIED_POOL} | {"deepseek"}
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "OpenAI(" not in text, path
        assert "chat.completions" not in text, path
        assert "call_deepseek" not in text, path
        lowered = text.lower()
        for provider in providers:
            assert provider not in lowered, (path, provider)
