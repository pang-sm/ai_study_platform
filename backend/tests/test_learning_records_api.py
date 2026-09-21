"""STEP 7F: Learning Records HTTP contract, isolation, and the write redline."""
from conftest import register_and_login


def _practice(client, qid="1001", correct=False, ns="exam_prep", source_type=None):
    sid = client.post("/practice/sessions", json={"service_namespace": ns}).json()["id"]
    return client.post(f"/practice/sessions/{sid}/attempts", json={
        "question_source_type": source_type or "static_question_bank",
        "question_source_id": qid, "answer": "A", "correct": correct})


def test_records_require_authentication(client):
    assert client.get("/learning-records").status_code in (401, 403)
    assert client.get("/learning-records/summary").status_code in (401, 403)
    assert client.get("/learning-records/taxonomy").status_code in (401, 403)
    # the detail route matches a canonical UUID only, so authentication is reached only
    # for a well-formed record identity
    assert client.get(
        "/learning-records/11111111-1111-5111-8111-111111111111").status_code in (401, 403)


def test_detail_route_does_not_swallow_literal_sibling_paths(client):
    """A3: ``/learning-records/{event_id}`` no longer captures ``/stats``."""
    register_and_login(client, "lra_ambig")

    # the legacy course-notebook stats route is REACHABLE again (it used to 404 with the
    # canonical handler's "record not found" because '{event_id}' swallowed the path)
    stats = client.get("/learning-records/stats")
    assert stats.status_code == 200, stats.text

    # and a non-UUID id can never be interpreted as a canonical event id
    assert client.get("/learning-records/not-a-uuid").status_code != 200


def test_no_client_side_event_write_endpoint(client):
    """Events come from server-side facts only — no write surface exists (§25)."""
    register_and_login(client, "lra_write")
    for method in (client.post, client.put, client.patch, client.delete):
        for path in ("/learning-records", "/learning-records/some-event-id"):
            status = method(path).status_code
            assert not (200 <= status < 300), f"{method.__name__} {path} -> {status}"


def test_practice_produces_a_visible_practice_record(client):
    register_and_login(client, "lra1")
    _practice(client, correct=False, ns="exam_prep")

    body = client.get("/learning-records").json()
    assert body["has_more"] is False
    records = body["records"]
    assert len(records) == 1
    record = records[0]
    assert record["event_type"] == "question_answered"
    assert record["record_category"] == "PracticeEvent"
    assert record["service_namespace"] == "exam_prep"
    assert record["summary"]["correct"] is False
    assert record["source"]["type"] and record["source"]["id"]


def test_record_view_does_not_leak_internal_fields(client):
    register_and_login(client, "lra2")
    _practice(client)
    record = client.get("/learning-records").json()["records"][0]
    for leaked in ("item_snapshot_json", "payload", "item_content_hash", "answer",
                   "idempotency_key", "source_item_index"):
        assert leaked not in record, leaked


def test_record_detail_by_event_id(client):
    register_and_login(client, "lra3")
    _practice(client)
    event_id = client.get("/learning-records").json()["records"][0]["event_id"]
    detail = client.get(f"/learning-records/{event_id}").json()
    assert detail["event_id"] == event_id
    assert "recovery" in detail


def test_records_are_user_scoped(client):
    register_and_login(client, "lra_owner")
    _practice(client)
    event_id = client.get("/learning-records").json()["records"][0]["event_id"]

    client.cookies.clear()
    register_and_login(client, "lra_intruder")
    assert client.get("/learning-records").json()["records"] == []
    assert client.get(f"/learning-records/{event_id}").status_code == 404
    assert client.get("/learning-records/summary").json()["total_events"] == 0


def test_namespace_and_type_filters(client):
    register_and_login(client, "lra4")
    _practice(client, qid="e1", ns="exam_prep")
    _practice(client, qid="p1", ns="programming", source_type="programming_exercise")

    exam = client.get("/learning-records?service_namespace=exam_11408").json()["records"]
    assert [r["service_namespace"] for r in exam] == ["exam_prep"]
    prog = client.get("/learning-records?category=ProgrammingEvent").json()["records"]
    assert [r["event_type"] for r in prog] == ["code_submitted"]
    practice = client.get("/learning-records?event_type=question_answered").json()["records"]
    assert [r["event_type"] for r in practice] == ["question_answered"]


def test_unknown_filters_are_rejected(client):
    register_and_login(client, "lra5")
    assert client.get("/learning-records?event_type=bogus").status_code == 400
    assert client.get("/learning-records?category=BogusEvent").status_code == 400
    assert client.get("/learning-records?service_namespace=bogus").status_code == 400
    assert client.get("/learning-records?start_at=not-a-date").status_code == 400


def test_pagination_is_bounded_and_stable(client):
    register_and_login(client, "lra6")
    for i in range(4):
        _practice(client, qid=f"pg-{i}", ns="exam_prep")

    first = client.get("/learning-records?limit=2").json()
    assert len(first["records"]) == 2 and first["has_more"] is True
    second = client.get(f"/learning-records?limit=2&cursor={first['next_cursor']}").json()
    assert {r["event_id"] for r in first["records"]}.isdisjoint(
        {r["event_id"] for r in second["records"]})
    assert client.get("/learning-records?limit=100000").status_code == 422  # bounded


def test_summary_endpoint(client):
    register_and_login(client, "lra7")
    _practice(client, qid="s1", correct=True)
    _practice(client, qid="s2", correct=False)
    summary = client.get("/learning-records/summary").json()
    assert summary["practice_attempts"] == 2
    assert summary["factual_correct"] == 1
    assert summary["factual_incorrect"] == 1
    assert summary["metrics_semantics"].startswith("deterministic")


def test_taxonomy_endpoint_is_read_only_reference(client):
    register_and_login(client, "lra8")
    body = client.get("/learning-records/taxonomy").json()
    assert body["event_schema_version"] == 2
    # ACCEL_SPRINT_S2: the type-level set; the per-event input rule is what decides.
    assert body["student_twin_eligible_types"] == ["course_practice", "question_answered"]
    # CONTRACT CORRECTION (P4). A rating of an AI response is product telemetry about the
    # RESPONSE, not study history — the same family as the AI accounting fact that was
    # already here. It joins this list so no learner ever sees "you rated this 👎" in 学习记录.
    assert body["audit_only_event_types"] == ["ai_called", "ai_feedback_submitted"]
    assert any(row["event_type"] == "ai_called" for row in body["ownership_matrix"])
