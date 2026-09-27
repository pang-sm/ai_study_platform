"""Re-wording a question keeps the conversation; renaming renames it.

Editing a question is neither an update to history nor a new conversation. The new wording is a
VERSION of that question, recorded inside the SAME session: the original and everything answered
from it stay in the database, the learner moves onto the new version's branch, and the history list
still holds exactly one conversation. These cases pin what the edit creates, what it leaves alone,
and what the conversation reads as afterwards.
"""
from __future__ import annotations

import dataclasses
import uuid

import pytest
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from fastapi.testclient import TestClient

import main
from models import ChatMessage, ChatSession, StudyMaterial, User
from usage.models import AIRequest

COURSE = "数据结构"
SCOPE = {"course": COURSE}
QUESTIONS = ("第一个问题", "第二个问题", "第三个问题")
EDITED = "换个问法"


@pytest.fixture
def provider(monkeypatch):
    calls = []

    class Recording(FakeProvider):
        def complete(self, spec):
            calls.append(spec)
            return dataclasses.replace(super().complete(spec), content="已收到")

        def stream(self, spec):
            calls.append(spec)
            return super().stream(spec)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", lambda name: Recording(provider=name))
    return calls


@pytest.fixture
def learner(client, db_session):
    username = f"p44-{uuid.uuid4().hex[:8]}"
    register_and_login(client, username)
    grant_unified_tier(db_session, username, "advanced")
    response = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": [COURSE], "material_types": ["课件"],
        "onboarding_completed": True,
    })
    assert response.status_code == 200, response.text
    return client, username


def _ask(client, question, *, session_id=None, edit_source_message_id=None,
         continue_from_message_id=None, attachment_ids=None):
    body = {"message": question, "service_key": "course_learning", "course_id": COURSE}
    if session_id is not None:
        body["session_id"] = session_id
    if edit_source_message_id is not None:
        body["edit_source_message_id"] = edit_source_message_id
    if continue_from_message_id is not None:
        body["continue_from_message_id"] = continue_from_message_id
    if attachment_ids:
        body["attachment_ids"] = attachment_ids
    response = client.post("/chat", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _messages(client, session_id):
    response = client.get(f"/chat/sessions/{session_id}", params=SCOPE)
    assert response.status_code == 200, response.text
    return response.json()["messages"]


def _username_of(db, user_id: int) -> str:
    return db.query(User).filter(User.id == user_id).one().username


def _message_with(db, session_id: int, content: str) -> ChatMessage:
    """The one message with this content IN THIS conversation.

    The test database is shared across the whole run, so a lookup that is not scoped to the
    conversation under test would match another test's rows.
    """
    return db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id,
        ChatMessage.content == content,
    ).one()


def _content(calls) -> str:
    return "\n".join(str(message.content) for spec in calls for message in spec.messages)


def _conversation(client):
    """A three-question conversation, returning (session_id, [user message ids])."""
    first = _ask(client, QUESTIONS[0])
    session_id = first["session"]["id"]
    _ask(client, QUESTIONS[1], session_id=session_id)
    _ask(client, QUESTIONS[2], session_id=session_id)
    user_ids = [m["id"] for m in _messages(client, session_id) if m["role"] == "user"]
    assert len(user_ids) == 3
    return session_id, user_ids


# ---------------------------------------------------------------- the edit is a version

def test_editing_stays_in_the_same_conversation(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    sessions_before = db_session.query(ChatSession).count()

    edited = _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    assert edited["session"]["id"] == session_id
    assert db_session.query(ChatSession).count() == sessions_before


def test_the_original_question_is_not_rewritten(learner, db_session, provider):
    client, username = learner
    session_id, user_ids = _conversation(client)
    before = db_session.get(ChatMessage, user_ids[1])
    original_content = before.content

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    after = db_session.get(ChatMessage, user_ids[1])
    db_session.refresh(after)
    assert after.id == user_ids[1] and after.content == original_content == QUESTIONS[1]


def test_the_new_wording_is_a_version_of_that_question(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    version = (
        db_session.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user",
            ChatMessage.content == EDITED,
        )
        .one()
    )
    # The existing version fields, used as the implementation already defines them.
    assert version.parent_message_id == user_ids[1]
    assert version.root_message_id == user_ids[1]
    assert version.branch_id.startswith(f"msg-{user_ids[1]}-v")
    assert version.version_index == 1
    # And the answer to it belongs to the same version/branch.
    answer = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.parent_message_id == version.id)
        .one()
    )
    assert answer.branch_id == version.branch_id and answer.version_index == version.version_index


