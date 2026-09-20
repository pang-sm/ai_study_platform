"""CS408_INTERACTION_DATASET_V1 — the frozen training-data CONTRACT for a native KT model.

WHAT THIS MODULE IS
-------------------
A CONTRACT, a MEASUREMENT and a GATE. It is not a model, not a trainer, and it produces no
prediction. Everything here is a deterministic read plus statements that were written down
BEFORE any model was fitted, which is the only order in which a readiness threshold means
anything.

WHY A CONTRACT AND NOT JUST AN EXPORTER
---------------------------------------
S6 shipped ``science.kt_dataset`` (contract ``kt-v1``) and a deterministic exporter. What
it did not ship was a dataset IDENTITY: a version, a scope, and a stated field set that a
future training run must refuse to proceed without. Without that, "the dataset changed" is
undetectable and a model's provenance is a filename. ``CS408_INTERACTION_DATASET_V1`` names
the join of (contract version, catalog version, exporter version, scope, collection start),
so two training runs can be compared or declared incomparable instead of assumed equal.

THE THREE THINGS THIS MODULE REFUSES TO DO
------------------------------------------
1. It does not infer a concept from a title, a path or a question number. Concept identity
   is only ever a canonical id that a stored fact actually carries
   (``learning.records.native_concept``). A fact that resolves only to a module is recorded
   at MODULE level, and module-level identity is never reported as knowledge-point mastery.
2. It does not convert a missing observation into a zero. Every optional field is nullable
   and NULL means NOT OBSERVED; the missingness is REPORTED instead of being filled.
3. It does not pick a threshold after seeing a result. ``READINESS_GATE`` is a module
   constant carrying its own rationale, and ``evaluate_readiness`` only reads it.

SCOPE VS EVENT (S6 decision, preserved)
---------------------------------------
``exam_track_id`` is a property of the DATASET'S SCOPE, not of a learning event. A track is
the learner's bundle choice; two learners who answered the same question under different
bundles must produce byte-identical facts, so the track is never written onto one. It is
reported once, at scope level, derived from the versioned catalog.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session as DbSession

from data_plane import origin as origin_mod

from . import kt_dataset

# ============================================================ PART B — the contract

DATASET_VERSION = "CS408_INTERACTION_DATASET_V1"
EXPORT_VERSION = "kt-export-v1"          # the S6 exporter this contract reads
CONTRACT_VERSION = kt_dataset.DATASET_CONTRACT_VERSION   # "kt-v1"

# The dataset is scoped to ONE preparation track by construction. Named here rather than
# read from the catalog, because a dataset whose scope silently follows the catalog would
# change identity when the catalog does — which is what catalog_version is for.
DATASET_TRACK_ID = "cs_408"

# Collection start for the CANONICAL fact stream this dataset reads. Recorded as a fact of
# the dataset: facts written before the canonical event pipeline existed are not in scope,
# and a reader must be able to tell that from a thin dataset.
COLLECTION_START_VERSION = "ACCEL_SPRINT_S6"
COLLECTION_START_DATE = "2026-09-19"

# ---------------------------------------------------------------- required fields
#
# REQUIRED means "an interaction without this is not an interaction". A missing required
# field is a DEFECT to be counted, never a value to be imputed.
REQUIRED_SCOPE_FIELDS = (
    "dataset_version", "contract_version", "export_version", "catalog_version",
    "exam_track_id", "collection_start", "telemetry_contract", "dataset_hash",
)

REQUIRED_INTERACTION_FIELDS = (
    # learner
    "learner_ref",          # anonymous stable research id (never a username / email / id)
    # event
    "attempt_ref",          # the canonical event id — stable attempt identity
    "occurred_at",          # the fact's own UTC epoch seconds
    # exam identity
    "exam_subject_id",
    "exam_module_id",
    # item
    "item_ref",
    "source_type",
    "event_type",
    # the label
    "correct",              # exactly True or False; anything else is EXCLUDED and counted
    # concept
    "concept_key",
    "concept_level",
)

# Required fields that live on the SEQUENCE (one value per learner+concept), not repeated
# on every interaction. Checked against the sequence, so a per-interaction check does not
# report them as missing on every row.
SEQUENCE_LEVEL_REQUIRED_FIELDS = (
    "learner_ref", "concept_key", "concept_level", "exam_subject_id",
)

# ---------------------------------------------------------------- optional telemetry
#
# OPTIONAL means "recorded only where it was genuinely observed". The rule is the whole
# point of the field set: a missing observation is NULL, and NULL never becomes 0.
OPTIONAL_INTERACTION_FIELDS = (
    "attempt_index",        # 1-based ordinal over (learner, question) — NULL if not observed
    "duration_ms",          # only ever with duration_source, never alone
    "duration_source",      # which boundary the duration was measured between
)

# PART P — what the export may NEVER carry. Enforced by kt_dataset.FORBIDDEN_FIELDS and
# restated here for the dataset identity, so a reader of THIS contract sees the privacy
# rule where the fields are declared.
FORBIDDEN_FIELDS = kt_dataset.FORBIDDEN_FIELDS + (
    "user_id", "learner_id", "session_secret", "auth_token", "filesystem_path",
)


def dataset_spec() -> dict:
    """The frozen contract, as data. Adding a required field is a VERSION change."""
    return {
        "dataset_version": DATASET_VERSION,
        "contract_version": CONTRACT_VERSION,
        "export_version": EXPORT_VERSION,
        "exam_track_id": DATASET_TRACK_ID,
        "collection_start": {"version": COLLECTION_START_VERSION,
                             "date": COLLECTION_START_DATE},
        "scope_semantics": {
            "exam_track_id": ("a property of the DATASET, reported once at scope level. It "
                              "is NOT written on any learning event: a track is the "
                              "learner's bundle choice, so two learners answering the same "
                              "question under different bundles must produce byte-identical "
                              "facts (S6 PART H, preserved)"),
        },
        "required_scope_fields": list(REQUIRED_SCOPE_FIELDS),
        "required_interaction_fields": list(REQUIRED_INTERACTION_FIELDS),
        "optional_interaction_fields": list(OPTIONAL_INTERACTION_FIELDS),
        "forbidden_fields": list(FORBIDDEN_FIELDS),
        "missing_value_rule": ("a missing optional field is NULL and STAYS null. A missing "
                               "observation is never converted to zero unless zero was "
                               "itself observed"),
        "concept_identity_rule": ("a concept key is included ONLY when a stored fact "
                                  "carries a canonical id for it; it is never inferred from "
                                  "a Chinese title, a path, a name or a question number"),
        "label_rule": ("`correct` is exactly True or False. An unanswered or ungraded item "
                       "carries neither and is EXCLUDED and counted, never read as wrong"),
    }


def catalog_version() -> str:
    """The versioned catalog the dataset's scope resolves against."""
    try:
        from learning.spaces.exam_prep import catalog
        return str(catalog.CATALOG_VERSION)
    except Exception:  # noqa: BLE001 — an unloadable catalog is reported, not guessed
        return "UNAVAILABLE"


