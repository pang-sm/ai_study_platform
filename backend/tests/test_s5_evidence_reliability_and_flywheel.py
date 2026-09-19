"""ACCEL_SPRINT_S5 — evidence_reliability preprocessing recovery + product-native flywheel.

PART A  the scaler gate: what may and may not produce the training standardizer, checked
        against the REAL research source bytes on disk, and the provenance of the exact
        facts transcribed from them.
PART B  the exact feature vector, in order, with each variant's width a strict prefix.
PART C  the per-feature product-compatibility classification.
PART D  canonical attempt telemetry: factual timing, factual hint semantics, stable
        attempt index, and no editorial-difficulty-as-IRT conversion.
PART E  nothing historical is backfilled.
PART K  the CS408-native concept reference.
PART L  the deterministic KT dataset export.
PART N  the capability summary's four independent readiness dimensions.
PART O  the telemetry migration, validated on a byte-for-byte COPY of the real database.

Doubles sit below the HTTP/runtime boundary only. The real database is never mutated.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from conftest import register_and_login
from fastapi.testclient import TestClient

from core.learning_context import ServiceNamespace
from data_plane import models as dp_models
from learning.practice.telemetry import (
    HINT_COUNTED,
    HINT_NO_MECHANISM,
    HINT_NOT_OBSERVED,
    DURATION_CLIENT_MONOTONIC_ACTIVE,
    DURATION_SERVER_SERVE_TO_SUBMIT,
    DURATION_UNAVAILABLE,
    EDITORIAL_DIFFICULTY_LABELS,
    AttemptTelemetry,
    derived_attempt_index,
    server_timed,
    unobserved,
)
from models import User
from science import capabilities as sci_capabilities
from science import evidence_reliability as er
from science import kt_dataset
from learning.records import native_concept

EXAM = ServiceNamespace.EXAM_PREP.value
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
REAL_DB = BACKEND / "app.db"

# The recovered research source, outside the repository.
ZHIXUE = Path(os.environ.get("ZHIXUE_HOME") or r"D:\ZhixueAI")
RESEARCH_SRC = ZHIXUE / "runtime_src" / "v1"
CHECKPOINT_DIR = ZHIXUE / "model_assets" / "v1" / "evidence_reliability"


# ================================================================ helpers

def make_user(session, username) -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    return u


def registered_user(client, session, username) -> User:
    register_and_login(client, username)
    return session.query(User).filter_by(username=username).one()


def cs408_event(session, user, event_id, *, qid=None, correct=True, occurred_at=1000.0,
                knowledge_point_ref=None, subject_key="cs_408", module="data_structure",
                response_time_ms=None, response_time_source=None, attempt_index=None):
    """One real canonical CS408 event, written through the real model."""
    qid = qid or f"q-{event_id}"
    ref = knowledge_point_ref if knowledge_point_ref is not None else {
        "knowledge_point_id": "kp-tree", "exam_module_id": module}
    ev = dp_models.LearningEvent(
        event_id=event_id, event_schema_version=2, event_type="question_answered",
        event_granularity="ITEM_LEVEL", source_type="exam_practice_attempt",
        source_attempt_id=f"att-{event_id}", source_item_key=f"{qid}:0",
        source_item_index=0, user_id=user.id, source_user_ref=user.username,
        service_key=EXAM, course_id=None, subject_key=subject_key, question_id=qid,
        knowledge_point_ref_json=json.dumps(ref),
        item_snapshot_json=json.dumps({"question_id": qid}),
        item_content_hash="h", answer="A", correct=correct, score=None,
        response_time_ms=response_time_ms, attempt_no=None,
        response_time_source=response_time_source, attempt_index=attempt_index,
        occurred_at=occurred_at, ingested_at=occurred_at, source_payload_version=1,
        idempotency_key=f"s5:{event_id}", snapshot_capture_mode="LIVE_EMITTER",
        snapshot_completeness="FULL", snapshot_missing_fields_json="[]")
    session.add(ev)
    session.commit()
    return ev


class _Unreachable:
    def __init__(self, *a, **kw):
        pass

    def infer(self, *a, **kw):
        from science import client as sci_client
        raise sci_client.ScientificUnavailable("runtime unreachable", component="test")

    def health(self, **kw):
        return {"status": "unavailable", "reason": "ConnectError"}


def code_only(path: Path) -> str:
    """The module's EXECUTABLE text: comments and string literals removed.

    A rule stated in a docstring must not satisfy a check that the rule is IMPLEMENTED, and
    a prohibition quoted in a comment must not trip a check that it is not. Both cases show
    up below, so the assertions run against tokens that carry behaviour.
    """
    import io
    import tokenize

    source = path.read_text(encoding="utf-8")
    out = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(token.string)
    return " ".join(out)


# ================================================================ PART A — scaler gate

def test_scaler_gate_state_is_definite_and_cannot_be_a_halfway_value():
    """PART A1/A2: the gate reports one of the accepted methods, or NOT_RECOVERED."""
    gate = er.scaler_gate()
    assert gate["recovery_method"] in (("NOT_RECOVERED",) + er.SCALER_GATE_ACCEPTED_METHODS)
    assert isinstance(gate["gate_passed"], bool)
    # the pass flag is derived from the method, never set independently
    assert gate["gate_passed"] is (
        gate["recovery_method"] in er.SCALER_GATE_ACCEPTED_METHODS)


def test_every_forbidden_recovery_route_is_named_so_none_can_be_used_quietly():
    """PART A2: the invented routes are enumerated, not merely discouraged."""
    forbidden = set(er.SCALER_GATE_FORBIDDEN_METHODS)
    for route in ("FIT_ON_PRODUCT_USERS", "FIT_ON_TEST_SPLIT", "FIT_ON_INFERENCE_BATCH",
                  "ASSUME_STANDARD_NORMAL", "COPY_FROM_OTHER_EXPERIMENT",
                  "DERIVE_FROM_CHECKPOINT"):
        assert route in forbidden, route
    # and none of them is also an accepted method — the sets are disjoint by construction
    assert not (forbidden & set(er.SCALER_GATE_ACCEPTED_METHODS))
    assert er.SCALER_RECOVERY_METHOD not in forbidden


def test_the_standardizer_is_declared_unbundled_while_the_gate_has_not_passed():
    """A gate that has not passed may not have a verified standardizer attached to it."""
    assert er.STANDARDIZATION["bundled_with_checkpoints"] is False
    if not er.scaler_gate()["gate_passed"]:
        assert er.SCALER_RECOVERY_METHOD == "NOT_RECOVERED"
        # an attempt was made and it is recorded; the gate may not be a bare "no"
        assert er.SCALER_RECOVERY_EVIDENCE is not None
        assert er.SCALER_RECOVERY_EVIDENCE["outcome"] == "REPRODUCTION_FAILED"


def test_the_recorded_recovery_evidence_names_what_worked_and_what_did_not():
    """Evidence, not a verdict: both halves are required, so it cannot be softened."""
    evidence = er.SCALER_RECOVERY_EVIDENCE
    assert evidence["attempted_method"] == "RECONSTRUCTED_FROM_FROZEN_DATA"
    assert evidence["checkpoints_match_frozen_manifest"] is True
    assert evidence["reproduced_exactly"], "nothing reproduced — that would be no evidence"
    assert evidence["not_reproduced"], "a bare 'it failed' is not evidence"
    assert evidence["max_abs_p_base_delta"] <= 1e-6
    assert evidence["free_fit_conflicts"], "the conflict must be named, not implied"


def test_the_product_mode_is_derived_from_the_gate_not_asserted_alongside_it():
    """A recovered scaler is a precondition for any surface, so the two cannot drift."""
    assert er.production_mode() == er.PRODUCT_MODE
    if not er.scaler_gate()["gate_passed"]:
        assert er.production_mode() == "SHADOW_NOT_USER_VISIBLE"


def test_a_promotion_requires_more_than_the_scaler_gate():
    """Even a recovered scaler would not open the surface while features are incompatible."""
    if er.scaler_gate()["gate_passed"]:
        assert er.PRODUCT_FEATURE_COMPATIBILITY == "COMPATIBLE", (
            "the scaler gate passed but the feature vector is still not constructible; the "
            "surface must stay closed")


def test_transcribed_schema_is_pinned_to_the_real_source_bytes():
    """PART A: the transcription's provenance, verified against the files themselves.

    Skipped (never failed) when the research source is not on this machine: the assertion
    is about the bytes that were read, and with no bytes there is nothing to check.
    """
    if not RESEARCH_SRC.is_dir():
        pytest.skip("recovered research source not present on this machine")

    checked = 0
    for rel, expected in er.SCIENTIFIC_SOURCE_SHA256.items():
        path = RESEARCH_SRC / rel
        if not path.is_file():
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, f"{rel} changed; the transcribed schema may be stale"
        checked += 1
    assert checked > 0, "no source file could be verified"


def test_frozen_checkpoint_hashes_match_the_frozen_artifact_manifest():
    """The five checkpoints are the frozen ones — identity, not a lookalike."""
    manifest = CHECKPOINT_DIR / "artifact.json"
    if not manifest.is_file():
        pytest.skip("evidence_reliability model assets not present on this machine")
    declared = {f["file"]: f["sha256"] for f in json.loads(manifest.read_text())["files"]}
    for name, expected in declared.items():
        path = CHECKPOINT_DIR / name
        assert path.is_file(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name


# ================================================================ PART B/C — the vector

def test_exact_feature_order_is_the_sources_own_layout():
    """PART B: static block in STATIC_ORDER, then the dynamic p_t concatenated last."""
    assert er.BIN_FEATURES == ("y", "attempt_gt1", "has_bottom_hint")
    assert er.CONT_FEATURES == ("log_rt", "hint_count", "log_opp", "b_s")
    assert er.STATIC_ORDER == er.BIN_FEATURES + er.CONT_FEATURES
    assert er.FEATURE_VECTOR == (
        "y", "attempt_gt1", "has_bottom_hint", "log_rt", "hint_count", "log_opp", "b_s",
        "p_t")
    assert er.FEATURE_VECTOR[-1] == "p_t"
    # indices are positional and dense
    assert [f["index"] for f in er.FEATURE_SCHEMA] == list(range(len(er.FEATURE_VECTOR)))
    assert tuple(f["name"] for f in er.FEATURE_SCHEMA) == er.FEATURE_VECTOR


def test_each_variant_width_matches_its_declared_ablation():
    """An ablation DROPS columns; none of them reorders or widens the vector.

    Widths are checked against the ablation each checkpoint was trained under, because a
    width alone cannot tell a dropped feature from a reordered one.
    """
    expected = {                 # variant -> the static block it was trained on
        "42": ("y", "attempt_gt1", "has_bottom_hint", "log_rt", "hint_count", "log_opp",
               "b_s"),
        "42_nort": ("y", "attempt_gt1", "has_bottom_hint", "hint_count", "log_opp", "b_s"),
        "42_surprise": ("y", "b_s"),
        "43": ("y", "attempt_gt1", "has_bottom_hint", "log_rt", "hint_count", "log_opp",
               "b_s"),
        "44": ("y", "attempt_gt1", "has_bottom_hint", "log_rt", "hint_count", "log_opp",
               "b_s"),
    }
    assert set(expected) == set(er.SCIENTIFIC_VARIANTS)
    for variant, statics in expected.items():
        static = list(statics)
        # every kept feature is a real position, kept in the vector's own order
        assert static == [f for f in er.FEATURE_VECTOR[:-1] if f in set(static)]
        assert er.SCIENTIFIC_VARIANTS[variant] == len(static) + 1   # + p_t
    assert er.SCIENTIFIC_VARIANTS["42_nort"] == er.SCIENTIFIC_VARIANTS["42"] - 1


def test_only_the_continuous_block_is_standardized():
    """The three binary features and p_t are raw. Getting this wrong changes every number."""
    assert er.STANDARDIZATION["applies_to"] == list(er.CONT_FEATURES)
    for raw in ("y", "attempt_gt1", "has_bottom_hint", "p_t"):
        assert raw in er.STANDARDIZATION["not_applied_to"], raw
    by_name = {f["name"]: f for f in er.FEATURE_SCHEMA}
    for name in er.BIN_FEATURES:
        assert "raw 0/1" in by_name[name]["transform"]
    assert "NOT z-scored" in by_name["p_t"]["transform"]


def test_missing_value_policy_is_the_sources_policy_not_a_convenience():
    """The two fills the source really performs, and no third one."""
    policy = er.MISSING_VALUE_POLICY
    assert set(policy) == {"b_s", "has_bottom_hint", "log_rt", "all_others"}
    assert "fillna(0.0)" in policy["b_s"]
    assert "never imputed" in policy["all_others"]


def test_feature_availability_classifies_every_feature_exactly_once():
    """PART C: the four categories, and one verdict per feature."""
    statuses = {f["name"]: f["product_status"] for f in er.FEATURE_AVAILABILITY}
    assert set(statuses) == set(er.FEATURE_VECTOR)
    for name, status in statuses.items():
        assert status in (er.AVAILABLE_NOW, er.CAN_BE_COLLECTED_FACTUALLY,
                          er.NOT_AVAILABLE, er.SEMANTICALLY_INCOMPATIBLE), name
    # the honest verdicts this product's surfaces produce today
    assert statuses["y"] == er.AVAILABLE_NOW
    assert statuses["hint_count"] == er.NOT_AVAILABLE
    assert statuses["has_bottom_hint"] == er.NOT_AVAILABLE
    assert statuses["b_s"] == er.SEMANTICALLY_INCOMPATIBLE
    assert statuses["log_opp"] == er.SEMANTICALLY_INCOMPATIBLE
    assert statuses["p_t"] == er.SEMANTICALLY_INCOMPATIBLE


def test_product_feature_compatibility_is_incompatible_because_of_named_features():
    """The summary flag is DERIVED from the table, so the two cannot disagree."""
    derived = tuple(f["name"] for f in er.FEATURE_AVAILABILITY
                    if f["product_status"] != er.AVAILABLE_NOW)
    assert er.INCOMPATIBLE_FEATURES == derived
    assert er.PRODUCT_FEATURE_COMPATIBILITY == "INCOMPATIBLE"
    assert "hint_count" in derived and "b_s" in derived


def test_no_hint_feature_may_be_defaulted_to_zero_anywhere_in_the_module():
    """The one substitution that must never appear: absent hints written as 0."""
    source = Path(er.__file__).read_text(encoding="utf-8")
    assert "hint_count = 0" not in source
    assert "hints_used = 0" not in source
    for entry in er.FEATURE_AVAILABILITY:
        if entry["name"] in ("hint_count", "has_bottom_hint"):
            assert entry["product_status"] == er.NOT_AVAILABLE
            assert entry["product_source"] is None


def test_the_module_never_fits_a_standardizer_on_product_data():
    """PART A2 as a source check: no fitting machinery exists on the product side.

    Checked against the module's EXECUTABLE text — its prose necessarily discusses mean
    and std (it records why they are absent), and a rule stated in a docstring must not be
    mistaken for code that implements it.
    """
    code = code_only(Path(er.__file__))
    for forbidden in (".std(", ".mean(", "fit(", "StandardScaler", "np.mean",
                      "statistics.", "sum(", "/ len("):
        assert forbidden not in code, forbidden


# ================================================================ PART D — telemetry

def test_a_duration_without_a_measured_boundary_is_refused_not_stored():
    """D1: UNAVAILABLE may not carry a number, and a source may not omit one."""
    ok = unobserved()
    assert ok.duration_ms is None and ok.duration_source == DURATION_UNAVAILABLE
    with pytest.raises(ValueError):
        AttemptTelemetry(duration_ms=4200, duration_source=DURATION_UNAVAILABLE)
    with pytest.raises(ValueError):
        AttemptTelemetry(duration_ms=None, duration_source=DURATION_CLIENT_MONOTONIC_ACTIVE)


def test_both_admissible_duration_sources_declare_their_boundaries_and_semantics():
    """D1: start boundary, submit boundary, units and background-tab behaviour."""
    from learning.practice import telemetry as tmod

    assert set(tmod.DURATION_SOURCES) == {DURATION_SERVER_SERVE_TO_SUBMIT,
                                          DURATION_CLIENT_MONOTONIC_ACTIVE}
    for source, declared in tmod.DURATION_SOURCES.items():
        for key in ("start_boundary", "submit_boundary", "unit", "background_tab",
                    "missing_semantics"):
            assert declared[key].strip(), f"{source}.{key}"
        assert "milliseconds" in declared["unit"]
        # both sources say out loud that background time is counted, because a reader
        # cannot tell an engaged 40s from a 40s tab left open without being told
        assert "INCLUDED" in declared["background_tab"]


def test_a_timestamp_difference_is_named_forbidden_as_a_duration():
    """D1: the forbidden derivations are written down AND never performed."""
    from learning.practice import telemetry as tmod

    joined = " ".join(tmod.DURATION_FORBIDDEN_DERIVATIONS)
    assert "created_at - submitted_at" in joined
    assert "session span" in joined

    # The envelope holds no timestamp at all, so there is nothing here to subtract: the
    # prohibition is structural, not merely a comment.
    for field in tmod.AttemptTelemetry.__dataclass_fields__:
        assert "at" != field[-2:] and not field.endswith("_at"), field
        assert "timestamp" not in field, field

    # and the executable text performs no subtraction on a timestamp attribute
    code = code_only(Path(tmod.__file__))
    for stamp in ("submitted_at", "created_at", "started_at"):
        assert stamp not in code, stamp


def test_server_and_client_timed_constructors_stamp_their_own_provenance():
    assert server_timed(1500).duration_source == DURATION_SERVER_SERVE_TO_SUBMIT
    assert server_timed(1500).duration_ms == 1500
    assert (AttemptTelemetry(duration_ms=1500,
                             duration_source=DURATION_CLIENT_MONOTONIC_ACTIVE)
            .duration_source == DURATION_CLIENT_MONOTONIC_ACTIVE)
    assert server_timed(1500).to_fact_fields() == {
        "response_time_ms": 1500,
        "response_time_source": DURATION_SERVER_SERVE_TO_SUBMIT,
        "attempt_index": None,
    }


def test_a_surface_with_no_hint_mechanism_can_never_record_a_hint_count():
    """D2: the whole point. 'No hints offered' is not 'zero hints used'."""
    natural = unobserved()
    assert natural.hint_count is None and natural.hint_source == HINT_NO_MECHANISM
    for source in (HINT_NO_MECHANISM, HINT_NOT_OBSERVED):
        with pytest.raises(ValueError):
            AttemptTelemetry(hint_count=0, hint_source=source)
    counted = AttemptTelemetry(hint_count=0, hint_source=HINT_COUNTED)
    assert counted.hint_count == 0          # a real counted zero IS allowed
    with pytest.raises(ValueError):
        AttemptTelemetry(hint_count=None, hint_source=HINT_COUNTED)


def test_every_cs408_surface_is_declared_as_having_no_hint_mechanism():
    from learning.practice import telemetry as tmod
    surfaces = " ".join(tmod.SURFACES_WITHOUT_HINT_MECHANISM)
    for surface in ("chapter practice", "past papers", "programming"):
        assert surface in surfaces, surface


def test_attempt_index_is_one_based_and_comes_from_a_real_count():
    """D3: an ordinal over canonical identity, not a session position."""
    assert derived_attempt_index(0) == 1
    assert derived_attempt_index(4) == 5
    for bad in (-1, "3", None, 1.5):
        with pytest.raises(ValueError):
            derived_attempt_index(bad)
    with pytest.raises(ValueError):
        AttemptTelemetry(attempt_index=0)
    assert "NOT a session position" in _attempt_index_semantics()


def _attempt_index_semantics() -> str:
    from learning.practice import telemetry as tmod
    return tmod.ATTEMPT_INDEX_SEMANTICS


def test_attempt_index_is_not_conflated_with_the_paper_sitting_number():
    """``attempt_no`` on the past-paper path is a sitting number; the two are distinct."""
    from learning.practice import telemetry as tmod
    source = Path(tmod.__file__).read_text(encoding="utf-8")
    assert "paper-sitting" in source.lower() or "paper-sitting" in source
    assert "attempt_no" not in tmod.AttemptTelemetry.__dataclass_fields__


def test_the_editorial_difficulty_label_is_never_turned_into_a_number():
    """D4: 简单/中等/困难 is a label, not an IRT b and not a continuous difficulty."""
    from learning.practice import telemetry as tmod
    assert tmod.EDITORIAL_DIFFICULTY_LABELS == ("简单", "中等", "困难")
    for value in (0, 1, -1, 0.0, 1.5):
        with pytest.raises(ValueError):
            tmod.assert_no_editorial_difficulty_numeric(value)
    tmod.assert_no_editorial_difficulty_numeric("中等")   # the label itself is fine
    assert "NOT converted" in tmod.EDITORIAL_DIFFICULTY_RULE


def test_telemetry_is_not_part_of_the_graded_fact_digest():
    """Adding provenance must not retroactively invalidate stored fact hashes.

    Every attempt recorded before S5 was hashed without telemetry. A new key in this dict
    would change the digest of an unchanged fact and make a legitimate replay raise
    AttemptConflict against history.
    """
    import ast

    tree = ast.parse((BACKEND / "learning" / "practice" / "service.py").read_text(
        encoding="utf-8"))
    payload_fn = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == "_fact_payload")
    returned = next(n for n in ast.walk(payload_fn) if isinstance(n, ast.Return))
    keys = {k.value for k in returned.value.keys}
    assert "response_time_ms" in keys and "attempt_no" in keys
    for forbidden in ("response_time_source", "attempt_index", "hint_count",
                      "hint_source"):
        assert forbidden not in keys, forbidden


def test_recording_an_attempt_with_telemetry_persists_provenance(db_session):
    """The envelope reaches the durable row, and the bare legacy path stays provenance-less."""
    from learning.practice import service as practice
    from learning.practice.refs import QuestionRef, QuestionSourceType

    user = make_user(db_session, "s5_tel")
    session = practice.create_session(db_session, user, EXAM)
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id="q-tel", service_namespace=ServiceNamespace.EXAM_PREP)

    measured = practice.record_attempt(db_session, user, session, ref, answer="A",
                                       correct=True, telemetry=server_timed(2500,
                                                                            attempt_index=2))
    assert measured.attempt.response_time_ms == 2500
    assert measured.attempt.response_time_source == DURATION_SERVER_SERVE_TO_SUBMIT
    assert measured.attempt.attempt_index == 2

    bare = practice.record_attempt(db_session, user, session, ref, answer="B",
                                   correct=False, response_time_ms=999)
    assert bare.attempt.response_time_ms == 999
    # a number whose boundaries were never recorded lands with NO provenance. ACCEL_SPRINT_S6
    # does not change this: the DURATION still has no source, because no serve boundary was
    # ever recorded.
    assert bare.attempt.response_time_source is None
    # ACCEL_SPRINT_S6 PART F changes the OTHER half. The live path now derives the ordinal
    # from a real count over canonical rows instead of leaving it NULL forever, so this row
    # carries one — and it carries exactly the count of canonical attempts on this question,
    # which is what "1-based ordinal among the SAME learner's attempts on the SAME question"
    # means. The S5 invariant that matters is unchanged: the ordinal is never invented.
    from learning.practice.models import PracticeAttempt

    prior = (db_session.query(PracticeAttempt)
             .filter(PracticeAttempt.user_id == user.id,
                     PracticeAttempt.question_source_id == str(ref.source_id),
                     PracticeAttempt.question_source_type == ref.source_type.value)
             .count())
    assert prior == 2, "the measured attempt and this one"
    assert bare.attempt.attempt_index == prior


def test_passing_both_a_duration_and_an_envelope_is_refused(db_session):
    from learning.practice import service as practice
    from learning.practice.refs import QuestionRef, QuestionSourceType

    user = make_user(db_session, "s5_tel2")
    session = practice.create_session(db_session, user, EXAM)
    ref = QuestionRef(source_type=QuestionSourceType.STATIC_QUESTION_BANK,
                      source_id="q-tel2", service_namespace=ServiceNamespace.EXAM_PREP)
    with pytest.raises(ValueError):
        practice.record_attempt(db_session, user, session, ref, answer="A", correct=True,
                                response_time_ms=10, telemetry=server_timed(20))


def test_the_http_boundary_refuses_an_uninterpretable_observation(client, db_session):
    user = registered_user(client, db_session, "s5_http_tel")
    session = client.post("/practice/sessions",
                          json={"service_namespace": EXAM}).json()
    body = {
        "question_source_type": "static_question_bank", "question_source_id": "q-h1",
        "answer": "A", "correct": True,
        "telemetry": {"duration_ms": 100, "duration_source": "UNAVAILABLE"},
    }
    r = client.post(f"/practice/sessions/{session['id']}/attempts", json=body)
    assert r.status_code == 400
    assert "boundary" in r.json()["detail"] or "duration" in r.json()["detail"]


def test_the_http_boundary_records_a_properly_declared_duration(client, db_session):
    user = registered_user(client, db_session, "s5_http_tel2")
    session = client.post("/practice/sessions",
                          json={"service_namespace": EXAM}).json()
    body = {
        "question_source_type": "static_question_bank", "question_source_id": "q-h2",
        "answer": "A", "correct": True,
        "telemetry": {"duration_ms": 3300,
                      "duration_source": DURATION_CLIENT_MONOTONIC_ACTIVE,
                      "attempt_index": 1},
    }
    r = client.post(f"/practice/sessions/{session['id']}/attempts", json=body)
    assert r.status_code == 200, r.text
    attempt = r.json()["attempt"]
    assert attempt["response_time_ms"] == 3300
    assert attempt["response_time_source"] == DURATION_CLIENT_MONOTONIC_ACTIVE
    assert attempt["attempt_index"] == 1


def test_the_event_bridge_carries_the_provenance_with_the_duration():
    """A reader must not have to open the practice row to interpret the number."""
    import ast

    tree = ast.parse((BACKEND / "learning" / "practice" / "events.py").read_text(
        encoding="utf-8"))
    build = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "build_event")
    returned = next(n for n in ast.walk(build) if isinstance(n, ast.Return))
    keys = {k.value for k in returned.value.keys}
    assert "response_time_ms" in keys
    assert "response_time_source" in keys, "the duration would travel without its source"
    assert "attempt_index" in keys, "the attempt ordinal would be lost at the boundary"


def test_the_records_envelope_also_carries_the_provenance():
    source = (BACKEND / "learning" / "records" / "envelope.py").read_text(encoding="utf-8")
    assert 'payload.get("response_time_source")' in source
    assert 'payload.get("attempt_index")' in source


# ================================================================ PART E — no backfill

def test_historical_events_keep_null_telemetry_and_are_never_backfilled(db_session):
    """PART E: an unobserved fact stays unobserved; nothing is inferred after the fact."""
    user = make_user(db_session, "s5_hist")
    ev = cs408_event(db_session, user, "s5-hist-1", occurred_at=500.0)
    assert ev.response_time_ms is None
    assert ev.response_time_source is None
    assert ev.attempt_index is None

    # the export reads it as missing rather than as a zero
    item = kt_dataset.interaction_of(ev)
    assert item["duration_ms"] is None
    assert item["duration_source"] is None
    assert item["attempt_index"] is None


def test_the_migration_adds_no_server_default_and_backfills_nothing():
    """PART E/O: a default would silently manufacture an observation."""
    path = (REPO_ROOT / "migrations" / "versions"
            / "20260919_0010_attempt_telemetry_provenance.py")
    text = path.read_text(encoding="utf-8")
    assert "nullable=True" in text
    assert "server_default" not in text
    assert "op.execute" not in text          # no UPDATE/backfill statement anywhere
    assert "UPDATE" not in text.upper()


# ================================================================ PART K — native concept

def test_native_concept_hierarchy_uses_only_existing_canonical_ids():
    """Exam identity and concept identity are separate, ordered, existing-ID spaces."""
    assert native_concept.EXAM_IDENTITY_LEVELS == ("exam_track_id", "exam_subject_id")
    assert native_concept.NATIVE_CONCEPT_LEVELS == (
        "exam_module_id", "knowledge_point_id")
    assert native_concept.NATIVE_CONCEPT_KEYS == ("knowledge_point_id", "exam_module_id")
    # the two spaces are disjoint — no id is both an exam and a concept
    assert not (set(native_concept.EXAM_IDENTITY_LEVELS)
                & set(native_concept.NATIVE_CONCEPT_LEVELS))


def test_a_track_is_never_recorded_on_a_fact():
    """Two learners with different bundles must produce byte-identical facts."""
    report = native_concept.declared_granularity_report()
    assert "track_never_recorded" in report
    assert "exam_track_id" not in native_concept.NATIVE_CONCEPT_KEYS
    assert native_concept.reference_from_context(
        {"exam_track_id": "cs_408", "exam_module_id": "data_structure"}) == {
        "exam_module_id": "data_structure"}


def test_a_question_title_never_becomes_a_concept_link():
    report = native_concept.declared_granularity_report()
    for non_identity in ("knowledge_point_name", "chapter_title", "question stem"):
        assert non_identity in report["non_identity_inputs"], non_identity
    assert "ABSENT rather than derived" in native_concept.REFERENCE_RULE
    # names and paths in the context are dropped, not used
    assert native_concept.reference_from_context(
        {"knowledge_point_name": "二叉树", "knowledge_point_path": "树/二叉树"}) == {}


def test_a_past_paper_records_module_granularity_and_not_more():
    """Only the granularity a fact actually knows is recorded."""
    report = native_concept.declared_granularity_report()
    assert report["surfaces"]["exam_prep.past_papers"] == ["exam_module_id"]
    assert report["surfaces"]["exam_prep.chapter_practice"] == [
        "exam_module_id", "knowledge_point_id"]


def test_the_concept_key_is_the_deepest_level_actually_present():
    assert native_concept.concept_key(
        {"exam_subject_id": "cs_408", "exam_module_id": "data_structure"}) == "data_structure"
    assert native_concept.concept_key(
        {"exam_subject_id": "cs_408", "exam_module_id": "data_structure",
         "knowledge_point_id": "kp-tree"}) == "kp-tree"
    assert native_concept.concept_level(
        {"exam_subject_id": "cs_408", "exam_module_id": "data_structure"}) == "exam_module_id"
    # an EXAM is not a CONCEPT: with nothing below the subject there is no key at all,
    # rather than "cs_408" standing in and looking like a concept assignment
    assert native_concept.concept_key({"exam_subject_id": "cs_408"}) is None
    assert native_concept.concept_level({"exam_subject_id": "cs_408"}) is None
    assert "exam_subject_id" in native_concept.EXAM_IDENTITY_LEVELS
    assert "exam_subject_id" not in native_concept.NATIVE_CONCEPT_LEVELS


def test_a_malformed_reference_is_unknown_not_partial():
    class _Row:
        knowledge_point_ref_json = "{not json"
        subject_key = "cs_408"

    assert native_concept.reference_from_event(_Row()) == {}
    assert native_concept.reference_for_learning_event(_Row()) == {
        "exam_subject_id": "cs_408"}


def test_the_envelope_and_the_dataset_reader_share_one_definition():
    from learning.records import envelope
    assert envelope._DOMAIN_CONTEXT_KEYS == native_concept.NATIVE_CONCEPT_KEYS
    assert envelope.domain_context_json({"exam_module_id": "m", "unrelated": 1}) == {
        "exam_module_id": "m"}


# ================================================================ PART L — KT export

def test_kt_export_is_deterministic_across_runs(db_session):
    user = make_user(db_session, "s5_kt")
    for i in range(5):
        cs408_event(db_session, user, f"s5-kt-{i}", qid=f"q{i}", correct=bool(i % 2),
                    occurred_at=1000.0 + i)
    first = kt_dataset.build(db_session, service_namespace=EXAM, user_id=user.id)
    second = kt_dataset.build(db_session, service_namespace=EXAM, user_id=user.id)
    assert first == second
    assert first["dataset_hash"] == second["dataset_hash"]
    assert first["interaction_count"] == 5


def test_kt_export_orders_interactions_by_fact_time_then_event_id(db_session):
    user = make_user(db_session, "s5_kt2")
    # inserted out of order on purpose
    for event_id, at in (("s5-o-c", 300.0), ("s5-o-a", 100.0), ("s5-o-b", 200.0)):
        cs408_event(db_session, user, event_id, occurred_at=at)
    body = kt_dataset.build(db_session, service_namespace=EXAM, user_id=user.id)
    times = [i["occurred_at"] for s in body["sequences"] for i in s["interactions"]]
    assert times == sorted(times) == [100.0, 200.0, 300.0]


def test_kt_export_keeps_tri_state_and_excludes_non_boolean_verdicts(db_session):
    user = make_user(db_session, "s5_kt3")
    cs408_event(db_session, user, "s5-kt-true", correct=True, occurred_at=1.0)
    cs408_event(db_session, user, "s5-kt-false", correct=False, occurred_at=2.0)
    # an unanswered / ungraded item: correct stays NULL and is NOT read as wrong
    ev = cs408_event(db_session, user, "s5-kt-null", correct=None, occurred_at=3.0)
    ev.answer = ""
    db_session.commit()

    body = kt_dataset.build(db_session, service_namespace=EXAM, user_id=user.id)
    labels = [i["correct"] for s in body["sequences"] for i in s["interactions"]]
    assert set(labels) == {True, False}
    assert len(labels) == 2
    assert body["excluded"].get(kt_dataset.EXCLUDED_NOT_BINARY) == 1
    assert "NOT a negative label" in body["exclusion_semantics"][
        kt_dataset.EXCLUDED_NOT_BINARY]


def test_kt_export_excludes_facts_with_no_native_concept(db_session):
    """A subject-only fact has an exam, not a concept, and is not filed under one."""
    user = make_user(db_session, "s5_kt4")
    cs408_event(db_session, user, "s5-kt-noconcept", occurred_at=1.0,
                knowledge_point_ref={"unrelated": "x"})
    body = kt_dataset.build(db_session, service_namespace=EXAM, user_id=user.id)
    assert body["interaction_count"] == 0
    assert body["excluded"].get(kt_dataset.EXCLUDED_NO_CONCEPT) == 1


def test_kt_export_carries_no_learner_identity_or_content(db_session):
    user = make_user(db_session, "s5_kt5")
    cs408_event(db_session, user, "s5-kt-pii", occurred_at=1.0)
    body = kt_dataset.build(db_session, service_namespace=EXAM, user_id=user.id)
    blob = json.dumps(body, ensure_ascii=False)
    assert user.username not in blob
    for forbidden in kt_dataset.FORBIDDEN_FIELDS:
        assert forbidden not in json.dumps(body["sequences"])
    # and the ref really is the declared deterministic digest, not the id itself
    assert [s["learner_ref"] for s in body["sequences"]] == [
        kt_dataset.learner_ref(user.id)]
    assert str(user.id) != kt_dataset.learner_ref(user.id)


def test_learner_ref_is_stable_and_not_the_user_id():
    assert kt_dataset.learner_ref(7) == kt_dataset.learner_ref(7)
    assert kt_dataset.learner_ref(7) != kt_dataset.learner_ref(8)
    assert kt_dataset.learner_ref(7) != "7"


def test_kt_export_scopes_by_learner_for_cross_user_isolation(db_session):
    one = make_user(db_session, "s5_kt_sc1")
    two = make_user(db_session, "s5_kt_sc2")
    cs408_event(db_session, one, "s5-sc-1", occurred_at=1.0)
    cs408_event(db_session, two, "s5-sc-2", occurred_at=2.0)

    scoped = kt_dataset.build(db_session, service_namespace=EXAM, user_id=one.id)
    assert scoped["interaction_count"] == 1
    assert scoped["scope"]["user_scoped"] is True
    assert {s["learner_ref"] for s in scoped["sequences"]} == {
        kt_dataset.learner_ref(one.id)}


def test_kt_audit_reports_readiness_without_the_rows(db_session):
    user = make_user(db_session, "s5_kt6")
    cs408_event(db_session, user, "s5-kt-audit", occurred_at=1.0)
    report = kt_dataset.audit(db_session, service_namespace=EXAM)
    assert "sequences" not in report
    assert report["readiness"]["native_concept_identity"] == "AVAILABLE"
    assert any("NO_TRAINING_RUN_ATTEMPTED" in b for b in report["readiness"]["blockers"])


def test_the_kt_audit_route_reports_health_without_carrying_rows(client, db_session):
    """PART L: the observable surface reports the contract's health, never the dataset."""
    user = registered_user(client, db_session, "s5_kt_route")
    cs408_event(db_session, user, "s5-kt-route-1", occurred_at=1.0)
    r = client.get("/exam/prep/scientific/kt-dataset-audit")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "sequences" not in body
    assert body["dataset_contract_version"] == kt_dataset.DATASET_CONTRACT_VERSION
    assert body["readiness"]["native_concept_identity"] in ("AVAILABLE", "NO_DATA_YET")
    assert any("NO_TRAINING_RUN_ATTEMPTED" in b for b in body["readiness"]["blockers"])
    # the scope is the CALLER's exam space, and no learner identity is echoed
    assert body["scope"]["service_namespace"] == EXAM
    assert user.username not in json.dumps(body)