def test_the_old_branch_is_kept(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    kept = {
        row.content
        for row in db_session.query(ChatMessage).filter(ChatMessage.session_id == session_id).all()
    }
    # Everything the learner replaced is still there, byte for byte.
    assert {QUESTIONS[1], QUESTIONS[2]} <= kept
    # The answer that followed the replaced question is still there too.
    answers = db_session.query(ChatMessage).filter(
        ChatMessage.session_id == session_id, ChatMessage.role == "assistant",
    ).count()
    assert answers >= 3


# ---------------------------------------------------------------- what the conversation reads as

def test_the_conversation_reads_as_the_new_branch_only(learner, provider):
    """One path, not every version side by side — and not the branch that was replaced."""
    client, _ = learner
    session_id, user_ids = _conversation(client)

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    visible = [m["content"] for m in _messages(client, session_id) if m["role"] == "user"]
    assert visible == [QUESTIONS[0], EDITED]
    # The replaced question and its whole tail are gone from the reading, though not from the DB.
    assert QUESTIONS[1] not in visible and QUESTIONS[2] not in visible


def test_an_ordinary_turn_after_an_edit_stays_on_the_new_branch(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    follow_up = _ask(client, "继续追问", session_id=session_id)

    assert follow_up["session"]["id"] == session_id
    visible = [m["content"] for m in _messages(client, session_id) if m["role"] == "user"]
    assert visible == [QUESTIONS[0], EDITED, "继续追问"]
    # The follow-up inherited the branch, which is what keeps the reading a single path.
    version = _message_with(db_session, session_id, EDITED)
    follow = _message_with(db_session, session_id, "继续追问")
    assert follow.branch_id == version.branch_id


def test_the_new_answer_is_not_grounded_in_the_abandoned_branch(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    calls = []
    provider.clear()

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    context = _content(provider)
    # What came before the edited question is still the conversation's context…
    assert QUESTIONS[0] in context
    # …and what followed the version being replaced is not.
    assert QUESTIONS[2] not in context


# ---------------------------------------------------------------- what an edit refuses

def test_another_learner_cannot_edit_your_question(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)

    with TestClient(main.app) as other:
        register_and_login(other, f"p44-other-{uuid.uuid4().hex[:8]}")
        response = other.post("/chat", json={
            "message": EDITED, "service_key": "course_learning", "course_id": COURSE,
            "session_id": session_id, "edit_source_message_id": user_ids[1],
        })
        assert response.status_code == 404, response.text
        assert QUESTIONS[1] not in response.text

    # Nothing was created, and nothing was re-worded.
    assert EDITED not in [m["content"] for m in _messages(client, session_id)]


def test_an_answer_is_not_a_question_to_re_word(learner, db_session, provider):
    client, _ = learner
    session_id, _ = _conversation(client)
    answer_id = next(m["id"] for m in _messages(client, session_id) if m["role"] == "assistant")

    response = client.post("/chat", json={
        "message": EDITED, "service_key": "course_learning", "course_id": COURSE,
        "session_id": session_id, "edit_source_message_id": answer_id,
    })
    assert response.status_code == 404, response.text


def test_a_message_from_another_conversation_is_refused(learner, db_session, provider):
    client, _ = learner
    first_session, first_users = _conversation(client)
    second_session, _ = _conversation(client)

    response = client.post("/chat", json={
        "message": EDITED, "service_key": "course_learning", "course_id": COURSE,
        "session_id": second_session, "edit_source_message_id": first_users[0],
    })
    assert response.status_code == 404, response.text


def test_a_refused_edit_writes_nothing_and_costs_nothing(learner, db_session, provider):
    client, _ = learner
    session_id, _ = _conversation(client)
    answer_id = next(m["id"] for m in _messages(client, session_id) if m["role"] == "assistant")
    before = (
        db_session.query(ChatSession).count(),
        db_session.query(ChatMessage).count(),
        db_session.query(AIRequest).count(),
    )

    for message_id in (answer_id, 99_999_999):
        response = client.post("/chat", json={
            "message": EDITED, "service_key": "course_learning", "course_id": COURSE,
            "session_id": session_id, "edit_source_message_id": message_id,
        })
        assert response.status_code == 404

    after = (
        db_session.query(ChatSession).count(),
        db_session.query(ChatMessage).count(),
        db_session.query(AIRequest).count(),
    )
    assert after == before


def test_an_edit_naming_no_conversation_is_refused_before_anything_is_created(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    before = db_session.query(ChatSession).count()

    response = client.post("/chat", json={
        "message": EDITED, "service_key": "course_learning", "course_id": COURSE,
        "edit_source_message_id": user_ids[1],
    })
    assert response.status_code == 400, response.text
    assert db_session.query(ChatSession).count() == before


# ---------------------------------------------------------------- attachments

def test_a_re_worded_question_carries_its_attachments_forward(learner, db_session, provider):
    client, _ = learner
    upload = client.post(f"/course-learning/courses/{COURSE}/materials",
                         files={"file": ("课件.txt", b"P44_ATTACHMENT_BODY", "text/plain")})
    material_id = upload.json()["material_id"]

    first = _ask(client, "第一问", attachment_ids=[material_id])
    session_id = first["session"]["id"]
    _ask(client, "第二问", session_id=session_id)
    user_ids = [m["id"] for m in _messages(client, session_id) if m["role"] == "user"]

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1],
         attachment_ids=[material_id])

    version = _message_with(db_session, session_id, EDITED)
    assert version.id
    # The SAME asset: asking about a file again does not re-upload, re-parse or copy it. Scoped to
    # this learner, because the shared database holds other tests' uploads of the same name.
    assert db_session.query(StudyMaterial).filter_by(
        username=_username_of(db_session, version.user_id), original_filename="课件.txt",
    ).count() == 1
    re_worded = next(m for m in _messages(client, session_id) if m["content"] == EDITED)
    assert [item["material_id"] for item in re_worded["attachments"]] == [material_id]


def test_a_deleted_attachment_stays_readable_on_the_old_branch(learner, db_session, provider):
    client, _ = learner
    upload = client.post(f"/course-learning/courses/{COURSE}/materials",
                         files={"file": ("会被删除.txt", b"P44_DELETED_BODY", "text/plain")})
    material_id = upload.json()["material_id"]

    first = _ask(client, "第一问", attachment_ids=[material_id])
    session_id = first["session"]["id"]
    _ask(client, "第二问", session_id=session_id)

    assert client.delete(f"/library/materials/{material_id}").status_code == 200

    # The history still says what was asked with what, even though it can no longer be asked with.
    first_message = next(m for m in _messages(client, session_id) if m["role"] == "user")
    assert first_message["attachments"][0]["filename"] == "会被删除.txt"
    assert first_message["attachments"][0]["parse_status"] == "deleted"


# ---------------------------------------------------------------- switching between versions

def _detail(client, session_id, version_message_id=None):
    params = dict(SCOPE)
    if version_message_id is not None:
        params["version_message_id"] = version_message_id
    response = client.get(f"/chat/sessions/{session_id}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _message_with_edit(client, session_id, text):
    return next(m for m in _detail(client, session_id)["messages"] if m["content"] == text)


def _visible_user_contents(detail):
    return [m["content"] for m in detail["messages"] if m["role"] == "user"]


def test_a_re_worded_question_reports_its_versions(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    shown = _message_with_edit(client, session_id, EDITED)
    assert shown["version"]["index"] == 2
    assert shown["version"]["total"] == 2
    assert shown["version"]["has_previous"] is True
    assert shown["version"]["has_next"] is False
    # The step back names the ORIGINAL message, not a branch.
    assert shown["version"]["previous_message_id"] == user_ids[1]

    # A question with no sibling offers no choice at all.
    plain = next(m for m in _detail(client, session_id)["messages"] if m["content"] == QUESTIONS[0])
    assert "version" not in plain


def test_the_original_version_reports_itself_as_the_first(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    edited = _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])
    edited_id = _message_with_edit(client, session_id, EDITED)["id"]

    first = _detail(client, session_id, version_message_id=user_ids[1])
    original = next(m for m in first["messages"] if m["id"] == user_ids[1])
    assert original["version"]["index"] == 1
    assert original["version"]["total"] == 2
    assert original["version"]["has_previous"] is False
    assert original["version"]["has_next"] is True
    assert original["version"]["next_message_id"] == edited_id
    assert edited["session"]["id"] == session_id


def test_reading_an_older_version_shows_that_branch(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    first = _detail(client, session_id, version_message_id=user_ids[1])

    # The original branch, whole: the replaced question AND everything that followed it.
    assert first["session"]["id"] == session_id
    assert _visible_user_contents(first) == list(QUESTIONS)
    # And the reading is only that branch — the edited version is not laid beside it.
    assert EDITED not in [m["content"] for m in first["messages"]]


def test_reading_the_newer_version_again_restores_it(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])
    edited_id = _message_with_edit(client, session_id, EDITED)["id"]

    first = _detail(client, session_id, version_message_id=user_ids[1])
    back = _detail(client, session_id, version_message_id=edited_id)

    assert _visible_user_contents(first) == list(QUESTIONS)
    assert _visible_user_contents(back) == [QUESTIONS[0], EDITED]


def test_each_versions_answer_travels_with_it(learner, provider):
    """A question and the answer to it are one step: switching cannot pair one with the other's."""
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    for version_message_id in (None, user_ids[1]):
        messages = _detail(client, session_id, version_message_id)["messages"]
        for position, message in enumerate(messages):
            if message["role"] != "user" or position + 1 >= len(messages):
                continue
            answer = messages[position + 1]
            assert answer["role"] == "assistant"
            # The answer that follows is the answer TO THIS question, on this branch.
            assert answer["parent_message_id"] == message["id"]


def test_switching_writes_nothing_and_costs_nothing(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])
    provider.clear()
    before = (
        db_session.query(ChatSession).count(),
        db_session.query(ChatMessage).count(),
        db_session.query(AIRequest).count(),
    )

    for version_message_id in (user_ids[1], user_ids[1], 1, 2, 3):
        response = client.get(f"/chat/sessions/{session_id}",
                              params={**SCOPE, "version_message_id": version_message_id})
        assert response.status_code in (200, 404)

    assert (
        db_session.query(ChatSession).count(),
        db_session.query(ChatMessage).count(),
        db_session.query(AIRequest).count(),
    ) == before
    assert provider == []


def test_another_learner_cannot_read_your_versions(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    with TestClient(main.app) as other:
        register_and_login(other, f"p45-other-{uuid.uuid4().hex[:8]}")
        response = other.get(f"/chat/sessions/{session_id}",
                             params={**SCOPE, "version_message_id": user_ids[1]})
        assert response.status_code == 404, response.text
        assert QUESTIONS[1] not in response.text


def test_a_version_from_another_conversation_is_refused(learner, provider):
    client, _ = learner
    first_session, first_users = _conversation(client)
    second_session, _ = _conversation(client)

    response = client.get(f"/chat/sessions/{second_session}",
                          params={**SCOPE, "version_message_id": first_users[1]})
    assert response.status_code == 404, response.text


def test_three_versions_are_ordered_and_switchable(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, "第二版问法", session_id=session_id, edit_source_message_id=user_ids[1])
    second = _message_with_edit(client, session_id, "第二版问法")
    _ask(client, "第三版问法", session_id=session_id, edit_source_message_id=second["id"])
    third = _message_with_edit(client, session_id, "第三版问法")

    assert third["version"] == {
        "index": 3, "total": 3, "has_previous": True, "has_next": False,
        "previous_message_id": second["id"], "next_message_id": None,
    }
    middle = next(m for m in _detail(client, session_id, second["id"])["messages"] if m["id"] == second["id"])
    assert (middle["version"]["index"], middle["version"]["has_previous"], middle["version"]["has_next"]) == (2, True, True)
    assert middle["version"]["previous_message_id"] == user_ids[1]
    assert middle["version"]["next_message_id"] == third["id"]
    first = next(m for m in _detail(client, session_id, user_ids[1])["messages"] if m["id"] == user_ids[1])
    assert (first["version"]["index"], first["version"]["has_previous"], first["version"]["has_next"]) == (1, False, True)

    # Editing the middle version adds a FOURTH version rather than replacing the second.
    _ask(client, "第四版问法", session_id=session_id, edit_source_message_id=second["id"])
    fourth = _message_with_edit(client, session_id, "第四版问法")
    assert (fourth["version"]["index"], fourth["version"]["total"]) == (4, 4)
    still_there = next(m for m in _detail(client, session_id, second["id"])["messages"] if m["id"] == second["id"])
    assert still_there["content"] == "第二版问法"


# ---------------------------------------------------------------- asking from a version

def test_a_question_asked_from_an_older_version_continues_that_version(learner, db_session, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])
    original_view = _detail(client, session_id, version_message_id=user_ids[1])["messages"]
    last_of_original = original_view[-1]["id"]

    _ask(client, "从旧版本追问", session_id=session_id, continue_from_message_id=last_of_original)

    visible = _visible_user_contents(_detail(client, session_id))
    # The follow-up joined the ORIGINAL branch: the replaced question and its tail are back, and
    # the version the learner had stepped away from is not on the reading.
    assert visible == [*QUESTIONS, "从旧版本追问"]
    assert EDITED not in visible


def test_a_question_asked_from_the_newer_version_continues_that_version(learner, provider):
    client, _ = learner
    session_id, user_ids = _conversation(client)
    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])
    edited_view = _detail(client, session_id)["messages"]
    last_of_edited = edited_view[-1]["id"]

    _ask(client, "从新版本追问", session_id=session_id, continue_from_message_id=last_of_edited)

    visible = _visible_user_contents(_detail(client, session_id))
    assert visible == [QUESTIONS[0], EDITED, "从新版本追问"]


