"""learner_state product integration (ACCEL_SPRINT_S3) — a GATED capability report.

WHAT learner_state IS
---------------------
A knowledge-tracing model family (DKT / SimpleKT / AKT / CGKT / CGKT-v2) trained on real
interaction sequences. It is a LEARNED model — unlike StudentTwin it is not a rule engine —
and it outputs ``next_response_probability``: the probability that the learner's NEXT
response is correct. The model executes (verified against the real checkpoints), and that
semantic is frozen: it is NOT a mastery probability, NOT a knowledge-mastery score, NOT an
exam-pass probability, NOT a question difficulty, and NOT a student ability score.

WHY IT PRODUCES NO NUMBER
-------------------------
The model's real input is an index sequence in ITS OWN ontology: ``base`` = ASSISTments
(123 skills) or ``junyi`` (835 concepts). The product's CS408 concepts live in a different
ontology, and no mapping between them exists — the frozen component record states
``ontology_mapping: NONE``.

Fabricating one would not merely be inelegant, it would be dishonest. Measured on the real
checkpoints: the SAME learner, the SAME real correctness sequence and the SAME CS408
concepts, with only a different ARBITRARY index assignment, moves the output by up to 0.46
(SimpleKT: 0.402 -> 0.863). The number would be an artifact of the invented mapping, not a
property of the learner. So this module reports the gate and the evidence, and produces NO
probability.

It follows that ``LEARNER_STATE_PRODUCT_MODE = SHADOW_NOT_USER_VISIBLE``. Nothing here is
displayed to a learner, and nothing here writes: no knowledge status, no wrong state, no
plan, no grade, no learner fact of any kind.
"""
from __future__ import annotations

import logging

from data_plane import eligibility
from data_plane.models import LearningEvent
from sqlalchemy.orm import Session as DbSession

from . import metadata
from .client import ScientificClient, get_client

logger = logging.getLogger("science.learner_state")

COMPONENT = "learner_state"
CONTRACT_VERSION = 1
RUNTIME_PATH = "/v1/inference/learner-state"

# Frozen scientific identity of the checkpoint set (coursegraph_kt @ 06d4366, research
# status "frozen", production_role "candidate"). Same convention as the StudentTwin
# constants: the product records the source identity as a contract fact and never imports
# the scientific stack.
SCIENTIFIC_SOURCE_COMMIT = "06d4366"
SCIENTIFIC_FAMILIES = ("DKT", "SimpleKT", "AKT", "CGKT", "CGKT_v2")
# ontology name -> index-space size. The model requires an index in this range; a product
# concept id is not one.
SCIENTIFIC_ONTOLOGIES = {"base": 123, "junyi": 835}

# The two independent reasons the product surface is closed. Neither is lowered here.
BLOCKER_ONTOLOGY = "ONTOLOGY_MAPPING_ABSENT"
BLOCKER_CALIBRATION = "CALIBRATION_GATE_NOT_ESTABLISHED"

# What the model is allowed to mean, in the words the product may use IF it is ever
# surfaced. It is deliberately reported inside the model-requirement block: this mode is
# SHADOW_NOT_USER_VISIBLE, so no learner sees it, and no number accompanies it.
USER_FACING_LABEL_ZH = "下一次作答正确概率（实验）"

SCORE_SEMANTICS = ("next_response_probability P(correct on the learner's NEXT response) — "
                   "NOT mastery probability, NOT knowledge mastery, NOT exam-pass "
                   "probability, NOT question difficulty, NOT ability")

# A bounded evidence window, matching the StudentTwin preview's bound.
MAX_EVENTS = 2000


def load_evidence_window(db: DbSession, user_id: int, *,
                         service_namespace: str | None = None,
                         exam_module_id: str | None = None,
                         limit: int = MAX_EVENTS) -> dict:
    """The caller's REAL canonical CS408 practice facts, oldest-first.

    This reports what the product genuinely has: an ordered sequence carrying an
    authoritative binary correctness fact. It does NOT invent the missing ontology index.

    The event filter is the SAME canonical input-domain rule the CS408 gate already
    applies (``data_plane.eligibility``): an event counts only when it carries a real
    boolean verdict. One rule, one definition of authoritative correctness.
    """
    from sqlalchemy import func

    q = db.query(LearningEvent).filter(
        LearningEvent.user_id == user_id,
        LearningEvent.event_type.in_(eligibility.STUDENT_TWIN_INPUT_EVENT_TYPES))
    if service_namespace:
        q = q.filter(LearningEvent.service_key == service_namespace)
    if exam_module_id:
        q = q.filter(func.json_extract(LearningEvent.knowledge_point_ref_json,
                                       "$.exam_module_id") == exam_module_id)

    rows = (q.order_by(LearningEvent.occurred_at.desc(), LearningEvent.event_id.desc())
            .limit(max(1, int(limit))).all())
    rows.reverse()

    event_types: dict[str, int] = {}
    excluded: dict[str, int] = {}
    eligible_count = 0
    first_at = last_at = None
    distinct_concepts: set[str] = set()
    for row in rows:
        verdict = eligibility.student_twin_event_eligibility(row)
        if not verdict.eligible:
            excluded[verdict.reason] = excluded.get(verdict.reason, 0) + 1
            continue
        eligible_count += 1
        event_types[row.event_type] = event_types.get(row.event_type, 0) + 1
        first_at = row.occurred_at if first_at is None else min(first_at, row.occurred_at)
        last_at = row.occurred_at if last_at is None else max(last_at, row.occurred_at)
        if row.question_id:
            distinct_concepts.add(row.question_id)

    return {
        "event_count": eligible_count,
        "event_types": event_types,
        "distinct_items": len(distinct_concepts),
        "excluded_event_count": sum(excluded.values()),
        "excluded_reasons": excluded or None,
        "scanned_events": len(rows),
        "bounded_to": MAX_EVENTS,
        "window": {"first_occurred_at": first_at, "last_occurred_at": last_at},
        "scope": {"service_namespace": service_namespace, "exam_module_id": exam_module_id},
        "eligibility_rule": eligibility.RULE_STATEMENT,
        "semantics": ("real canonical practice facts: an ordered sequence with an "
                      "authoritative boolean correctness verdict, and the item each "
                      "observation belongs to; no derived or invented feature"),
    }


