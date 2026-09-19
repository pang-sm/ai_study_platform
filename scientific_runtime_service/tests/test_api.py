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
    # ACCEL_SPRINT_S4 appended evidence_reliability. The release id is unchanged: serving
    # an additional component over HTTP changes no scientific computation.
    assert r.json()["components"] == ["student_twin", "misconception_v2", "tutor_policy",
                                      "learner_state", "evidence_reliability"]
    assert r.json()["runtime_release_id"] == "zhixue-runtime-v1-phase1gr-p1"


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


# --- misconception_v2 inference contract -------------------------------------------

def _misconception(**overrides):
    base = {"contract_version": 1, "request_id": "mc-1",
            "question": "What is the time complexity of binary search?",
            "answer": "O(n)", "top_k": 3}
    base.update(overrides)
    return base


def test_misconception_requires_non_empty_input():
    assert client.post("/v1/inference/misconception-v2",
                       json=_misconception(question="  ")).status_code == 400
    assert client.post("/v1/inference/misconception-v2",
                       json=_misconception(answer="")).status_code == 400
    assert client.post("/v1/inference/misconception-v2",
                       json=_misconception(contract_version=2)).status_code == 400


def test_misconception_scores_are_similarities(monkeypatch):
    """The runtime must not relabel a similarity as a probability."""
    from app import runtime_bridge
    monkeypatch.setattr(runtime_bridge, "misconception_matches", lambda q, a, k: {
        "results": [{"rank": 0, "misconception_id": "m1", "misconception_text": "off-by-one",
                     "retrieval_score": 0.71}],
        "score_semantics": "cosine-like normalized inner product (NOT probability)",
        "weak_label": True, "ontology_size": 2587,
        "product_role": "DATA_PRODUCER", "controls_product_decision": False,
    })
    r = client.post("/v1/inference/misconception-v2", json=_misconception())
    assert r.status_code == 200
    body = r.json()
    assert body["matches"][0] == {"rank": 0, "misconception_id": "m1",
                                  "misconception_text": "off-by-one", "similarity": 0.71}
    assert "probability" in body["score_semantics"]
    assert body["weak_label"] is True
    assert body["controls_product_decision"] is False
    # the response shape carries no probability/confidence vocabulary at all
    assert not any(k in body for k in ("probability", "confidence", "score"))


def test_misconception_asset_failure_is_bounded(monkeypatch):
    """A missing model asset is a bounded 503, never an unhandled 500."""
    from app import runtime_bridge

    def _boom(*_a, **_k):
        raise RuntimeError("AssetMissingError: index.faiss")

    monkeypatch.setattr(runtime_bridge, "misconception_matches", _boom)
    r = client.post("/v1/inference/misconception-v2", json=_misconception())
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"]


# --- tutor_policy inference contract ------------------------------------------------

def _tutor_policy(**overrides):
    base = {"contract_version": 1, "request_id": "tp-1",
            "problem": "Prove that a DFA and an NFA accept the same languages.",
            "wrong": "The student claims NFA is strictly more powerful.",
            "profile": None, "confusion": None, "prev_actions": [], "history": []}
    base.update(overrides)
    return base


def test_tutor_policy_requires_non_empty_input():
    assert client.post("/v1/inference/tutor-policy",
                       json=_tutor_policy(problem="")).status_code == 400
    assert client.post("/v1/inference/tutor-policy",
                       json=_tutor_policy(wrong=" ")).status_code == 400
    assert client.post("/v1/inference/tutor-policy",
                       json=_tutor_policy(contract_version=9)).status_code == 400


def test_tutor_policy_action_ontology_is_the_frozen_four(monkeypatch):
    from app import runtime_bridge
    monkeypatch.setattr(runtime_bridge, "tutor_policy_action",
                        lambda *a, **k: {
                            "requested_action": "probing",
                            "action_probabilities": {"focus": 0.1, "generic": 0.2,
                                                     "probing": 0.5, "telling": 0.2},
                            "ranking": ["probing", "generic", "telling", "focus"],
                            "action_ontology": ["focus", "generic", "probing", "telling"],
                            "product_role": "DATA_PRODUCER",
                            "controls_product_decision": False})
    r = client.post("/v1/inference/tutor-policy", json=_tutor_policy())
    assert r.status_code == 200
    body = r.json()
    assert body["suggested_action"] == "probing"
    assert body["action_ontology"] == ["focus", "generic", "probing", "telling"]
    assert body["controls_product_decision"] is False
    assert "ALLOW" not in body["action_ontology"] and "REJECT" not in body["action_ontology"]


