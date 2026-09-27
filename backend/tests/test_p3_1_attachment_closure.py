"""P3.1 explicit-attachment validation and persistence closure matrix."""
from __future__ import annotations

import dataclasses
import uuid

import pytest
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from fastapi.testclient import TestClient
import main
from models import ChatMessage, ChatMessageAttachment, ChatSession, StudyMaterial, User
from usage.models import AIRequest, AICostRecord
from rag import soft_delete_material_chunks


@pytest.fixture
def provider(monkeypatch):
    calls = []
    class Recording(FakeProvider):
        def complete(self, spec): calls.append(spec); return dataclasses.replace(super().complete(spec), content="ok")
        def stream(self, spec): calls.append(spec); return super().stream(spec)
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", lambda name: Recording(provider=name))
    return calls


def _counts(db):
    return tuple(db.query(model).count() for model in (AIRequest, AICostRecord, ChatMessageAttachment, ChatSession, ChatMessage))


def _assert_rejected(client, db, provider, material_id):
    before = _counts(db); calls = len(provider)
    for path in ("/chat", "/chat/stream"):
        response = client.post(path, json={"message": "附件验证", "service_key": "course_learning", "attachment_ids": [material_id]})
        assert response.status_code in {400, 404}, response.text
        assert len(provider) == calls
        assert _counts(db) == before