def build_v1(db: DbSession, **kwargs) -> dict:
    """The V1 dataset body: the S6 row producer PLUS the V1 scope identity.

    ``science.kt_dataset`` stays the frozen ``kt-v1`` ROW contract and is not version-
    bumped by this sprint. The V1 dataset is the layer above it: it adds the scope identity
    the dataset must carry to have one, and RE-HASHES, because a dataset whose identity
    includes more fields is a different dataset and must not share a hash with one that
    does not.

    Deterministic: every identity field is a constant or a versioned config value, so the
    body carries no wall clock and the same snapshot still exports byte-identically.
    """
    body = kt_dataset.build(db, **kwargs)
    scope = dict(body.get("scope") or {})
    scope.update({
        "dataset_version": DATASET_VERSION,
        "contract_version": CONTRACT_VERSION,
        "export_version": EXPORT_VERSION,
        "catalog_version": catalog_version(),
        "exam_track_id": DATASET_TRACK_ID,
        "collection_start": {"version": COLLECTION_START_VERSION,
                             "date": COLLECTION_START_DATE},
    })
    body["scope"] = scope
    body["dataset_version"] = DATASET_VERSION
    body.pop("dataset_hash", None)
    body["dataset_hash"] = hashlib.sha256(
        kt_dataset._canonical_json(body).encode("utf-8")).hexdigest()
    return body


def dataset_identity(body: dict | None = None) -> dict:
    """The identity a training run must record. Two runs with different identities are not
    comparable, and this is what makes that checkable instead of assumed."""
    body = body or {}
    scope = body.get("scope") or {}
    return {
        "dataset_version": DATASET_VERSION,
        "contract_version": CONTRACT_VERSION,
        "export_version": EXPORT_VERSION,
        "catalog_version": catalog_version(),
        "exam_track_id": DATASET_TRACK_ID,
        "collection_start_version": COLLECTION_START_VERSION,
        "collection_start_date": COLLECTION_START_DATE,
        "dataset_hash": body.get("dataset_hash"),
        "events_scanned": scope.get("events_scanned"),
        "interaction_count": body.get("interaction_count"),
        "sequence_count": body.get("sequence_count"),
    }


def spec_compliance(body: dict) -> dict:
    """Whether a produced body satisfies THIS contract. Missing required fields are listed
    rather than raised, so an audit reports the defect instead of failing on it."""
    scope = body.get("scope") or {}
    # dataset_hash is a body-level field, not a scope one — read it where it lives rather
    # than reporting a missing field that is present under a different key.
    scope_present = {k: (body.get("dataset_hash") if k == "dataset_hash"
                         else scope.get(k)) is not None
                     for k in REQUIRED_SCOPE_FIELDS}
    missing_scope = sorted(k for k, ok in scope_present.items() if not ok)

    interactions = [i for s in (body.get("sequences") or []) for i in s.get("interactions") or []]
    missing_interaction: dict[str, int] = {}

    # `correct` is required to BE a bool rather than merely present: interaction_of()
    # already guarantees that, so a non-bool here is a contract breach, not a missing value
    bad_correct = sum(1 for i in interactions if not isinstance(i.get("correct"), bool))
    if bad_correct:
        missing_interaction["correct"] = bad_correct

    for field in REQUIRED_INTERACTION_FIELDS:
        if field in SEQUENCE_LEVEL_REQUIRED_FIELDS:
            continue  # carried by the sequence, not by each interaction
        n = sum(1 for i in interactions
                if i.get(field) is None and field != "correct")
        if n:
            missing_interaction[field] = n

    return {
        "dataset_version": DATASET_VERSION,
        "compliant": not missing_scope and not missing_interaction,
        "missing_scope_fields": missing_scope,
        "interactions_missing_required_field": missing_interaction,
        "forbidden_field_leak": _forbidden_leaks(body),
    }


