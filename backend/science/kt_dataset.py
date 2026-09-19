"""Offline deterministic KT dataset contract — NOT a model, and NOT a training run.

WHAT THIS IS
------------
The export that a FUTURE CS408-native knowledge-tracing model would be trained from. The
product's existing KT checkpoints read an index into someone else's ontology (ASSISTments
skills, Junyi concepts), and the measured 0.46 swing under an arbitrary index assignment is
why none of them may be surfaced. The replacement has to be trained on the product's own
concept space, and this module is the contract that dataset will be built under — written
now, while the facts are being recorded, so the schema cannot be retro-fitted around
whatever happens to be convenient later.

It trains nothing, predicts nothing, and reads no model. It is a deterministic read over
canonical events.

WHAT A RECORD CARRIES, AND WHY EACH FIELD IS THERE
--------------------------------------------------
    learner_ref      a stable, opaque reference to one learner
    concept_key      the DEEPEST native concept level the fact actually carries
    interactions[]   ordered, each with:
                       attempt_ref   the canonical event id — the attempt's identity
                       item_ref      the question the interaction was with
                       correct       an authoritative boolean, true or false
                       occurred_at   the fact's own UTC epoch, in seconds
                       attempt_index / duration_ms / duration_source
                                     S5 telemetry, and NULL wherever it was not observed

WHAT IT DELIBERATELY DOES NOT CARRY
-----------------------------------
No learner name, no username, no email — ``learner_ref`` is a fixed-domain digest, so the
export is stable across runs while the identity it points at is not readable from it. No
question stem, no answer text, no explanation, no analysis, no source code, no AI prompt
and no AI response. A KT model consumes (who, what concept, right or wrong, when); the
content of the question is a separate asset with its own governance, and copying it into a
training set is not this module's decision to make.

TRI-STATE IS PRESERVED, NEVER COLLAPSED
---------------------------------------
``correct`` is true / false / NULL on a canonical fact. An ungraded big question and an
unanswered item both carry NULL, and neither is "wrong". Only ``True`` and ``False`` enter
an interaction here; everything else is excluded and COUNTED in the audit, where the
exclusion is visible instead of being silently read as a zero.

DETERMINISM
-----------
The same database produces byte-identical output. Ordering is
``(occurred_at, event_id)`` — the event id is a deterministic UUIDv5 over the source
triple, so it is a stable tie-break, not an incidental one. Nothing in the body is a wall
clock or a random value; ``dataset_hash`` is a sha256 over the canonical body, so an export
can be audited by re-running it. A caller that wants a generation time puts one OUTSIDE the
body — putting it inside would make the hash meaningless.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session as DbSession

from learning.records import native_concept

DATASET_CONTRACT_VERSION = "kt-v1"

# Fixed domain separator for the opaque learner reference. Changing it changes every
# learner_ref, so it is versioned with the contract rather than being a free parameter.
LEARNER_REF_DOMAIN = "zhixue-kt-v1:"

# Every field a record may NOT carry, listed where the record is defined.
FORBIDDEN_FIELDS = (
    "username", "email", "display_name", "learner_name",
    "question_stem", "answer_text", "standard_answer", "analysis", "explanation",
    "source_code", "ai_prompt", "ai_response",
)

# Why a canonical event did not become an interaction. Stable codes.
EXCLUDED_NOT_BINARY = "CORRECTNESS_NOT_AUTHORITATIVE_BOOLEAN"
EXCLUDED_NO_CONCEPT = "NO_NATIVE_CONCEPT_REFERENCE"


def learner_ref(user_id: int) -> str:
    """A stable, opaque reference for one learner.

    Reproducible across runs and across machines, and not the user id. This is not a
    security boundary — it is a boundary against the export casually carrying identities
    it has no reason to carry.
    """
    digest = hashlib.sha256(f"{LEARNER_REF_DOMAIN}{int(user_id)}".encode("utf-8"))
    return digest.hexdigest()[:16]


def is_kt_eligible(event) -> tuple[bool, str | None]:
    """Whether one canonical event may become an interaction. Pure."""
    correct = getattr(event, "correct", None)
    # exactly True or False: isinstance also rejects 0/1 smuggled in as ints
    if not isinstance(correct, bool):
        return False, EXCLUDED_NOT_BINARY
    return True, None


def interaction_of(event) -> dict | None:
    """One interaction record, or ``None`` when the fact carries no native concept.

    A fact whose concept is unknown is EXCLUDED rather than filed under its subject: a
    sequence grouped at a level the fact does not actually carry would teach a model a
    concept boundary that no product fact asserts.
    """
    reference = native_concept.reference_for_learning_event(event)
    concept_key = native_concept.concept_key(reference)
    if concept_key is None:
        return None
    return {
        "attempt_ref": str(event.event_id),
        "item_ref": str(event.question_id) if event.question_id else None,
        "concept_key": concept_key,
        "concept_level": native_concept.concept_level(reference),
        "exam_subject_id": reference.get("exam_subject_id"),
        # ACCEL_SPRINT_S6 PART H: the module is a MINIMUM dataset field, and it is not
        # recoverable from the concept key alone — when a fact resolves to a knowledge
        # point, the concept key is the point and the module it belongs to would otherwise
        # be lost. It is copied from the fact, never looked up from the point's name.
        "exam_module_id": reference.get("exam_module_id"),
        "source_type": (str(event.source_type)
                        if getattr(event, "source_type", None) else None),
        "event_type": (str(event.event_type)
                       if getattr(event, "event_type", None) else None),
        "correct": bool(event.correct),
        "occurred_at": float(event.occurred_at),
        # S5 telemetry: present only where it was actually observed. Both halves of a
        # duration travel together, so a consumer can never read a number without its
        # provenance.
        "attempt_index": getattr(event, "attempt_index", None),
        "duration_ms": getattr(event, "response_time_ms", None),
        "duration_source": getattr(event, "response_time_source", None),
    }


def _exam_track_ids(sequences: list) -> list[str]:
    """Which preparation tracks CONTAIN the subjects in this dataset — from the catalog.

    A track is deliberately absent from every FACT: it is the learner's own bundle choice,
    and two learners who answered the same question under different bundles must produce
    byte-identical facts (``core.learning_context.LearningContext.to_event_context``). So
    it cannot be read off an interaction, and it is not invented here either.

    It is, however, a real fact about the CATALOG — this subject belongs to that track —
    and the catalog is versioned config, not learner data. That is the only sense in which
    a track is reported: as a property of the subject the dataset is scoped to. A subject
    the catalog does not place in any track contributes nothing, rather than contributing
    a guessed one.
    """
    subjects = {s.get("exam_subject_id") for s in sequences if s.get("exam_subject_id")}
    if not subjects:
        return []
    try:
        from learning.spaces.exam_prep import catalog
    except Exception:  # noqa: BLE001 — a catalog that will not load yields no claim
        return []
    tracks: set[str] = set()
    for subject_id in sorted(subjects):
        definition = catalog.get_subject(subject_id)
        tracks.update(str(t) for t in (getattr(definition, "suggested_tracks", ()) or ()))
    return sorted(tracks)


def telemetry_contract() -> dict:
    """The telemetry schema this export's optional fields were collected under.

    Carried INSIDE the hashed body on purpose: a dataset assembled from facts recorded
    under a different telemetry contract is a different dataset, and a hash that ignored
    the contract would call them the same.
    """
    from learning.practice.telemetry import (TELEMETRY_COLLECTION_START_VERSION,
                                             TELEMETRY_CONTRACT, TELEMETRY_SCHEMA_VERSION)
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "collection_start_version": TELEMETRY_COLLECTION_START_VERSION,
        "optional_fields": sorted(TELEMETRY_CONTRACT["columns"]),
        "null_means": "NOT OBSERVED — never impute to zero",
    }


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _ordered_events(events) -> list:
    """Deterministic order: the fact's own time, then the deterministic event id."""
    return sorted(events, key=lambda e: (float(e.occurred_at), str(e.event_id)))


