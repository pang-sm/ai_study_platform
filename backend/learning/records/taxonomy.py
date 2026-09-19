"""Canonical LearningEvent taxonomy (STEP 7F) — CONFIG, not a SQL table.

NO SOURCE → NO EVENT
--------------------
An event type is only ACTIVE when a real server-side producer exists for it today.
Types the SSOT lists as typical but that no durable fact can currently produce are
recorded as DEFERRED: they are reserved names, not licence to synthesize events.

ONE FACT → ONE EVENT
--------------------
Each business fact has exactly ONE authoritative producer. ``OWNERSHIP_MATRIX`` is the
registry of that decision; adding a second producer for a fact already owned here is the
failure mode this table exists to prevent.

The read-model ``category`` is a display classification. It is deliberately independent
of the stored ``event_type`` (and of the physical columns): the course_practice
exception below is visible as a practice record without its stored type being renamed.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.learning_context import ServiceNamespace

# producer status
ACTIVE = "ACTIVE"          # a real producer exists today
DEFERRED = "DEFERRED"      # reserved name; no durable source exists yet
COMPAT_ALIAS = "COMPAT_ALIAS"  # legacy name kept for compatibility only

# read-model categories (§20)
CAT_MATERIAL = "MaterialEvent"
CAT_AI = "AIEvent"
CAT_PRACTICE = "PracticeEvent"
CAT_WRONG_ANSWER = "WrongAnswerEvent"
CAT_REVIEW = "ReviewEvent"
CAT_PLAN = "PlanEvent"
CAT_PROGRAMMING = "ProgrammingEvent"
CAT_KNOWLEDGE = "KnowledgeEvent"

# event granularity (existing column, String(20))
ITEM_LEVEL = "ITEM_LEVEL"
ACTIVITY_LEVEL = "ACTIVITY_LEVEL"

# read-surface visibility. AUDIT_ONLY types are valid backend facts (accounting, ops) that
# are NOT study history: the canonical records read surface excludes them SERVER-SIDE, so no
# client has to filter them out and no learner ever sees ops telemetry in 学习记录.
USER_FACING = "USER_FACING"
AUDIT_ONLY = "AUDIT_ONLY"

# Frozen event schema version. STEP 7F's taxonomy is fully expressible under the
# existing envelope, so the version is NOT bumped (§33).
EVENT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class EventTypeSpec:
    event_type: str
    category: str
    owner: str                      # authoritative producer module:function
    durable_source: str             # the product fact behind the event
    granularity: str
    status: str
    student_twin_eligible: bool
    visibility: str = USER_FACING
    required_payload: tuple[str, ...] = ()
    namespaces: tuple[str, ...] = ()   # empty = any learning space
    description: str = ""


COURSE = ServiceNamespace.COURSE_LEARNING.value
EXAM = ServiceNamespace.EXAM_PREP.value
PROG = ServiceNamespace.PROGRAMMING.value

TAXONOMY: tuple[EventTypeSpec, ...] = (
    # ── the frozen STEP6/7A exception: DO NOT rename, DO NOT re-emit ──
    EventTypeSpec(
        event_type="course_practice",
        category=CAT_PRACTICE,
        owner="data_plane.emitter.build_course_practice_events",
        durable_source="ai_question_attempts (AIQuestionAttempt)",
        granularity=ITEM_LEVEL,
        status=ACTIVE,
        student_twin_eligible=True,
        required_payload=("answer", "correct"),
        namespaces=(COURSE,),
        description="The frozen STEP6/7A StudentTwin family. Its deterministic UUIDv5 "
                    "identity is a frozen contract (STEP6/STEP7A): STEP7F must not rename "
                    "it to question_answered and must not emit a second equivalent event "
                    "for the same attempt. Since ACCEL_SPRINT_S2 it is no longer the ONLY "
                    "eligible family, and it too is subject to the per-event input rule.",
    ),
    # ── practice spine (STEP7D owner) ──
    EventTypeSpec(
        event_type="question_answered",
        category=CAT_PRACTICE,
        owner="learning.practice.events.emit_for_attempt",
        durable_source="practice_attempts (non-AIQuestionAttempt lineage)",
        granularity=ITEM_LEVEL,
        status=ACTIVE,
        student_twin_eligible=True,
        required_payload=("correct",),
        namespaces=(COURSE, EXAM),
        description="One factual objective attempt. correct is tri-state and is carried "
                    "as-is; question_correct / question_wrong are DERIVED from it, never "
                    "stored as extra events. ACCEL_SPRINT_S2: the family MAY feed "
                    "StudentTwin, but TYPE eligibility is necessary and NOT sufficient — "
                    "the per-event input rule in data_plane.eligibility decides whether "
                    "this particular event carries an authoritative binary correctness "
                    "fact. It is NOT renamed to course_practice, and no scientific "
                    "algorithm changes.",
    ),
    EventTypeSpec(
        event_type="code_submitted",
        category=CAT_PROGRAMMING,
        owner="learning.practice.events.emit_for_attempt",
        durable_source="practice_attempts (real judge result)",
        granularity=ITEM_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("correct",),
        namespaces=(PROG,),
        description="One real judged programming submission. code_passed / code_failed "
                    "are DERIVED classifications; no source code is stored.",
    ),
    # ── AI ──
    EventTypeSpec(
        event_type="ai_called",
        category=CAT_AI,
        owner="ai.orchestrator.AIOrchestrator.execute",
        durable_source="ai_requests (terminal state)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        visibility=AUDIT_ONLY,
        required_payload=("ai_request_id", "status"),
        description="One terminal AI request. No prompt, no response, no model cost "
                    "detail beyond a coarse class. Accounting/ops fact: excluded from the "
                    "user-facing record surface (F1C6), never deleted.",
    ),
    # ── knowledge ──
    EventTypeSpec(
        event_type="knowledge_status_changed",
        category=CAT_KNOWLEDGE,
        owner="learning.records.producers.emit_knowledge_status_changed",
        durable_source="knowledge_progress_events / user_knowledge_progress",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("new_status",),
        description="A real user knowledge-status transition. Never an LLM-inferred "
                    "mastery claim: LearnerState next-response P(correct) is NOT mastery.",
    ),
    # ── material ──
    EventTypeSpec(
        event_type="material_asked",
        category=CAT_MATERIAL,
        owner="learning.records.producers.emit_material_asked",
        durable_source="chat_messages / ai_requests (material QA)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("material_id",),
        description="The learner asked something about a material. The question text "
                    "stays in chat_messages; the event carries references only.",
    ),
    EventTypeSpec(
        event_type="material_opened",
        category=CAT_MATERIAL,
        owner="learning.records.producers.emit_material_opened",
        durable_source="study_materials access (deduped)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("material_id",),
        description="A material was opened by the learner. Deduped per (user, material, "
                    "UTC day) so page refreshes do not become events.",
    ),

    # ── reserved, NO SOURCE YET: names only, never synthesized ──
    EventTypeSpec("review_completed", CAT_REVIEW, "—", "review_items (not built)",
                  ACTIVITY_LEVEL, DEFERRED, False, description="STEP7G+ Review Core."),
    EventTypeSpec("plan_created", CAT_PLAN, "—", "plans (not built)",
                  ACTIVITY_LEVEL, DEFERRED, False, description="Planning Core, later STEP."),
    EventTypeSpec("task_completed", CAT_PLAN, "—", "tasks (not built)",
                  ACTIVITY_LEVEL, DEFERRED, False, description="Planning Core, later STEP."),
    EventTypeSpec("wrong_answer_resolved", CAT_WRONG_ANSWER, "—",
                  "wrong_answer_states (manual action only)",
                  ACTIVITY_LEVEL, DEFERRED, False,
                  description="WrongAnswerState is operational state rebuilt from practice "
                              "events; a per-recompute event would be pure duplication."),
)

_BY_TYPE = {spec.event_type: spec for spec in TAXONOMY}


def spec_for(event_type: str) -> EventTypeSpec | None:
    return _BY_TYPE.get(event_type)


def is_registered(event_type: str) -> bool:
    return event_type in _BY_TYPE


def is_active(event_type: str) -> bool:
    spec = _BY_TYPE.get(event_type)
    return bool(spec and spec.status == ACTIVE)


def category_for(event_type: str) -> str | None:
    spec = _BY_TYPE.get(event_type)
    return spec.category if spec else None


def active_event_types() -> tuple[str, ...]:
    return tuple(s.event_type for s in TAXONOMY if s.status == ACTIVE)


def deferred_event_types() -> tuple[str, ...]:
    return tuple(s.event_type for s in TAXONOMY if s.status == DEFERRED)


def all_categories() -> tuple[str, ...]:
    return (CAT_MATERIAL, CAT_AI, CAT_PRACTICE, CAT_WRONG_ANSWER, CAT_REVIEW,
            CAT_PLAN, CAT_PROGRAMMING, CAT_KNOWLEDGE)


def ownership_matrix() -> list[dict]:
    """The one-fact-one-owner registry (§6)."""
    return [
        {
            "business_fact": spec.durable_source,
            "event_type": spec.event_type,
            "authoritative_producer": spec.owner,
            "event_identity": "UUIDv5(source_type, source_attempt_id, source_item_key)",
            "scientific_eligible": spec.student_twin_eligible,
            "status": spec.status,
        }
        for spec in TAXONOMY
    ]


def student_twin_eligible_types() -> tuple[str, ...]:
    return tuple(s.event_type for s in TAXONOMY if s.student_twin_eligible)


def user_facing_event_types() -> tuple[str, ...]:
    """Types that ARE study history. The default scope of every record read."""
    return tuple(s.event_type for s in TAXONOMY
                 if s.status == ACTIVE and s.visibility == USER_FACING)


def audit_only_event_types() -> tuple[str, ...]:
    """Types that are real backend facts but NOT study history (accounting / ops)."""
    return tuple(s.event_type for s in TAXONOMY if s.visibility == AUDIT_ONLY)


def is_user_facing(event_type: str) -> bool:
    spec = _BY_TYPE.get(event_type)
    return bool(spec and spec.visibility == USER_FACING)
