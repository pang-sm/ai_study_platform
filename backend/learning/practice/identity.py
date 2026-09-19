"""Deterministic identity for Practice Core rows.

Same principle as the Data Plane identity contract: identity is derived only from the
source's own identity, never from timestamps, answers, correctness, or randomness — so
replaying an import always lands on the same row.

This namespace is separate from ``data_plane.identity.EVENT_UUID_NAMESPACE``. Learning
event ids are a frozen contract that must not shift; practice row identity is a
different fact and gets its own namespace so the two can never be confused.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from core.learning_context import normalize_service_namespace

PRACTICE_UUID_NAMESPACE = uuid.UUID("7d1e4f62-3b8a-4c5d-9e10-5a6b7c8d9e0f")

# FROZEN identity tokens. Practice row identity is a permanent contract: the same
# logical legacy row must yield the same uid in EVERY environment and across every data
# history, so it keys on a frozen token rather than on the current canonical namespace
# name. `exam_prep` deliberately keeps the historical `exam_11408` token — renaming the
# learning space must never re-identify an attempt that already exists (or would have
# existed) under the old name. Changing any value here is a breaking identity change.
IDENTITY_TOKEN_BY_NAMESPACE = {
    "course_learning": "course_learning",
    "exam_prep": "exam_11408",
    "programming": "programming",
}


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fact_hash(payload: dict) -> str:
    """Content hash of an attempt's fact payload, used to detect conflicting re-imports."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def identity_token(service_namespace: str) -> str:
    """Canonical (or legacy alias) namespace → the frozen token used in uuid5 names.

    Accepts either the canonical namespace or any legacy input alias, so a replay that
    says ``exam_11408`` and a fresh write that says ``exam_prep`` produce one identity.
    An unknown namespace falls through as-is: identity must stay total rather than
    raising deep inside a mirror.
    """
    try:
        canonical = normalize_service_namespace(service_namespace)
    except ValueError:
        canonical = str(service_namespace or "")
    return IDENTITY_TOKEN_BY_NAMESPACE.get(canonical, canonical)


def session_uid(service_namespace: str, source_type: str, source_session_key,
                user_id=None) -> str:
    """Deterministic id for a legacy-compat session.

    The same (user, namespace, container type, container id) always yields the same
    session, so a retried or backfilled attempt cannot spawn a second session.

    ``user_id`` is part of the name on purpose: legacy container ids are not guaranteed
    to be unique ACROSS users, and without it two learners mirroring the same container
    id would collide on the unique constraint.
    """
    token = identity_token(service_namespace)
    name = f"practice_session|u{user_id}|{token}|{source_type}|{source_session_key}"
    return str(uuid.uuid5(PRACTICE_UUID_NAMESPACE, name))


def attempt_uid(service_namespace: str, source_attempt_type: str, source_attempt_id,
                source_item_key, user_id=None) -> str:
    """Deterministic id for a mirrored attempt — mirrors the learning-event item key.

    User-scoped for the same reason as ``session_uid``.
    """
    token = identity_token(service_namespace)
    name = (f"practice_attempt|u{user_id}|{token}|{source_attempt_type}"
            f"|{source_attempt_id}|{source_item_key}")
    return str(uuid.uuid5(PRACTICE_UUID_NAMESPACE, name))


def live_attempt_uid() -> str:
    """Fresh identity for an attempt created directly through the Practice Core API."""
    return str(uuid.uuid4())


def live_session_uid() -> str:
    return str(uuid.uuid4())