def _forbidden_leaks(body) -> list[str]:
    """Forbidden field names carried by the SEQUENCES — the real payload, not a promise.

    Scoped to the sequences and interactions deliberately. The body also contains its own
    ``forbidden_fields`` DECLARATION, so scanning the whole document would match that list
    and report every prohibition as a violation of itself. What matters is whether a
    learner's data carries the field, and that lives in the sequences.
    """
    payload = json.dumps(body.get("sequences") or [], ensure_ascii=False)
    return sorted(name for name in FORBIDDEN_FIELDS if f'"{name}"' in payload)


# ============================================================ PART F3 — NATIVE ONTOLOGY
#
# A single mapping is created per contract version:
#
#     native product concept identity  ->  contiguous training index
#
# It is valid BECAUSE the model is trained from scratch on the SAME native ontology. It is
# NOT a mapping of CS408 concepts into ASSISTments skills or Junyi concepts — no such
# mapping exists, and the measured 0.46 output swing under an arbitrary index assignment is
# exactly what this design avoids. Nothing here reads, or is derived from, a foreign
# ontology, and the module imports no foreign ontology artifact.
ONTOLOGY_VERSION = "cs408-native-ontology-v1"
ONTOLOGY_CONCEPT_LEVELS = ("knowledge_point_id", "exam_module_id")


def native_ontology(body: dict) -> dict:
    """Build the native index map from the DATASET'S OWN observed concept keys.

    Assignment is by sorted order of the concept key, so the mapping is a pure function of
    the concept set: the same concepts always map to the same indices, and adding a new
    concept APPENDS a new index rather than renumbering the existing ones.
    """
    keys = sorted({str(s["concept_key"]) for s in (body.get("sequences") or [])
                   if s.get("concept_key")})
    levels = {}
    for sequence in body.get("sequences") or []:
        key = sequence.get("concept_key")
        if key:
            levels.setdefault(str(key), sequence.get("concept_level"))
    mapping = {key: index for index, key in enumerate(keys)}
    payload = json.dumps({"version": ONTOLOGY_VERSION, "mapping": mapping},
                         sort_keys=True, separators=(",", ":"))
    return {
        "ontology_version": ONTOLOGY_VERSION,
        "kind": "NATIVE_PRODUCT_ONTOLOGY",
        "built_from": "the dataset's own concept keys — no foreign ontology is read",
        "not_a_foreign_mapping": ("this is NOT a mapping of CS408 concepts into ASSISTments "
                                  "skills or Junyi concepts; that mapping does not exist"),
        "concept_levels": list(ONTOLOGY_CONCEPT_LEVELS),
        "index_scheme": "contiguous 0..n-1 over the sorted concept key set",
        "stability_rule": ("a new concept APPENDS the next index; existing indices are "
                           "never renumbered, so a persisted mapping stays valid"),
        "concept_count": len(mapping),
        "levels_present": sorted({str(v) for v in levels.values() if v}),
        "mapping_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "mapping": mapping,
    }


def ontology_is_native(mapping: dict) -> dict:
    """Guard: the mapping may not contain an index that came from elsewhere.

    A foreign ontology reuse would show up as a concept COUNT that does not equal the
    mapping size, or as an index that is not contiguous from zero. Both are checked.
    """
    table = mapping.get("mapping") or {}
    indices = sorted(table.values())
    contiguous = indices == list(range(len(indices)))
    return {
        "native": (mapping.get("kind") == "NATIVE_PRODUCT_ONTOLOGY"
                   and mapping.get("concept_count") == len(table)
                   and contiguous),
        "concept_count_matches": mapping.get("concept_count") == len(table),
        "indices_contiguous_from_zero": contiguous,
        "foreign_ontology_imported": False,
    }


# ============================================================ PART C — DATA QUALITY AUDIT

