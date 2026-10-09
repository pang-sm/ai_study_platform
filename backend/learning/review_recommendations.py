"""Deterministic recommendation projection over the existing unified review facts.

This module has no persistence of its own. A recommendation is recalculated from the
caller-owned review projection and canonical practice attempts on every read; only the
separate snooze overlay may suppress a current item.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy.orm import Session as DbSession

from core.learning_context import normalize_service_namespace

POLICY_VERSION = "review_recommendation_v1"
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_SOURCE_ITEMS = 200

_PRIORITY = {
    "scheduled_overdue": 0,
    "repeated_wrong": 1,
    "programming_repeated_failure": 1,
    "programming_single_failure": 2,
    "programming_user_marked": 2,
    "single_wrong": 3,
}


def _utc_naive(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return _utc_naive(parsed)


def _identity_key(identity: dict) -> str:
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scope(item: dict) -> tuple:
    domain = item.get("domain_context") or {}
    return (item["service_namespace"],
            str(domain.get("course_id") or ""),
            str(domain.get("exam_module_id") or ""),
            str(domain.get("language") or ""))


def _knowledge_identity(item: dict) -> dict:
    domain = item.get("domain_context") or {}
    metrics = item.get("metrics") or {}
    code = str(metrics.get("knowledge_point_code") or "").strip()
    point_id = metrics.get("knowledge_point_id")
    scope = (item["service_namespace"], domain.get("course_id"),
             domain.get("exam_module_id"))
    if point_id and str(point_id) != "0":
        return {"kind": "knowledge", "scope": scope, "point_id": str(point_id)}
    if code:
        return {"kind": "knowledge", "scope": scope, "code": code}
    return {"kind": "knowledge", "scope": scope,
            "progress_id": str(item.get("source_id") or "")}


def _question_identity(item: dict) -> dict:
    metrics = item.get("metrics") or {}
    point_id = metrics.get("knowledge_point_id")
    if point_id and str(point_id) != "0":
        domain = item.get("domain_context") or {}
        return {"kind": "knowledge", "scope": (
            item["service_namespace"], domain.get("course_id"),
            domain.get("exam_module_id")), "point_id": str(point_id)}
    question = item.get("question_identity") or {}
    return {"kind": "question", "scope": _scope(item),
            "source_type": str(question.get("question_source_type") or ""),
            "source_id": str(question.get("question_source_id") or item["source_id"]),
            "question_scope_key": str(question.get("question_scope_key") or "")}


def _programming_identity(item: dict) -> dict:
    domain = item.get("domain_context") or {}
    return {"kind": "programming_exercise", "namespace": "programming",
            "language": str(domain.get("language") or ""),
            "exercise_id": str(domain.get("exercise_id") or item["source_id"])}


def _programming_evidence(progress, attempts: list, as_of: datetime) -> tuple[str, dict] | None:
    if progress is None:
        return None
    last_attempt = attempts[-1] if attempts else None
    if last_attempt is not None:
        if last_attempt.correct is True:
            # A later real pass resolves earlier failures for this exercise recommendation.
            return None
        failed_since_pass = 0
        for attempt in reversed(attempts):
            if attempt.correct is True:
                break
            if attempt.correct is False:
                failed_since_pass += 1
        if failed_since_pass >= 2:
            return "programming_repeated_failure", {
                "failed_attempt_count": failed_since_pass,
                "last_attempt_at": last_attempt.submitted_at.isoformat(),
                "passed_count": int(progress.last_public_passed_count or 0),
                "total_count": int(progress.last_public_total_count or 0),
            }
        return "programming_single_failure", {
            "failed_attempt_count": failed_since_pass,
            "last_attempt_at": last_attempt.submitted_at.isoformat(),
            "passed_count": int(progress.last_public_passed_count or 0),
            "total_count": int(progress.last_public_total_count or 0),
        }

    # Old/partial histories may not have a PracticeAttempt mirror. The progress row still
    # records the authoritative latest sandbox verdict and timestamp; use it once, honestly.
    if progress.last_submit_at and progress.last_submit_at <= as_of \
            and progress.last_submit_passed is False:
        return "programming_single_failure", {
            "failed_attempt_count": 1,
            "last_attempt_at": progress.last_submit_at.isoformat(),
            "passed_count": int(progress.last_public_passed_count or 0),
            "total_count": int(progress.last_public_total_count or 0),
        }
    if progress.personal_status == "needs_work":
        return "programming_user_marked", {
            "personal_status": "needs_work",
            "last_attempt_at": (progress.last_updated_at.isoformat()
                                if progress.last_updated_at else None),
        }
    return None


def _reason(reason_code: str, evidence: dict) -> str:
    if reason_code == "scheduled_overdue":
        return "已有复习计划已到期"
    if reason_code == "repeated_wrong":
        count = int(evidence.get("wrong_count") or 0)
        return f"这道题有 {count} 次真实错误记录，尚未订正"
    if reason_code == "single_wrong":
        return "这道题有一次尚未订正的真实错误"
    if reason_code == "programming_repeated_failure":
        count = int(evidence.get("failed_attempt_count") or 0)
        return f"最近已有 {count} 次不同提交未通过判题"
    if reason_code == "programming_single_failure":
        passed = int(evidence.get("passed_count") or 0)
        total = int(evidence.get("total_count") or 0)
        suffix = f"（{passed}/{total} 个公开用例通过）" if total else ""
        return f"最近一次真实提交未通过{suffix}"
    return "你已将这道练习标记为需要加强"


def _candidate(item: dict, as_of: datetime, db: DbSession, user,
               programming_facts: dict | None = None) -> dict | None:
    source = item.get("source_type")
    namespace = normalize_service_namespace(item.get("service_namespace"))
    item = {**item, "service_namespace": namespace}
    evidence: dict
    if source == "knowledge_review":
        due = _parse_datetime(item.get("due_at"))
        if due is None or due > as_of:
            return None
        reason_code = "scheduled_overdue"
        evidence = {"source_type": source, "source_id": str(item["source_id"]),
                    "due_at": due.isoformat(), "due_source": item.get("due_source"),
                    "review_interval_days": (item.get("metrics") or {}).get(
                        "review_interval_days"),
                    "last_studied_at": item.get("last_attempt_at")}
        identity = _knowledge_identity(item)
        kind = "knowledge"
    elif source == "wrong_answer":
        metrics = item.get("metrics") or {}
        count = max(0, int(metrics.get("wrong_count") or 0))
        if count < 1:
            return None
        reason_code = "repeated_wrong" if count >= 2 else "single_wrong"
        evidence = {"source_type": source, "source_id": str(item["source_id"]),
                    "wrong_count": count, "last_wrong_at": item.get("last_attempt_at")}
        identity = _question_identity(item)
        kind = identity["kind"]
        question = item.get("question_identity") or {}
        display_id = question.get("question_source_id") or item["source_id"]
        item = {**item, "title": f"题目 {display_id}"}
    elif source == "programming_exercise":
        facts = (programming_facts or {}).get(str(item["source_id"]), (None, []))
        found = _programming_evidence(facts[0], facts[1], as_of)
        if found is None:
            return None
        reason_code, evidence = found
        evidence = {"source_type": source, "source_id": str(item["source_id"]),
                    **evidence}
        identity = _programming_identity(item)
        kind = "programming_exercise"
    else:
        return None

    rank = _PRIORITY[reason_code]
    due = _parse_datetime(item.get("due_at"))
    failures = int(evidence.get("wrong_count") or evidence.get("failed_attempt_count") or 0)
    occurred = (_parse_datetime(evidence.get("last_wrong_at"))
                or _parse_datetime(evidence.get("last_attempt_at"))
                or _parse_datetime(evidence.get("last_studied_at")))
    key = _identity_key(identity)
    domain = item.get("domain_context") or {}
    if namespace == "course_learning":
        direction = f"专业学习 · {domain.get('course_id') or '课程'}"
    elif namespace == "exam_prep":
        direction = f"11408 · {domain.get('exam_module_id') or '备考'}"
    else:
        direction = f"编程 · {domain.get('language') or '练习'}"

    if source == "wrong_answer":
        action = item.get("deep_link") or "/review"
    elif kind == "knowledge":
        if namespace == "course_learning":
            course_id = str(domain.get("course_id") or "")
            point_id = (item.get("metrics") or {}).get("knowledge_point_id")
            action = (f"/course/{quote(course_id, safe='')}/study?knowledge_point_id={point_id}"
                      if course_id and point_id else item.get("deep_link") or "/course")
        else:
            action = item.get("deep_link") or "/exam/cs408/knowledge"
    else:
        if kind == "programming_exercise":
            language = str(domain.get("language") or "Python")
            action = (f"/programming/workbench?language={quote(language, safe='')}"
                      f"&exercise={quote(str(domain.get('exercise_id') or item['source_id']), safe='')}")
        else:
            action = item.get("deep_link") or "/review"
    overdue_seconds = max(0, int((as_of - due).total_seconds())) if due else 0
    # This tuple is the entire tie-break policy and contains only stable, factual values.
    sort_key = [rank, -overdue_seconds, -failures,
                occurred.isoformat() if occurred else "9999-12-31T23:59:59",
                key]
    return {"recommendation_key": key, "kind": kind,
            "service_namespace": namespace,
            "domain_context": domain,
            "title": item.get("title") or "复习内容",
            "direction": direction,
            "reason_code": reason_code,
            "reason": _reason(reason_code, evidence),
            "evidence": evidence,
            "sort_key": sort_key,
            "action": {"label": "开始复习", "deep_link": action},
            "source_items": [str(item["id"])],
            "due_at": due.isoformat() if due else None}


def _merge(candidates: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in candidates:
        grouped.setdefault(item["recommendation_key"], []).append(item)
    merged = []
    for key, group in grouped.items():
        group.sort(key=lambda value: value["sort_key"])
        winner = dict(group[0])
        winner["source_items"] = sorted({source for item in group
                                          for source in item["source_items"]})
        winner["evidence_sources"] = [item["evidence"] for item in group]
        merged.append(winner)
    return sorted(merged, key=lambda item: item["sort_key"])


def build_recommendations(db: DbSession, user, *, service_namespace=None,
                          as_of: datetime | None = None,
                          limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict:
    """Recalculate a bounded, user-scoped recommendation page without writes."""
    from learning import review as review_service

    now = _utc_naive(as_of)
    namespace = (normalize_service_namespace(service_namespace)
                 if service_namespace else None)
    projection = review_service.collect_review_items(
        db, user, service_namespace=namespace, limit=MAX_SOURCE_ITEMS,
        offset=0)
    programming_ids = sorted({int(item["source_id"]) for item in projection["items"]
                              if item.get("source_type") == "programming_exercise"
                              and str(item.get("source_id", "")).isdigit()})
    programming_facts: dict[str, tuple[object, list]] = {}
    if programming_ids:
        from learning.practice.models import PracticeAttempt
        from models import ProgrammingExerciseProgress

        progress_rows = (db.query(ProgrammingExerciseProgress)
                         .filter(ProgrammingExerciseProgress.username == user.username,
                                 ProgrammingExerciseProgress.exercise_id.in_(programming_ids))
                         .all())
        attempts = (db.query(PracticeAttempt)
                    .filter(PracticeAttempt.user_id == user.id,
                            PracticeAttempt.service_namespace == "programming",
                            PracticeAttempt.question_source_type == "programming_exercise",
                            PracticeAttempt.question_source_id.in_(
                                [str(value) for value in programming_ids]),
                            PracticeAttempt.submitted_at.isnot(None),
                            PracticeAttempt.submitted_at <= now,
                            PracticeAttempt.correct.isnot(None))
                    .order_by(PracticeAttempt.submitted_at.asc(), PracticeAttempt.id.asc())
                    .all())
        progress_by_id = {str(row.exercise_id): row for row in progress_rows}
        attempts_by_id: dict[str, list] = {}
        for attempt in attempts:
            attempts_by_id.setdefault(attempt.question_source_id, []).append(attempt)
        programming_facts = {
            str(exercise_id): (progress_by_id.get(str(exercise_id)),
                               attempts_by_id.get(str(exercise_id), []))
            for exercise_id in programming_ids
        }
    candidates = []
    for item in projection["items"]:
        candidate = _candidate(item, now, db, user, programming_facts)
        if candidate is not None:
            candidates.append(candidate)
    items = _merge(candidates)
    total = len(items)
    safe_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    safe_offset = max(0, int(offset or 0))
    return {"policy_version": POLICY_VERSION,
            "generated_at": now.isoformat(),
            "service_namespace": namespace,
            "items": items[safe_offset:safe_offset + safe_limit],
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "semantics": ("read-only deterministic projection of stored review dates, active "
                          "wrong-answer states and real programming judge attempts")}


def visible_recommendations(db: DbSession, user, **kwargs) -> dict:
    """Read projection with the independent snooze overlay applied after generation."""
    from learning import review_snoozes

    requested_limit = max(1, min(int(kwargs.get("limit") or DEFAULT_LIMIT), MAX_LIMIT))
    requested_offset = max(0, int(kwargs.get("offset") or 0))
    result = build_recommendations(db, user, **{**kwargs, "limit": MAX_LIMIT, "offset": 0})
    hidden = review_snoozes.active_keys(db, user, as_of=kwargs.get("as_of"))
    all_items = list(result["items"])
    # Read the full bounded candidate projection before applying snoozes and pagination.
    # Each source is capped at MAX_SOURCE_ITEMS, so this loop makes at most three reads.
    offset = len(all_items)
    previous_page_size = len(all_items)
    while previous_page_size == MAX_LIMIT:
        page = build_recommendations(db, user, **{**kwargs, "limit": MAX_LIMIT,
                                                  "offset": offset})["items"]
        all_items.extend(page)
        previous_page_size = len(page)
        offset += len(page)
    visible = [item for item in all_items if item["recommendation_key"] not in hidden]
    total = len(visible)
    result["items"] = visible[requested_offset:requested_offset + requested_limit]
    result["total"] = total
    result["limit"] = requested_limit
    result["offset"] = requested_offset
    return result


def recommendation_exists(db: DbSession, user, recommendation_key: str) -> bool:
    """Validate a requested snooze against the complete current bounded projection."""
    offset = 0
    while True:
        page = build_recommendations(db, user, limit=MAX_LIMIT, offset=offset)["items"]
        if any(item["recommendation_key"] == recommendation_key for item in page):
            return True
        if len(page) < MAX_LIMIT:
            return False
        offset += len(page)
