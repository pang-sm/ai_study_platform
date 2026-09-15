"""Deterministic identity + canonical serialization for the Product Data Plane.

Identity is derived ONLY from (source_type, source_attempt_id, source_item_key).
It never depends on timestamp, answer, correctness, or random UUIDs, so the same
source item always yields the same logical event across replay and backfill.
"""
import hashlib
import json
import uuid

# Fixed, documented namespace for UUIDv5 event_id generation.  Do NOT change this
# after go-live; it is part of the identity contract.
EVENT_UUID_NAMESPACE = uuid.UUID("1a2b3c4d-5e6f-7890-0000-000000000000")


def canonical_json(obj) -> str:
    """Deterministic canonical JSON (stable across runs): UTF-8, sorted keys, compact separators."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def source_item_key(question_id, source_item_index) -> str:
    return f"{question_id}:{source_item_index}"


def idempotency_key(source_type, source_attempt_id, item_key) -> str:
    return f"{source_type}:{source_attempt_id}:{item_key}"


def event_id(source_type, source_attempt_id, item_key) -> str:
    name = f"{source_type}|{source_attempt_id}|{item_key}"
    return str(uuid.uuid5(EVENT_UUID_NAMESPACE, name))


def item_content_hash(item_snapshot: dict) -> str:
    return hashlib.sha256(canonical_json(item_snapshot).encode("utf-8")).hexdigest()