def model_requirement() -> dict:
    """What the model needs as input — a REQUIREMENT statement, not a claim of execution."""
    return {
        "component": COMPONENT,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "families": list(SCIENTIFIC_FAMILIES),
        "ontologies": dict(SCIENTIFIC_ONTOLOGIES),
        "required_input": ["q (concept index sequence in the model's own ontology)",
                           "r_prev (previous-response 0/1 sequence)"],
        "available_product_input": ["concept/item reference (CS408 knowledge point)",
                                    "correctness (authoritative boolean)",
                                    "occurrence order"],
        "missing_input": ["concept index in the ASSISTments (123) / Junyi (835) ontology"],
        "ontology_mapping": "NONE",
        "active_product_variant": None,
        "variant_mode": "PANEL",
        "engineering_representative_only": True,
        "score_semantics": SCORE_SEMANTICS,
        "user_facing_label_zh": USER_FACING_LABEL_ZH,
        "user_facing_label_note": ("the only permitted framing for this semantic; NOT "
                                   "surfaced in this mode"),
    }


def blockers(evidence: dict) -> list[str]:
    """The exact, independent reasons no product number is produced."""
    return [
        f"{BLOCKER_ONTOLOGY}: the model reads an index in its own ontology "
        f"(ASSISTments {SCIENTIFIC_ONTOLOGIES['base']} skills / Junyi "
        f"{SCIENTIFIC_ONTOLOGIES['junyi']} concepts); the product has CS408 knowledge "
        f"points and no mapping exists, so any index would be invented",
        f"{BLOCKER_CALIBRATION}: the frozen component record carries "
        f"scientific_threshold = null — no calibration/validity threshold was established "
        f"for this component",
    ]


def preview(db: DbSession, user_id: int, *, service_namespace: str | None = None,
            exam_module_id: str | None = None, probe_runtime: bool = False,
            client: ScientificClient | None = None) -> dict:
    """Report the learner_state gate for this caller. Never raises, never writes.

    No inference is attempted, because there is no honest input to attempt it with. The
    response states the exact blocker and the real evidence that exists.
    """
    evidence = load_evidence_window(db, user_id, service_namespace=service_namespace,
                                    exam_module_id=exam_module_id)
    gate_blockers = blockers(evidence)
    if evidence["event_count"] == 0:
        gate_blockers = gate_blockers + ["NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE"]

    reachable = None
    if probe_runtime:
        # Bounded by construction. ``health`` has its own short timeout and answers
        # "unavailable" rather than raising, and the whole probe is wrapped anyway: a
        # scientific outage is reported as unreachable, never escalated to a product 500.
        try:
            client = client or get_client()
            reachable = client.health().get("status") == "ok"
        except Exception as exc:  # noqa: BLE001 — a probe may never break the caller
            logger.warning("learner_state runtime probe failed: %s", type(exc).__name__)
            reachable = False

    return {
        "metadata": metadata.metadata(
            component=COMPONENT, mode=metadata.MODE_SHADOW_NOT_USER_VISIBLE,
            runtime_release_id=None, source_class="ORIGINAL_ARCHIVE_VERIFIED",
            blockers=gate_blockers,
            # any mention of "probability" is negated in its own sentence — the word may
            # never read as a label standing alone (S1 semantic convention)
            semantics="a next-response probability — NOT a mastery probability — and no "
                      "number is produced in this mode; the product surface is closed"),
        "score_semantics": SCORE_SEMANTICS,
        "next_response_probability": None,
        "model_requirement": model_requirement(),
        "evidence_window": evidence,
        "runtime_reachable": reachable,
        "runtime_provenance": {
            "runtime_path": RUNTIME_PATH,
            "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
            "model_executes": True,
            "executed_for_this_request": False,
            "note": ("the model is real and executable; it was NOT executed for this "
                     "request because the honest input does not exist"),
        },
    }