def _quantile(sorted_values: list[float], q: float) -> float | None:
    """Pure-python quantile (linear interpolation). No numpy in the product backend."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return float(sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac)


def _distribution(values: list[int]) -> dict:
    ordered = sorted(float(v) for v in values)
    return {
        "n": len(ordered),
        "min": int(ordered[0]) if ordered else None,
        "p50": _quantile(ordered, 0.50),
        "p90": _quantile(ordered, 0.90),
        "p99": _quantile(ordered, 0.99),
        "max": int(ordered[-1]) if ordered else None,
        "mean": (sum(ordered) / len(ordered)) if ordered else None,
    }


def audit(db: DbSession, **kwargs) -> dict:
    """PART C — the measured state of the REAL product data, with no PII in the report.

    Reads the canonical fact stream through the S6 contract (the same reader the export
    uses), so the audit cannot describe a dataset the exporter would not produce.
    """
    body = build_v1(db, **kwargs)
    sequences = body.get("sequences") or []
    interactions = [i for s in sequences for i in (s.get("interactions") or [])]

    per_learner: dict[str, int] = {}
    per_item: set[str] = set()
    per_concept: dict[str, int] = {}
    concept_levels: dict[str, int] = {}
    per_module: dict[str, int] = {}
    chapter_level: dict[str, int] = {}
    positives = negatives = 0
    with_attempt_index = 0
    with_duration = 0
    attempt_refs: list[str] = []
    timestamps: list[float] = []

    for sequence in sequences:
        ref = sequence["learner_ref"]
        items = sequence.get("interactions") or []
        per_learner[ref] = per_learner.get(ref, 0) + len(items)
        key = sequence.get("concept_key")
        if key:
            level = str(sequence.get("concept_level") or "UNKNOWN")
            concept_levels[level] = concept_levels.get(level, 0) + len(items)
            # C1: the two levels are DISJOINT buckets, not nested. A fact that carries only
            # a module id reaches CHAPTER level; a fact carrying a canonical knowledge-point
            # id reaches CONCEPT level. Summing them would report a chapter id as a concept.
            if level == "exam_module_id":
                chapter_level[str(key)] = chapter_level.get(str(key), 0) + len(items)
            elif level == "knowledge_point_id":
                per_concept[str(key)] = per_concept.get(str(key), 0) + len(items)
        for item in items:
            per_item.add(str(item.get("item_ref")))
            module = item.get("exam_module_id")
            if module:
                per_module[str(module)] = per_module.get(str(module), 0) + 1
            if item.get("correct") is True:
                positives += 1
            elif item.get("correct") is False:
                negatives += 1
            if item.get("attempt_index") is not None:
                with_attempt_index += 1
            if item.get("duration_ms") is not None:
                with_duration += 1
            attempt_refs.append(str(item.get("attempt_ref")))
            timestamps.append(float(item.get("occurred_at") or 0.0))

    # --- raw-stream anomalies, measured on the events themselves, not the export ---
    rows = _scoped_events(db, **kwargs)
    invalid_correctness = sum(1 for e in rows
                              if not isinstance(getattr(e, "correct", None), bool))
    duplicates = len(attempt_refs) - len(set(attempt_refs))
    timestamp_anomalies = _timestamp_anomalies(sequences)
    total = len(interactions)

    module_coverage = {m: {"interactions": n} for m, n in sorted(per_module.items())}
    chapter_coverage = {c: {"interactions": n} for c, n in sorted(chapter_level.items())}
    concept_coverage = {c: {"interactions": n} for c, n in sorted(per_concept.items())}

    return {
        # ACCEL_PRODUCT_S10 PART G — stated on the audit itself, because the numbers below
        # are REAL-learner numbers and a reader must be able to see that a demo rehearsal was
        # removed rather than silently not counted.
        "dataset_origin_policy": {
            "admissible": sorted(origin_mod.TRAINING_ADMISSIBLE),
            "excluded": sorted(origin_mod.EXCLUDED_FROM_TRAINING),
            "unclassified": origin_mod.UNCLASSIFIED,
            "note": ("only real learner-origin facts may satisfy DATA_READINESS_GATE; demo, "
                     "acceptance, test and synthetic back-fill facts are excluded before any "
                     "count below is taken"),
        },
        "dataset_identity": dataset_identity(body),
        "dataset_hash": body.get("dataset_hash"),
        "users_with_eligible_interactions": len(per_learner),
        "total_eligible_interactions": total,
        "events_scanned": (body.get("scope") or {}).get("events_scanned"),
        "excluded": dict(body.get("excluded") or {}),
        "interactions_per_user": _distribution(list(per_learner.values())),
        "sequence_length": _distribution([len(s.get("interactions") or []) for s in sequences]),
        # C1 — the three coverages are reported SEPARATELY. A chapter id and a stable
        # concept id answer different questions and are never summed into one number.
        "module_coverage": {
            "levels": len(module_coverage),
            "interactions_covered": sum(v["interactions"] for v in module_coverage.values()),
            "modules": module_coverage,
        },
        "chapter_coverage": {
            "levels": len(chapter_coverage),
            "interactions_covered": sum(v["interactions"] for v in chapter_coverage.values()),
            "chapters": chapter_coverage,
        },
        "concept_coverage": {
            "levels": len(concept_coverage),
            "interactions_covered": sum(v["interactions"] for v in concept_coverage.values()),
            "concepts": concept_coverage,
        },
        "question_coverage": {"distinct_items": len(per_item)},
        "label_balance": {
            "correct": positives, "incorrect": negatives,
            "positive_rate": (positives / total) if total else None,
            "minority_share": (min(positives, negatives) / total) if total else None,
        },
        "telemetry_missingness": {
            "attempt_index": _missingness(with_attempt_index, total),
            "duration_ms": _missingness(with_duration, total),
            "rule": "NULL means NOT OBSERVED — it is never imputed to zero",
        },
        "duplicate_interactions": duplicates,
        "duplicate_rate": (duplicates / total) if total else None,
        "invalid_correctness_events": invalid_correctness,
        "invalid_correctness_rate": (invalid_correctness / len(rows)) if rows else None,
        "timestamp_anomalies": timestamp_anomalies,
        "distinct_concept_keys": len(per_concept),
        "concept_levels_present": dict(sorted(concept_levels.items())),
        "privacy": {
            "pii_fields_present": _forbidden_leaks(body),
            "learner_ref_is_anonymous_digest": True,
        },
    }


def _scoped_events(db: DbSession, **kwargs) -> list:
    """The same scoped event read the export performs. One query definition, two readers."""
    from data_plane.models import LearningEvent

    q = db.query(LearningEvent).filter(LearningEvent.user_id.isnot(None))
    if kwargs.get("service_namespace"):
        q = q.filter(LearningEvent.service_key == kwargs["service_namespace"])
    if kwargs.get("user_id") is not None:
        q = q.filter(LearningEvent.user_id == kwargs["user_id"])
    if kwargs.get("event_types"):
        q = q.filter(LearningEvent.event_type.in_(kwargs["event_types"]))
    return q.limit(max(1, int(kwargs.get("limit", 20000)))).all()


def _missingness(observed: int, total: int) -> dict:
    return {"observed": observed, "missing": total - observed,
            "observed_rate": (observed / total) if total else None}


def _timestamp_anomalies(sequences: list) -> dict:
    """Ordering defects a KT model would read as real learning sequence.

    Three, each independently meaningful: an interaction out of order within its own
    sequence, a non-positive timestamp, and a sequence whose interactions are not strictly
    increasing in time.
    """
    non_positive = 0
    unsorted_sequences = 0
    for sequence in sequences:
        times = [float(i.get("occurred_at") or 0.0) for i in sequence.get("interactions") or []]
        non_positive += sum(1 for t in times if t <= 0)
        if any(b < a for a, b in zip(times, times[1:])):
            unsorted_sequences += 1
    return {
        "non_positive_timestamps": non_positive,
        "sequences_not_time_ordered": unsorted_sequences,
        "note": ("the export orders by (occurred_at, event_id); a sequence that is not "
                 "increasing in time means the ORDER ITSELF is a defect to investigate"),
    }


# ============================================================ PART D — READINESS GATE
#
# WRITTEN BEFORE ANY MODEL WAS FITTED, AND NOT CHANGED AFTER. These numbers are OPERATIONAL
# MINIMUMS for "a model could be trained and evaluated honestly", NOT claims that a model
# trained above them would be any good. They are deliberately modest and deliberately
# round, because they are a floor for feasibility, not a target.
#
# The last clause is the one that actually protects the result: a threshold chosen after
# seeing model scores is not a standard, it is a description of whatever happened.
READINESS_GATE = {
    "gate_version": "cs408-kt-readiness-v1",
    "registered": "2026-09-19",
    "registered_before_training": True,
    "thresholds": {
        "users_with_eligible_interactions": 100,
        "total_eligible_interactions": 2000,
        "median_sequence_length": 5,
        "trainable_concepts": 20,
        "trainable_concept_min_interactions": 20,
        "modules_covered": 2,
        "minority_class_share": 0.20,
        "minimum_split_interactions": 100,
        "minimum_split_users": 10,
    },
    "rationale": {
        "users_with_eligible_interactions": ("a user-grouped split needs enough DISTINCT "
                                             "learners that no single learner can carry a "
                                             "split; below this, per-user behaviour is "
                                             "indistinguishable from the model"),
        "total_eligible_interactions": ("below a few thousand interactions the test split "
                                        "is too small for any metric to be stable"),
        "median_sequence_length": ("a knowledge-tracing recurrence needs several steps per "
                                   "sequence; a median below this makes most sequences "
                                   "single-step, which no sequential model can learn from"),
        "trainable_concepts": ("with fewer concepts the model has almost nothing to "
                               "generalise ACROSS, and per-concept results are noise"),
        "trainable_concept_min_interactions": ("a concept seen this few times cannot appear "
                                               "in train, dev AND test with any power"),
        "modules_covered": ("one module means per-module behaviour is unmeasurable and the "
                            "model may simply be learning that module"),
        "minority_class_share": ("an extreme label skew lets a constant predictor score "
                                 "well, which would make every baseline comparison vacuous"),
        "minimum_split_interactions": ("train/dev/test must each carry enough interactions "
                                       "that 'held-out evaluation' is not nominal"),
        "minimum_split_users": ("each split needs more than a handful of learners, or one "
                                "learner's behaviour IS the split's result"),
    },
    "explicitly_not": ("a claim that a model trained above these thresholds is valid, "
                       "calibrated, or useful. Their only job is to refuse to train when "
                       "the data cannot support an honest evaluation"),
    "may_not_be_lowered_to_unlock_a_result": True,
}


def _trainable_concepts(audit_body: dict, minimum: int) -> list[str]:
    return sorted(k for k, v in audit_body["concept_coverage"]["concepts"].items()
                  if v["interactions"] >= minimum)


def evaluate_readiness(audit_body: dict, split: dict | None = None) -> dict:
    """PART D — the gate's verdict. Reads READINESS_GATE; never writes to it."""
    t = READINESS_GATE["thresholds"]
    checks: list[dict] = []

    def check(name: str, observed, required, ok: bool, note: str = "") -> None:
        checks.append({"check": name, "observed": observed, "required": required,
                       "passed": bool(ok), "note": note})

    users = audit_body["users_with_eligible_interactions"]
    total = audit_body["total_eligible_interactions"]
    median_len = audit_body["sequence_length"]["p50"]
    trainable = _trainable_concepts(audit_body, t["trainable_concept_min_interactions"])
    modules = audit_body["module_coverage"]["levels"]
    minority = audit_body["label_balance"]["minority_share"]

    check("users_with_eligible_interactions", users, t["users_with_eligible_interactions"],
          users >= t["users_with_eligible_interactions"])
    check("total_eligible_interactions", total, t["total_eligible_interactions"],
          total >= t["total_eligible_interactions"])
    check("median_sequence_length", median_len, t["median_sequence_length"],
          median_len is not None and median_len >= t["median_sequence_length"])
    check("trainable_concepts", len(trainable), t["trainable_concepts"],
          len(trainable) >= t["trainable_concepts"],
          note=f"a concept counts as trainable at >= {t['trainable_concept_min_interactions']} "
               f"interactions")
    check("modules_covered", modules, t["modules_covered"], modules >= t["modules_covered"])
    check("minority_class_share", minority, t["minority_class_share"],
          minority is not None and minority >= t["minority_class_share"])

    if split is not None:
        for name in ("train", "dev", "test"):
            counts = (split.get("counts") or {}).get(name) or {}
            check(f"split.{name}.interactions", counts.get("interactions"),
                  t["minimum_split_interactions"],
                  (counts.get("interactions") or 0) >= t["minimum_split_interactions"])
            check(f"split.{name}.users", counts.get("learners"), t["minimum_split_users"],
                  (counts.get("learners") or 0) >= t["minimum_split_users"])
        check("user_leakage", split.get("learner_overlap_between_splits") or [],
              [], split.get("overlap_is_empty") is True)

    failed = [c for c in checks if not c["passed"]]
    return {
        "gate_version": READINESS_GATE["gate_version"],
        "verdict": "PASS" if not failed else "FAIL",
        "checks": checks,
        "failed_checks": [c["check"] for c in failed],
        "trainable_concepts": trainable,
        "thresholds": dict(t),
        "note": READINESS_GATE["explicitly_not"],
    }


