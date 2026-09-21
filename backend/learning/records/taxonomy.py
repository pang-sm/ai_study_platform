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
    # ── the programming working loop (THREE_DOMAIN P1) ──
    #
    # `code_submitted` covers the GRADED fact. The other three deliberate, server-executed
    # actions in the exercise loop had no canonical fact at all, so the product could not
    # say what a learner actually did before they submitted. They are emitted from the
    # request that really executed the code, never from the AI's prose about it.
    #
    # NOTHING HERE FEEDS A MODEL: all three are student_twin_eligible=False, the S2/eligibility
    # input rule rejects them by family, and `data_plane.worker` selects `course_practice`
    # only. `code_run` is EVENT_ONLY (the progress row keeps only the LAST run time, so the
    # event is the durable record) — it is recovered by nothing and claims nothing.
    EventTypeSpec(
        event_type="exercise_started",
        category=CAT_PROGRAMMING,
        owner="learning.spaces.programming.events.emit_exercise_started",
        durable_source="code_projects (the exercise's per-learner project)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        namespaces=(PROG,),
        description="The learner began working on an exercise. Deduped per (user, "
                    "exercise): opening the same exercise again is not a second fact.",
    ),
    EventTypeSpec(
        event_type="code_run",
        category=CAT_PROGRAMMING,
        owner="learning.spaces.programming.events.emit_exercise_activity",
        durable_source="programming_exercise_progress.last_run_at (last only → EVENT_ONLY)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        namespaces=(PROG,),
        description="The learner ran their code for an exercise and the server executed "
                    "it. A run produces no verdict: it is neither pass nor fail.",
    ),
    EventTypeSpec(
        event_type="code_tested",
        category=CAT_PROGRAMMING,
        owner="learning.spaces.programming.events.emit_exercise_activity",
        durable_source="programming_exercise_progress.last_test_at (last only → EVENT_ONLY)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        namespaces=(PROG,),
        description="The learner checked their code against the exercise's own tests. "
                    "The verdict of that check belongs to `code_submitted`.",
    ),
    # ── AI ──
    #
    # P3A — the Deep Study workflow. ``ai_called`` is the ACCOUNTING fact for each model
    # call; these two are the STUDY fact: the learner ran a grounded strong-reasoning session
    # and it produced an answer. They are separate families because they answer separate
    # questions (what did the platform spend / what did the learner study), and neither is a
    # duplicate of the other: a denied or failed call emits ``ai_called`` and NO study fact.
    #
    # The payload carries references and counts (run id, capability, the AI request that
    # answered, how much evidence was used). It never carries the question, the answer or a
    # material body — those stay in their own stores (§34, enforced by
    # ``envelope.assert_payload_is_safe``).
    EventTypeSpec(
        event_type="strong_reasoning_requested",
        category=CAT_AI,
        owner="learning.deep_study.run_deep_study",
        durable_source="ai_requests / the Deep Study workflow's accepted request",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("run_id",),
        namespaces=(COURSE, EXAM),
        description="The learner started a Deep Study session in a real learning space. "
                    "Emitted once the TIER permission is granted and before the model call, "
                    "so a request the tier does not permit produces no study fact at all. A "
                    "request the tier allowed but the BUDGET then refused keeps this fact "
                    "(the session really started) and gets no completed fact — its "
                    "accounting outcome is the ``ai_called`` denial.",
    ),
    EventTypeSpec(
        event_type="strong_reasoning_completed",
        category=CAT_AI,
        owner="learning.deep_study.run_deep_study",
        durable_source="ai_requests (the settled request that produced the answer)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("run_id", "status"),
        namespaces=(COURSE, EXAM),
        description="The Deep Study session produced an answer. Carries the run id and the "
                    "AI request id that answered, so the answer's cost and evidence are "
                    "traceable; a failed session emits nothing here — its accounting fact is "
                    "``ai_called``.",
    ),
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
    # ── the programming debug agent (P3A) ──
    #
    # ONE RUN → these three types, and the run's steps are carried in the payload as a
    # CODE-FREE trace (index, action, status, latency, credits, the id of the AI request that
    # served it, the exercise's own test result, a patch's SIZE). Source code, diffs, prompts
    # and model responses belong to their own stores — §34 forbids them here, and the
    # producer is the only writer of these families.
    EventTypeSpec(
        event_type="programming_agent_started",
        category=CAT_PROGRAMMING,
        owner="learning.spaces.programming.agent.run_debug_agent",
        durable_source="the agent run itself (bounded workflow)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("agent_run_id",),
        namespaces=(PROG,),
        description="A bounded debug workflow began for the learner's own exercise. Emitted "
                    "after the capability permission is granted, never for a refused run.",
    ),
    EventTypeSpec(
        event_type="programming_agent_completed",
        category=CAT_PROGRAMMING,
        owner="learning.spaces.programming.agent.run_debug_agent",
        durable_source="the agent run itself (bounded workflow)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("agent_run_id", "status"),
        namespaces=(PROG,),
        description="The debug workflow finished — whether the tests passed, and every step "
                    "it took. ``status`` distinguishes a completed run from a failed one; the "
                    "run id is the same id its ``ai_requests`` rows carry. The verdict of "
                    "any execution stays the exercise's own fact: this family never claims "
                    "``code_tested`` or ``code_submitted`` on the learner's behalf.",
    ),
    EventTypeSpec(
        event_type="programming_agent_failed",
        category=CAT_PROGRAMMING,
        owner="learning.spaces.programming.agent.run_debug_agent",
        durable_source="the agent run itself (bounded workflow)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("agent_run_id", "status"),
        namespaces=(PROG,),
        description="A debug workflow stopped before it could finish (budget, refusal or a "
                    "technical failure), with the steps that DID happen. The steps already "
                    "run were settled individually; this event states the outcome instead of "
                    "hiding a partial workflow.",
    ),
    # ── P3B: the structured learning report ──
    #
    # ONE fact: a report was produced for a learner and a period. The report's CONTENT (its
    # metrics and its narrative) stays in the response and in the AI request that composed the
    # narrative — the event states that it happened, for which period, and which deterministic
    # blocks it covered.
    EventTypeSpec(
        event_type="report_generated",
        category=CAT_AI,
        owner="learning.report.generate_learning_report",
        durable_source="ai_requests (the report's own request) + the deterministic builder",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("report_id", "period_days"),
        namespaces=(COURSE, EXAM, PROG),
        description="A structured learning report was generated. Its metrics are computed "
                    "from stored facts by a deterministic builder; the narrative (when "
                    "requested) is an AI composition OVER those metrics and never a new fact "
                    "about the learner.",
    ),
    # ── P3B: deep wrong-cause analysis ──
    EventTypeSpec(
        event_type="wrong_analysis_generated",
        category=CAT_WRONG_ANSWER,
        owner="learning.wrong_analysis.analyze_wrong_answer",
        durable_source="wrong_answer_states + the AI request that analysed it",
        granularity=ITEM_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("state_id",),
        namespaces=(COURSE, EXAM),
        description="A wrong-answer state was analysed. The FACTS (the question, the "
                    "learner's answer, the reference answer, the attempt history) come from "
                    "the canonical stores; the analysis itself is an AI hypothesis and is "
                    "reported as such — never as a measured property of the learner.",
    ),
    # ── P3B: dynamic planning (proposal and apply are SEPARATE facts) ──
    EventTypeSpec(
        event_type="plan_adjustment_proposed",
        category=CAT_PLAN,
        owner="learning.plan_adjustment.propose_adjustment",
        durable_source="the AI proposal (request) — writes nothing to the plan",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("proposal_id", "change_count"),
        namespaces=(COURSE, EXAM, PROG),
        description="A plan adjustment was proposed. A proposal NEVER mutates the plan: it "
                    "carries the plan identity it was built from, so a stale proposal can be "
                    "refused at apply time.",
    ),
    EventTypeSpec(
        event_type="plan_adjustment_applied",
        category=CAT_PLAN,
        owner="learning.plan_adjustment.apply_adjustment",
        durable_source="exam_study_plan_tasks (the learner-accepted change)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("proposal_id", "applied_count"),
        namespaces=(COURSE, EXAM, PROG),
        description="The learner ACCEPTED a proposal and it was applied. Only this action "
                    "changes a plan, and only after re-verifying ownership and the plan "
                    "identity it was proposed against.",
    ),
    # ── P4: review completion (promoted from DEFERRED by building its producer) ──
    EventTypeSpec(
        event_type="review_completed",
        category=CAT_REVIEW,
        owner="learning.review_schedule.complete_review",
        durable_source="the learner's own review action + its REAL result",
        granularity=ITEM_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("item_id", "result"),
        namespaces=(COURSE, EXAM),
        description="The learner finished a review of one item, with the result they "
                    "reported or produced. The next due date is derived from that result by "
                    "the deterministic policy, and both facts are emitted together — a "
                    "schedule is never advanced by a review that did not happen.",
    ),
    # ── P4: unified AI response feedback (AUDIT_ONLY: product telemetry, not study history) ──
    EventTypeSpec(
        event_type="ai_feedback_submitted",
        category=CAT_AI,
        owner="learning.feedback.submit_feedback",
        durable_source="ai_requests (the request being rated) + the learner's rating",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        visibility=AUDIT_ONLY,
        required_payload=("request_id", "rating"),
        namespaces=(COURSE, EXAM, PROG),
        description="One rating of one AI response, with the frozen reason taxonomy when it "
                    "is negative. References and classifications only — no free text, no "
                    "prompt, no response. It never trains the router online: it is stored so "
                    "a later, offline decision can use it.",
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

    # ── P4: adaptive practice, review scheduling, model feedback ──
    EventTypeSpec(
        event_type="adaptive_practice_selected",
        category=CAT_PRACTICE,
        owner="learning.adaptive.select_candidates",
        durable_source="the selection request (practice_attempts / wrong_answer_states / "
                        "review dates / knowledge status — all read-only inputs)",
        granularity=ACTIVITY_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("selection_id", "candidate_count"),
        namespaces=(COURSE, EXAM, PROG),
        description="An adaptive practice selection was made, with the deterministic REASON "
                    "CODE of every candidate. A selection is a product decision over stored "
                    "facts — it is not a weakness prediction and carries no model output.",
    ),
    EventTypeSpec(
        event_type="review_scheduled",
        category=CAT_REVIEW,
        owner="learning.review_schedule.schedule_items",
        durable_source="the review scheduling policy run (policy_version + its input facts)",
        granularity=ITEM_LEVEL,
        status=ACTIVE,
        student_twin_eligible=False,
        required_payload=("item_id", "due_at", "policy_version"),
        namespaces=(COURSE, EXAM),
        description="A next review date was computed for one item by the DETERMINISTIC "
                    "policy: policy_version, the reason code and the facts it used travel "
                    "with the date, so any due date can be re-derived and checked. No "
                    "interval history is invented — an item with no real history gets the "
                    "policy's first-schedule interval and says so.",
    ),
    # ── reserved, NO SOURCE YET: names only, never synthesized ──
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
