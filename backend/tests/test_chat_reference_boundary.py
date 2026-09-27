"""P3.1 targeted tests: the PUBLIC boundary of chat references.

Retrieval hands the chat endpoints an INTERNAL item — material/chunk ids, ranking scores,
storage path, scope provenance. None of that is a product fact a learner may read, so the sync
response, the SSE ``done`` frame and the session-detail read path must each publish only the
small public projection, and must publish it identically.

Every case here drives a real endpoint (``POST /chat``, ``POST /chat/stream``,
``GET /chat/sessions/{id}``); the only thing stubbed is the retrieval layer, which is the exact
boundary the projection is meant to guard.
"""
from __future__ import annotations

import dataclasses
import json
import uuid

import pytest
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import ChatMessage, ChatSession, User

COURSE_DISPLAY = "数据结构"
COURSE_ID = "data_structure"

# The ONE allowlist, used by all three read paths. The session-detail projection also carries
# `page`/`section` when the persisted reference has them; sync and SSE carry `filename`/`snippet`.
PUBLIC_REFERENCE_KEYS = frozenset({"filename", "snippet", "page", "section"})
REQUIRED_REFERENCE_KEYS = frozenset({"filename", "snippet"})

# Internal-only facts. These exist in the retrieval item and in the persisted column, and must
# never survive any projection.
FORBIDDEN_REFERENCE_KEYS = (
    "material_id", "chunk_id", "score", "similarity_score",
    "scope_type", "source_kind", "storage_path", "subject",
)

# A retrieval item as the internal layer really produces it (`rag.py`), plus the extra internal
# fields a persisted reference can carry.
INTERNAL_REFERENCE = {
    "source_filename": "ref.txt",
    "chunk_text": "public snippet",
    "page": 3,
    "section": "Section A",
    "material_id": 123,
    "chunk_id": 456,
    "score": 0.91,
    "similarity_score": 0.88,
    "scope_type": "personal",
    "source_kind": "personal",
    "storage_path": "/internal/path",
    "subject": "internal-subject",
    "chunk_summary": "internal summary",
    "keywords": "internal keywords",
    "file_type": "txt",
    "created_at": None,
}

# A reference as it sits in the persisted ``chat_messages.reference_payload`` column: already
# projected (`filename`/`snippet`), plus everything an older row may still carry.
HISTORICAL_REFERENCE = {
    "filename": "ref.txt",
    "snippet": "public snippet",
    "page": 3,
    "section": "Section A",
    "material_id": 123,
    "chunk_id": 456,
    "score": 0.91,
    "similarity_score": 0.88,
    "scope_type": "personal",
    "source_kind": "personal",
    "storage_path": "/internal/path",
    "subject": "internal-subject",
}


def assert_public_reference(item: dict, *, filename: str, snippet: str) -> None:
    """One public reference: the documented keys, and nothing from the internal item."""
    assert item["filename"] == filename
    assert item["snippet"] == snippet
    assert set(item) <= PUBLIC_REFERENCE_KEYS, f"unexpected public keys: {sorted(set(item) - PUBLIC_REFERENCE_KEYS)}"
    assert set(item) >= REQUIRED_REFERENCE_KEYS
    for forbidden in FORBIDDEN_REFERENCE_KEYS:
        assert forbidden not in item, f"{forbidden} leaked into a public reference"


# ---------------------------------------------------------------- doubles


@pytest.fixture
def provider(monkeypatch):
    """A recording fake so no case here can reach a paid API.

    Every test in this file requests it, and the teardown assertion is the guard: without it a
    test could quietly drop the fixture and reach a real provider — which is exactly what a
    reviewer would not notice, since the reference assertions still pass either way.
    """
    calls: list = []

    class Recording(FakeProvider):
        def complete(self, spec):
            calls.append(spec)
            return dataclasses.replace(super().complete(spec), content="已收到")

        def stream(self, spec):
            calls.append(spec)
            return super().stream(spec)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        lambda name: Recording(provider=name, input_tokens=20, output_tokens=20))
    yield calls
    assert calls, "no fake-provider call was recorded — a real provider may have been reached"


@pytest.fixture
def retriever(monkeypatch):
    """Hand the endpoints an INTERNAL retrieval item.

    Both retrieval entries are patched because the endpoints pick one by request shape: an
    attachment turn goes through ``retrieve_chunks_for_materials``, a plain course turn through
    ``search_relevant_material_chunks``. Pinning one and letting the other run for real would
    let a case pass while the path it claims to cover was never exercised.
    """
    calls: list = []

    def fake(**kwargs):
        calls.append(kwargs)
        return [dict(INTERNAL_REFERENCE)]

    monkeypatch.setattr("main.search_relevant_material_chunks", fake)
    monkeypatch.setattr("main.retrieve_chunks_for_materials", fake)
    return calls


@pytest.fixture
def learner(client, db_session):
    """A registered learner who owns the course and holds a paid tier."""
    username = f"ref-{uuid.uuid4().hex[:8]}"
    register_and_login(client, username)
    grant_unified_tier(db_session, username, "advanced")
    reply = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "",
        "selected_courses": [COURSE_DISPLAY], "recommended_courses": [],
        "material_types": [], "course_goals": {}, "onboarding_completed": True,
    })
    assert reply.status_code == 200, reply.text
    return client, username


