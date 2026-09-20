"""ACCEL_SPRINT_S7 — CS408_INTERACTION_DATASET_V1, the readiness gate and the evaluator.

The sprint's central result is a REFUSAL: the product holds no real CS408 interaction data,
so the pre-registered readiness gate fails and no model is trained. These tests hold that
refusal to its reasons — the gate may not be lowered, the shadow evaluator may not invent a
target, and closing the evidence_reliability scaler gate must not open its product surface.

They also hold the parts that are not conditional: the dataset contract's identity, the
deterministic export, the learner-grouped split, the native ontology, the metrics, and the
fact that none of it can import the scientific stack into the product backend.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from conftest import register_and_login

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"

CS408_CTX = {"service_namespace": "exam_prep", "subject_key": "operating_system",
             "exam_module_id": "operating_system", "knowledge_point_id": "2.1"}


# ============================================================ helpers

def _event(db, user_id: int, *, event_id: str, correct, occurred_at: float,
           module: str = "operating_system", concept: str | None = "2.1",
           question_id: str = "Q1", attempt_index=None, response_time_ms=None,
           response_time_source=None, event_type: str = "question_answered"):
    from data_plane.models import LearningEvent

    ref = {}
    if module:
        ref["exam_module_id"] = module
    if concept:
        ref["knowledge_point_id"] = concept
    row = LearningEvent(
        event_id=event_id,
        event_type=event_type,
        source_type="static_question_bank",
        source_attempt_id=event_id,
        source_item_key=question_id,
        source_item_index=0,
        user_id=user_id,
        service_key="exam_prep",
        subject_key="cs_408",
        question_id=question_id,
        knowledge_point_ref_json=json.dumps(ref) if ref else None,
        correct=correct,
        occurred_at=occurred_at,
        ingested_at=occurred_at,
        attempt_index=attempt_index,
        response_time_ms=response_time_ms,
        response_time_source=response_time_source,
        idempotency_key=f"idem-{event_id}",
        # ACCEL_PRODUCT_S10: a real learner fact declares itself one; an unstamped row is
        # excluded from every dataset by design.
        data_origin="LEARNER",
    )
    db.add(row)
    db.commit()
    return row


# ============================================================ PART B — contract

def test_the_dataset_contract_is_versioned_and_named():
    from science import kt_native

    spec = kt_native.dataset_spec()
    assert spec["dataset_version"] == "CS408_INTERACTION_DATASET_V1"
    assert spec["exam_track_id"] == "cs_408"
    assert spec["contract_version"] == "kt-v1"
    assert spec["collection_start"]["version"]
    for field in ("dataset_version", "catalog_version", "exam_track_id", "export_version",
                  "collection_start"):
        assert field in spec["required_scope_fields"], field


def test_a_fact_may_not_be_required_to_carry_the_track(client, db_session):
    """PART B3: exam_track_id belongs to the DATASET SCOPE and is not written on a fact."""
    from data_plane.models import LearningEvent
    from science import kt_native

    spec = kt_native.dataset_spec()
    assert "exam_track_id" not in spec["required_interaction_fields"]
    # and the contract says so explicitly, so a reader does not re-add it "for completeness"
    assert "DATASET" in spec["scope_semantics"]["exam_track_id"]

    user = register_and_login(client, f"s7trk{uuid.uuid4().hex[:8]}")
    _event(db_session, user["id"], event_id=f"trk-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=1_700_000_000.0)
    body = kt_native.build_v1(db_session, service_namespace="exam_prep",
                              user_id=user["id"])
    assert body["scope"]["exam_track_id"] == "cs_408"
    for sequence in body["sequences"]:
        for item in sequence["interactions"]:
            assert "exam_track_id" not in item


def test_the_export_is_deterministic_across_runs(client, db_session):
    """PART R: same snapshot + same contract -> byte-identical body, including the hash."""
    from science import kt_native

    user = register_and_login(client, f"s7det{uuid.uuid4().hex[:8]}")
    base = 1_700_000_000.0
    for i, correct in enumerate([True, False, True, True]):
        _event(db_session, user["id"], event_id=f"det-{i}-{uuid.uuid4().hex[:6]}",
               correct=correct, occurred_at=base + i)

    first = kt_native.build_v1(db_session, service_namespace="exam_prep")
    second = kt_native.build_v1(db_session, service_namespace="exam_prep")
    assert first["dataset_hash"] == second["dataset_hash"]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    # the body carries no wall clock: a hash that changed every second would be meaningless
    assert "generated_at" not in first
    assert "generated_at" not in (first.get("scope") or {})


def test_the_scoped_identity_is_present_and_compliance_can_pass(client, db_session):
    from science import kt_native

    user = register_and_login(client, f"s7id{uuid.uuid4().hex[:8]}")
    _event(db_session, user["id"], event_id=f"id-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=1_700_000_000.0)
    body = kt_native.build_v1(db_session, service_namespace="exam_prep",
                              user_id=user["id"])
    compliance = kt_native.spec_compliance(body)
    assert compliance["missing_scope_fields"] == []
    assert compliance["compliant"] is True
    identity = kt_native.dataset_identity(body)
    assert identity["dataset_version"] == "CS408_INTERACTION_DATASET_V1"
    assert identity["catalog_version"] != "UNAVAILABLE"
    assert identity["dataset_hash"] == body["dataset_hash"]


# ============================================================ PART B2/C — missing != zero

def test_a_missing_observation_is_never_reported_as_zero(client, db_session):
    """A real 0 and 'not observed' are different facts and must stay different."""
    from science import kt_native

    user = register_and_login(client, f"s7miss{uuid.uuid4().hex[:8]}")
    _event(db_session, user["id"], event_id=f"m1-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=1_700_000_000.0)                       # nothing observed
    _event(db_session, user["id"], event_id=f"m2-{uuid.uuid4().hex[:6]}", correct=False,
           occurred_at=1_700_000_001.0, attempt_index=1,      # a REAL observed 0 duration
           response_time_ms=0, response_time_source="CLIENT_MONOTONIC")

    measured = kt_native.audit(db_session, service_namespace="exam_prep",
                               user_id=user["id"])
    body = kt_native.build_v1(db_session, service_namespace="exam_prep",
                              user_id=user["id"])
    items = [i for s in body["sequences"] for i in s["interactions"]]
    by_ref = {i["attempt_ref"]: i for i in items}

    observed_zero = [i for i in items if i.get("duration_ms") == 0]
    assert len(observed_zero) == 1, "a real observed zero must survive as a zero"
    assert observed_zero[0]["duration_source"] == "CLIENT_MONOTONIC"
    nulls = [i for i in items if i.get("duration_ms") is None]
    assert nulls, "the unobserved interaction must still be NULL"
    for item in nulls:
        assert item["duration_source"] is None, "a duration and its provenance travel together"

    miss = measured["telemetry_missingness"]
    assert miss["duration_ms"]["observed"] == 1
    assert miss["duration_ms"]["missing"] == len(items) - 1
    assert "NOT OBSERVED" in miss["rule"]
    assert by_ref  # the reader and the audit describe the same rows


def test_a_non_boolean_verdict_is_excluded_and_counted_not_read_as_wrong(client, db_session):
    from science import kt_native

    user = register_and_login(client, f"s7tri{uuid.uuid4().hex[:8]}")
    _event(db_session, user["id"], event_id=f"t1-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=1_700_000_000.0)
    _event(db_session, user["id"], event_id=f"t2-{uuid.uuid4().hex[:6]}", correct=None,
           occurred_at=1_700_000_001.0)

    measured = kt_native.audit(db_session, service_namespace="exam_prep",
                               user_id=user["id"])
    assert measured["total_eligible_interactions"] == 1
    assert measured["excluded"].get("CORRECTNESS_NOT_AUTHORITATIVE_BOOLEAN") == 1
    assert measured["invalid_correctness_events"] == 1
    # the ungraded item is NOT a negative label
    assert measured["label_balance"]["incorrect"] == 0


# ============================================================ PART E — splits

def test_a_learner_is_in_exactly_one_split():
    from science import kt_native

    body = {"sequences": [{"learner_ref": f"L{i:04d}", "concept_key": f"C{i % 5}",
                           "concept_level": "knowledge_point_id",
                           "exam_subject_id": "cs_408",
                           "interactions": [{"attempt_ref": f"{i}-{j}", "item_ref": "Q",
                                             "concept_key": f"C{i % 5}",
                                             "concept_level": "knowledge_point_id",
                                             "correct": True,
                                             "occurred_at": float(j)} for j in range(6)]}
                          for i in range(400)]}
    split = kt_native.primary_split(body)
    assert split["overlap_is_empty"] is True
    assert split["learner_overlap_between_splits"] == []
    seen: set[str] = set()
    for name in ("train", "dev", "test"):
        refs = {s["learner_ref"] for s in body["sequences"]
                if kt_native.kt_dataset.split_of(s["learner_ref"]) == name}
        assert not (refs & seen), f"{name} shares a learner with an earlier split"
        seen |= refs


def test_the_temporal_holdout_is_per_learner_and_ordered():
    """A GLOBAL time cut would put whole learners on one side and degenerate into the
    primary split; the holdout must cut each learner's own history."""
    from science import kt_native

    body = {"sequences": [
        {"learner_ref": f"L{i}", "concept_key": "C", "concept_level": "knowledge_point_id",
         "interactions": [{"attempt_ref": f"{i}-{j}", "item_ref": "Q", "correct": True,
                           "occurred_at": 1000.0 + i * 100 + j} for j in range(10)]}
        for i in range(5)]}
    holdout = kt_native.temporal_holdout(body, holdout_share=0.30)
    assert holdout["policy_version"] == "kt-split-temporal-v1"
    assert holdout["answer_is_earlier_than_holdout"] is True
    assert holdout["train_interactions"] == 35
    assert holdout["holdout_interactions"] == 15
    # every learner contributes to BOTH sides — that is what makes it temporal, not grouped
    assert holdout["learners_with_both_sides"] == 5