def training_decision(readiness: dict) -> dict:
    """PART F — the gate that decides whether a training run may be executed at all."""
    allowed = readiness["verdict"] == "PASS"
    return {
        "data_readiness_gate": readiness["verdict"],
        "training_permitted": allowed,
        "cs408_native_kt_trained": False,   # set only by an actual, recorded training run
        "reason": ("the pre-registered readiness thresholds are met"
                   if allowed else
                   "the pre-registered readiness thresholds are NOT met; training would "
                   "produce numbers that cannot be evaluated honestly, so it is refused"),
        "note": ("a refused gate is a RESULT, not a failure: it is the measurement the "
                 "sprint asked for"),
    }


# ============================================================ PART E — SPLIT POLICY
#
# PRIMARY evaluation split is USER-GROUPED: a learner appears in exactly one of
# train / dev / test, so no interaction leaks across the boundary. Individual ROWS are
# never split at random — for a knowledge-tracing model that measures memorisation of the
# learner and reports it as generalisation.

PRIMARY_SPLIT_POLICY = kt_dataset.SPLIT_POLICY_VERSION       # "kt-split-v1", S6
TEMPORAL_SPLIT_POLICY = "kt-split-temporal-v1"


def primary_split(body: dict) -> dict:
    """The user-grouped split (delegates to the S6 policy; this module adds no new rule)."""
    return kt_dataset.user_grouped_split(body)