def build(db: DbSession, *, service_namespace: str | None = None,
          user_id: int | None = None, event_types: tuple[str, ...] | None = None,
          limit: int = 20000) -> dict:
    """The deterministic KT dataset body. Pure read; writes nothing.

    ``user_id`` narrows the export to one learner; leaving it ``None`` exports every
    learner in scope, which is what a training run wants and what the audit reports on.
    """
    from data_plane.models import LearningEvent

    q = db.query(LearningEvent).filter(LearningEvent.user_id.isnot(None))
    if service_namespace:
        q = q.filter(LearningEvent.service_key == service_namespace)
    if user_id is not None:
        q = q.filter(LearningEvent.user_id == user_id)
    if event_types:
        q = q.filter(LearningEvent.event_type.in_(event_types))

    rows = (q.order_by(LearningEvent.occurred_at.asc(), LearningEvent.event_id.asc())
            .limit(max(1, int(limit))).all())

    excluded: dict[str, int] = {}
    by_bucket: dict[tuple[str, str, str | None], dict] = {}
    concept_levels: dict[str, int] = {}

    for event in _ordered_events(rows):
        eligible, reason = is_kt_eligible(event)
        if not eligible:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        item = interaction_of(event)
        if item is None:
            excluded[EXCLUDED_NO_CONCEPT] = excluded.get(EXCLUDED_NO_CONCEPT, 0) + 1
            continue
        key = (learner_ref(event.user_id), item["concept_key"],
               item.get("exam_subject_id"))
        bucket = by_bucket.get(key)
        if bucket is None:
            bucket = {
                "learner_ref": key[0],
                "concept_key": item["concept_key"],
                "concept_level": item["concept_level"],
                "exam_subject_id": item.get("exam_subject_id"),
                "interactions": [],
            }
            by_bucket[key] = bucket
        bucket["interactions"].append({
            k: v for k, v in item.items()
            if k not in ("concept_key", "concept_level", "exam_subject_id")
        })
        level = str(item["concept_level"])
        concept_levels[level] = concept_levels.get(level, 0) + 1

    sequences = [by_bucket[key] for key in sorted(by_bucket, key=lambda k: (k[0], k[1]))]

    body = {
        "dataset_contract_version": DATASET_CONTRACT_VERSION,
        "semantics": ("ordered CS408-native interaction sequences for a FUTURE knowledge-"
                      "tracing model. Not a model, not a prediction, and not a training "
                      "run."),
        "scope": {
            "service_namespace": service_namespace,
            "user_scoped": user_id is not None,
            "event_types": list(event_types) if event_types else None,
            "events_scanned": len(rows),
            "bounded_to": max(1, int(limit)),
            "exam_track_ids": _exam_track_ids(sequences),
            "telemetry_contract": telemetry_contract(),
        },
        "sequence_count": len(sequences),
        "interaction_count": sum(len(s["interactions"]) for s in sequences),
        "concept_levels": dict(sorted(concept_levels.items())),
        "excluded": dict(sorted(excluded.items())),
        "exclusion_semantics": {
            EXCLUDED_NOT_BINARY: ("the fact carries no authoritative boolean verdict; an "
                                  "unanswered or ungraded item is NOT a negative label"),
            EXCLUDED_NO_CONCEPT: ("the fact carries no native concept reference below the "
                                  "exam subject; it is excluded rather than grouped at a "
                                  "level it does not assert"),
        },
        "forbidden_fields": list(FORBIDDEN_FIELDS),
        "sequences": sequences,
    }
    body["dataset_hash"] = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    return body