def test_the_temporal_holdout_refuses_a_degenerate_share():
    from science import kt_native

    body = {"sequences": []}
    for bad in (0.0, 1.0, -0.5, 2.0):
        with pytest.raises(ValueError):
            kt_native.temporal_holdout(body, holdout_share=bad)


# ============================================================ PART F3 — native ontology

def test_the_native_ontology_is_contiguous_stable_and_not_a_foreign_mapping():
    from science import kt_native

    body = {"sequences": [
        {"learner_ref": "L1", "concept_key": "b_concept", "concept_level": "knowledge_point_id",
         "interactions": []},
        {"learner_ref": "L1", "concept_key": "a_concept", "concept_level": "exam_module_id",
         "interactions": []},
    ]}
    mapping = kt_native.native_ontology(body)
    assert mapping["kind"] == "NATIVE_PRODUCT_ONTOLOGY"
    assert mapping["concept_count"] == 2
    assert mapping["mapping"] == {"a_concept": 0, "b_concept": 1}
    assert kt_native.ontology_is_native(mapping)["native"] is True
    assert "ASSISTments" in mapping["not_a_foreign_mapping"]
    assert "NOT" in mapping["not_a_foreign_mapping"]

    # stability: adding a NEW concept appends an index and renumbers nothing
    grown = dict(body)
    grown["sequences"] = body["sequences"] + [
        {"learner_ref": "L2", "concept_key": "c_concept", "concept_level": "knowledge_point_id",
         "interactions": []}]
    grown_map = kt_native.native_ontology(grown)
    for key, index in mapping["mapping"].items():
        assert grown_map["mapping"][key] == index, f"{key} was renumbered"
    assert grown_map["concept_count"] == 3