def temporal_holdout(body: dict, *, holdout_share: float = 0.20) -> dict:
    """OPTIONAL second split, for DEPLOYMENT-DRIFT evaluation.

    It answers a different question from the primary split — "does this predict facts
    recorded LATER?" rather than "does this generalise to other learners?" — which is why
    it is a separate policy with its own version and is never mixed into the primary one.

    The cut is a per-learner time boundary, not a global one: each learner's own earliest
    ``1 - holdout_share`` of interactions form the training portion and their latest form
    the holdout. A single global timestamp would put whole learners entirely on one side
    and silently degenerate into a second user-grouped split.
    """
    if not 0.0 < holdout_share < 1.0:
        raise ValueError("holdout_share must be strictly between 0 and 1")

    train_pairs: list[tuple] = []
    holdout_pairs: list[tuple] = []
    per_learner: dict[str, int] = {}
    for sequence in body.get("sequences") or []:
        items = sorted(sequence.get("interactions") or [],
                       key=lambda i: (float(i.get("occurred_at") or 0.0),
                                      str(i.get("attempt_ref") or "")))
        if not items:
            continue
        cut = int(len(items) * (1.0 - holdout_share))
        # at least one interaction on each side, or the learner contributes nothing usable
        cut = max(1, min(cut, len(items) - 1)) if len(items) >= 2 else 0
        head, tail = items[:cut], items[cut:]
        if head:
            train_pairs.extend((sequence["learner_ref"], i) for i in head)
        if tail:
            holdout_pairs.extend((sequence["learner_ref"], i) for i in tail)
        per_learner[sequence["learner_ref"]] = len(items)

    return {
        "policy_version": TEMPORAL_SPLIT_POLICY,
        "role": "OPTIONAL — deployment-drift evaluation. NOT the primary split",
        "cut": "per learner, by that learner's own occurred_at ordering",
        "holdout_share": holdout_share,
        "train_interactions": len(train_pairs),
        "holdout_interactions": len(holdout_pairs),
        "learners": len(per_learner),
        "learners_with_both_sides": len(
            {ref for ref, _ in train_pairs} & {ref for ref, _ in holdout_pairs}),
        "answer_is_earlier_than_holdout": _temporal_order_holds(train_pairs, holdout_pairs),
        "trained": False,
    }


