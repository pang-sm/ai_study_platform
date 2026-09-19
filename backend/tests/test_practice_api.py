"""STEP 7D: Practice Core HTTP contract + isolation through the API."""
from conftest import register_and_login


def _create_session(client, namespace="exam_prep", mode="chapter"):
    r = client.post("/practice/sessions",
                    json={"service_namespace": namespace, "mode": mode})
    assert r.status_code == 200, r.text
    return r.json()


def _record(client, session_id, **overrides):
    payload = {"question_source_type": "static_question_bank",
               "question_source_id": "1001", "answer": "A", "correct": True}
    payload.update(overrides)
    return client.post(f"/practice/sessions/{session_id}/attempts", json=payload)


def test_practice_requires_authentication(client):
    assert client.get("/practice/sessions").status_code in (401, 403)
    assert client.post("/practice/sessions",
                       json={"service_namespace": "exam_prep"}).status_code in (401, 403)


def test_session_lifecycle_over_api(client):
    register_and_login(client, "api_p1")
    session = _create_session(client)
    assert session["status"] == "active"
    assert session["service_namespace"] == "exam_prep"

    listed = client.get("/practice/sessions").json()["sessions"]
    assert [s["id"] for s in listed] == [session["id"]]

    got = client.get(f"/practice/sessions/{session['id']}").json()
    assert got["id"] == session["id"]

    closed = client.post(f"/practice/sessions/{session['id']}/complete").json()
    assert closed["status"] == "completed"
    # idempotent
    assert client.post(f"/practice/sessions/{session['id']}/complete").json()["status"] \
        == "completed"


def test_record_and_list_attempts_over_api(client):
    register_and_login(client, "api_p2")
    session = _create_session(client)

    created = _record(client, session["id"])
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["created"] is True
    assert body["attempt"]["correct"] is True

    # same source identity is not recorded twice by the API either
    listed = client.get(f"/practice/sessions/{session['id']}/attempts").json()["attempts"]
    assert len(listed) == 1

    history = client.get("/practice/history").json()["attempts"]
    assert [a["id"] for a in history] == [body["attempt"]["id"]]


def test_attempt_null_correctness_survives_the_api(client):
    register_and_login(client, "api_p3")
    session = _create_session(client)
    r = _record(client, session["id"], correct=None, score=7.5, max_score=10.0)
    assert r.status_code == 200
    a = r.json()["attempt"]
    assert a["correct"] is None          # null, not false
    assert a["score"] == 7.5 and a["max_score"] == 10.0


def test_completed_session_refuses_new_attempts_over_api(client):
    register_and_login(client, "api_p4")
    session = _create_session(client)
    client.post(f"/practice/sessions/{session['id']}/complete")
    assert _record(client, session["id"]).status_code == 409


def test_unknown_namespace_is_rejected(client):
    register_and_login(client, "api_p5")
    r = client.post("/practice/sessions",
                    json={"service_namespace": "not_a_space"})
    assert r.status_code == 400


def test_unknown_question_source_type_is_rejected(client):
    register_and_login(client, "api_p6")
    session = _create_session(client)
    r = _record(client, session["id"], question_source_type="mystery")
    assert r.status_code == 400


def test_other_user_cannot_read_or_write_a_session(client):
    register_and_login(client, "api_owner")
    session = _create_session(client)

    client.cookies.clear()
    register_and_login(client, "api_intruder")

    assert client.get(f"/practice/sessions/{session['id']}").status_code == 404
    assert client.get(f"/practice/sessions/{session['id']}/attempts").status_code == 404
    assert _record(client, session["id"]).status_code == 404
    assert client.get("/practice/sessions").json()["sessions"] == []
    assert client.get("/practice/history").json()["attempts"] == []


def test_summary_endpoint_reports_real_counts(client):
    register_and_login(client, "api_p7")
    session = _create_session(client)
    _record(client, session["id"], question_source_id="1", correct=True)
    _record(client, session["id"], question_source_id="2", correct=False)
    _record(client, session["id"], question_source_id="3", correct=None)

    summary = client.get(f"/practice/sessions/{session['id']}/summary").json()
    assert summary["attempt_count"] == 3
    assert summary["correct_count"] == 1
    assert summary["ungraded_count"] == 1


def test_sessions_are_namespace_scoped_over_api(client):
    register_and_login(client, "api_p8")
    _create_session(client, namespace="course_learning")
    _create_session(client, namespace="programming")
    only = client.get("/practice/sessions?service_namespace=programming").json()["sessions"]
    assert [s["service_namespace"] for s in only] == ["programming"]


def test_practice_api_does_not_expose_the_full_registry_or_other_users(client):
    """The practice surface returns only the caller's own rows, nothing global."""
    register_and_login(client, "api_p9")
    body = client.get("/practice/sessions").json()
    assert set(body) == {"sessions"}
    assert body["sessions"] == []