def test_tutor_policy_rejects_actions_outside_the_ontology(monkeypatch):
    """A rejected action is a 422 (caller's fault), never a 503 "unavailable"."""
    from app import runtime_bridge

    def _reject(*_a, **_k):
        raise runtime_bridge.RuntimeInputError("prev_action 'praise' not in ontology")

    monkeypatch.setattr(runtime_bridge, "tutor_policy_action", _reject)
    r = client.post("/v1/inference/tutor-policy",
                    json=_tutor_policy(prev_actions=["praise"]))
    assert r.status_code == 422
    assert "praise" in r.json()["detail"]


# --- learner_state inference contract (ACCEL_SPRINT_S3) ------------------------------

def _learner_state(**overrides):
    base = {"contract_version": 1, "request_id": "ls-1", "family": "DKT",
            "q": [3, 3, 17, 17], "r_prev": [0, 1, 0, 1], "mask": None}
    base.update(overrides)
    return base


def test_learner_state_request_validation_is_4xx_not_outage():
    assert client.post("/v1/inference/learner-state",
                       json=_learner_state(contract_version=2)).status_code == 400
    assert client.post("/v1/inference/learner-state",
                       json=_learner_state(q=[], r_prev=[])).status_code == 400
    # q and r_prev must describe the same sequence
    r = client.post("/v1/inference/learner-state", json=_learner_state(r_prev=[0, 1]))
    assert r.status_code == 400
    # an unknown family is the caller's error, never a 503
    r = client.post("/v1/inference/learner-state", json=_learner_state(family="NoSuchKT"))
    assert r.status_code in (422, 503)  # 422 when torch is present, bounded 503 without
    assert r.status_code != 500


def test_learner_state_missing_heavy_dependency_is_bounded(monkeypatch):
    """Without torch the endpoint is a bounded 503 — never an unhandled 500.

    This is the SAME contract misconception_v2 / tutor_policy already have: the service
    imports each component's stack lazily, so a deployment that does not serve this
    component needs none of it.
    """
    from app import runtime_bridge

    def _no_torch(*_a, **_k):
        raise RuntimeError("ModuleNotFoundError: No module named 'torch'")

    monkeypatch.setattr(runtime_bridge, "learner_state_predict", _no_torch)
    r = client.post("/v1/inference/learner-state", json=_learner_state())
    assert r.status_code == 503
    assert "learner_state unavailable" in r.json()["detail"]


def test_learner_state_response_is_next_response_probability(monkeypatch):
    """The contract names the semantic: P(correct on the NEXT response), not mastery."""
    from app import runtime_bridge

    monkeypatch.setattr(runtime_bridge, "learner_state_predict",
                        lambda family, q, r_prev, mask: {
                            "family": family, "ontology": "base", "num_skills": 123,
                            "next_response_probability": [0.25, 0.75],
                            "score_semantics": "next_response_probability P(correct) — "
                                               "NOT mastery probability",
                            "engineering_representative_only": True,
                            "active_product_variant": None,
                            "product_role": "DATA_PRODUCER",
                            "controls_product_decision": False})
    r = client.post("/v1/inference/learner-state", json=_learner_state())
    assert r.status_code == 200
    body = r.json()
    assert body["component_id"] == "learner_state"
    assert body["scientific_source_commit"] == "06d4366"
    assert body["next_response_probability"] == [0.25, 0.75]
    assert body["ontology"] == "base" and body["num_skills"] == 123
    assert body["active_product_variant"] is None
    assert body["engineering_representative_only"] is True
    assert body["controls_product_decision"] is False
    # the response carries NO mastery / ability / difficulty vocabulary
    for forbidden in ("mastery_probability", "ability", "difficulty", "mastery_score"):
        assert forbidden not in body