def _temporal_order_holds(train_pairs, holdout_pairs) -> bool:
    """Per learner, every training interaction must precede every holdout interaction."""
    latest_train: dict[str, float] = {}
    earliest_holdout: dict[str, float] = {}
    for ref, item in train_pairs:
        t = float(item.get("occurred_at") or 0.0)
        latest_train[ref] = max(latest_train.get(ref, float("-inf")), t)
    for ref, item in holdout_pairs:
        t = float(item.get("occurred_at") or 0.0)
        earliest_holdout[ref] = min(earliest_holdout.get(ref, float("inf")), t)
    for ref, latest in latest_train.items():
        if ref in earliest_holdout and earliest_holdout[ref] < latest:
            return False
    return True


# ============================================================ PART I — PROMOTION GATE
#
# The MAXIMUM mode any model produced under this contract may reach, absent an explicit
# final gate decision, is SHADOW. Promotion is a separate act from training, and this
# predicate is what makes "silently promoted" detectable.
PROMOTION_MAX_MODE = "SHADOW"
PROMOTION_TARGET_MODE = "USER_VISIBLE_PREVIEW"
PROMOTION_REQUIREMENTS = (
    "honest_native_ontology",
    "user_grouped_held_out_evaluation",
    "calibrated_probability",
    "meaningful_performance_above_simple_baseline",
    "stable_per_module_behavior",
    "no_data_leakage",
    "deterministic_artifact_loading",
    "checkpoint_provenance",
    "product_backend_no_learner_fact_mutation",
)


def promotion_gate(evidence: dict | None = None) -> dict:
    """Whether this contract's model may exceed SHADOW. Default answer: no."""
    evidence = evidence or {}
    unmet = [name for name in PROMOTION_REQUIREMENTS if not evidence.get(name)]
    return {
        "max_mode": PROMOTION_MAX_MODE,
        "target_mode": PROMOTION_TARGET_MODE,
        "requirements": list(PROMOTION_REQUIREMENTS),
        "evidence": {name: bool(evidence.get(name)) for name in PROMOTION_REQUIREMENTS},
        "unmet": unmet,
        "promotion_permitted": not unmet and bool(evidence.get("explicit_final_gate_decision")),
        "explicit_final_gate_decision_required": True,
        "note": ("even with every requirement met, USER_VISIBLE_PREVIEW needs an explicit "
                 "final gate decision; it is never reached by a model merely existing"),
    }


# ============================================================ PART J — ARTIFACT MANIFEST

ARTIFACT_MANIFEST_VERSION = "cs408-kt-artifact-manifest-v1"
REQUIRED_ARTIFACT_KINDS = (
    "model_weights", "architecture_config", "ontology_mapping", "dataset_manifest",
    "split_manifest", "metrics", "calibrator", "training_config", "environment_versions",
    "source_commit",
)


def artifact_manifest(entries: dict, *, source_commit: str | None = None) -> dict:
    """The packaging record a trained model must carry. No undocumented local path.

    Every entry is ``kind ->{"sha256": ..., "ref": ...}`` where ``ref`` is a name INSIDE
    the bundle, never an absolute path: a manifest that points at one machine's filesystem
    is not a manifest.
    """
    missing = [k for k in REQUIRED_ARTIFACT_KINDS if k not in entries]
    absolute: list[str] = []
    digests: dict[str, str] = {}
    for kind, entry in entries.items():
        ref = str((entry or {}).get("ref") or "")
        if ref.startswith(("/", "\\")) or (len(ref) > 1 and ref[1] == ":"):
            absolute.append(kind)
        digests[kind] = str((entry or {}).get("sha256") or "")

    payload = json.dumps({"version": ARTIFACT_MANIFEST_VERSION, "sha256": digests,
                          "source_commit": source_commit},
                         sort_keys=True, separators=(",", ":"))
    return {
        "manifest_version": ARTIFACT_MANIFEST_VERSION,
        "required_kinds": list(REQUIRED_ARTIFACT_KINDS),
        "missing_kinds": missing,
        "absolute_path_refs": absolute,
        "complete": not missing and not absolute,
        "source_commit": source_commit,
        "source_commit_present": bool(source_commit),
        "manifest_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "digests": digests,
        "rule": ("every artifact is referenced by a bundle-relative name and carries its "
                 "own sha256; no dependency on an undocumented local path"),
    }