def test_the_kt_audit_route_requires_authentication(client):
    client.cookies.clear()
    assert client.get("/exam/prep/scientific/kt-dataset-audit").status_code in (401, 403)


def test_the_export_is_not_a_model():
    """No training, no fitting, no prediction — the executable text carries none of them."""
    code = code_only(Path(kt_dataset.__file__))
    for word in ("torch", "numpy", "sklearn", "transformers", "faiss",
                 "backward(", "optimizer", "state_dict"):
        assert word not in code, word
    # `predict` may appear in prose (the module says it does not predict); it may not
    # appear as a callable or an attribute access.
    assert ".predict" not in code
    assert "def predict" not in code


# ================================================================ PART M — tutor ledger

def test_no_pedagogical_action_ledger_is_claimed():
    """PART M: the audit says NO, and no ledger is invented to make it say YES."""
    from science import tutor_policy

    status = tutor_policy.pedagogical_action_ledger_status()
    assert status["ledger_ready"] is False
    assert status["recorded_pedagogical_actions"] == 0
    assert status["tutor_policy_promoted"] is False
    assert status["product_mode_unchanged"] == tutor_policy.PRODUCT_MODE == "SHADOW"


def test_the_audited_decisions_are_recorded_and_classified_honestly():
    """Every choice the product really makes is listed, and none is relabelled."""
    from science import tutor_policy

    audited = tutor_policy.pedagogical_action_ledger_status()["audited_decisions"]
    kinds = {d["decision"]: d for d in audited}
    assert kinds["prompts.detect_question_type -> response structure"]["recorded"] is False
    assert kinds["ai.orchestrator capability selection"]["recorded"] is True
    for decision in audited:
        assert decision["pedagogical_action"] is False, decision["decision"]
        assert decision["why_not"].strip()