def _upload(client, path, name, text):
    response = client.post(path, files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json().get("id") or response.json()["material_id"]


@pytest.fixture
def owner(client, db_session):
    username = f"p31-{uuid.uuid4().hex[:8]}"
    register_and_login(client, username)
    grant_unified_tier(db_session, username, "advanced")
    return client, username


def test_rejects_nonexistent_course_deleted_states_and_empty_chunks(owner, db_session, provider):
    owner, _ = owner
    _assert_rejected(owner, db_session, provider, 99999999)
    personal = _upload(owner, "/personal-materials/upload", "p.txt", "P_TOKEN")
    chat = _upload(owner, "/chat/attachments/upload", "c.txt", "C_TOKEN")
    # NOTE: the scope of an owned file is deliberately NOT a rejection reason. Every door into
    # the library — course, personal, chat — produces something its owner may choose again, so
    # the cases below are the ones that still refuse: gone, or not parsed.
    deleted = db_session.get(StudyMaterial, personal); deleted.is_deleted = True; db_session.commit()
    _assert_rejected(owner, db_session, provider, personal)
    local = db_session.get(StudyMaterial, chat); local.is_deleted = True; db_session.commit()
    _assert_rejected(owner, db_session, provider, chat)
    for status in ("pending", "failed", "processing"):
        candidate = _upload(owner, "/personal-materials/upload", f"{status}.txt", status)
        row = db_session.get(StudyMaterial, candidate); row.parse_status = status; db_session.commit()
        _assert_rejected(owner, db_session, provider, candidate)
    empty = _upload(owner, "/personal-materials/upload", "empty.txt", "empty")
    row = db_session.get(StudyMaterial, empty); row.chunk_count = 0; db_session.commit()
    _assert_rejected(owner, db_session, provider, empty)


def test_dedupes_and_derives_source_kind(owner, db_session, provider):
    owner, username = owner
    personal = _upload(owner, "/personal-materials/upload", "personal.txt", "PERSONAL_ONCE")
    local = _upload(owner, "/chat/attachments/upload", "local.txt", "LOCAL_ONCE")
    response = owner.post("/chat", json={"message": "附件", "service_key": "course_learning", "attachment_ids": [personal, personal, local, local]})
    assert response.status_code == 200, response.text
    user = db_session.query(User).filter_by(username=username).one()
    message = db_session.query(ChatMessage).filter_by(user_id=user.id, role="user").order_by(ChatMessage.id.desc()).one()
    rows = db_session.query(ChatMessageAttachment).filter_by(message_id=message.id).all()
    assert {(row.material_id, row.source_kind) for row in rows} == {(personal, "personal"), (local, "local")}
    context = "\n".join(message.content for spec in provider for message in spec.messages)
    assert context.count("PERSONAL_ONCE") == 1 and context.count("LOCAL_ONCE") == 1


def test_cross_user_personal_chat_and_session_metadata_are_isolated(client, db_session, provider):
    register_and_login(client, "p31-owner-a")
    grant_unified_tier(db_session, "p31-owner-a", "advanced")
    personal = _upload(client, "/personal-materials/upload", "private-personal.txt", "PRIVATE_PERSONAL")
    local = _upload(client, "/chat/attachments/upload", "private-local.txt", "PRIVATE_LOCAL")
    ok = client.post("/chat", json={"message": "保存附件", "service_key": "course_learning", "attachment_ids": [personal]})
    assert ok.status_code == 200, ok.text
    session_id = ok.json()["session"]["id"]

    with TestClient(main.app) as other:
        register_and_login(other, "p31-owner-b")
        grant_unified_tier(db_session, "p31-owner-b", "advanced")
        assert all(item["id"] != personal for item in other.get("/library/materials").json()["materials"])
        assert all(item["id"] != personal for item in other.get("/library/materials", params={"q": "private-personal"}).json()["materials"])
        assert other.delete(f"/personal-materials/{personal}").status_code == 404
        for material_id in (personal, local):
            _assert_rejected(other, db_session, provider, material_id)
        detail = other.get(f"/chat/sessions/{session_id}")
        assert detail.status_code in {400, 403, 404}
        assert "private-personal.txt" not in detail.text and "source_kind" not in detail.text
        for material_id in (personal, local):
            download = other.get(f"/materials/{material_id}/download")
            assert download.status_code in {401, 403, 404}


def test_soft_deleted_personal_and_chat_keep_history_but_reject_reuse(owner, db_session, provider):
    owner, username = owner
    personal = _upload(owner, "/personal-materials/upload", "delete-personal.txt", "DELETE_PERSONAL")
    local = _upload(owner, "/chat/attachments/upload", "delete-local.txt", "DELETE_LOCAL")
    assert any(item["id"] == personal for item in owner.get("/library/materials").json()["materials"])
    sent = owner.post("/chat", json={"message": "使用附件", "service_key": "exam_11408", "exam_subject": "data_structure", "attachment_ids": [personal, local]})
    assert sent.status_code == 200
    session_id = sent.json()["session"]["id"]
    assert owner.delete(f"/personal-materials/{personal}").status_code == 200
    assert all(item["id"] != personal for item in owner.get("/library/materials", params={"q": "delete-personal"}).json()["materials"])
    row = db_session.get(StudyMaterial, local); row.is_deleted = True; db_session.commit(); soft_delete_material_chunks(db_session, local)
    for material_id in (personal, local): _assert_rejected(owner, db_session, provider, material_id)
    detail = owner.get(f"/chat/sessions/{session_id}", params={"exam_subject": "data_structure"}).json()
    user_message = next(message for message in detail["messages"] if message["role"] == "user")
    attachments = {item["material_id"]: item for item in user_message["attachments"]}
    assert attachments[personal]["source_kind"] == "personal" and attachments[personal]["parse_status"] == "deleted"
    assert attachments[local]["source_kind"] == "local" and attachments[local]["parse_status"] == "deleted"
    assert db_session.query(ChatMessageAttachment).count() >= 2


def test_legacy_material_id_fallback_dedupes_and_keeps_deleted_metadata(owner, db_session):
    owner, username = owner
    material = _upload(owner, "/personal-materials/upload", "legacy.txt", "LEGACY")
    user = db_session.query(User).filter_by(username=username).one()
    session = ChatSession(user_id=user.id, title="legacy", subject="", exam_subject="data_structure")
    db_session.add(session); db_session.commit()
    message = ChatMessage(user_id=user.id, session_id=session.id, role="user", content="old", material_id=material)
    db_session.add(message); db_session.commit()
    db_session.add(ChatMessageAttachment(message_id=message.id, material_id=material, source_kind="personal")); db_session.commit()
    db_session.get(StudyMaterial, material).is_deleted = True; db_session.commit(); soft_delete_material_chunks(db_session, material)
    detail = owner.get(f"/chat/sessions/{session.id}", params={"exam_subject": "data_structure"}).json()
    restored = next(item for item in detail["messages"] if item["id"] == message.id)["attachments"]
    assert len(restored) == 1 and restored[0]["filename"] == "legacy.txt" and restored[0]["parse_status"] == "deleted"


@pytest.mark.parametrize("scope_type,filename", [("personal", "legacy-no-relation.txt"), ("course", "legacy-course.txt")])
def test_legacy_material_id_without_relation_is_returned_by_session_detail(owner, db_session, provider, scope_type, filename):
    owner, username = owner
    material_id = _upload(owner, "/personal-materials/upload", filename, "LEGACY_FALLBACK")
    material = db_session.get(StudyMaterial, material_id); material.scope_type = scope_type
    if scope_type == "course": material.course_id = "data_structure"; material.subject_key = "data_structure"; material.subject = "数据结构"
    db_session.commit()
    user = db_session.query(User).filter_by(username=username).one()
    session = ChatSession(user_id=user.id, title="legacy fallback", subject="", exam_subject="data_structure")
    db_session.add(session); db_session.commit()
    message = ChatMessage(user_id=user.id, session_id=session.id, role="user", content="old", material_id=material_id)
    db_session.add(message); db_session.commit()
    assert db_session.query(ChatMessageAttachment).filter_by(message_id=message.id).count() == 0
    detail = owner.get(f"/chat/sessions/{session.id}", params={"exam_subject": "data_structure"})
    assert detail.status_code == 200, detail.text
    attachments = next(item for item in detail.json()["messages"] if item["id"] == message.id)["attachments"]
    assert len(attachments) == 1 and attachments[0]["material_id"] == material_id and attachments[0]["filename"] == filename
    # Both spellings are now attachable by their owner — a course file is a library file — so
    # what this case pins is the session-detail fallback, not a scope refusal.