# The calibration split names, duplicated here only as documentation strings so this module
# does not import the evaluation layer (which would invert the dependency direction).
CALIBRATION_FIT_SPLIT_DOC = "dev"
CALIBRATION_EVAL_SPLIT_DOC = "test"
CALIBRATION_METHODS_DOC = ("PLATT", "ISOTONIC", "TEMPERATURE")


def training_run_plan(readiness: dict, ontology: dict | None = None,
                      *, source_commit: str | None = None) -> dict:
    """The TRAINING stage of the pipeline, as a governed, checkable plan.

    This is deliberately NOT a trainer. A trainer with no data to validate it against would
    be unvalidated ML shipped into a repository where every scientific claim has to be
    measured, and the sprint's own rule is "train if and only if the gate passes". What is
    built here is the stage BOUNDARY: what a run may consume, what it must produce, and the
    refusal that comes first.

    The refusal is the part that is actually load-bearing. A pipeline whose first stage
    cannot say no is not gated, it is merely ordered.
    """
    decision = training_decision(readiness)
    allowed = decision["training_permitted"]
    return {
        "stage": "TRAIN",
        "permitted": allowed,
        "refused_by": None if allowed else "DATA_READINESS_GATE",
        "consumes": {
            "dataset_version": DATASET_VERSION,
            "contract_version": CONTRACT_VERSION,
            "ontology_version": (ontology or {}).get("ontology_version"),
            "ontology_mapping_hash": (ontology or {}).get("mapping_hash"),
            "split_policy": PRIMARY_SPLIT_POLICY,
            "evaluation_split_policy": TEMPORAL_SPLIT_POLICY,
        },
        # The architecture question PART F asks: reuse an existing research implementation
        # with a NEW native embedding space, rather than auto-including every historical
        # family. CGKT is named as excluded on the F2 grounds, not on convenience.
        "candidate_families": ["DKT", "SimpleKT", "AKT"],
        "excluded_families": {
            "CGKT": ("requires graph semantics that are not genuinely available and "
                     "frozen for the native ontology"),
            "LEGACY_LEARNER_STATE": ("its input is an integer index into the ASSISTments / "
                                     "Junyi ontology; reusing it would be the 0.46-swing "
                                     "mapping this design exists to avoid"),
        },
        "must_produce": list(REQUIRED_ARTIFACT_KINDS),
        "must_report": ["auroc", "accuracy", "log_loss", "brier", "ece",
                        "reliability_bins", "per_module_metrics", "sample_counts"],
        "baselines_required_first": ["global_correctness_prior", "per_module_prior"],
        "calibration": {"fit_on": CALIBRATION_FIT_SPLIT_DOC,
                        "evaluate_on": CALIBRATION_EVAL_SPLIT_DOC,
                        "methods": list(CALIBRATION_METHODS_DOC)},
        "max_resulting_mode": PROMOTION_MAX_MODE,
        "environment": ("OFFLINE ONLY — a training run must never execute inside the "
                        "Product Backend process"),
        "source_commit": source_commit,
        "implemented": False,
        "implemented_note": ("the stage boundary, its inputs, its outputs and its refusal "
                             "are implemented and tested; the trainer BODY is not, because "
                             "with no data it could not be validated and this repository "
                             "does not ship unmeasured scientific code"),
    }


# ============================================================ PART O — V2 DECISION
#
# S5 could not recover the old pipeline. S7 DID recover it — so the old checkpoint family
# is no longer "lost", and it must NOT be retrained under the same name either way. What
# S7 changes is WHY a v2 is needed:
#
#   S5's reason:  the preprocessing is unrecoverable, so the old model cannot be used.
#   S7's reason:  the preprocessing IS recovered and the old model is fully reproducible,
#                 but its input vector is keyed by the ASSISTments skill ontology. That is
#                 an INPUT-DOMAIN fact, not a software gap, and no amount of recovery fixes
#                 it. A user-visible evidence-reliability capability therefore needs a
#                 model trained on the product's OWN ontology.
EVIDENCE_RELIABILITY_V2 = {
    "classification": "PRODUCT_NATIVE_RETRAIN_REQUIRED",
    "required": True,
    "trigger": ("the frozen checkpoints consume b_s / log_opp / p_t, all keyed by the "
                "scientific skill ontology the product has no honest mapping onto"),
    "not_the_trigger": ("preprocessing loss — S7 recovered and VERIFIED the scaler; that "
                        "was S5's trigger and it no longer applies"),
    "old_checkpoint_family": ("RETAINED as verified research provenance. Not retrained "
                              "under the same name, and not superseded in place"),
    "old_family_product_mode": "SHADOW_NOT_USER_VISIBLE",
    "reusable_from_old_work": ("the architecture, the objective and the recovered "
                               "standardizer (for reproducing the old runs); NOT the "
                               "feature semantics and NOT the ontology"),
}


def v2_decision() -> dict:
    return dict(EVIDENCE_RELIABILITY_V2)
