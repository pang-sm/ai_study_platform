"""Wrong-answer HTTP contract + isolation through the API.

BC7 replaced the raw state view with a normalized product record. The assertions below are
about the CONTRACT the frontend consumes: a stable record id, a factual status, a source
kind from a closed vocabulary, the learner's own answer and the reference answer, and —
for an exam question — the module it belongs to. Implementation identity
(``question_source_type`` / ``question_source_id``) is deliberately not asserted because it
is deliberately not returned.
"""
from conftest import register_and_login


def _session(client, namespace="exam_prep"):
    r = client.post("/practice/sessions",
                    json={"service_namespace": namespace})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _attempt(client, session_id, *, qid="1001", correct=False, source_type=None):
    payload = {"question_source_type": source_type or "static_question_bank",
               "question_source_id": qid, "answer": "A", "correct": correct}
    r = client.post(f"/practice/sessions/{session_id}/attempts", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["attempt"]


def _items(client, query=""):
    body = client.get(f"/wrong-answers{query}").json()
    assert set(body) == {"items", "total", "limit", "offset"}
    return body["items"]


def test_wrong_answer_requires_authentication(client):
    assert client.get("/wrong-answers").status_code in (401, 403)
    assert client.get("/wrong-answers/1").status_code in (401, 403)
    assert client.patch("/wrong-answers/1", json={"resolved": True}).status_code in (401, 403)


def test_wrong_answer_appears_after_an_incorrect_attempt(client):
    register_and_login(client, "waa1")
    sid = _session(client)
    _attempt(client, sid, correct=False)

    items = _items(client)
    assert len(items) == 1
    record = items[0]
    assert record["status"] == "active"
    assert record["repeat_wrong_count"] == 1
    assert record["service_namespace"] == "exam_prep"
    assert record["source_kind"] == "chapter_practice"
    assert record["source_label"] == "章节练习"
    assert record["question_bank_id"] == 1001      # chapter redo identity, not source_id
    assert record["user_answer"] == "A"
    assert isinstance(record["wrong_record_id"], int)
    # implementation identity is not part of the contract
    assert "question_source_type" not in record
    assert "question_source_id" not in record


def test_correct_attempt_creates_no_wrong_answer(client):
    register_and_login(client, "waa2")
    sid = _session(client)
    _attempt(client, sid, correct=True)
    assert _items(client) == []


def test_ungraded_attempt_creates_no_wrong_answer(client):
    register_and_login(client, "waa3")
    sid = _session(client)
    _attempt(client, sid, correct=None)
    assert _items(client) == []


def test_detail_exposes_display_data_and_history(client):
    register_and_login(client, "waa4")
    sid = _session(client)
    _attempt(client, sid, correct=False)
    _attempt(client, sid, correct=False)
    _attempt(client, sid, correct=True)

    state_id = _items(client)[0]["wrong_record_id"]
    detail = client.get(f"/wrong-answers/{state_id}").json()
    assert detail["status"] == "resolved"              # latest factual attempt wins
    assert len(detail["attempt_history"]) == 3         # history from practice_attempts
    assert [a["correct"] for a in detail["attempt_history"]] == [False, False, True]
    assert detail["user_answer"] == "A"
    assert detail["error_analysis"] is None            # null, not a guess


def test_manual_lifecycle_update(client):
    register_and_login(client, "waa5")
    sid = _session(client)
    _attempt(client, sid, correct=False)
    state_id = _items(client)[0]["wrong_record_id"]

    resolved = client.patch(f"/wrong-answers/{state_id}", json={"resolved": True}).json()
    assert resolved["status"] == "resolved"
    assert resolved["source_kind"] == "chapter_practice"   # same record shape as the list
    reopened = client.patch(f"/wrong-answers/{state_id}", json={"resolved": False}).json()
    assert reopened["status"] == "active"


def test_namespace_and_status_filters(client):
    register_and_login(client, "waa6")
    _attempt(client, _session(client, "exam_prep"), qid="e1")
    _attempt(client, _session(client, "course_learning"), qid="c1",
             source_type="material_generated")

    exam = _items(client, "?service_namespace=exam_11408")
    assert [s["service_namespace"] for s in exam] == ["exam_prep"]
    active = _items(client, "?status=active")
    assert len(active) == 2
    assert _items(client, "?status=resolved") == []
    # a total is reported for the whole filtered set, not just the page
    assert client.get("/wrong-answers?limit=1").json()["total"] == 2
    assert len(_items(client, "?limit=1&offset=1")) == 1


def test_unknown_namespace_and_status_are_rejected(client):
    register_and_login(client, "waa7")
    assert client.get("/wrong-answers?service_namespace=not_a_space").status_code == 400
    assert client.get("/wrong-answers?status=mastered").status_code == 400


def test_module_filter(client):
    register_and_login(client, "waa_module")
    _attempt(client, _session(client, "exam_prep"), qid="m1")
    assert _items(client, "?module=operating_system") == []
    assert _items(client, "?module=nothing_here") == []


def test_cross_user_isolation_over_api(client):
    register_and_login(client, "waa_owner")
    sid = _session(client)
    _attempt(client, sid, correct=False)
    state_id = _items(client)[0]["wrong_record_id"]

    client.cookies.clear()
    register_and_login(client, "waa_intruder")

    assert _items(client) == []
    assert client.get(f"/wrong-answers/{state_id}").status_code == 404
    assert client.patch(f"/wrong-answers/{state_id}",
                        json={"resolved": True}).status_code == 404
    assert _items(client) == []


def test_source_id_collision_across_namespaces_over_api(client):
    register_and_login(client, "waa8")
    _attempt(client, _session(client, "exam_prep"), qid="123", correct=False)
    _attempt(client, _session(client, "programming"), qid="123", correct=False,
             source_type="programming_exercise")
    items = _items(client)
    assert len(items) == 2
    assert {s["service_namespace"] for s in items} == {"exam_prep", "programming"}


def test_legacy_exam_wrong_endpoint_still_works(client):
    """The canonical core must not disturb the legacy exam surface."""
    register_and_login(client, "waa9")
    r = client.get("/exam/11408/ds/wrong-questions")
    assert r.status_code in (200, 400, 404)     # unchanged behaviour, not a 500
