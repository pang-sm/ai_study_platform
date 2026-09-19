"""Idempotent past-paper reconcile for the 11408 past-paper builders.

Past-paper questions have a REAL logical identity — unlike chapter questions, whose
identity is their whole content:

    PAST_PAPER_STABLE_KEY = (subject_key, year, question_number)

Audit (STEP7H2 §11, 235 rows): unique across all 170 ACTIVE rows; the 65 legacy
superseded rows (an earlier image-placeholder generation, ``is_active = 0``) share a
key with their replacement. That history is NOT rewritten — see the survivor rule.

The previous builders did ``DELETE`` + ``INSERT`` on every run. That produced clean
counts but **changed ``exam_question_bank.id`` on every re-import**, silently breaking
every reference held by done-records, wrong-answers, favorites and attempts. Two of them
had instead used ``UPDATE is_active=False`` + INSERT, which accumulated a duplicate batch
per deploy. Both protocols are wrong in opposite directions.

Reconcile semantics here:

  * stable key matches exactly one row  → UPDATE CONTENT IN PLACE, KEEP ITS id
  * stable key matches several rows     → deterministically pick a survivor
                                          (an ACTIVE row first, then the highest id) and
                                          update that one; the others are LEFT ALONE
                                          and counted as duplicate groups
  * stable key matches nothing          → INSERT

  * rows whose key the new source no longer contains → deactivate (soft), never delete:
    they may already be referenced, and this module must not destroy a learner's history.

No table, column or index is added.
"""
from __future__ import annotations

PAST_PAPER_SOURCE_TYPE = "past_paper"


def past_paper_stable_key(subject_key, year, question_number):
    """The frozen logical identity of one past-paper question."""
    return (str(subject_key), int(year), int(question_number))


def _pick_survivor(rows):
    """Deterministically choose which existing row a re-import owns.

    An ACTIVE row wins (it is the one the product is serving); otherwise the highest id
    wins (the most recent import). Never raises, never depends on row order.
    """
    active = [r for r in rows if r.is_active]
    return max(active or rows, key=lambda r: r.id or 0)


def upsert_past_paper_questions(db, models, subject_key, questions, build_row):
    """Reconcile past-paper rows by stable key. Never deletes.

    ``questions`` is the parsed source list; ``build_row(q)`` returns the COLUMN values
    to write (stem / options_json / standard_answer / analysis / difficulty / …). Each
    builder keeps its own content assembly — only the write protocol is shared.

    Returns ``(inserted, updated, deactivated, duplicate_groups, unkeyed)``.
    """
    by_key: dict[tuple, list] = {}
    unkeyed = 0
    for row in db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key,
        models.ExamQuestionBank.source_type == PAST_PAPER_SOURCE_TYPE,
    ).all():
        if row.year is None or row.question_number is None:
            # Malformed past-paper row: it has no logical identity, so it must not be
            # silently folded into some other question's key.
            unkeyed += 1
            continue
        key = past_paper_stable_key(row.subject_key, row.year, row.question_number)
        by_key.setdefault(key, []).append(row)

    duplicate_groups = sum(1 for rows in by_key.values() if len(rows) > 1)

    seen = set()
    inserted = updated = 0
    for q in questions:
        key = past_paper_stable_key(subject_key, q["year"], q["question_number"])
        seen.add(key)
        values = build_row(q)
        rows = by_key.get(key)
        if rows:
            row = _pick_survivor(rows)
            for field, value in values.items():
                setattr(row, field, value)
            row.is_active = True
            updated += 1
        else:
            # The identity columns come from the stable key, never from build_row: a
            # builder that forgot them would otherwise create an unreconcilable row.
            insert_values = {k: v for k, v in values.items()
                             if k not in ("subject_key", "source_type", "year",
                                          "question_number")}
            db.add(models.ExamQuestionBank(
                subject_key=subject_key, source_type=PAST_PAPER_SOURCE_TYPE,
                year=int(q["year"]), question_number=int(q["question_number"]),
                **insert_values,
            ))
            inserted += 1

    deactivated = 0
    for key, rows in by_key.items():
        if key in seen:
            continue
        for row in rows:
            if row.is_active:
                row.is_active = False
                deactivated += 1

    db.commit()
    return inserted, updated, deactivated, duplicate_groups, unkeyed
