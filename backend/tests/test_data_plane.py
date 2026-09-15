"""Product Data Plane foundation tests (identity, snapshots, models, emitter, backfill)."""
import json
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect

import database
import models
from data_plane import identity, snapshots, emitter, backfill
from data_plane import models as dp_models


# --------------------------------------------------------------------------- #
# identity (pure)
# --------------------------------------------------------------------------- #
def test_event_id_uuidv5_deterministic():
    a = identity.event_id("course_practice", "999", "101:0")
    b = identity.event_id("course_practice", "999", "101:0")
    assert a == b
    assert len(a) == 36


def test_event_id_distinct_for_distinct_items():
    a = identity.event_id("course_practice", "999", "101:0")
    b = identity.event_id("course_practice", "999", "101:1")
    c = identity.event_id("course_practice", "999", "102:0")
    assert len({a, b, c}) == 3


def test_idempotency_key_deterministic():
    assert identity.idempotency_key("course_practice", "999", "101:0") == "course_practice:999:101:0"


def test_source_item_key_keeps_index():
    assert identity.source_item_key("101", 0) == "101:0"
    assert identity.source_item_key("101", 1) == "101:1"


def test_duplicate_question_different_index_distinct():
    a = identity.event_id("course_practice", "999", identity.source_item_key("101", 0))
    b = identity.event_id("course_practice", "999", identity.source_item_key("101", 1))
    assert a != b


def test_canonical_json_stable():
    assert identity.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_item_content_hash_unicode_stable():
    s = {"question_text": "三角形的内角和", "options": ["A", "B"], "standard_answer": "B"}
    assert identity.item_content_hash(s) == identity.item_content_hash(s)
    assert len(identity.item_content_hash(s)) == 64


# --------------------------------------------------------------------------- #
# snapshots (pure)
# --------------------------------------------------------------------------- #
def _live_item():
    return SimpleNamespace(
        id=101, stem="What is 2+2?", subject_key="math",
        knowledge_point_id="kp_1", question_type="choice",
        options_json='[{"key":"A","text":"3"},{"key":"B","text":"4"}]',
        standard_answer="B",
    )


def test_live_snapshot_full():
    s = snapshots.build_live_item_snapshot(_live_item())
    assert s["question_id"] == "101"
    assert s["question_text"] == "What is 2+2?"
    assert s["question_type"] == "choice"
    assert s["options"] is not None
    assert s["standard_answer"] == "B"


def test_backfill_snapshot_partial():
    attempt = SimpleNamespace(subject_key="math", knowledge_point_id="kp_1")
    ri = {"question_id": "101", "standard_answer": "B"}
    s, missing = snapshots.build_backfill_item_snapshot(attempt, ri)
    assert s["question_text"] is None
    assert s["question_type"] is None
    assert s["options"] is None
    assert set(missing) == {"question_text", "question_type", "options"}


# --------------------------------------------------------------------------- #
# models / schema (DB)
# --------------------------------------------------------------------------- #
def test_five_tables_created():
    tables = set(inspect(database.engine).get_table_names())
    assert {"learning_events", "model_versions", "model_inference_runs",
            "model_predictions", "learning_outcomes"} <= tables


def test_learning_event_unique_constraints():
    ev = dp_models.LearningEvent
    cols = [c.name for c in ev.__table__.columns]
    for c in ("event_id", "idempotency_key"):
        assert c in cols
    # unique constraints on source triple + idempotency key
    uq = [u.name for u in ev.__table__.constraints if getattr(u, "name", None)]
    assert "uq_learning_event_source_item" in uq


# --------------------------------------------------------------------------- #
# emitter (DB)
# --------------------------------------------------------------------------- #
def _fake_user():
    return SimpleNamespace(id=7)


def _fake_attempt(aid=999):
    import datetime
    return SimpleNamespace(
        id=aid, username="alice", subject_key="math", knowledge_point_id="kp_1",
        question_ids_json=json.dumps([101]), submitted_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
        status="submitted", answers_json=json.dumps({"101": "B"}),
        result_json=json.dumps({"question_id": 101, "standard_answer": "B", "correct": True}),
    )