def test_the_frozen_action_ontology_is_not_rewritten_or_widened():
    from science import tutor_policy

    assert tutor_policy.ACTION_ONTOLOGY == ("focus", "generic", "probing", "telling")
    assert tutor_policy.TUTOR_POLICY_CONTROLS_RESPONSE is False


def test_the_orchestrator_chooses_no_action_in_the_frozen_ontology():
    """The audit's premise, checked against the real orchestrator source."""
    import ast

    tree = ast.parse((BACKEND / "ai" / "orchestrator.py").read_text(encoding="utf-8"))
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for action in ("focus", "probing", "telling"):
        assert action not in names, action


# ================================================================ PART N — capabilities

def test_every_capability_reports_the_four_independent_readiness_dimensions():
    body = sci_capabilities.summary()
    for entry in body["components"]:
        for key in ("runtime_available", "scientifically_compatible",
                    "product_input_ready", "user_visible", "mode", "blockers"):
            assert key in entry, (entry["component"], key)
        assert isinstance(entry["runtime_available"], bool)
        assert isinstance(entry["scientifically_compatible"], bool)
        assert isinstance(entry["product_input_ready"], bool)
    assert "runtime_available" in body["terminology"]
    assert "product_input_ready" in body["terminology"]


def test_endpoint_existence_never_implies_readiness():
    """The reading the summary exists to prevent."""
    by_name = {e["component"]: e for e in sci_capabilities.summary()["components"]}
    reachable_but_unusable = [n for n, e in by_name.items()
                              if e["runtime_available"] and not e["product_input_ready"]]
    assert reachable_but_unusable, "the distinction must be observable on real data"
    for name in reachable_but_unusable:
        assert by_name[name]["blockers"], name


