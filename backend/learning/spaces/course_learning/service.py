"""Course Space service — a domain view over the shared Learning Core.

This module COORDINATES; it does not re-implement. Practice reads come from
``learning.practice``, wrong answers from ``learning.wrong_answers``, records from
``learning.records``. Nothing here talks to an AI provider or duplicates a shared
service.

Every read is scoped by user AND course: a course-A view can never include course-B
rows, and matching chapter/knowledge *titles* never stand in for identity.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from learning.practice import service as practice_service
from learning.records import service as records_service
from learning.wrong_answers import service as wrong_service

from .context import (
    COURSE_NAMESPACE,
    CourseContextError,
    course_identity_forms,
    normalize_course_id,
    resolve_course_context,
)

logger = logging.getLogger("learning.spaces.course_learning")


def list_user_courses(db: DbSession, user) -> list[dict]:
    """The course contexts attached to this user (identity = the stored course key)."""
    from models import CourseLearningPreference

    rows = (db.query(CourseLearningPreference)
            .filter(CourseLearningPreference.username == user.username)
            .order_by(CourseLearningPreference.course_id.asc()).all())
    return [{
        "course_id": r.course_id,
        "display_name": r.display_name or r.course_id,
        "mastery_level": r.mastery_level,
        "learning_goal": r.learning_goal,
        "is_started": bool(r.is_started),
    } for r in rows]


def course_context(db: DbSession, user, course_id) -> dict:
    """Resolve the canonical course context, or raise if the user does not have it."""
    ref, context = resolve_course_context(db, user, course_id)
    return {"ref": ref.to_dict(), "context": context.to_dict()}


def course_knowledge_state(db: DbSession, user, course_id) -> dict:
    """Deterministic knowledge state for ONE course.

    ``mastery_score`` is the legacy product field name for a deterministic point
    counter; nothing here reinterprets it as a probability or a scientific estimate.
    """
    from models import UserKnowledgeProgress

    key = normalize_course_id(course_id)
    rows = (db.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == user.username,
                    UserKnowledgeProgress.course_id == key)
            .order_by(UserKnowledgeProgress.knowledge_point_code.asc()).all())
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
    return {
        "course_id": key,
        "service_namespace": COURSE_NAMESPACE,
        "points": [{
            "knowledge_point_id": r.knowledge_point_id,
            "knowledge_point_code": r.knowledge_point_code,
            "title": r.knowledge_point_title,
            "status": r.status,
            "system_suggested_status": r.system_suggested_status,
            "user_confirmed_status": r.user_confirmed_status,
            "mastery_score": r.mastery_score,      # deterministic counter, legacy name
            "practice_count": r.practice_count,
            "task_count": r.task_count,
            "review_due_at": r.review_due_at.isoformat() if r.review_due_at else None,
        } for r in rows],
        "by_status": by_status,
        "total_points": len(rows),
        "semantics": "deterministic product state; not a mastery probability",
    }


def course_practice_view(db: DbSession, user, course_id, *, limit: int = 50) -> dict:
    """Course-scoped practice read, delegated to the shared Practice Core.

    The course filter is applied in SQL, before the limit. Filtering the fetched page in
    Python instead would let another course's rows consume the page and report a short
    (or empty) list for a course the learner actually practised.
    """
    key = normalize_course_id(course_id)
    sessions = practice_service.list_sessions(
        db, user.id, service_namespace=COURSE_NAMESPACE, course_id=key, limit=limit)
    attempts = practice_service.list_attempts(
        db, user.id, service_namespace=COURSE_NAMESPACE, course_id=key, limit=limit)
    return {
        "course_id": key,
        "sessions": [{"id": s.id, "mode": s.mode, "status": s.status} for s in sessions],
        "attempts": [{"id": a.id, "question_source_type": a.question_source_type,
                      "question_source_id": a.question_source_id,
                      "correct": a.correct, "submitted_at": (
                          a.submitted_at.isoformat() if a.submitted_at else None)}
                     for a in attempts],
        "attempt_count": len(attempts),
    }


def course_wrong_view(db: DbSession, user, course_id, *, limit: int = 100) -> dict:
    """Course-scoped wrong-answer read, delegated to the shared Wrong Answer Core."""
    page = course_wrong_page(db, user, course_id, limit=limit)
    return {
        "course_id": page["course_id"],
        "states": [wrong_service._state_view(s) for s in page["states"]],
        "active_count": wrong_service.count_states(
            db, user.id, service_namespace=COURSE_NAMESPACE, status="active",
            course_id=page["course_id"]),
    }


def course_records(db: DbSession, user, course_id, *, limit: int = 50,
                   cursor: str | None = None, event_type: str | None = None,
                   start_at=None, end_at=None) -> dict:
    """Course-scoped learning records, delegated to the shared Records read model.

    The shared model pages over the event stream; the course filter is applied in SQL on
    the event's own ``course_id`` column, never on a display name, and before pagination —
    so a page is always full and the next cursor never skips a matching row.
    """
    key = normalize_course_id(course_id)
    page = records_service.list_records(
        db, user.id, service_namespace=COURSE_NAMESPACE, course_id=key,
        event_type=event_type, start_at=start_at, end_at=end_at,
        limit=limit, cursor=cursor)
    return {"course_id": key, "records": page["records"],
            "next_cursor": page["next_cursor"], "has_more": page["has_more"]}


def course_records_summary(db: DbSession, user, course_id, *, start_at=None,
                           end_at=None) -> dict:
    """Course-scoped records metrics — the SAME SQL aggregates, course-filtered.

    Course-scoped for the same reason the page is: a summary that counted every namespace
    would report a learner's exam history under their course.
    """
    key = normalize_course_id(course_id)
    return records_service.summarize_records(
        db, user.id, service_namespace=COURSE_NAMESPACE, course_id=key,
        start_at=start_at, end_at=end_at)


def course_wrong_page(db: DbSession, user, course_id, *, status: str | None = None,
                      limit: int = 50, offset: int = 0) -> dict:
    """Course-scoped wrong-answer page, delegated to the shared Wrong Answer Core.

    The course filter is applied in SQL (``question_scope_key == course:<id>``), BEFORE the
    limit. Filtering after the page was fetched would let another course's states fill the
    page the caller asked for and would silently report a short list.
    """
    key = normalize_course_id(course_id)
    states = wrong_service.list_states(
        db, user.id, service_namespace=COURSE_NAMESPACE, status=status,
        course_id=key, limit=limit, offset=offset)
    total = wrong_service.count_states(
        db, user.id, service_namespace=COURSE_NAMESPACE, status=status, course_id=key)
    return {"course_id": key, "states": states, "total": total}


def course_review_state(db: DbSession, user, course_id) -> dict:
    """How many of this course's knowledge points are DUE for review, from real rows.

    ``review_due_at`` is a stored product field on the knowledge progress row — this reads
    it and counts. No schedule is computed here and none is invented: a point with no
    recorded due date is not due.
    """
    from datetime import datetime, timezone

    from models import UserKnowledgeProgress

    key = normalize_course_id(course_id)
    rows = (db.query(UserKnowledgeProgress)
            .filter(UserKnowledgeProgress.username == user.username,
                    UserKnowledgeProgress.course_id == key).all())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    due = [r for r in rows if r.review_due_at is not None and r.review_due_at <= now]
    return {
        "scheduled": sum(1 for r in rows if r.review_due_at is not None),
        "due": len(due),
        "due_points": [{
            "knowledge_point_id": r.knowledge_point_id,
            "knowledge_point_code": r.knowledge_point_code,
            "title": r.knowledge_point_title,
            "review_due_at": r.review_due_at.isoformat() if r.review_due_at else None,
        } for r in sorted(due, key=lambda r: r.review_due_at)[:20]],
        "review_semantics": ("counted from the stored knowledge review_due_at field; "
                             "knowledge status is written by the learner's own actions, "
                             "not by a model"),
    }


def course_plan_state(db: DbSession, user, course_id) -> dict:
    """The learner's study tasks for this course, from the SHARED task table.

    Reused, not duplicated: ``exam_study_plan_tasks`` is the product's per-direction task
    store, and the course direction is addressed through the SAME subject-key derivation
    the study-plan routes use, so the state and the plan page can never disagree about
    which tasks belong to which course.
    """
    from main import _course_learning_task_subject_key  # lazy: avoids an import cycle
    from models import ExamStudyPlanTask

    subject_key = _course_learning_task_subject_key(course_id)
    rows = (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == user.username,
                    ExamStudyPlanTask.subject_key == subject_key).all())
    by_status: dict[str, int] = {}
    for row in rows:
        status = (row.status or "not_started").strip() or "not_started"
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "subject_key": subject_key,
        "total": len(rows),
        "by_status": by_status,
        "open": sum(count for status, count in by_status.items() if status != "completed"),
    }


STATE_SEMANTICS = (
    "deterministic projection of recorded course facts (knowledge status, practice "
    "attempts, wrong-answer states, canonical events, study tasks). Not a mastery "
    "probability, not a readiness score, and not a model output."
)


def course_state(db: DbSession, user, course_id, *, recent_limit: int = 10) -> dict:
    """The deterministic state of ONE course. READ-ONLY; writes nothing.

    Every figure below is a stored fact or a count over stored facts. Nothing here is
    predicted, inferred, ranked, or produced by a model — the course space has no
    scientific capability, and a state view that looked like one would be a fabrication.
    """
    key = normalize_course_id(course_id)
    from models import CourseLearningPreference

    preference = (db.query(CourseLearningPreference)
                  .filter(CourseLearningPreference.username == user.username,
                          CourseLearningPreference.course_id == key).first())
    knowledge = course_knowledge_state(db, user, key)
    records = course_records(db, user, key, limit=recent_limit)
    return {
        "service_namespace": COURSE_NAMESPACE,
        "course": {
            "course_id": key,
            "display_name": (preference.display_name or key) if preference else key,
            "is_started": bool(preference.is_started) if preference else False,
            # the learner's OWN onboarding answer, not an assessed level. Deliberately
            # named ``declared_`` so no reader can take it for a measured ability.
            "declared_level": (preference.mastery_level or None) if preference else None,
            "learning_goal": (preference.learning_goal or None) if preference else None,
        },
        "knowledge_progress": {
            "total_points": knowledge["total_points"],
            "by_status": knowledge["by_status"],
            "status_semantics": knowledge["semantics"],
        },
        "practice": practice_service.attempt_counts(
            db, user.id, service_namespace=COURSE_NAMESPACE, course_id=key),
        "wrong_answers": {
            "active": wrong_service.count_states(
                db, user.id, service_namespace=COURSE_NAMESPACE, status="active",
                course_id=key),
            "resolved": wrong_service.count_states(
                db, user.id, service_namespace=COURSE_NAMESPACE, status="resolved",
                course_id=key),
        },
        "review": course_review_state(db, user, key),
        "plan": course_plan_state(db, user, key),
        "recent_activity": records["records"],
        "recent_activity_has_more": records["has_more"],
        "state_semantics": STATE_SEMANTICS,
    }


def course_today_plan(db: DbSession, user, course_id) -> dict:
    """Today's work for ONE course, from the SAME task rows the course plan counts.

    The plan task key is derived through the ONE shared derivation
    (``_course_learning_task_subject_key``), so this list and the course state's ``plan``
    block can never disagree about which tasks belong to the course.

    The generic ``learning_tasks`` rows have no such key: their ``course_id`` is free text.
    They are admitted only when that text IS one of this course's exact identity forms —
    a dictionary lookup, never a substring, a prefix or a title match. A row that cannot
    be attributed (blank, or a name this build does not recognize) is left out rather than
    guessed into the course: reporting another course's task here would be a fabrication
    with the learner's own data.

    READ-ONLY. Unlike the global today-plan route this creates no preference row and saves
    no ordering — a GET must not write.
    """
    from main import (  # lazy: avoids an import cycle at module load
        COURSE_LEARNING_MODE_LABELS,
        _course_learning_task_subject_key,
        _parse_track_onboarding_detail,
        _serialize_task,
        course_learning_exam_settings_for,
        course_learning_urgency_rank,
        get_user_track,
        normalize_course_learning_mode,
        parse_course_learning_date,
        serialize_datetime,
    )
    from models import CourseLearningPreference, ExamStudyPlanTask, LearningTask

    key = normalize_course_id(course_id)
    forms = course_identity_forms(key)
    preference = (db.query(CourseLearningPreference)
                  .filter(CourseLearningPreference.username == user.username,
                          CourseLearningPreference.course_id == key).first())
    course_name = (preference.display_name or key) if preference else key
    mode = normalize_course_learning_mode(
        getattr(preference, "primary_mode", "") or "daily", "daily")

    track = get_user_track(db, user.id, "university_course")
    detail = _parse_track_onboarding_detail(track)
    order_map = detail.get("today_plan_order")
    order_map = order_map if isinstance(order_map, dict) else {}
    exam_settings = course_learning_exam_settings_for(detail, key)
    exam_dt = parse_course_learning_date(exam_settings.get("exam_date"))

    def user_order(item_id: str) -> int:
        value = order_map.get(item_id, "")
        return int(value) if str(value).isdigit() else 9999

    items: list[dict] = []
    rows = (db.query(ExamStudyPlanTask)
            .filter(ExamStudyPlanTask.username == user.username,
                    ExamStudyPlanTask.subject_key == _course_learning_task_subject_key(key))
            .all())
    for task in rows:
        serialized = _serialize_task(task, db)
        status = (serialized.get("computed_status") or serialized.get("status") or "").strip()
        if status in {"completed", "done", "finished"}:
            continue
        item_id = f"exam_task:{task.id}"
        task_mode = mode
        if task.task_type == "review" and (exam_settings.get("exam_date")
                                           or exam_settings.get("target")):
            task_mode = "exam"
        rank, label = course_learning_urgency_rank(
            parse_course_learning_date(task.due_date), task_mode, exam_dt)
        items.append({
            "id": item_id,
            "raw_id": task.id,
            "source": "course_study_plan",
            "course_id": key,
            "course_name": course_name,
            "title": task.title,
            "mode": task_mode,
            "mode_label": COURSE_LEARNING_MODE_LABELS.get(task_mode, "平日学习"),
            "due_date": task.due_date or "",
            "urgency_rank": rank,
            "urgency_label": label,
            "user_order": user_order(item_id),
            "status": status or "not_started",
            "task_type": task.task_type or "knowledge",
        })

    for task in (db.query(LearningTask)
                 .filter(LearningTask.username == user.username,
                         LearningTask.status != "done").all()):
        if str(task.course_id or "").strip() not in forms:
            continue
        item_id = f"task:{task.id}"
        rank, label = course_learning_urgency_rank(
            parse_course_learning_date(task.due_date), "daily", None)
        items.append({
            "id": item_id,
            "raw_id": task.id,
            "source": "learning_tasks",
            "course_id": key,
            "course_name": course_name,
            "title": task.title,
            "mode": "daily",
            "mode_label": "平日学习",
            "due_date": serialize_datetime(task.due_date) if task.due_date else "",
            "urgency_rank": rank,
            "urgency_label": label,
            "user_order": user_order(item_id),
            "status": task.status or "todo",
            "task_type": task.task_type or "custom",
        })

    # SAME ordering rule as the global today-plan: a dateless task sorts last rather than
    # first, so "no due date" never outranks "due today".
    items.sort(key=lambda item: (
        item["urgency_rank"],
        item["user_order"],
        parse_course_learning_date(item.get("due_date"))
        or datetime.max.replace(tzinfo=timezone.utc),
        item["id"],
    ))
    return {"service_namespace": COURSE_NAMESPACE, "course_id": key,
            "items": items, "total": len(items), "empty": not items}


def course_materials(db: DbSession, user, course_id) -> dict:
    """This course's material library, scoped to the course's OWN identity forms.

    Reused, not duplicated: the rows are the same ``study_materials`` the material library
    serves, and the serializer is the same one. What this adds is the scope — a material
    is listed only when BOTH stored identity columns are a form this course is known by,
    so an exam scope or a programming course that happens to share a spelling (the same
    ``python_programming`` / ``Python 程序设计`` pair, for instance) cannot surface here.
    """
    from main import serialize_material_list_item  # lazy: avoids an import cycle
    from models import StudyMaterial

    key = normalize_course_id(course_id)
    forms = sorted(course_identity_forms(key))
    rows = (db.query(StudyMaterial)
            .filter(StudyMaterial.username == user.username,
                    StudyMaterial.is_deleted.is_(False),
                    StudyMaterial.course_id.in_(forms),
                    StudyMaterial.subject_key.in_(forms))
            .order_by(StudyMaterial.is_default_reference.desc(),
                      StudyMaterial.created_at.desc())
            .all())
    return {"course_id": key, "items": [serialize_material_list_item(row) for row in rows],
            "total": len(rows)}


def course_owns_wrong_state(state, course_id) -> bool:
    """Whether a wrong-answer state belongs to THIS course.

    The state's own scope discriminator decides — the same value the writer derived from
    the attempt's context. An unscoped state belongs to no course and is therefore not
    claimable by one.
    """
    from learning.wrong_answers.project import course_scope

    return (state.question_scope_key or "") == course_scope(course_id)


def assert_owned_course(db: DbSession, user, course_id) -> str:
    """Raise unless the user actually has this course — the cross-course entry guard."""
    key = normalize_course_id(course_id)
    from models import CourseLearningPreference

    exists = (db.query(CourseLearningPreference)
              .filter(CourseLearningPreference.username == user.username,
                      CourseLearningPreference.course_id == key).first())
    if exists is None:
        raise CourseContextError(f"course {key!r} is not attached to this user")
    return key


# ---------------------------------------------------------------- helpers