def test_emitter_build_full_events():
    evs = emitter.build_course_practice_events(_fake_attempt(), _live_item(), "B", True, _fake_user())
    assert len(evs) == 1
    assert evs[0]["snapshot_capture_mode"] == "LIVE_EMITTER"
    assert evs[0]["snapshot_completeness"] == "FULL"
    assert evs[0]["snapshot_missing_fields_json"] == "[]"
    assert evs[0]["user_id"] == 7
    assert evs[0]["source_user_ref"] == "alice"
    assert evs[0]["correct"] is True


def test_emitter_feature_flag_off(monkeypatch, db_session):
    monkeypatch.setenv("DATA_PLANE_WRITE_ENABLED", "false")
    evs = emitter.build_course_practice_events(_fake_attempt(), _live_item(), "B", True, _fake_user())
    n = emitter.best_effort_emit(evs, database.SessionLocal)
    assert n == 0


def test_emitter_feature_flag_on_idempotent(monkeypatch, db_session):
    monkeypatch.setenv("DATA_PLANE_WRITE_ENABLED", "true")
    evs = emitter.build_course_practice_events(_fake_attempt(), _live_item(), "B", True, _fake_user())
    n1 = emitter.best_effort_emit(evs, database.SessionLocal)
    n2 = emitter.best_effort_emit(evs, database.SessionLocal)
    assert n1 == 1
    assert n2 == 0  # idempotent (duplicate prevented)


def test_emitter_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv("DATA_PLANE_WRITE_ENABLED", "true")
    evs = [{"event_id": "x", "source_attempt_id": "999"}]  # missing required fields -> insert fails
    # best_effort_emit must swallow the error and return, not raise
    n = emitter.best_effort_emit(evs, database.SessionLocal)
    assert n == 0


# --------------------------------------------------------------------------- #
# backfill (DB)
# --------------------------------------------------------------------------- #
def test_backfill_partial_events():
    a = _fake_attempt(2001)
    evs = backfill.build_backfill_events(a, 7)
    assert len(evs) == 1
    assert evs[0]["snapshot_capture_mode"] == "SOURCE_BACKFILL"
    assert evs[0]["snapshot_completeness"] == "PARTIAL"
    assert json.loads(evs[0]["snapshot_missing_fields_json"]) == ["question_text", "question_type", "options"]


def test_backfill_idempotent(monkeypatch, db_session):
    monkeypatch.setenv("DATA_PLANE_WRITE_ENABLED", "true")
    a = _fake_attempt(2002)
    # first backfill -> 1 created; second -> 0 (idempotent)
    r1 = backfill.backfill([a], database.SessionLocal, {"alice": 7}, apply=True)
    r2 = backfill.backfill([a], database.SessionLocal, {"alice": 7}, apply=True)
    assert r1["events_created"] == 1
    assert r2["events_created"] == 0
    assert r2["duplicate_prevented"] == 1


def test_backfill_dry_run_writes_zero(monkeypatch, db_session):
    a = _fake_attempt(2003)
    r = backfill.backfill([a], database.SessionLocal, {"alice": 7}, apply=False)
    assert r["events_created"] == 0
    assert r["items_seen"] == 1


def test_emitter_then_backfill_cross_idempotent(monkeypatch, db_session):
    monkeypatch.setenv("DATA_PLANE_WRITE_ENABLED", "true")
    a = _fake_attempt(2004)
    evs = emitter.build_course_practice_events(a, _live_item(), "B", True, _fake_user())
    emitter.best_effort_emit(evs, database.SessionLocal)
    # backfill over the same attempt must not create duplicates
    r = backfill.backfill([a], database.SessionLocal, {"alice": 7}, apply=True)
    assert r["events_created"] == 0
    assert r["duplicate_prevented"] == 1


# --------------------------------------------------------------------------- #
# no model inference / no runtime import
# --------------------------------------------------------------------------- #
def test_no_runtime_import():
    assert "zhixue_runtime" not in __import__("sys").modules


def test_no_model_inference_rows(db_session):
    for model in (dp_models.ModelVersion, dp_models.ModelInferenceRun,
                  dp_models.ModelPrediction, dp_models.LearningOutcome):
        assert db_session.query(model).count() == 0