def test_the_runtime_available_set_matches_the_served_components():
    declared = {e["component"] for e in sci_capabilities.summary()["components"]
                if e["runtime_available"]}
    assert declared == set(sci_capabilities.RUNTIME_ENDPOINT_COMPONENTS)
    assert len(declared) == 5        # student_twin, misconception, tutor_policy, kt, ER


def test_product_input_ready_and_available_never_disagree():
    for entry in sci_capabilities.summary()["components"]:
        assert entry["product_input_ready"] is entry["available"], entry["component"]


def test_user_visible_implies_input_ready_and_compatible():
    """Nothing may be shown unless it is both feedable and meaningful here."""
    for entry in sci_capabilities.summary()["components"]:
        if entry["user_visible"]:
            assert entry["product_input_ready"], entry["component"]
            assert entry["scientifically_compatible"], entry["component"]


# ================================================================ PART B/I — the gate

def test_evidence_reliability_still_produces_no_weight_and_says_why(client, db_session):
    user = registered_user(client, db_session, "s5_er")
    cs408_event(db_session, user, "s5-er-1", correct=False)

    r = client.get("/exam/prep/scientific/evidence-reliability")
    assert r.status_code == 200
    body = r.json()
    assert body["reliability_weight"] is None
    assert body["metadata"]["writes_learner_fact"] is False
    assert body["metadata"]["controls_product_decision"] is False
    assert body["metadata"]["mode"] == "SHADOW_NOT_USER_VISIBLE"
    # the S5 additions are part of the contract
    assert body["scaler_gate"]["gate_passed"] is False
    assert body["model_requirement"]["product_feature_compatibility"] == "INCOMPATIBLE"
    assert body["model_requirement"]["feature_vector"][-1] == "p_t"