# ============================================================ PART K — split policy

SPLIT_POLICY_VERSION = "kt-split-v1"

# Fixed, versioned domain separator. Changing it reassigns every learner, so it is part of
# the policy's identity rather than a free parameter.
SPLIT_SEED = "zhixue-kt-split-v1"

# thousandths. dev and test are carved out of the top of the hash space; everything else
# is train.
SPLIT_DEV_SHARE = 150
SPLIT_TEST_SHARE = 150
_SPLIT_SCALE = 1000

SPLIT_TRAIN = "train"
SPLIT_DEV = "dev"
SPLIT_TEST = "test"


def learner_split_bucket(ref: str) -> int:
    """A learner's fixed position in [0, 1000). Deterministic; depends on nothing else."""
    digest = hashlib.sha256(f"{SPLIT_SEED}:{ref}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % _SPLIT_SCALE


def split_of(ref: str) -> str:
    bucket = learner_split_bucket(ref)
    if bucket < SPLIT_DEV_SHARE:
        return SPLIT_DEV
    if bucket < SPLIT_DEV_SHARE + SPLIT_TEST_SHARE:
        return SPLIT_TEST
    return SPLIT_TRAIN


def user_grouped_split(body: dict) -> dict:
    """Assign every SEQUENCE to train / dev / test. Trains nothing; reads nothing.

    THE INVARIANT THAT MATTERS: a learner appears in exactly one split. A split that puts
    one learner's interactions in both train and test measures MEMORISATION of that
    learner and reports it as generalisation — a knowledge-tracing model in particular will
    happily learn "this learner gets things right" and score well on their other rows.
    Because a sequence is already one learner's ordered interactions on one concept, and a
    learner's split is a property of the learner alone, the invariant holds by construction
    rather than by a check that could be forgotten.

    WHY THE ASSIGNMENT IS A HASH AND NOT A SHUFFLE. A shuffle is deterministic only for a
    fixed input list: the moment a new learner is recorded, every position shifts and the
    splits are silently re-cut, which makes two training runs incomparable without any
    evidence that anything changed. A per-learner hash is stable — a learner keeps their
    split as the cohort grows — at the cost of approximate shares, which is the trade this
    policy deliberately makes. Shares are reported so the approximation is visible.

    TEMPORAL EVALUATION IS A DIFFERENT POLICY and is NOT defined here. Splitting by time
    answers a different question ("does this predict the future?") and must cut by
    ``occurred_at``; mixing the two would produce a split that is neither. When a temporal
    evaluation is required it gets its own policy version and its own report.
    """
    splits: dict[str, list] = {SPLIT_TRAIN: [], SPLIT_DEV: [], SPLIT_TEST: []}
    for sequence in body.get("sequences") or []:
        splits[split_of(sequence["learner_ref"])].append(sequence)

    counts = {}
    for name, sequences in splits.items():
        counts[name] = {
            "learners": len({s["learner_ref"] for s in sequences}),
            "sequences": len(sequences),
            "interactions": sum(len(s.get("interactions") or []) for s in sequences),
        }
    total_interactions = sum(c["interactions"] for c in counts.values())

    learners_by_split = {name: {s["learner_ref"] for s in seqs}
                         for name, seqs in splits.items()}
    overlaps = sorted(
        f"{a}&{b}" for a, b in (("train", "dev"), ("train", "test"), ("dev", "test"))
        if learners_by_split[a] & learners_by_split[b])

    return {
        "policy_version": SPLIT_POLICY_VERSION,
        "grouping_key": "learner_ref",
        "assignment": "sha256(policy_seed + learner_ref) mod 1000, fixed per learner",
        "target_shares": {"dev": SPLIT_DEV_SHARE / _SPLIT_SCALE,
                          "test": SPLIT_TEST_SHARE / _SPLIT_SCALE},
        "counts": counts,
        "interaction_share": {
            name: (round(c["interactions"] / total_interactions, 4)
                   if total_interactions else 0.0)
            for name, c in counts.items()},
        "learner_overlap_between_splits": overlaps,
        "overlap_is_empty": not overlaps,
        "trained": False,
        "temporal_evaluation": ("NOT DEFINED — a time-ordered split answers a different "
                                "question and would need its own policy version"),
    }


def audit(db: DbSession, **kwargs) -> dict:
    """The dataset contract's health WITHOUT the rows — safe to expose as a product report.

    Answers "could a native model be trained from what the product holds today, and what is
    missing?", which is a different question from "what is in the dataset".
    """
    body = build(db, **kwargs)
    return {
        "dataset_contract_version": body["dataset_contract_version"],
        "sequence_count": body["sequence_count"],
        "interaction_count": body["interaction_count"],
        "concept_levels": body["concept_levels"],
        "excluded": body["excluded"],
        "exclusion_semantics": body["exclusion_semantics"],
        "dataset_hash": body["dataset_hash"],
        "scope": body["scope"],
        "semantics": body["semantics"],
        "readiness": _readiness(body),
    }


def _readiness(body: dict) -> dict:
    """What is still missing before a native model could actually be trained."""
    interactions = body["interaction_count"]
    learners = len({s["learner_ref"] for s in body["sequences"]})
    # Deliberately NOT a scientific threshold — a statement of scale, so a reader can see
    # the dataset is thin without mistaking this for a validity claim.
    return {
        "interactions_collected": interactions,
        "learners_collected": learners,
        "native_concept_identity": "AVAILABLE" if interactions else "NO_DATA_YET",
        "blockers": ([
            "NO_TRAINING_RUN_ATTEMPTED — this module builds a dataset, not a model",
            "CALIBRATION_GATE_NOT_ESTABLISHED — no validation protocol exists yet for a "
            "native KT model",
        ] + ([] if interactions else ["NO_ELIGIBLE_INTERACTIONS_IN_SCOPE"])),
    }