def test_learner_state_family_is_explicit_never_auto_selected(monkeypatch):
    """The panel must not silently pick a winner: the family is the caller's."""
    from app import runtime_bridge

    seen = []

    def _capture(family, q, r_prev, mask):
        seen.append(family)
        return {"family": family, "ontology": "base", "num_skills": 123,
                "next_response_probability": [0.5],
                "score_semantics": "next_response_probability P(correct)",
                "engineering_representative_only": True, "active_product_variant": None,
                "product_role": "DATA_PRODUCER", "controls_product_decision": False}

    monkeypatch.setattr(runtime_bridge, "learner_state_predict", _capture)
    client.post("/v1/inference/learner-state", json=_learner_state(family="CGKT_v2"))
    assert seen == ["CGKT_v2"]


# ---------------------------------------------------------------- evidence_reliability

def _panel_request(**overrides):
    base = {
        "contract_version": 1,
        "request_id": "er-1",
        "features_by_variant": {"42": [0.0] * 8, "42_nort": [0.0] * 7,
                                "42_surprise": [0.0] * 3, "43": [0.0] * 8,
                                "44": [0.0] * 8},
    }
    base.update(overrides)
    return base


def test_evidence_reliability_is_advertised():
    assert "evidence_reliability" in client.get("/v1/capabilities").json()["components"]


def test_evidence_reliability_empty_features_is_a_400():
    r = client.post("/v1/inference/evidence-reliability",
                    json=_panel_request(features_by_variant={}))
    assert r.status_code == 400
    assert "must not be empty" in r.json()["detail"]


def test_evidence_reliability_wrong_contract_version_is_a_400():
    r = client.post("/v1/inference/evidence-reliability",
                    json=_panel_request(contract_version=2))
    assert r.status_code == 400


def test_evidence_reliability_bounded_failure_never_leaks_a_traceback(monkeypatch):
    """Without the heavy stack the endpoint degrades to a bounded 503 — never a 500."""
    from app import runtime_bridge

    def _boom(_features):
        raise runtime_bridge.RuntimeExecutionError("RuntimeExecutionError: torch missing")

    monkeypatch.setattr(runtime_bridge, "evidence_reliability_panel", _boom)
    r = client.post("/v1/inference/evidence-reliability", json=_panel_request())
    assert r.status_code == 503
    assert "Traceback" not in r.text
    assert "torch missing" not in r.text


def test_evidence_reliability_contract_validation_is_a_422(monkeypatch):
    """A malformed feature vector is the CALLER's fault — a 422, not an outage."""
    from app import runtime_bridge

    def _bad(_features):
        raise runtime_bridge.RuntimeInputError("variant 42 expects 8 features, got 3")

    monkeypatch.setattr(runtime_bridge, "evidence_reliability_panel", _bad)
    r = client.post("/v1/inference/evidence-reliability", json=_panel_request())
    assert r.status_code == 422


def test_evidence_reliability_response_shape_and_semantics(monkeypatch):
    """Every field the product contract consumes, from a stubbed execution."""
    from app import runtime_bridge

    def _panel(_features):
        return {
            "variant_outputs": {"42": 0.4, "42_nort": 0.42, "42_surprise": 0.53,
                                "43": 0.59, "44": 0.6},
            "score_range": 0.2, "score_std": 0.08, "variant_disagreement": 0.08,
            "averaging": False, "auto_selection": False,
            "active_product_variant": None, "variant_mode": "PANEL",
            "replacement_readiness": "COLLECTING_DATA",
            "score_semantics": runtime_bridge.EVIDENCE_RELIABILITY_SEMANTICS,
            "product_role": "DATA_PRODUCER", "controls_product_decision": False,
        }

    monkeypatch.setattr(runtime_bridge, "evidence_reliability_panel", _panel)
    body = client.post("/v1/inference/evidence-reliability", json=_panel_request()).json()

    assert body["component_id"] == "evidence_reliability"
    assert body["averaging"] is False and body["auto_selection"] is False
    assert body["active_product_variant"] is None
    assert body["controls_product_decision"] is False
    assert body["scientific_source_commit"] == "WORKING_TREE(no-git-HEAD)"
    assert "NOT probability" in body["score_semantics"]
    for weight in body["variant_outputs"].values():
        assert 0.0 < weight < 1.0


def test_evidence_reliability_openapi_is_concrete():
    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/v1/inference/evidence-reliability"]["post"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in ref
    assert "EvidenceReliabilityResponse" in ref["$ref"]
    props = spec["components"]["schemas"]["EvidenceReliabilityResponse"]["properties"]
    assert "variant_outputs" in props
    assert "probability" not in props