def test_exposing_the_scaler_gate_writes_no_learner_fact(client, db_session):
    """PART I: a report is a read."""
    user = registered_user(client, db_session, "s5_er_read")
    cs408_event(db_session, user, "s5-er-2", correct=True)
    before = (db_session.query(dp_models.LearningEvent).count(),
              db_session.query(dp_models.ModelPrediction).count(),
              db_session.query(dp_models.ModelInferenceRun).count())
    client.get("/exam/prep/scientific/evidence-reliability")
    client.get("/exam/prep/scientific/capabilities")
    db_session.expire_all()
    assert (db_session.query(dp_models.LearningEvent).count(),
            db_session.query(dp_models.ModelPrediction).count(),
            db_session.query(dp_models.ModelInferenceRun).count()) == before


def test_evidence_reliability_never_reads_another_users_evidence(client, db_session):
    mine = registered_user(client, db_session, "s5_er_mine")
    other = make_user(db_session, "s5_er_other")
    cs408_event(db_session, other, "s5-er-other", correct=True)
    body = client.get("/exam/prep/scientific/evidence-reliability").json()
    assert body["evidence_window"]["event_count"] == 0


def test_a_runtime_outage_is_bounded_and_never_a_500(client, db_session, monkeypatch):
    import routers.exam_prep as exam_prep
    from science import learner_state
    registered_user(client, db_session, "s5_er_outage")
    monkeypatch.setattr(learner_state, "get_client", lambda *a, **kw: _Unreachable())
    r = client.get("/exam/prep/scientific/evidence-reliability?probe_runtime=true")
    assert r.status_code == 200
    assert r.json()["runtime_reachable"] is False