def _body(**more) -> dict:
    body = {"message": "线性表的核心概念是什么？", "service_key": "course_learning",
            "course": COURSE_ID, "course_id": COURSE_ID}
    body.update(more)
    return body


def _upload(client, name: str, text: str) -> int:
    response = client.post("/personal-materials/upload",
                           files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload.get("id") or payload["material_id"]


def _sse_frames(text: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    event = None
    for line in text.split("\n"):
        if line.startswith("event: "):
            event = line[7:].strip()
        elif line.startswith("data: "):
            out.append((event, json.loads(line[6:])))
        elif line == "":
            event = None
    return out


# ---------------------------------------------------------------- the three read paths


def test_sync_chat_publishes_only_the_public_reference_contract(learner, retriever, provider):
    client, _ = learner
    response = client.post("/chat", json=_body())
    assert response.status_code == 200, response.text

    references = response.json()["references"]
    assert len(references) == 1
    assert_public_reference(references[0], filename="ref.txt", snippet="public snippet")


def test_streaming_chat_publishes_only_the_public_reference_contract(learner, retriever, provider):
    """Endpoint-level SSE: the `done` frame is what a browser actually reads."""
    client, _ = learner
    response = client.post("/chat/stream", json=_body())
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")

    parsed = _sse_frames(response.text)
    assert parsed[-1][0] == "done", response.text
    references = parsed[-1][1]["references"]
    assert len(references) == 1
    assert_public_reference(references[0], filename="ref.txt", snippet="public snippet")


def test_session_detail_publishes_only_the_public_reference_contract(learner, db_session, retriever, provider):
    """A HISTORICAL persisted payload — written before the projection existed — still cannot
    reach a client: the read path re-projects rather than trusting the stored column."""
    client, _ = learner
    created = client.post("/chat", json=_body())
    assert created.status_code == 200, created.text
    session_id = created.json()["session"]["id"]
    assistant_id = created.json()["assistant_message_id"]

    row = db_session.get(ChatMessage, assistant_id)
    row.reference_payload = json.dumps([HISTORICAL_REFERENCE], ensure_ascii=False)
    db_session.commit()

    detail = client.get(f"/chat/sessions/{session_id}", params={"course": COURSE_ID})
    assert detail.status_code == 200, detail.text
    assistant = next(item for item in detail.json()["messages"] if item["id"] == assistant_id)

    assert len(assistant["references"]) == 1
    reference = assistant["references"][0]
    assert_public_reference(reference, filename="ref.txt", snippet="public snippet")
    # The session-detail projection is the documented superset: it keeps the locator keys a
    # persisted reference may carry, and only those.
    assert reference["page"] == 3 and reference["section"] == "Section A"


def test_sanitizing_references_does_not_touch_user_attachment_metadata(learner, db_session, retriever, provider):
    """The two boundaries are independent: a sanitized assistant reference must not cost the
    user turn its attachment contract."""
    client, _ = learner
    material_id = _upload(client, "attach.txt", "ATTACHMENT_BODY")

    created = client.post("/chat", json=_body(attachment_ids=[material_id]))
    assert created.status_code == 200, created.text
    session_id = created.json()["session"]["id"]
    assistant_id = created.json()["assistant_message_id"]

    detail = client.get(f"/chat/sessions/{session_id}", params={"course": COURSE_ID})
    assert detail.status_code == 200, detail.text
    messages = detail.json()["messages"]

    # The assistant turn is projected...
    assistant = next(item for item in messages if item["id"] == assistant_id)
    assert len(assistant["references"]) == 1
    assert_public_reference(assistant["references"][0],
                            filename="ref.txt", snippet="public snippet")
    assert assistant["attachments"] == []

    # ...and the user turn still carries the full attachment contract, untouched.
    user_message = next(item for item in messages if item["role"] == "user")
    attachments = user_message["attachments"]
    assert len(attachments) == 1
    attachment = attachments[0]
    assert set(attachment) == {"material_id", "filename", "file_type",
                               "source_kind", "parse_status"}
    assert attachment["material_id"] == material_id
    assert attachment["filename"] == "attach.txt"
    assert attachment["file_type"] == "text"
    assert attachment["source_kind"] == "personal"
    assert attachment["parse_status"] == "success"


# ---------------------------------------------------------------- shared projection


def test_every_read_path_publishes_the_same_public_key_set(learner, db_session, retriever, provider):
    """No path invents a private allowlist: sync, SSE and session detail agree on the keys."""
    from main import serialize_reference_item

    client, _ = learner
    synced = client.post("/chat", json=_body()).json()["references"][0]
    streamed = _sse_frames(client.post("/chat/stream", json=_body()).text)[-1][1]["references"][0]

    session_id = client.post("/chat", json=_body()).json()["session"]["id"]
    detail = client.get(f"/chat/sessions/{session_id}", params={"course": COURSE_ID}).json()
    stored = next(item for item in detail["messages"]
                  if item["role"] == "assistant")["references"][0]

    projected = serialize_reference_item(dict(INTERNAL_REFERENCE))
    for label, item in (("sync", synced), ("sse", streamed), ("session", stored)):
        assert set(item) <= PUBLIC_REFERENCE_KEYS, label
        assert item["filename"] == projected["filename"], label
        assert item["snippet"] == projected["snippet"], label
