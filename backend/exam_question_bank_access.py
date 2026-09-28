"""Shared authorization for ``exam_question_bank`` rows — SECURITY_S1B.

``exam_question_bank`` is the CS408 question store. The SSOT treats it as **static, server-owned
content** (9,333 rows: chapter 9,098 / past_paper 235) built by the offline importers, not as
user-generated data. Two properties follow, and they are the whole point of this module:

* a shared/public row is official content — a learner must never be able to write one;
* a row the learner does not own is invisible to them, including through the ids they can
  supply to ``chapter-practice``.

Before this module each route re-implemented its own filter, and most implemented none: the
chapter list, the attempt-create boundary and the attempt hydration all queried by
``id.in_(...)`` alone. So a learner could name another learner's private question id, have it
captured into their attempt, submit, and read the ``standard_answer`` and ``analysis`` back.

Every read path for this table goes through the predicates here so the rule is stated once.
"""

from __future__ import annotations

from sqlalchemy import or_

import models

PUBLIC_VISIBILITY = "public"
PRIVATE_VISIBILITY = "private"
VALID_VISIBILITIES = (PUBLIC_VISIBILITY, PRIVATE_VISIBILITY)

# The source_type the chapter-practice flow is allowed to consume. Past papers have their own
# resolution path (``exam_past_paper``); letting a chapter attempt pull a past-paper row would
# mix two catalogues with different grading and disclosure rules.
CHAPTER_SOURCE_TYPE = "chapter"

# One opaque refusal for every reason. Distinguishing "missing" from "inactive" from "not
# yours" would turn the endpoint into an existence oracle for other learners' rows.
UNAVAILABLE_CODE = "question_not_available"
UNAVAILABLE_MESSAGE = "所选题目不可用，请重新选择。"


def visible_query(query, username: str | None):
    """Restrict an ``ExamQuestionBank`` query to rows ``username`` may see.

    Visibility is ``public`` OR ``owner_username == username``. A caller with no identity (an
    unauthenticated route) sees only public rows.
    """
    owner = (username or "").strip()
    if not owner:
        return query.filter(models.ExamQuestionBank.visibility == PUBLIC_VISIBILITY)
    return query.filter(
        or_(
            models.ExamQuestionBank.visibility == PUBLIC_VISIBILITY,
            models.ExamQuestionBank.owner_username == owner,
        )
    )


def is_visible_to(row, username: str | None) -> bool:
    """Row-level form of :func:`visible_query`, for rows already loaded."""
    if row is None:
        return False
    if (row.visibility or "") == PUBLIC_VISIBILITY:
        return True
    owner = (username or "").strip()
    return bool(owner) and (row.owner_username or "") == owner


def is_usable_in_chapter_practice(row, *, subject_key: str, username: str | None) -> bool:
    """Whether ``row`` may be consumed by a chapter-practice request in ``subject_key``."""
    if row is None or not row.is_active:
        return False
    if (row.subject_key or "") != subject_key:
        return False
    if (row.source_type or "") != CHAPTER_SOURCE_TYPE:
        return False
    return is_visible_to(row, username)


def _reject(question_id) -> None:
    """Refuse one unusable id, in the shape the endpoint already documented.

    400 (not 404) preserves the existing attempt-create contract. It also keeps a foreign
    private row indistinguishable from a row that does not exist — a 404 for one and 400 for
    the other would confirm that someone else's row is there.
    """
    from fastapi import HTTPException

    raise HTTPException(
        status_code=400,
        detail={"code": UNAVAILABLE_CODE, "message": UNAVAILABLE_MESSAGE, "question_id": question_id},
    )


def resolve_chapter_questions(db, question_ids, *, subject_key: str, username: str | None):
    """Resolve client-supplied ids to chapter rows this learner may actually practise.

    The client's ``question_ids`` are a *request*, never an authorization. Every id is checked
    against existence, ``is_active``, the route's ``subject_key``, the chapter source type and
    visibility. One bad id refuses the whole call: silently dropping ids would hand back a
    different attempt than the client asked for, and would tell the client which guesses hit.
    """
    ids: list[int] = []
    for raw in question_ids or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            _reject(raw)

    rows = (
        db.query(models.ExamQuestionBank)
        .filter(models.ExamQuestionBank.id.in_(ids))
        .all()
    ) if ids else []
    by_id = {row.id: row for row in rows}

    ordered: list = []
    seen: set[int] = set()
    for question_id in ids:
        row = by_id.get(question_id)
        if not is_usable_in_chapter_practice(row, subject_key=subject_key, username=username):
            _reject(question_id)
        if question_id not in seen:
            seen.add(question_id)
            ordered.append(row)
    return ordered


def hydrate_chapter_questions(db, question_ids, *, subject_key: str, username: str | None):
    """Load the rows an already-created attempt references, dropping any it may no longer use.

    Used on the read/submit side, where the attempt itself is already owner-bound. A row that
    fails the check is omitted rather than raising, so an attempt that was captured before this
    rule existed still opens — without disclosing the foreign row it once contained.
    """
    ids = []
    for raw in question_ids or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not ids:
        return []
    rows = db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.id.in_(ids)).all()
    by_id = {row.id: row for row in rows}
    result = []
    seen: set[int] = set()
    for question_id in ids:
        if question_id in seen:
            continue
        seen.add(question_id)
        row = by_id.get(question_id)
        if is_usable_in_chapter_practice(row, subject_key=subject_key, username=username):
            result.append(row)
    return result