def test_no_foreign_ontology_mapping_exists_anywhere_in_the_science_layer():
    """PART C/J: no ASSISTments/Junyi index is ever derived for a CS408 concept."""
    science_dir = BACKEND / "science"
    for path in science_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for banned in ("assistments_index", "junyi_index", "skill_id_map",
                       "concept_index_map", "map_to_assistments"):
            assert banned not in text, f"{path.name}: {banned}"
    assert er.PRODUCT_FEATURE_COMPATIBILITY == "INCOMPATIBLE"


def test_the_product_backend_still_imports_none_of_the_heavy_scientific_stack():
    import subprocess
    probe = (
        "import sys; sys.path.insert(0, r'%s');"
        "import science.kt_dataset, science.capabilities, science.evidence_reliability;"
        "bad=[m for m in ('torch','transformers','faiss','zhixue_runtime') if m in sys.modules];"
        "print(bad)" % str(BACKEND))
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                         cwd=str(BACKEND))
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", out.stdout


# ================================================================ PART O — migration

def test_the_telemetry_migration_is_the_head_of_the_chain():
    """Read the revision graph from the files, so a broken chain cannot pass silently."""
    import ast

    versions = REPO_ROOT / "migrations" / "versions"
    revisions: dict[str, str | None] = {}
    for path in versions.glob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        values: dict[str, object] = {}
        for node in module.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in ("revision", "down_revision") and \
                        isinstance(node.value, ast.Constant):
                    values[node.target.id] = node.value.value
        if "revision" in values:
            revisions[str(values["revision"])] = values.get("down_revision")

    heads = set(revisions) - set(v for v in revisions.values() if v)
    assert heads == {"20260919_0010"}, heads
    assert revisions["20260919_0010"] == "20260919_0009"
    # the chain is linear and complete back to the first revision
    seen, cursor, depth = set(), "20260919_0010", 0
    while cursor:
        assert cursor not in seen, f"cycle at {cursor}"
        seen.add(cursor)
        assert cursor in revisions, f"{cursor} has no migration file"
        cursor = revisions[cursor]
        depth += 1
    assert depth >= 10