def test_a_foreign_ontology_reuse_is_detectable():
    from science import kt_native

    foreign = {"ontology_version": "assistments-skills", "kind": "FOREIGN",
               "concept_count": 123, "mapping": {"skill_1": 0, "skill_2": 1}}
    assert kt_native.ontology_is_native(foreign)["native"] is False
    # a non-contiguous index set is also a foreign signature
    gappy = {"kind": "NATIVE_PRODUCT_ONTOLOGY", "concept_count": 3,
             "mapping": {"a": 0, "b": 7, "c": 9}}
    assert kt_native.ontology_is_native(gappy)["indices_contiguous_from_zero"] is False


# ============================================================ PART P — privacy

def test_the_export_carries_no_pii(client, db_session):
    from science import kt_native

    user = register_and_login(client, f"s7priv{uuid.uuid4().hex[:8]}")
    username = user["username"]
    _event(db_session, user["id"], event_id=f"p1-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=1_700_000_000.0)
    body = kt_native.build_v1(db_session, service_namespace="exam_prep",
                              user_id=user["id"])
    text = json.dumps(body, ensure_ascii=False)

    assert username not in text, "the learner's username reached the export"
    assert kt_native.spec_compliance(body)["forbidden_field_leak"] == []
    # the learner reference is an opaque digest, not the user id
    for sequence in body["sequences"]:
        assert sequence["learner_ref"] != str(user["id"])
        assert len(sequence["learner_ref"]) == 16


# ============================================================ PART C1 — coverage levels

def test_module_chapter_and_concept_coverage_are_reported_separately(client, db_session):
    """A chapter id is not a concept and the two are never summed into one number."""
    from science import kt_native

    user = register_and_login(client, f"s7cov{uuid.uuid4().hex[:8]}")
    _event(db_session, user["id"], event_id=f"c1-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=1_700_000_000.0, module="data_structure", concept=None)
    _event(db_session, user["id"], event_id=f"c2-{uuid.uuid4().hex[:6]}", correct=False,
           occurred_at=1_700_000_001.0, module="operating_system", concept="2.1")

    measured = kt_native.audit(db_session, service_namespace="exam_prep",
                               user_id=user["id"])
    assert measured["chapter_coverage"]["levels"] == 1        # only the module-only fact
    assert measured["concept_coverage"]["levels"] == 1        # only the concept-bearing fact
    assert measured["module_coverage"]["levels"] == 2
    # the two buckets are DISJOINT levels, not nested: a chapter id is never counted as a
    # concept, which is the whole reason C1 asks for them separately
    assert set(measured["chapter_coverage"]["chapters"]) == {"data_structure"}
    assert set(measured["concept_coverage"]["concepts"]) == {"2.1"}


def test_a_title_is_never_promoted_to_a_concept(client, db_session):
    """A knowledge point id that only embeds a display title is NOT a stable concept."""
    from science import kt_native

    user = register_and_login(client, f"s7title{uuid.uuid4().hex[:8]}")
    _event(db_session, user["id"], event_id=f"tt-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=1_700_000_000.0, module="computer_network", concept=None)
    measured = kt_native.audit(db_session, service_namespace="exam_prep",
                               user_id=user["id"])
    assert measured["concept_coverage"]["levels"] == 0
    assert measured["chapter_coverage"]["levels"] == 1


# ============================================================ PART D — readiness gate

def test_the_readiness_gate_is_pre_registered_before_any_training():
    from science import kt_native

    gate = kt_native.READINESS_GATE
    assert gate["registered_before_training"] is True
    assert gate["gate_version"] == "cs408-kt-readiness-v1"
    for key, value in gate["thresholds"].items():
        assert isinstance(value, (int, float)) and value > 0, key
    assert gate["thresholds"]["users_with_eligible_interactions"] >= 100
    assert gate["may_not_be_lowered_to_unlock_a_result"] is True
    # every threshold states WHY, so it cannot be quietly relaxed as "a judgement call"
    for key in gate["thresholds"]:
        assert key in gate["rationale"], key


def test_an_empty_product_fails_the_gate_and_refuses_to_train(client, db_session):
    """THE SPRINT'S CENTRAL MEASUREMENT, asserted."""
    from science import kt_native

    # a learner with no facts at all — the product's real state today, measured
    # WITHOUT the rest of this test session's synthetic events in scope
    NOBODY = 987654321
    measured = kt_native.audit(db_session, service_namespace="exam_prep", user_id=NOBODY)
    body = kt_native.build_v1(db_session, service_namespace="exam_prep", user_id=NOBODY)
    split = kt_native.primary_split(body)
    readiness = kt_native.evaluate_readiness(measured, split=split)
    decision = kt_native.training_decision(readiness)

    assert measured["users_with_eligible_interactions"] == 0
    assert measured["total_eligible_interactions"] == 0
    assert readiness["verdict"] == "FAIL"
    assert "users_with_eligible_interactions" in readiness["failed_checks"]
    assert decision["training_permitted"] is False
    assert decision["cs408_native_kt_trained"] is False
    # the refusal is a RESULT, and it says so rather than reading like an error
    assert "RESULT" in decision["note"]


def test_the_training_stage_refuses_before_it_could_run(client, db_session):
    """The pipeline's first stage must be able to say no, or it is merely ordered."""
    from science import kt_native

    NOBODY = 987654322
    measured = kt_native.audit(db_session, service_namespace="exam_prep", user_id=NOBODY)
    body = kt_native.build_v1(db_session, service_namespace="exam_prep", user_id=NOBODY)
    readiness = kt_native.evaluate_readiness(measured, split=kt_native.primary_split(body))
    plan = kt_native.training_run_plan(readiness, kt_native.native_ontology(body))

    assert plan["permitted"] is False
    assert plan["refused_by"] == "DATA_READINESS_GATE"
    assert plan["max_resulting_mode"] == "SHADOW"
    assert plan["implemented"] is False, "a trainer that was never validated must not claim to exist"
    # the architecture question PART F asks, answered as a contract rather than a choice
    assert plan["candidate_families"] == ["DKT", "SimpleKT", "AKT"]
    assert "CGKT" in plan["excluded_families"]
    assert "LEGACY_LEARNER_STATE" in plan["excluded_families"]
    assert plan["calibration"]["fit_on"] == "dev"
    assert plan["calibration"]["evaluate_on"] == "test"
    assert plan["must_produce"] == list(kt_native.REQUIRED_ARTIFACT_KINDS)
    assert "OFFLINE ONLY" in plan["environment"]


def test_the_gate_reads_the_thresholds_it_does_not_write_them():
    from science import kt_native

    before = json.dumps(kt_native.READINESS_GATE, sort_keys=True)
    kt_native.evaluate_readiness({"users_with_eligible_interactions": 0,
                                  "total_eligible_interactions": 0,
                                  "sequence_length": {"p50": None},
                                  "concept_coverage": {"concepts": {}},
                                  "module_coverage": {"levels": 0},
                                  "label_balance": {"minority_share": None}})
    assert json.dumps(kt_native.READINESS_GATE, sort_keys=True) == before


# ============================================================ PART I/J/O — gates & packaging

def test_promotion_cannot_exceed_shadow_without_an_explicit_decision():
    from science import kt_native

    gate = kt_native.promotion_gate({})
    assert gate["max_mode"] == "SHADOW"
    assert gate["promotion_permitted"] is False
    assert set(gate["unmet"]) == set(kt_native.PROMOTION_REQUIREMENTS)
    # even a fully evidenced model needs the explicit final decision
    full = {name: True for name in kt_native.PROMOTION_REQUIREMENTS}
    assert kt_native.promotion_gate(full)["promotion_permitted"] is False
    assert kt_native.promotion_gate(
        {**full, "explicit_final_gate_decision": True})["promotion_permitted"] is True


def test_the_artifact_manifest_requires_every_kind_and_no_absolute_path():
    from science import kt_native

    entries = {k: {"sha256": "ab" * 32, "ref": f"{k}.bin"}
               for k in kt_native.REQUIRED_ARTIFACT_KINDS}
    manifest = kt_native.artifact_manifest(entries, source_commit="deadbeef")
    assert manifest["complete"] is True
    assert manifest["missing_kinds"] == []
    assert manifest["absolute_path_refs"] == []
    assert manifest["manifest_hash"]

    incomplete = kt_native.artifact_manifest(
        {k: {"sha256": "ab", "ref": f"{k}.bin"} for k in ("model_weights",)})
    assert incomplete["complete"] is False
    assert incomplete["missing_kinds"]

    absolute = dict(entries)
    absolute["model_weights"] = {"sha256": "ab", "ref": "C:\\models\\weights.pt"}
    assert kt_native.artifact_manifest(absolute)["absolute_path_refs"] == ["model_weights"]


def test_the_evidence_reliability_v2_decision_names_the_real_trigger():
    from science import kt_native

    decision = kt_native.v2_decision()
    assert decision["classification"] == "PRODUCT_NATIVE_RETRAIN_REQUIRED"
    assert decision["required"] is True
    assert "ontology" in decision["trigger"]
    # S7 recovered the preprocessing, so that is explicitly NOT the trigger any more
    assert "preprocessing loss" in decision["not_the_trigger"]
    assert decision["old_family_product_mode"] == "SHADOW_NOT_USER_VISIBLE"


# ============================================================ PART G — metrics

def test_metrics_match_their_analytic_values():
    from science import kt_evaluation as ev

    y = [1.0, 1.0, 0.0, 0.0]
    p = [0.9, 0.8, 0.2, 0.1]
    assert ev.auroc(y, p) == 1.0
    assert ev.auroc(y, [1 - x for x in p]) == 0.0
    assert ev.auroc([1.0, 0.0], [0.5, 0.5]) == 0.5     # ties get mid-ranks
    assert ev.auroc([1.0, 1.0], [0.5, 0.6]) is None    # one class: no ranking to measure
    assert ev.accuracy(y, p) == 1.0
    assert ev.brier(y, p) == pytest.approx(0.025)
    assert ev.ece([1.0, 0.0], [1.0, 0.0]) == 0.0
    assert ev.ece([1.0, 0.0], [0.0, 1.0]) == 1.0
    assert ev.log_loss(y, p) == pytest.approx(
        -(sum(__import__("math").log(v) for v in (0.9, 0.8)) +
          sum(__import__("math").log(v) for v in (0.8, 0.9))) / 4)


def test_a_row_without_a_target_is_excluded_and_counted():
    from science import kt_evaluation as ev

    metrics = ev.metrics_from_pairs([(True, 0.9), (None, 0.4), (False, 0.2), (True, None)])
    assert metrics["n"] == 2
    assert metrics["excluded_rows"] == 2
    assert "EXCLUDED" in metrics["exclusion_rule"]


def test_per_module_metrics_report_sample_counts_and_refuse_to_score_noise():
    from science import kt_evaluation as ev

    pairs = [(True, 0.9), (False, 0.1), (True, 0.8)]
    groups = ["m1", "m1", "m2"]
    out = ev.grouped_metrics(pairs, groups, min_n=2)
    assert out["m1"]["n"] == 2
    assert out["m1"]["metrics"]["auroc"] is not None
    assert out["m2"]["metrics"] is None
    assert "noise" in out["m2"]["reason"]


def test_a_simple_baseline_is_available_and_is_not_a_model():
    """PART F1: the global correctness prior, the honest thing a learned model must beat."""
    from science import kt_evaluation as ev

    y = [1.0, 1.0, 0.0, 1.0]
    prior = sum(y) / len(y)
    metrics = ev.classification_metrics(y, [prior] * len(y))
    assert metrics["auroc"] == 0.5                          # a constant cannot rank
    assert metrics["accuracy"] == pytest.approx(0.75)       # it predicts the majority class
    assert metrics["majority_class_rate"] == pytest.approx(0.75)


# ============================================================ PART H — calibration

def test_calibration_is_fitted_on_dev_and_evaluated_on_an_untouched_test():
    from science import kt_evaluation as ev

    dev_y = [1, 1, 0, 0, 1, 0, 1, 0]
    dev_p = [0.9, 0.7, 0.4, 0.3, 0.8, 0.2, 0.6, 0.5]
    cal = ev.fit_calibrator("PLATT", dev_y, dev_p, dev_split_digest="devdigest")
    assert cal["fitted_on"] == "dev"
    assert cal["evaluated_on"] == "test"
    assert cal["fit_split_digest"] == "devdigest"
    assert cal["calibrator_hash"]

    test_y = [1, 0, 1, 0]
    test_p = [0.95, 0.85, 0.6, 0.4]
    calibrated = ev.apply_calibrator(cal, test_p)
    assert len(calibrated) == len(test_p)
    assert all(0.0 <= v <= 1.0 for v in calibrated)
    # the calibrator was NOT refitted on test: the same dev fit gives the same outputs
    assert calibrated == ev.apply_calibrator(cal, test_p)


def test_every_calibration_method_is_deterministic_and_bounded():
    from science import kt_evaluation as ev

    y = [1, 1, 0, 0, 1, 0]
    p = [0.9, 0.7, 0.4, 0.3, 0.8, 0.2]
    for method in ev.CALIBRATION_METHODS:
        first = ev.fit_calibrator(method, y, p)
        second = ev.fit_calibrator(method, y, p)
        assert first["calibrator_hash"] == second["calibrator_hash"]
        out = ev.apply_calibrator(first, p)
        assert all(0.0 <= v <= 1.0 for v in out)


def test_an_unknown_calibration_method_is_refused():
    from science import kt_evaluation as ev

    with pytest.raises(ValueError):
        ev.fit_calibrator("MAGIC", [1], [0.5])
    with pytest.raises(ValueError):
        ev.apply_calibrator({"method": "MAGIC", "params": {}}, [0.5])


# ============================================================ PART N — online evaluator

def test_the_shadow_evaluator_pairs_a_prediction_with_the_NEXT_observed_response():
    from science import kt_evaluation as ev

    predictions = [{"prediction_id": "p1", "learner_ref": "L1", "concept_key": "C1",
                    "predicted_at": 100.0, "probability": 0.8}]
    outcomes = [
        {"event_id": "e0", "learner_ref": "L1", "concept_key": "C1",
         "occurred_at": 50.0, "correct": False},        # EARLIER — must not be the target
        {"event_id": "e1", "learner_ref": "L1", "concept_key": "C1",
         "occurred_at": 101.0, "correct": True},
        {"event_id": "e2", "learner_ref": "L1", "concept_key": "C1",
         "occurred_at": 200.0, "correct": False},
    ]
    report = ev.evaluate_shadow(predictions, outcomes)
    assert report["predictions_paired"] == 1
    assert report["observations"][0]["target_event_id"] == "e1"
    assert report["observations"][0]["target_correct"] is True
    assert report["overall"]["n"] == 1


def test_an_unobserved_target_is_excluded_not_scored_as_a_miss():
    from science import kt_evaluation as ev

    report = ev.evaluate_shadow(
        [{"prediction_id": "p1", "learner_ref": "L1", "concept_key": "C1",
          "predicted_at": 1000.0, "probability": 0.9}],
        [{"event_id": "e", "learner_ref": "L1", "concept_key": "C1",
          "occurred_at": 10.0, "correct": True}])
    assert report["predictions_paired"] == 0
    assert report["predictions_without_target"] == 1
    assert report["unmatched_reason_code"] == ev.NO_TARGET_OBSERVED
    assert report["overall"]["n"] == 0
    assert "not observed yet" in report["unmatched_rule"]


def test_an_ungraded_fact_is_not_a_target():
    from science import kt_evaluation as ev

    report = ev.evaluate_shadow(
        [{"prediction_id": "p1", "learner_ref": "L1", "concept_key": "C1",
          "predicted_at": 1.0, "probability": 0.9}],
        [{"event_id": "e", "learner_ref": "L1", "concept_key": "C1",
          "occurred_at": 2.0, "correct": None}])
    assert report["predictions_paired"] == 0
    assert report["predictions_without_target"] == 1


def test_the_evaluator_is_cross_user_isolated():
    """Another learner's response is never this learner's target."""
    from science import kt_evaluation as ev

    report = ev.evaluate_shadow(
        [{"prediction_id": "p1", "learner_ref": "L1", "concept_key": "C1",
          "predicted_at": 1.0, "probability": 0.9}],
        [{"event_id": "e", "learner_ref": "L2", "concept_key": "C1",
          "occurred_at": 2.0, "correct": True}])
    assert report["predictions_paired"] == 0
    assert report["predictions_without_target"] == 1


def test_the_evaluator_is_deterministic_regardless_of_input_order():
    from science import kt_evaluation as ev

    predictions = [
        {"prediction_id": "p2", "learner_ref": "L1", "concept_key": "C1",
         "predicted_at": 100.0, "probability": 0.3},
        {"prediction_id": "p1", "learner_ref": "L1", "concept_key": "C1",
         "predicted_at": 10.0, "probability": 0.7},
    ]
    outcomes = [
        {"event_id": "e2", "learner_ref": "L1", "concept_key": "C1",
         "occurred_at": 200.0, "correct": False},
        {"event_id": "e1", "learner_ref": "L1", "concept_key": "C1",
         "occurred_at": 50.0, "correct": True},
        {"event_id": "e0", "learner_ref": "L1", "concept_key": "C1",
         "occurred_at": 5.0, "correct": True},
    ]
    first = ev.evaluate_shadow(predictions, outcomes)
    second = ev.evaluate_shadow(list(reversed(predictions)), list(reversed(outcomes)))
    assert first["observations"] == second["observations"]
    assert first["overall"]["n"] == second["overall"]["n"] == 2


def test_the_evaluator_writes_no_learner_fact(client, db_session):
    """PART N: a measurement, not an intervention."""
    from data_plane.models import LearningEvent
    from science import kt_evaluation as ev

    user = register_and_login(client, f"s7eval{uuid.uuid4().hex[:8]}")
    _event(db_session, user["id"], event_id=f"ev-{uuid.uuid4().hex[:6]}", correct=True,
           occurred_at=5.0)
    before = db_session.query(LearningEvent).count()
    ev.evaluate_shadow(
        [{"prediction_id": "p", "learner_ref": "L", "concept_key": "C",
          "predicted_at": 1.0, "probability": 0.5}],
        [{"event_id": "e", "learner_ref": "L", "concept_key": "C",
          "occurred_at": 2.0, "correct": True}])
    db_session.expire_all()
    assert db_session.query(LearningEvent).count() == before
    report = ev.evaluate_shadow([], [])
    assert report["wrote_learner_fact"] is False
    assert report["controls_product_decision"] is False


def test_the_evaluator_isolates_a_malformed_input():
    """PART R: failure isolation — bad rows are skipped, they do not take the run down."""
    from science import kt_evaluation as ev

    report = ev.evaluate_shadow(
        [{"prediction_id": "good", "learner_ref": "L", "concept_key": "C",
          "predicted_at": 1.0, "probability": 0.5},
         None,
         {"prediction_id": "bad-prob", "learner_ref": "L", "concept_key": "C",
          "predicted_at": 1.0, "probability": "not-a-number"}],
        [{"event_id": "e", "learner_ref": "L", "concept_key": "C",
          "occurred_at": 2.0, "correct": True},
         {"event_id": "e2", "learner_ref": "L", "concept_key": "C",
          "occurred_at": 3.0, "correct": True}])
    assert report["overall"]["n"] == 1          # the good row still scored
    assert report["overall"]["excluded_rows"] == 1


def test_the_evaluator_is_armed_but_reports_that_it_is_not_running():
    from science import kt_evaluation as ev

    state = ev.evaluator_is_ready()
    assert state["available"] is True
    assert state["blocked_by"] == []
    assert "ARMED, not RUNNING" in state["note"]


# ============================================================ PART A — the closed gate

def test_the_scaler_gate_is_closed_and_recorded_as_verified():
    from science import evidence_reliability as er

    gate = er.scaler_gate()
    assert gate["gate_passed"] is True
    assert gate["recovery_method"] == "RECONSTRUCTED_FROM_FROZEN_DATA"
    assert er.SCALER_RECOVERY_METHOD not in er.SCALER_GATE_FORBIDDEN_METHODS
    evidence = er.SCALER_RECOVERY_EVIDENCE
    assert evidence["outcome"] == "REPRODUCED_EXACTLY"
    assert evidence["rows_verified"] == 188262
    assert evidence["max_abs_delta"] <= 1e-6
    assert evidence["checkpoints_match_frozen_manifest"] is True
    # the free fit is explicitly NOT the basis, so it cannot be promoted by accident
    assert "NOT the basis" in evidence["free_fit_was_not_used"]


def test_closing_the_scaler_gate_did_not_open_the_product_surface():
    """The trap this sprint had to avoid: one gate passing is not both gates passing."""
    from science import evidence_reliability as er

    assert er.scaler_gate()["gate_passed"] is True
    assert er.PRODUCT_FEATURE_COMPATIBILITY == "INCOMPATIBLE"
    assert er.production_mode() == "SHADOW_NOT_USER_VISIBLE"
    assert er.production_mode() == er.PRODUCT_MODE
    assert er.SCIENTIFIC_THRESHOLD is None


def test_the_recovered_standardizer_is_recorded_and_is_the_proven_one():
    from science import evidence_reliability as er

    params = er.SCALER_STANDARDIZATION_PARAMS
    assert set(params) == {"42", "43", "44"}
    for seed, entry in params.items():
        assert set(entry["mean"]) == set(er.CONT_FEATURES), seed
        assert set(entry["std"]) == set(er.CONT_FEATURES), seed
        for value in list(entry["mean"].values()) + list(entry["std"].values()):
            assert isinstance(value, float)
    # the per-variant b_s mode is recorded, because one source revision cannot express it
    assert er.B_S_PER_VARIANT["42"] == er.B_S_MODE_ZSCORED
    assert er.B_S_PER_VARIANT["44"] == er.B_S_MODE_RAW


def test_the_blocker_set_is_complete_and_says_which_reasons_were_closed():
    from science import evidence_reliability as er

    open_codes = {b.split(":")[0] for b in er.blockers()}
    resolved_codes = {b["code"] for b in er.resolved_blockers()}
    named_by_s4 = {er.BLOCKER_HINTS, er.BLOCKER_RESPONSE_TIME, er.BLOCKER_ATTEMPT_COUNT,
                   er.BLOCKER_ONTOLOGY, er.BLOCKER_B_MAP, er.BLOCKER_STANDARDIZATION,
                   er.BLOCKER_UPSTREAM_P_T, er.BLOCKER_CALIBRATION}
    # none silently disappeared, and none is in both states at once
    assert open_codes | resolved_codes == named_by_s4
    assert not (open_codes & resolved_codes)
    for entry in er.resolved_blockers():
        assert entry["resolved_by"] and entry["what_changed"]


# ============================================================ PART Q — imports

def test_the_product_backend_cannot_import_the_scientific_stack():
    """PART Q/R: heavy imports stay at zero in the Product Backend process.

    Run in a SUBPROCESS so an earlier test that imported numpy into this interpreter
    cannot make the check pass or fail for the wrong reason.
    """
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "sys.path.insert(0, r'%s');"
        "import science.kt_native, science.kt_evaluation, science.evidence_reliability;"
        "heavy=[m for m in ('numpy','torch','scipy','sklearn','pandas','transformers') "
        "if m in sys.modules];"
        "print(','.join(heavy))" % (BACKEND, BACKEND.parent / "backend")
    )
    result = subprocess.run([str(PYTHON), "-c", code], capture_output=True, text=True,
                            cwd=str(BACKEND))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"heavy imports leaked: {result.stdout.strip()}"


def test_the_training_modules_are_not_imported_by_the_product_backend():
    """Nothing under backend/ may import a training harness: training is offline-only."""
    science_dir = BACKEND / "science"
    offenders = []
    for path in science_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("import torch", "import numpy", "from torch", "from numpy"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == [], offenders
