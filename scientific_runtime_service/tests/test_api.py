"""Runtime service API tests (StudentTwin inference contract v1)."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _request(**overrides):
    base = {
        "contract_version": 1,
        "request_id": "req-1",
        "runtime_release_id": "zhixue-runtime-v1-phase1gr-p1",
        "user_ref": "u1",
        "target_event_id": "e2",
        "events": [
            {"event_id": "e1", "occurred_at": 1000.0, "activity_type": "PRACTICE",
             "item_id": "q1", "concept_ref": "c1", "correct": False,
             "source": "course_practice", "response_time_ms": None, "attempt_no": None, "hints": None},
            {"event_id": "e2", "occurred_at": 1060.0, "activity_type": "PRACTICE",
             "item_id": "q1", "concept_ref": "c1", "correct": True,
             "source": "course_practice", "response_time_ms": None, "attempt_no": None, "hints": None},
        ],
    }
    base.update(overrides)
    return base


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["runtime_release_id"] == "zhixue-runtime-v1-phase1gr-p1"
    assert body["component"] == "student_twin"


def test_capabilities():
    r = client.get("/v1/capabilities")
    assert r.status_code == 200
    assert r.json()["components"] == ["student_twin"]


def test_invalid_contract_version():
    r = client.post("/v1/inference/student-twin", json=_request(contract_version=2))
    assert r.status_code == 400


def test_empty_event_list():
    r = client.post("/v1/inference/student-twin", json=_request(events=[]))
    assert r.status_code == 400


def test_invalid_event_missing_required():
    ev = {"event_id": "e1"}  # missing occurred_at/activity_type/correct
    r = client.post("/v1/inference/student-twin", json=_request(events=[ev]))
    assert r.status_code == 422


def test_one_event():
    body = _request(events=_request()["events"][:1], target_event_id="e1")
    r = client.post("/v1/inference/student-twin", json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp["contract_version"] == 1
    assert resp["component_id"] == "student_twin"
    assert resp["target_event_id"] == "e1"
    assert resp["replayed_events"] == 1
    assert resp["scientific_source_class"] == "ORIGINAL_ARCHIVE_VERIFIED"
    assert resp["scientific_source_commit"] == "a16efa27aac90d9c8d8d9ee703aefe5919f4839e"
    assert resp["state"]["user_id"] == "u1"
    assert "concepts" in resp["state"] and "global_ability" in resp["state"]


def test_multiple_events():
    r = client.post("/v1/inference/student-twin", json=_request())
    assert r.status_code == 200
    resp = r.json()
    assert resp["replayed_events"] == 2
    assert resp["state"]["concepts"]["c1"]["exposure_count"] == 2


def test_determinism():
    body = _request()
    a = client.post("/v1/inference/student-twin", json=body).json()["state"]
    b = client.post("/v1/inference/student-twin", json=body).json()["state"]
    assert a == b


def test_optional_fields_preserved_as_null():
    body = _request()
    r = client.post("/v1/inference/student-twin", json=body)
    assert r.status_code == 200
    # the scientific state is deterministic regardless; optional fields stayed null in
    # the request and were not fabricated by the service
    assert body["events"][0]["response_time_ms"] is None
    assert body["events"][0]["attempt_no"] is None
    assert body["events"][0]["hints"] is None


# --- Phase 6R request validation ---
def test_target_event_id_must_match_last_event():
    # events end with e2, but target_event_id is e1
    r = client.post("/v1/inference/student-twin", json=_request(target_event_id="e1"))
    assert r.status_code == 400


def test_non_unique_event_id_rejected():
    body = _request()
    body["events"][1]["event_id"] = "e1"  # duplicate e1
    r = client.post("/v1/inference/student-twin", json=body)
    assert r.status_code == 400


def test_out_of_order_events_rejected():
    body = _request()
    body["events"] = list(reversed(body["events"]))  # decreasing occurred_at
    r = client.post("/v1/inference/student-twin", json=body)
    assert r.status_code == 400


def test_wrong_runtime_release_id_rejected():
    r = client.post("/v1/inference/student-twin",
                    json=_request(runtime_release_id="zhixue-runtime-v1-phase1gr"))
    assert r.status_code == 400