def test_the_migration_adds_exactly_the_four_declared_nullable_columns():
    from importlib import util as importlib_util
    path = REPO_ROOT / "migrations" / "versions" / "20260919_0010_attempt_telemetry_provenance.py"
    spec = importlib_util.spec_from_file_location("s5_migration_0010", path)
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.NEW_COLUMNS) == {"practice_attempts", "learning_events"}
    for table, columns in module.NEW_COLUMNS.items():
        assert [c[0] for c in columns] == ["response_time_source", "attempt_index"], table


MIGRATION_TABLES = ("practice_attempts", "learning_events")
PROTECTED_TABLES = ("exam_question_bank", "programming_exercises", "knowledge_points")


@pytest.mark.skipif(not REAL_DB.is_file(), reason="real database not present")
def test_migration_upgrades_a_byte_for_byte_COPY_of_the_real_database():
    """PART O: validated on a COPY. The real database is never opened for writing."""
    import subprocess as sp

    before_digest = hashlib.sha256(REAL_DB.read_bytes()).hexdigest()
    before_protected = _protected_row_counts(REAL_DB)
    tmpdir = tempfile.mkdtemp(prefix="s5_migration_")
    try:
        copy = Path(tmpdir) / "app_copy.db"
        shutil.copyfile(REAL_DB, copy)
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == before_digest

        env = dict(os.environ, DATABASE_URL=f"sqlite:///{copy.as_posix()}")
        result = sp.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-2000:]

        conn = sqlite3.connect(str(copy))
        try:
            assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
            for table in MIGRATION_TABLES:
                cols = {r[1] for r in conn.execute(f'pragma table_info("{table}")')}
                assert {"response_time_source", "attempt_index"} <= cols, table
            # the telemetry columns arrive EMPTY: nothing was backfilled
            for table in MIGRATION_TABLES:
                non_null = conn.execute(
                    f'select count(*) from "{table}" '
                    f'where response_time_source is not null or attempt_index is not null'
                ).fetchone()[0]
                assert non_null == 0, f"{table} was backfilled"
            # protected content survived byte-for-byte in count
            assert _protected_row_counts_from(conn) == before_protected
        finally:
            conn.close()

        # the original was never touched
        assert hashlib.sha256(REAL_DB.read_bytes()).hexdigest() == before_digest
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _protected_row_counts(db: Path) -> dict:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return _protected_row_counts_from(conn)
    finally:
        conn.close()


def _protected_row_counts_from(conn) -> dict:
    counts = {}
    for table in PROTECTED_TABLES:
        try:
            counts[table] = conn.execute(f'select count(*) from "{table}"').fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = None
    return counts


# ================================================================ contract surface

def test_the_gate_response_is_openapi_concrete(client):
    schema = client.get("/openapi.json").json()
    assert "EvidenceReliabilityPreviewResponse" in json.dumps(schema)
    assert "ScalerGate" in json.dumps(schema) or "scaler_gate" in json.dumps(schema)


def test_the_reliability_weight_field_is_typed_nullable_not_any():
    from science.contract import EvidenceReliabilityPreviewResponse
    field = EvidenceReliabilityPreviewResponse.model_fields["reliability_weight"]
    assert "float" in str(field.annotation)
    assert "None" in str(field.annotation) or field.default is None
