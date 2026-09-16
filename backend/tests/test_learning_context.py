"""STEP 7A unit tests: canonical LearningContext (backend/core/learning_context.py)."""
import pytest
from pydantic import ValidationError

from core.learning_context import (
    LearningContext,
    ServiceNamespace,
    VALID_SERVICE_NAMESPACES,
    is_valid_service_namespace,
)


def test_valid_context_construction():
    ctx = LearningContext(user_id=1, service_namespace="course_learning", course_id="c1")
    assert ctx.user_id == 1
    assert ctx.service_namespace is ServiceNamespace.COURSE_LEARNING
    assert ctx.course_id == "c1"


def test_invalid_namespace_rejected():
    with pytest.raises(ValidationError):
        LearningContext(user_id=1, service_namespace="bogus")


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        LearningContext(user_id=1, service_namespace="course_learning", fake_field="x")


def test_frozen_immutable():
    ctx = LearningContext(service_namespace="exam_11408")
    with pytest.raises((TypeError, ValueError)):
        ctx.course_id = "mutated"  # frozen=True forbids attribute assignment


def test_serialization_roundtrip_excludes_none():
    ctx = LearningContext(user_id=7, service_namespace="programming",
                          programming_language="c", exercise_id=3)
    d = ctx.to_dict()
    assert d["service_namespace"] == "programming"
    assert d["exercise_id"] == 3
    assert "course_id" not in d  # exclude_none=True
    assert LearningContext.from_dict(d) == ctx


def test_to_event_context():
    ctx = LearningContext(user_id=7, service_namespace="course_learning",
                          course_id="c1", subject_key="ds", knowledge_point_id="kp1")
    ec = ctx.to_event_context()
    assert ec["service_namespace"] == "course_learning"
    assert ec["course_id"] == "c1"
    assert ec["knowledge_point_id"] == "kp1"
    # canonical service_namespace maps 1:1 onto the LearningEvent service_key column
    assert ec["service_namespace"] in ("course_learning", "exam_11408", "programming")


def test_namespace_helpers():
    assert VALID_SERVICE_NAMESPACES == {"course_learning", "exam_11408", "programming"}
    assert is_valid_service_namespace("course_learning") is True
    assert is_valid_service_namespace("programming") is True
    assert is_valid_service_namespace("bogus") is False


def test_learning_context_is_not_scientific_state():
    """LearningContext is business/request context, never scientific learner state."""
    ctx = LearningContext(user_id=1, service_namespace="course_learning")
    assert not hasattr(ctx, "mastery_probability")
    assert not hasattr(ctx, "global_ability")
    assert not hasattr(ctx, "learner_state")