def test_a_continuation_naming_another_conversation_is_refused(learner, db_session, provider):
    client, _ = learner
    first_session, _ = _conversation(client)
    second_session, _ = _conversation(client)
    other_view = _detail(client, first_session)["messages"]
    before = db_session.query(ChatMessage).count()

    response = client.post("/chat", json={
        "message": "越界", "service_key": "course_learning", "course_id": COURSE,
        "session_id": second_session, "continue_from_message_id": other_view[-1]["id"],
    })
    assert response.status_code == 404, response.text
    assert db_session.query(ChatMessage).count() == before


def test_a_continuation_without_a_conversation_is_refused(learner, db_session, provider):
    client, _ = learner
    session_id, _ = _conversation(client)
    before = db_session.query(ChatSession).count()

    response = client.post("/chat", json={
        "message": "没有会话", "service_key": "course_learning", "course_id": COURSE,
        "continue_from_message_id": 1,
    })
    assert response.status_code == 400, response.text
    assert db_session.query(ChatSession).count() == before


# ---------------------------------------------------------------- rename

def test_the_owner_renames_their_conversation(learner, provider):
    client, _ = learner
    session_id, _ = _conversation(client)

    response = client.patch(f"/chat/sessions/{session_id}", params=SCOPE, json={"title": "哈希表梳理"})
    assert response.status_code == 200, response.text
    assert response.json()["session"]["title"] == "哈希表梳理"

    listed = client.get("/chat/history", params=SCOPE).json()["sessions"]
    assert next(entry["title"] for entry in listed if entry["id"] == session_id) == "哈希表梳理"


def test_a_title_is_trimmed_before_it_is_stored(learner, provider):
    client, _ = learner
    session_id, _ = _conversation(client)

    client.patch(f"/chat/sessions/{session_id}", params=SCOPE, json={"title": "  前后有空格  "})
    listed = client.get("/chat/history", params=SCOPE).json()["sessions"]
    assert next(entry["title"] for entry in listed if entry["id"] == session_id) == "前后有空格"


@pytest.mark.parametrize("title", ["", "   ", "\n\t "])
def test_an_empty_title_is_refused(learner, provider, title):
    client, _ = learner
    session_id, _ = _conversation(client)

    response = client.patch(f"/chat/sessions/{session_id}", params=SCOPE, json={"title": title})
    assert response.status_code == 400, response.text


def test_an_overlong_title_is_refused(learner, provider):
    client, _ = learner
    session_id, _ = _conversation(client)

    response = client.patch(f"/chat/sessions/{session_id}", params=SCOPE, json={"title": "长" * 101})
    assert response.status_code == 400, response.text
    assert client.patch(f"/chat/sessions/{session_id}", params=SCOPE, json={"title": "长" * 100}).status_code == 200


def test_another_learner_cannot_rename_it(learner, provider, db_session):
    client, _ = learner
    session_id, _ = _conversation(client)
    original = client.get(f"/chat/sessions/{session_id}", params=SCOPE).json()["session"]["title"]

    with TestClient(main.app) as other:
        register_and_login(other, f"p44-rename-{uuid.uuid4().hex[:8]}")
        response = other.patch(f"/chat/sessions/{session_id}", params=SCOPE, json={"title": "不是我的"})
        assert response.status_code == 404, response.text
        assert "不是我的" not in response.text

    assert client.get(f"/chat/sessions/{session_id}", params=SCOPE).json()["session"]["title"] == original


def test_a_rename_does_not_touch_the_messages(learner, provider):
    client, _ = learner
    session_id, _ = _conversation(client)
    before = _messages(client, session_id)

    client.patch(f"/chat/sessions/{session_id}", params=SCOPE, json={"title": "换个名字"})

    after = _messages(client, session_id)
    assert [(m["id"], m["content"]) for m in after] == [(m["id"], m["content"]) for m in before]


def test_editing_keeps_the_conversation_name(learner, provider):
    """The conversation is renamed, not replaced — an edit has no business changing its name."""
    client, _ = learner
    session_id, user_ids = _conversation(client)
    title = client.get(f"/chat/sessions/{session_id}", params=SCOPE).json()["session"]["title"]

    _ask(client, EDITED, session_id=session_id, edit_source_message_id=user_ids[1])

    assert client.get(f"/chat/sessions/{session_id}", params=SCOPE).json()["session"]["title"] == title
    listed = client.get("/chat/history", params=SCOPE).json()["sessions"]
    assert len([entry for entry in listed if entry["id"] == session_id]) == 1
